"""Build the optimization-phase research dataset: one row per candidate trade
from research/capture_trades.py pickles, with its outcome and every feature
as it was known on the SIGNAL bar (the bar before the entry fill).

On top of the ~50 features capture_trades already records
(research/feature_extraction.py) it adds, all strictly from bars <= signal:
  * daily 200 EMA: distance (ATR), slope, fresh reclaim, full 9>21>50>200 stack
  * composite momentum rank (63/126/252d, cross-sectional) and 30d efficiency
  * support/resistance ZONES (analysis.chart_read.find_zones): distance to the
    nearest zone above/below in ATR, and resistance BEHAVIOUR over the last 5
    bars -- rejections (wick into the level, close below) and failed
    breakouts (traded above, closed below) -- against both the zone and the
    prior 60-bar high
  * entry quality: signal-candle range/body/close location, gap, 1d and 5d run-up
  * market context: SPY above 50/200 SMA, SPY 20d return, VIX
  * the 4H 200 EMA (only where 1h history exists, ~last 2 years)
  * chart-pattern confirmation (analysis.patterns): a robust pattern breaking
    out on the signal bar or up to 3 bars before, or sitting just under its trigger

    python -m research.opt_dataset --captures a.pkl b.pkl --out dataset.pkl
"""

from __future__ import annotations

import argparse
import multiprocessing
import pickle
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

from analysis.chart_read import find_zones, resample_to_4h
from analysis.patterns import detect_patterns
from analysis.setup_finder import EXCLUDED as PATTERN_EXCLUDED
from config.schema import load_config
from data.cache import DiskCache
from data.provider import DataUnavailable
from data.yfinance_provider import YFinanceProvider
from indicators.trend import ema
from indicators.volatility import atr as atr_fn
from relative_strength.relative_strength import efficiency_ratio, universe_momentum_rank_series

SETUP_CLASS = {
    "Bullish Breakout": "BREAKOUT", "Momentum Continuation": "TREND CONTINUATION",
    "Trend Continuation": "TREND CONTINUATION", "Bullish Pullback": "PULLBACK",
    "Support Bounce": "SUPPORT BOUNCE", "Mean Reversion": "MEAN REVERSION",
}


def load_captures(paths: list[str]) -> pd.DataFrame:
    rows = []
    for path in paths:
        with open(path, "rb") as f:
            p = pickle.load(f)
        for tr, strat, score, regime, rr, feat in zip(p["trades"], p["strategies"], p["scores"], p["regimes"],
                                                        p["rrs"], p["features"]):
            risk = tr.shares * (tr.entry_price - tr.stop)
            rows.append({
                "ticker": tr.ticker, "entry_date": tr.entry_date, "exit_date": tr.exit_date,
                "entry": tr.entry_price, "stop": float(tr.stop), "target": float(tr.target), "shares": tr.shares,
                "r": tr.pnl / risk if risk > 0 else np.nan, "pnl": tr.pnl, "pct": tr.pnl_pct,
                "exit_reason": tr.exit_reason, "bars": tr.holding_bars, "strategy": strat,
                "setup": SETUP_CLASS.get(strat, strat), "score": score, "regime": regime, "rr": rr,
                **{f"f_{k}": v for k, v in (feat or {}).items() if not k.startswith("raw_")},
            })
    df = pd.DataFrame(rows).drop_duplicates(subset=["ticker", "entry_date"])
    return df.sort_values("entry_date").reset_index(drop=True)


def _rejections(h, lo, c, idxs, level, a):
    rej = failed = 0
    for j in idxs:
        rng = max(h[j] - lo[j], 1e-9)
        if h[j] >= level - 0.25 * a and c[j] < level and (h[j] - c[j]) >= 0.4 * rng:
            rej += 1
        if h[j] > level and c[j] < level:
            failed += 1
    return rej, failed


