"""LEADER_DIP: buy a short-term dip in a cross-sectional momentum leader.

Robustness grid on every day of both universes. One open trade per ticker
per parameter set. Entry next open (+0.05%), stop k_stop ATR below (never
tighter than 2 ATR), time exit after `hold` bars; gap-through fills.

Parameters varied (the chosen values sit in the middle of each range):
  mom      momentum-rank threshold          70 / 80 / 90
  dip      N-day return <= -dip ATR          0.5 / 1.0 / 1.5 / 2.0
  look     N (dip lookback)                  3 / 5 / 10
  stop     k_stop                            2.0 / 2.5 / 3.0
  hold     time exit                         5 / 7 / 10 / 15

    python -m research.leader_dip --out grid.pkl
"""

from __future__ import annotations

import argparse
import itertools
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
from indicators.volatility import atr as atr_fn
from relative_strength.relative_strength import universe_momentum_rank_series

SLIP = 0.0005
GRID = {"mom": (70, 80, 90), "dip": (0.5, 1.0, 1.5, 2.0), "look": (3, 5, 10), "stop": (2.0, 2.5, 3.0), "hold": (5, 7, 10, 15)}
DEFAULT = {"mom": 80, "dip": 1.0, "look": 5, "stop": 2.5, "hold": 10}


def trades_for(df: pd.DataFrame, mom: pd.Series, p: dict) -> list[tuple]:
    o, h, lo, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    a = atr_fn(df["high"], df["low"], df["close"], 14).to_numpy()
    m = mom.reindex(df.index).to_numpy()
    ret = np.full(len(c), np.nan)
    L = p["look"]
    ret[L:] = (c[L:] - c[:-L]) / a[L:]
    sig = (m >= p["mom"]) & (ret <= -p["dip"])
    out, busy = [], -1
    n = len(c)
    for i in np.flatnonzero(sig):
        if i < 220 or i + 1 >= n or i <= busy or not np.isfinite(a[i]):
            continue
        fi = i + 1
        entry = o[fi] * (1 + SLIP)
        stop = entry - max(p["stop"], 2.0) * a[i]
        risk = entry - stop
        r, j = None, min(fi + p["hold"], n - 1)
        for k in range(1, p["hold"] + 1):
            jj = fi + k
            if jj >= n:
                break
            if lo[jj] <= stop:
                r, j = (min(o[jj], stop) * (1 - SLIP) - entry) / risk, jj
                break
        if r is None:
            r = (c[j] * (1 - SLIP) - entry) / risk
        busy = j
        out.append((df.index[i], r, a[i] / c[i] * 100))
    return out


def run_universe(hist: dict[str, pd.DataFrame], params: list[dict]) -> pd.DataFrame:
    ranks = universe_momentum_rank_series({t: d["close"] for t, d in hist.items()})
    rows = []
    for t, df in hist.items():
        df = df.dropna(subset=["open", "high", "low", "close"])
        if t not in ranks.columns or len(df) < 260:
            continue
        for pid, p in enumerate(params):
            for d, r, ap in trades_for(df, ranks[t], p):
                rows.append((pid, t, d, r, ap))
    return pd.DataFrame(rows, columns=["pid", "ticker", "date", "r", "atr_pct"])


def _job(args):
    hist, params = args
    return run_universe(hist, params)


def param_sets() -> list[dict]:
    sets = [dict(DEFAULT)]
    for k, vals in GRID.items():
        for v in vals:
            p = dict(DEFAULT, **{k: v})
            if p not in sets:
                sets.append(p)
    return sets


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--oos-tickers", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    cfg = load_config(None)
    prov = YFinanceProvider(cache=DiskCache(cache_dir=cfg.data.cache_dir, ttl_hours=1e6))
    params = param_sets()
    out = []
    for uni, tickers in (("dev", list(DEFAULT_UNIVERSE)), ("oos", args.oos_tickers.split(","))):
        hist = {}
        for t in tickers:
            try:
                hist[t] = prov.get_history(t, "5y")
            except DataUnavailable:
                pass
        # parallelize over parameter subsets; the momentum rank needs the whole universe
        chunks = [params[i::4] for i in range(4)]
        with ProcessPoolExecutor(4, mp_context=multiprocessing.get_context("fork")) as ex:
            parts = list(ex.map(_job, [(hist, ch) for ch in chunks]))
        for ch, part in zip(chunks, parts):
            idx = {i: params.index(p) for i, p in enumerate(ch)}
            part["pid"] = part["pid"].map(idx)
            part["universe"] = uni
            out.append(part)
    res = pd.concat(out)
    res.attrs["params"] = params
    pd.to_pickle({"trades": res, "params": params}, args.out)
    print(f"{len(res)} trades, {len(params)} parameter sets -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
