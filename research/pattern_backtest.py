"""Which chart patterns actually pay? Every bullish pattern in
analysis/patterns.py, backtested on its breakout day across the universe.

Walk-forward: at bar i the pattern is built from bars < i and the breakout is
bar i's close above the trigger. Entry at bar i+1's open (+slippage); stop at
the pattern's invalidation minus 0.25 ATR, kept between 2 and 4 ATR from the
entry (never tighter than the audit's 2-ATR minimum); target = the
measured move, clamped to 2-4 R; time exit after `--hold` bars; gap-through
fills at the open; one position per ticker per pattern.

    python -m research.pattern_backtest --workers 4 --out events.pkl
"""

from __future__ import annotations

import argparse
import multiprocessing
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

from analysis.patterns import detect_patterns
from config.schema import load_config
from data.cache import DiskCache
from data.provider import DataUnavailable
from data.universe import DEFAULT_UNIVERSE
from data.yfinance_provider import YFinanceProvider
from indicators.trend import ema
from indicators.volatility import atr as atr_fn

SLIP = 0.0005
HOLD = 10


def ticker_events(job) -> list[dict]:
    ticker, df = job
    df = df.dropna(subset=["open", "high", "low", "close"])
    n = len(df)
    if n < 300:
        return []
    o, h, lo, c, v = (df[k].to_numpy() for k in ("open", "high", "low", "close", "volume"))
    a = atr_fn(df["high"], df["low"], df["close"], 14).to_numpy()
    e21, e50, e200 = (ema(df["close"], w).to_numpy() for w in (21, 50, 200))
    v20 = pd.Series(v).rolling(20).mean().to_numpy()
    busy: dict[str, int] = {}
    out = []
    for i in range(260, n - 1):
        if c[i] <= c[i - 1] or not np.isfinite(a[i]):
            continue
        for hit in detect_patterns(df.iloc[: i + 1]):
            if not hit.broke_out_today or i <= busy.get(hit.name, -1):
                continue
            entry = o[i + 1] * (1 + SLIP)
            dist = entry - (hit.invalidation - 0.25 * a[i])
            risk = float(np.clip(dist, 2 * a[i], 4 * a[i]))
            stop = entry - risk
            tgt_r = float(np.clip((hit.target - entry) / risk, 2.0, 4.0))
            target = entry + tgt_r * risk
            last = min(i + 1 + HOLD, n - 1)
            exit_px, why, j = c[last], "time", last
            for j in range(i + 2, last + 1):
                if lo[j] <= stop:
                    exit_px, why = min(o[j], stop) * (1 - SLIP), "stop"
                    break
                if h[j] >= target:
                    exit_px, why = max(o[j], target) * (1 - SLIP), "target"
                    break
            else:
                j = last
            busy[hit.name] = j
            out.append({
                "ticker": ticker, "date": df.index[i], "pattern": hit.name, "r": (exit_px - entry) / risk,
                "exit": why, "stop_pct": risk / entry * 100, "bars": hit.bars,
                "above200": c[i] > e200[i], "stacked": e21[i] > e50[i] > e200[i],
                "vol_surge": v20[i] > 0 and v[i] > 1.5 * v20[i],
                "atr_pct": a[i] / c[i] * 100,
                "fwd10": (c[min(i + 10, n - 1)] / c[i] - 1) * 100,
            })
    return out


def summarize(ev: pd.DataFrame, by: str = "pattern") -> pd.DataFrame:
    mid = ev["date"].min() + (ev["date"].max() - ev["date"].min()) / 2

    def agg(g):
        r = g["r"]
        return pd.Series({
            "n": len(g), "win%": (r > 0).mean() * 100, "meanR": r.mean(),
            "PF": r[r > 0].sum() / -r[r < 0].sum() if (r < 0).any() else np.inf,
            "H1": g.loc[g["date"] < mid, "r"].mean(), "H2": g.loc[g["date"] >= mid, "r"].mean(),
            "fwd10%": g["fwd10"].median(),
        })
    return ev.groupby(by).apply(agg).sort_values("meanR", ascending=False)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tickers", default=None)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    cfg = load_config(None)
    prov = YFinanceProvider(cache=DiskCache(cache_dir=cfg.data.cache_dir, ttl_hours=cfg.data.cache_ttl_hours))
    tickers = args.tickers.split(",") if args.tickers else list(DEFAULT_UNIVERSE)
    jobs = []
    for t in tickers:
        try:
            jobs.append((t, prov.get_history(t, "5y")))
        except DataUnavailable:
            pass
    with ProcessPoolExecutor(args.workers, mp_context=multiprocessing.get_context("fork")) as ex:
        ev = pd.DataFrame([e for evs in ex.map(ticker_events, jobs, chunksize=1) for e in evs])
    if args.out:
        ev.to_pickle(args.out)
    print(f"{len(ev)} breakout events, {ev['ticker'].nunique() if len(ev) else 0} tickers")
    if len(ev):
        pd.set_option("display.width", 160)
        print(summarize(ev).round(3).to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
