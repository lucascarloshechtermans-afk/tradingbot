"""Back to the drawing board: pre-registered entry hypotheses on EVERY day of
every ticker (not just the scanner's candidates), against an unconditional
baseline in the same stocks.

The scanner's own candidates underperformed random entries in the same
stocks (research/opt_random_baseline.py) -- it buys short-term strength, and
short-term strength tends to reverse. These hypotheses test the opposite,
well-documented idea (short-term reversal inside a longer-term uptrend) next
to a strength-buying control, each with a couple of threshold variants:

  BASE        every 5th day (unconditional drift of these stocks)
  PULLBACK_UP close > EMA200, EMA50 > EMA200, 5-day return <= -k ATR
  RSI2_UP     close > EMA200, RSI(2) < x
  LEADER_DIP  momentum rank >= 80, 5-day return <= -k ATR
  EMA21_TOUCH close > EMA200, EMA21 rising, low <= EMA21 < close (bounce off the 21)
  BREAKOUT20  close at a 20-day closing high with volume > 1.5x (control: buying strength)

Entry next open (+0.05%); stop 2.5 ATR below (never tighter than 2 ATR);
exits: time 5 / 10 / 20 bars, or the first close above the prior day's high
(capped at 10 bars) -- gap-through fills at the open; no position stacking
within a hypothesis (one open trade per ticker).

    python -m research.drawing_board --universe dev|oos --out events.pkl
"""

from __future__ import annotations

import argparse
import multiprocessing
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

from config.schema import load_config
from data.cache import DiskCache
from data.provider import DataUnavailable
from data.universe import DEFAULT_UNIVERSE
from data.yfinance_provider import YFinanceProvider
from indicators.momentum import rsi
from indicators.trend import ema
from indicators.volatility import atr as atr_fn
from relative_strength.relative_strength import universe_momentum_rank_series

SLIP = 0.0005
STOP_ATR = 2.5


def _exit(o, h, lo, c, fi, entry, stop, cap, first_up=False):
    n = len(c)
    for k in range(1, cap + 1):
        j = fi + k
        if j >= n:
            return (c[n - 1] - entry) / (entry - stop), n - 1
        if lo[j] <= stop:
            return (min(o[j], stop) * (1 - SLIP) - entry) / (entry - stop), j
        if first_up and c[j] > h[j - 1]:
            return (c[j] * (1 - SLIP) - entry) / (entry - stop), j
    j = min(fi + cap, n - 1)
    return (c[j] * (1 - SLIP) - entry) / (entry - stop), j


def signals(df: pd.DataFrame, mom: pd.Series | None) -> dict[str, np.ndarray]:
    c, lo = df["close"], df["low"]
    a = atr_fn(df["high"], df["low"], df["close"], 14)
    e21, e50, e200 = ema(c, 21), ema(c, 50), ema(c, 200)
    r2 = rsi(c, 2)
    ret5 = (c - c.shift(5)) / a
    up = (c > e200) & (e50 > e200)
    vol = df["volume"]
    m = mom.reindex(df.index) if mom is not None else pd.Series(np.nan, index=df.index)
    base = pd.Series(False, index=df.index)
    base.iloc[::5] = True
    sig = {
        "BASE": base,
        "PULLBACK_UP k=1.0": up & (ret5 <= -1.0),
        "PULLBACK_UP k=1.5": up & (ret5 <= -1.5),
        "PULLBACK_UP k=2.0": up & (ret5 <= -2.0),
        "RSI2_UP <5": (c > e200) & (r2 < 5),
        "RSI2_UP <10": (c > e200) & (r2 < 10),
        "RSI2_UP <20": (c > e200) & (r2 < 20),
        "LEADER_DIP k=1.0": (m >= 80) & (ret5 <= -1.0),
        "LEADER_DIP k=1.5": (m >= 80) & (ret5 <= -1.5),
        "EMA21_TOUCH": (c > e200) & (e21 > e21.shift(5)) & (lo <= e21) & (c > e21),
        "BREAKOUT20": (c >= c.rolling(20).max()) & (vol > 1.5 * vol.rolling(20).mean().shift(1)),
    }
    return {k: v.fillna(False).to_numpy() for k, v in sig.items()}, a.to_numpy()


def ticker_events(job) -> list[dict]:
    t, df, mom = job
    df = df.dropna(subset=["open", "high", "low", "close"])
    if len(df) < 260:
        return []
    o, h, lo, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    sig, a = signals(df, mom)
    atr_pct = a / c * 100
    out = []
    for name, s in sig.items():
        busy = -1
        for i in np.flatnonzero(s):
            if i < 220 or i + 1 >= len(c) or i <= busy or not np.isfinite(a[i]):
                continue
            fi = i + 1
            entry = o[fi] * (1 + SLIP)
            stop = entry - max(STOP_ATR, 2.0) * a[i]
            res = {"ticker": t, "date": df.index[i], "hyp": name, "atr_pct": atr_pct[i]}
            last = fi
            for cap in (5, 10, 20):
                res[f"r{cap}"], j = _exit(o, h, lo, c, fi, entry, stop, cap)
                if cap == 10:
                    last = j
            res["r_up"], _ = _exit(o, h, lo, c, fi, entry, stop, 10, first_up=True)
            busy = last
            out.append(res)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickers", required=True, help="comma list, or 'default'")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    cfg = load_config(None)
    prov = YFinanceProvider(cache=DiskCache(cache_dir=cfg.data.cache_dir, ttl_hours=1e6))
    tickers = list(DEFAULT_UNIVERSE) if args.tickers == "default" else args.tickers.split(",")
    hist = {}
    for t in tickers:
        try:
            hist[t] = prov.get_history(t, "5y")
        except DataUnavailable:
            pass
    ranks = universe_momentum_rank_series({t: d["close"] for t, d in hist.items()})
    jobs = [(t, d, ranks[t] if t in ranks.columns else None) for t, d in hist.items()]
    with ProcessPoolExecutor(4, mp_context=multiprocessing.get_context("fork")) as ex:
        ev = pd.DataFrame([e for evs in ex.map(ticker_events, jobs, chunksize=4) for e in evs])
    ev.to_pickle(args.out)
    print(f"{len(ev)} events on {len(jobs)} tickers -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
