"""Run all pre-registered hypotheses; save trades; print DEV-cell results only.

    python -m research.run_round4 --big big.pkl --out round4.pkl
"""
from __future__ import annotations

import argparse
import sys
import time

import pandas as pd

from research.engine2 import HOLDS, add_context, baseline, build_panel, cell_stats, simulate
from research.hypotheses4 import indicators, signals


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--big", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", default=None)
    args = ap.parse_args(argv)
    t0 = time.time()
    p = build_panel(pd.read_pickle(args.big))
    print(f"panel {p.c.shape} built in {time.time() - t0:.0f}s; eligible cells {p.eligible.sum():,}", flush=True)
    base = baseline(p)
    print(f"baseline done {time.time() - t0:.0f}s", flush=True)
    ind = indicators(p)
    sig = signals(p, ind)
    allt = {}
    for name, s in sig.items():
        if args.only and args.only not in name:
            continue
        tr = add_context(p, simulate(p, s), base)
        allt[name] = tr
        dev = tr[tr.cell == "DEV"]
        line = f"{name:<28} n={len(dev):>6}"
        for H in HOLDS:
            st = cell_stats(dev, H)
            if st.get("n", 0) >= 30:
                line += f" | H{H}: R {st['R']:+.3f} X {st['X']:+.3f} t {st['t']:+.1f} yrs {st['yrs+']*100:3.0f}%"
        print(line, flush=True)
    pd.to_pickle({"trades": allt, "dates": p.dates, "tickers": p.tickers}, args.out)
    print(f"done {time.time() - t0:.0f}s -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
