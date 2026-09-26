"""Second research round on the chart-pattern setups (analysis/patterns.py,
analysis/setup_finder.py). One walk-forward pass per ticker collects:

  * BREAKOUT events (close above the trigger), with the 'ready to boom' score
    and every score component as it was on that day, and the R of a grid of
    exits: hold 5/10/20 bars x target 2R / 3R / measured move (2-6R).
  * READY events (close within min(3%, 1 ATR) under the trigger), traded as a
    buy-stop at the trigger for the next session only: filled at
    max(open, trigger) if the high reaches it, else no trade.
  * whether the close was above the 4H 200 EMA (last ~2 years only, where
    1h data exists).

Entry/exit rules match research/pattern_backtest.py: stop at invalidation
- 0.25 ATR kept 2-4 ATR from the fill, gap-through fills at the open, exits
checked from the bar after the fill, 0.05% slippage per side, one position
per ticker per pattern and event type.

    python -m research.pattern_research --tickers A,B,... --out events.pkl
"""

from __future__ import annotations

import argparse
import multiprocessing
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

from analysis.chart_read import resample_to_4h
from analysis.patterns import detect_patterns
from analysis.setup_finder import EXCLUDED, score_setup
from config.schema import load_config
from data.cache import DiskCache
from data.provider import DataUnavailable
from data.universe import DEFAULT_UNIVERSE
from data.yfinance_provider import YFinanceProvider
from indicators.trend import ema
from indicators.volatility import atr as atr_fn
from relative_strength.relative_strength import universe_momentum_rank_series

SLIP = 0.0005
HOLDS = (5, 10, 20)
TARGETS = ("2R", "3R", "MM")


def _exit_grid(o, h, lo, c, fill_i: int, entry: float, stop: float, measured: float) -> dict:
    risk = entry - stop
    n = len(c)
    out = {}
    for tname in TARGETS:
        tr = {"2R": 2.0, "3R": 3.0}.get(tname) or float(np.clip((measured - entry) / risk, 2.0, 6.0))
        target = entry + tr * risk
        for hold in HOLDS:
            last = min(fill_i + hold, n - 1)
            px = c[last]
            for j in range(fill_i + 1, last + 1):
                if lo[j] <= stop:
                    px = min(o[j], stop) * (1 - SLIP)
                    break
                if h[j] >= target:
                    px = max(o[j], target) * (1 - SLIP)
                    break
            out[f"r_h{hold}_{tname}"] = (px - entry) / risk
    return out


def ticker_research(job) -> list[dict]:
    ticker, df, mom_rank, ema4h_daily = job
    df = df.dropna(subset=["open", "high", "low", "close"])
    n = len(df)
    if n < 300:
        return []
    o, h, lo, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    a = atr_fn(df["high"], df["low"], df["close"], 14).to_numpy()
    busy: dict[tuple[str, str], int] = {}
    rows = []
    for i in range(260, n - 2):
        if not np.isfinite(a[i]):
            continue
        window = df.iloc[: i + 1]
        hits = [x for x in detect_patterns(window) if x.name not in EXCLUDED]
        if not hits:
            continue
        brk = [x for x in hits if x.broke_out_today]
        ready = [x for x in hits if not x.broke_out_today and 0 < x.distance_pct <= min(3.0, a[i] / c[i] * 100)]
        mr = mom_rank.get(df.index[i]) if mom_rank is not None else None
        mr = None if mr is None or pd.isna(mr) else float(mr)
        e4 = ema4h_daily.get(df.index[i].tz_convert("America/New_York").date()) if ema4h_daily is not None else None
        for kind, group in (("breakout", brk), ("ready", ready)):
            for hit in group:
                if i <= busy.get((kind, hit.name), -1):
                    continue
                status = "BREAKOUT TODAY" if kind == "breakout" else "READY"
                score, _, _, _, _, parts = score_setup(window, status, hit, group, mr, float(a[i]))
                if kind == "breakout":
                    fill_i, entry = i + 1, o[i + 1] * (1 + SLIP)
                else:
                    if h[i + 1] < hit.trigger:
                        continue  # buy-stop not reached: no trade
                    fill_i, entry = i + 1, max(o[i + 1], hit.trigger) * (1 + SLIP)
                risk = float(np.clip(entry - (hit.invalidation - 0.25 * a[i]), 2 * a[i], 4 * a[i]))
                grid = _exit_grid(o, h, lo, c, fill_i, entry, entry - risk, hit.target)
                busy[(kind, hit.name)] = min(fill_i + 10, n - 1)
                rows.append({
                    "ticker": ticker, "date": df.index[i], "kind": kind, "pattern": hit.name, "score": score,
                    "n_patterns": len({x.name for x in group}), "mom_rank": mr,
                    "above_4h200": (None if e4 is None or pd.isna(e4) else bool(c[i] > e4)),
                    "gap_fill_pct": (o[i + 1] / hit.trigger - 1) * 100 if kind == "ready" else None,
                    **{f"p_{k}": v for k, v in parts.items()}, **grid,
                })
    return rows


def _ema4h_by_day(hourly: pd.DataFrame) -> dict | None:
    """{NY calendar date: 4H 200 EMA at that session's close}."""
    h4 = resample_to_4h(hourly)
    if len(h4) < 220:
        return None
    e = ema(h4["close"], 200).dropna()
    return e.groupby(e.index.date).last().to_dict()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tickers", default=None)
    ap.add_argument("--rank-tickers", default=None, help="universe for the momentum rank (default: --tickers)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--no-4h", action="store_true")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    cfg = load_config(None)
    prov = YFinanceProvider(cache=DiskCache(cache_dir=cfg.data.cache_dir, ttl_hours=cfg.data.cache_ttl_hours))
    tickers = args.tickers.split(",") if args.tickers else list(DEFAULT_UNIVERSE)
    rank_list = args.rank_tickers.split(",") if args.rank_tickers else tickers
    hist = {}
    for t in sorted(set(tickers) | set(rank_list)):
        try:
            hist[t] = prov.get_history(t, "5y")
        except DataUnavailable:
            pass
    ranks = universe_momentum_rank_series({t: d["close"] for t, d in hist.items() if t in rank_list})
    jobs = []
    for t in tickers:
        if t not in hist:
            continue
        e4 = None
        if not args.no_4h:
            try:
                e4 = _ema4h_by_day(prov.get_history(t, "730d", "1h"))
            except DataUnavailable:
                e4 = None
        jobs.append((t, hist[t], ranks[t] if t in ranks.columns else None, e4))
    with ProcessPoolExecutor(args.workers, mp_context=multiprocessing.get_context("fork")) as ex:
        ev = pd.DataFrame([r for rows in ex.map(ticker_research, jobs, chunksize=1) for r in rows])
    ev.to_pickle(args.out)
    print(f"{len(ev)} events ({(ev['kind'] == 'breakout').sum() if len(ev) else 0} breakouts) on {len(jobs)} tickers -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
