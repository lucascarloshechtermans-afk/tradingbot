"""Exit research on the optimization dataset: the same candidate entries
(entry price, stop) replayed with different holding caps and targets, plus a
time-based failure exit and a trailing stop, via research.exit_sweep's
engine-identical exit replay (gap-through fills, stop checked first).

    python -m research.opt_exits --data ds_dev.pkl ds_oos.pkl
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
from data.yfinance_provider import YFinanceProvider
from indicators.trend import ema

CAPS = (3, 5, 7, 10, 15, 20)
SLIP = 0.05


def _replay(o, h, lo, c, fi, entry, stop, target, cap, trail=None, fail_bars=None):
    """R of one exit variant. trail: None | 'ema21' (exit on close below the
    21 EMA, known at the close -> filled next open). fail_bars: exit at the
    close of bar fi+fail_bars if price is still below entry + 0.25R."""
    risk = entry - stop
    n = len(c)
    for k in range(1, cap + 1):
        j = fi + k
        if j >= n:
            return (c[n - 1] - entry) / risk
        if lo[j] <= stop:
            return (min(o[j], stop) * (1 - SLIP / 100) - entry) / risk
        if h[j] >= target:
            return (max(o[j], target) * (1 - SLIP / 100) - entry) / risk
        if fail_bars is not None and k == fail_bars and c[j] < entry + 0.25 * risk:
            return (c[j] - entry) / risk
        if trail is not None and c[j] < trail[j] and k >= 2:
            nxt = min(j + 1, n - 1)
            return (o[nxt] * (1 - SLIP / 100) - entry) / risk
    j = min(fi + cap, n - 1)
    return (c[j] - entry) / risk


def ticker_exits(job):
    t, df, rows = job
    df = df.dropna(subset=["open", "high", "low", "close"])
    o, h, lo, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    e21 = ema(df["close"], 21).to_numpy()
    pos = {ts: k for k, ts in enumerate(df.index)}
    out = []
    for r in rows:
        fi = pos.get(r["entry_date"])
        if fi is None:
            continue
        entry, stop, tgt = r["entry"], r["stop"], r["target"]
        risk = entry - stop
        if risk <= 0:
            continue
        res = {"key": r["key"]}
        for cap in CAPS:
            res[f"orig_{cap}"] = _replay(o, h, lo, c, fi, entry, stop, tgt, cap)
            res[f"3R_{cap}"] = _replay(o, h, lo, c, fi, entry, stop, entry + 3 * risk, cap)
            res[f"none_{cap}"] = _replay(o, h, lo, c, fi, entry, stop, np.inf, cap)
        res["ema21trail_20"] = _replay(o, h, lo, c, fi, entry, stop, np.inf, 20, trail=e21)
        res["fail3_orig_7"] = _replay(o, h, lo, c, fi, entry, stop, tgt, 7, fail_bars=3)
        res["fail5_none_20"] = _replay(o, h, lo, c, fi, entry, stop, np.inf, 20, fail_bars=5)
        out.append(res)
    return out


def run(ds: pd.DataFrame, workers: int = 4) -> pd.DataFrame:
    cfg = load_config(None)
    prov = YFinanceProvider(cache=DiskCache(cache_dir=cfg.data.cache_dir, ttl_hours=1e6))
    ds = ds.assign(key=range(len(ds)))
    jobs = [(t, prov.get_history(t, "5y"), g[["key", "entry_date", "entry", "stop", "target"]].to_dict("records"))
            for t, g in ds.groupby("ticker")]
    with ProcessPoolExecutor(workers, mp_context=multiprocessing.get_context("fork")) as ex:
        res = pd.DataFrame([r for rows in ex.map(ticker_exits, jobs, chunksize=1) for r in rows])
    return ds.merge(res, on="key").drop(columns=["key"])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", nargs="+", required=True)
    ap.add_argument("--out-suffix", default="_exits")
    args = ap.parse_args(argv)
    for path in args.data:
        ex = run(pd.read_pickle(path).dropna(subset=["r"]))
        out = path.replace(".pkl", f"{args.out_suffix}.pkl")
        ex.to_pickle(out)
        print(f"{path}: {len(ex)} trades -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
