"""Adversarial benchmark: does the scanner pick better entries than chance?

For every candidate trade, draw `draws` random entry days for the SAME ticker
within +-60 trading days of the real entry, and give each the same stop
distance in ATRs and the same exit rules (research.opt_exits._replay). The
scanner's selection edge = its mean R minus the random entries' mean R.

    python -m research.opt_random_baseline --data ds_dev_exits.pkl ds_oos_exits.pkl
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
from indicators.volatility import atr as atr_fn
from research.opt_exits import _replay

VARIANTS = {"orig_5": ("orig", 5), "orig_7": ("orig", 7), "none_10": ("none", 10), "none_20": ("none", 20)}


def job_fn(job):
    t, df, rows, draws, seed = job
    rng = np.random.default_rng(seed)
    df = df.dropna(subset=["open", "high", "low", "close"])
    o, h, lo, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    a = atr_fn(df["high"], df["low"], df["close"], 14).to_numpy()
    pos = {ts: k for k, ts in enumerate(df.index)}
    out = []
    for r in rows:
        fi = pos.get(r["entry_date"])
        if fi is None or not np.isfinite(a[fi - 1]) or a[fi - 1] <= 0:
            continue
        k_atr = (r["entry"] - r["stop"]) / a[fi - 1]
        tgt_r = (r["target"] - r["entry"]) / (r["entry"] - r["stop"])
        acc = {v: [] for v in VARIANTS}
        for _ in range(draws):
            fj = int(np.clip(fi + rng.integers(-60, 61), 220, len(c) - 2))
            entry = o[fj] * 1.0005
            stop = entry - k_atr * a[fj - 1]
            if not np.isfinite(stop) or stop >= entry:
                continue
            for v, (kind, cap) in VARIANTS.items():
                target = entry + tgt_r * (entry - stop) if kind == "orig" else np.inf
                acc[v].append(_replay(o, h, lo, c, fj, entry, stop, target, cap))
        out.append({"key": r["key"], **{f"rnd_{v}": np.mean(x) if x else np.nan for v, x in acc.items()}})
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", nargs="+", required=True)
    ap.add_argument("--draws", type=int, default=5)
    args = ap.parse_args(argv)
    cfg = load_config(None)
    prov = YFinanceProvider(cache=DiskCache(cache_dir=cfg.data.cache_dir, ttl_hours=1e6))
    for path in args.data:
        ds = pd.read_pickle(path).reset_index(drop=True)
        ds["key"] = ds.index
        jobs = [(t, prov.get_history(t, "5y"), g[["key", "entry_date", "entry", "stop", "target"]].to_dict("records"), args.draws, i)
                for i, (t, g) in enumerate(ds.groupby("ticker"))]
        with ProcessPoolExecutor(4, mp_context=multiprocessing.get_context("fork")) as ex:
            res = pd.DataFrame([r for rows in ex.map(job_fn, jobs, chunksize=1) for r in rows])
        out = ds.merge(res, on="key").drop(columns=["key"])
        out.to_pickle(path.replace(".pkl", "_rnd.pkl"))
        print(f"{path}: {len(out)} -> _rnd")
    return 0


if __name__ == "__main__":
    sys.exit(main())