def enrich_ticker(job) -> list[dict]:
    ticker, df, trades, mom_rank, ctx_df, e4h = job
    df = df.dropna(subset=["open", "high", "low", "close"])
    o, h, lo, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    a = atr_fn(df["high"], df["low"], df["close"], 14).to_numpy()
    e = {w: ema(df["close"], w).to_numpy() for w in (9, 21, 50, 200)}
    pos = {ts: k for k, ts in enumerate(df.index)}
    out = []
    for row in trades:
        fi = pos.get(row["entry_date"])
        if fi is None or fi < 60:
            continue
        s = fi - 1  # signal bar
        A = a[s]
        if not np.isfinite(A) or A <= 0:
            continue
        win = df.iloc[: s + 1]
        f: dict = {"idx": row["idx"]}
        e200 = e[200][s]
        f["x_above_ema200"] = float(c[s] > e200) if np.isfinite(e200) else np.nan
        f["x_ema200_dist_atr"] = (c[s] - e200) / A if np.isfinite(e200) else np.nan
        f["x_ema200_slope20"] = (e200 / e[200][s - 20] - 1) * 100 if s >= 20 and np.isfinite(e[200][s - 20]) else np.nan
        f["x_d200_reclaim10"] = float(np.isfinite(e200) and c[s] > e200 and (c[s - 10:s] <= e[200][s - 10:s]).any())
        f["x_ema_stack_full"] = float(e[9][s] > e[21][s] > e[50][s] > e200) if np.isfinite(e200) else np.nan
        f["x_ema21_dist_atr"] = (c[s] - e[21][s]) / A
        f["x_mom_rank"] = mom_rank.get(df.index[s], np.nan) if mom_rank is not None else np.nan
        er = efficiency_ratio(win["close"])
        f["x_eff30"] = er if er is not None else np.nan
        # zones and resistance behaviour
        zones = find_zones(win)
        above = [z for z in zones if z.low > c[s]]
        below = [z for z in zones if z.high <= c[s]]
        f["x_res_zone_dist_atr"] = min(20.0, (min(z.low for z in above) - c[s]) / A) if above else 20.0
        f["x_res_zone_touches"] = float(min(above, key=lambda z: z.low).touches) if above else 0.0
        f["x_sup_zone_dist_atr"] = min(20.0, (c[s] - max(z.high for z in below)) / A) if below else 20.0
        last5 = range(max(0, s - 4), s + 1)
        if above:
            zlow = min(z.low for z in above)
            f["x_rej5_zone"], f["x_failed5_zone"] = _rejections(h, lo, c, last5, zlow, A)
        else:
            f["x_rej5_zone"], f["x_failed5_zone"] = 0, 0
        hh = h[max(0, s - 64):s - 4].max() if s > 10 else np.nan
        f["x_hh60_dist_atr"] = (hh - c[s]) / A if np.isfinite(hh) else np.nan
        if np.isfinite(hh) and hh > c[s] - 0.25 * A:
            f["x_rej5_hh60"], f["x_failed5_hh60"] = _rejections(h, lo, c, last5, hh, A)
        else:
            f["x_rej5_hh60"], f["x_failed5_hh60"] = 0, 0
        f["x_dist_52w_high_atr"] = (h[max(0, s - 251):s + 1].max() - c[s]) / A
        # entry quality
        rng = max(h[s] - lo[s], 1e-9)
        f["x_candle_range_atr"] = rng / A
        f["x_candle_body_atr"] = abs(c[s] - o[s]) / A
        f["x_close_location"] = (c[s] - lo[s]) / rng
        f["x_gap_pct"] = (o[s] / c[s - 1] - 1) * 100
        f["x_ret1_atr"] = (c[s] - c[s - 1]) / A
        f["x_ret5_atr"] = (c[s] - c[s - 5]) / A
        f["x_entry_gap_atr"] = (o[fi] - c[s]) / A  # known at the fill (the open), not at the signal
        # market context
        d = df.index[s]
        if ctx_df is not None and d in ctx_df.index:
            for k in ("spy_above50", "spy_above200", "spy_ret20", "vix"):
                f[f"x_{k}"] = ctx_df.at[d, k]
        # 4H 200 EMA (NY calendar date of the signal bar)
        if e4h is not None:
            v = e4h.get(d.tz_convert("America/New_York").date())
            f["x_above_4h200"] = float(c[s] > v) if v is not None and np.isfinite(v) else np.nan
        # chart-pattern confirmation
        brk = rdy = None
        for k in range(0, 4):
            for hit in detect_patterns(df.iloc[: s + 1 - k]):
                if hit.name in PATTERN_EXCLUDED:
                    continue
                if hit.broke_out_today and brk is None and c[s] > hit.trigger:
                    brk = hit.name
                if k == 0 and not hit.broke_out_today and 0 < hit.distance_pct <= 3 and rdy is None:
                    rdy = hit.name
        f["x_pattern_breakout"] = float(brk is not None)
        f["x_pattern_ready"] = float(rdy is not None)
        f["x_pattern_name"] = brk or rdy
        out.append(f)
    return out


def market_context(prov) -> pd.DataFrame:
    spy = prov.get_history("SPY", "5y")["close"]
    vix = prov.get_history("^VIX", "5y")["close"]
    ctx = pd.DataFrame({
        "spy_above50": (spy > spy.rolling(50).mean()).astype(float),
        "spy_above200": (spy > spy.rolling(200).mean()).astype(float),
        "spy_ret20": (spy / spy.shift(20) - 1) * 100,
    })
    ctx["vix"] = vix.reindex(ctx.index, method="ffill")
    return ctx


def _ema4h_by_day(prov, ticker):
    try:
        h4 = resample_to_4h(prov.get_history(ticker, "730d", "1h"))
    except DataUnavailable:
        return None
    if len(h4) < 220:
        return None
    s = ema(h4["close"], 200).dropna()
    return s.groupby(s.index.date).last().to_dict()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--captures", nargs="+", required=True)
    ap.add_argument("--rank-tickers", default=None, help="universe for the momentum rank (default: tickers in the captures)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--no-4h", action="store_true")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    cfg = load_config(None)
    prov = YFinanceProvider(cache=DiskCache(cache_dir=cfg.data.cache_dir, ttl_hours=1e6))
    trades = load_captures(args.captures)
    trades["idx"] = trades.index
    tickers = sorted(trades["ticker"].unique())
    rank_list = args.rank_tickers.split(",") if args.rank_tickers else tickers
    hist = {}
    for t in sorted(set(tickers) | set(rank_list)):
        try:
            hist[t] = prov.get_history(t, "5y")
        except DataUnavailable:
            pass
    ranks = universe_momentum_rank_series({t: d["close"] for t, d in hist.items() if t in rank_list})
    ctx = market_context(prov)
    jobs = []
    for t, g in trades.groupby("ticker"):
        if t not in hist:
            continue
        e4 = None if args.no_4h else _ema4h_by_day(prov, t)
        jobs.append((t, hist[t], g.to_dict("records"), ranks[t] if t in ranks.columns else None, ctx, e4))
    with ProcessPoolExecutor(args.workers, mp_context=multiprocessing.get_context("fork")) as ex:
        extra = pd.DataFrame([r for rows in ex.map(enrich_ticker, jobs, chunksize=1) for r in rows])
    ds = trades.merge(extra, on="idx", how="inner").drop(columns=["idx"])
    ds.to_pickle(args.out)
    print(f"{len(ds)} trades, {ds['ticker'].nunique()} tickers, {ds.shape[1]} columns -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
