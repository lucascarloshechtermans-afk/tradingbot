"""Does the 'SYNA setup' -- falling wedge / descending channel breakout plus a
reclaim of the daily 200 EMA -- actually pay, and which ingredients matter?

Event study over the universe's 5y daily history, strictly walk-forward (the
pattern/zones at bar i are computed from bars <= i only):
  - signal at bar i's close, entry at bar i+1's open (+slippage)
  - stop: the reclaimed level minus 0.25 ATR, but never tighter than 2 ATR
    (the audit's minimum-stop rule)
  - exit: stop (gap-through fills at the open), target at `--target-r` R,
    or time exit at the close after `--hold` bars; one position per ticker
Variants are reported side by side, each a different set of ingredients.

    python -m research.wedge_reclaim_backtest --workers 4
"""

from __future__ import annotations

import argparse
import multiprocessing
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

from analysis.chart_read import FRESH_BARS, find_descending_pattern, find_zones
from config.schema import load_config
from data.cache import DiskCache
from data.provider import DataUnavailable
from data.universe import DEFAULT_UNIVERSE
from data.yfinance_provider import YFinanceProvider
from indicators.trend import ema
from indicators.volatility import atr as atr_fn

SLIP = 0.0005


def events_for_ticker(args) -> list[dict]:
    ticker, df = args
    df = df.dropna(subset=["open", "high", "low", "close"])
    n = len(df)
    if n < 320:
        return []
    c, o, h, lo = (df[k].to_numpy() for k in ("close", "open", "high", "low"))
    e200 = ema(df["close"], 200).to_numpy()
    e50 = ema(df["close"], 50).to_numpy()
    e21 = ema(df["close"], 21).to_numpy()
    a = atr_fn(df["high"], df["low"], df["close"], 14).to_numpy()
    vol = df["volume"].to_numpy()
    vol20 = pd.Series(vol).rolling(20).mean().to_numpy()
    roll_max = pd.Series(h).rolling(160, min_periods=60).max().to_numpy()
    out = []
    for i in range(260, n - 1):
        if not np.isfinite(e200[i]) or not np.isfinite(a[i]):
            continue
        # cheap precheck: a real decline happened (>= 12% off the 160-bar high
        # somewhere in the last 60 bars), and today closed up
        if np.nanmin(lo[i - 60:i + 1]) > roll_max[i] * 0.88 or c[i] <= c[i - 1]:
            continue
        window = df.iloc[: i + 1]
        pat = find_descending_pattern(window)
        wedge_fresh = pat is not None and pat.broke_out and pat.breakout_bars_ago is not None and pat.breakout_bars_ago <= 3
        above200 = c[i] > e200[i]
        reclaim200 = above200 and (c[i - FRESH_BARS:i] <= e200[i - FRESH_BARS:i]).any()
        if not (wedge_fresh or reclaim200):
            continue
        zones = find_zones(window)
        zone_break = any(c[i] > z.high and (c[i - FRESH_BARS:i] <= z.high).any() for z in zones)
        above = [z for z in zones if z.low > c[i]]
        room_atr = (min(z.low for z in above) - c[i]) / a[i] if above else 20.0
        out.append({
            "ticker": ticker, "i": i, "date": df.index[i],
            "wedge": wedge_fresh, "pattern": pat.name if pat is not None else None,
            "above200": above200, "reclaim200": reclaim200, "zone_break": zone_break,
            "above21_50": c[i] > e21[i] and c[i] > e50[i],
            "vol_surge": vol20[i] > 0 and vol[i] > 1.5 * vol20[i],
            "room_atr": room_atr,
            "day_gain_atr": (c[i] - c[i - 1]) / a[i],
        })
    return [dict(ev, **_simulate(df, ev["i"], e200, a)) for ev in out] if out else []


def _simulate(df: pd.DataFrame, i: int, e200, a, hold: int = 10, target_r: float = 3.0) -> dict:
    n = len(df)
    if i + 1 >= n:
        return {"r": np.nan}
    o, h, lo, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    entry = o[i + 1] * (1 + SLIP)
    level = e200[i] if c[i] > e200[i] else c[i] - 2 * a[i]
    stop = min(level - 0.25 * a[i], entry - 2 * a[i])
    risk = entry - stop
    if risk <= 0:
        return {"r": np.nan}
    target = entry + target_r * risk
    last = min(i + 1 + hold, n - 1)
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
    fwd = {f"fwd{k}": (c[min(i + k, n - 1)] / c[i] - 1) * 100 for k in (5, 10, 20)}
    return {"r": (exit_px - entry) / risk, "exit": why, "exit_i": j, "stop_pct": risk / entry * 100, **fwd}


def one_position(ev: pd.DataFrame) -> pd.DataFrame:
    keep, busy_until = [], {}
    for idx, row in ev.sort_values(["ticker", "i"]).iterrows():
        if row["i"] <= busy_until.get(row["ticker"], -1):
            continue
        keep.append(idx)
        busy_until[row["ticker"]] = row.get("exit_i", row["i"])
    return ev.loc[keep]


def report(ev: pd.DataFrame) -> None:
    ev = ev.dropna(subset=["r"])
    start, end = ev["date"].min(), ev["date"].max()
    mid = start + (end - start) / 2
    variants = {
        "D200 reclaim (any)": ev["reclaim200"],
        "wedge breakout (any)": ev["wedge"],
        "wedge + above D200": ev["wedge"] & ev["above200"],
        "wedge + D200 reclaim": ev["wedge"] & ev["reclaim200"],
        "wedge + D200 + zone break": ev["wedge"] & ev["reclaim200"] & ev["zone_break"],
        "D200 reclaim + zone break": ev["reclaim200"] & ev["zone_break"],
        "wedge+D200, room >= 3 ATR": ev["wedge"] & ev["above200"] & (ev["room_atr"] >= 3),
        "wedge+D200, vol surge": ev["wedge"] & ev["above200"] & ev["vol_surge"],
        "wedge+D200, above 21/50": ev["wedge"] & ev["above200"] & ev["above21_50"],
    }
    print(f"{'variant':<30}{'n':>6}{'win%':>7}{'meanR':>8}{'PF':>6}{'H1':>8}{'H2':>8}{'fwd5%':>7}{'fwd10%':>8}{'fwd20%':>8}")
    for name, mask in variants.items():
        t = one_position(ev[mask])
        if len(t) < 10:
            print(f"{name:<30}{len(t):>6}  (too few)")
            continue
        r = t["r"]
        pf = r[r > 0].sum() / -r[r < 0].sum() if (r < 0).any() else np.inf
        print(f"{name:<30}{len(t):>6}{(r > 0).mean() * 100:>7.1f}{r.mean():>8.3f}{pf:>6.2f}"
              f"{t[t.date < mid].r.mean():>8.3f}{t[t.date >= mid].r.mean():>8.3f}"
              f"{t.fwd5.median():>7.2f}{t.fwd10.median():>8.2f}{t.fwd20.median():>8.2f}")


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
        rows = [e for evs in ex.map(events_for_ticker, jobs) for e in evs]
    ev = pd.DataFrame(rows)
    print(f"{len(ev)} candidate events on {len(jobs)} tickers")
    if args.out:
        ev.to_pickle(args.out)
    if not ev.empty:
        report(ev)
    return 0


if __name__ == "__main__":
    sys.exit(main())
