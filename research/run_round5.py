"""Round 5 A+B (research/HYPOTHESES.md): H01-H19 and L01-L06 on a dataset,
scored against the same-day same-half random stock.

    python -m research.run_round5 DATA.pkl OUT.pkl [CELLS] [ONLY]
"""
from __future__ import annotations

import sys
import time

import numpy as np
import pandas as pd

from research.engine2 import add_context, add_half_day_excess, build_panel, cell_stats, day_baseline_halves, simulate
from research.hypotheses4 import indicators, signals

HOLDS5 = (5, 10, 20, 40, 60)


def long_signals(p, I) -> dict[str, np.ndarray]:
    C, H, L = I["C"], I["H"], I["L"]
    sma50, sma200 = I["sma50"], I["sma200"]
    sma150 = C.rolling(150).mean()
    e9, e21, e50 = (C.ewm(span=s, adjust=False).mean() for s in (9, 21, 50))
    e200 = C.ewm(span=200, adjust=False).mean()
    hi252, lo252 = C.rolling(252).max(), C.rolling(252).min()
    every5 = pd.Series(np.arange(len(p.dates)) % 5 == 0, index=p.dates).to_numpy()[:, None]
    week_end = pd.Series(p.dates.isocalendar().week.to_numpy(), index=p.dates)
    week_end = (week_end != week_end.shift(-1)).to_numpy()[:, None]
    below = (C < e200).astype(float)
    below_run = below.rolling(20).sum().shift(1)
    S = {
        "L01 TREND_TEMPLATE": (C > sma50) & (sma50 > sma150) & (sma150 > sma200) & (sma200 > sma200.shift(21))
        & (C >= 1.25 * lo252) & (C >= 0.75 * hi252) & (I["mom_rank"] >= 70) & every5,
        "L02 GOLDEN_CROSS": (sma50 > sma200) & (sma50.shift(1) <= sma200.shift(1)),
        "L03 EMA200_RECLAIM": (C > e200) & (below_run >= 20),
        "L04 WEEKLY_26W_BREAKOUT": (C >= C.rolling(126).max().shift(1)) & week_end,
        "L05 EMA_STACK_PULLBACK": (e9 > e21) & (e21 > e50) & (e50 > e200) & (L <= e21) & (C >= e21),
        "L06 TIGHT_NEAR_HIGH": (C >= 0.95 * hi252) & (I["bbw_pct"] <= 0.20),
    }
    del H
    return {k: np.asarray(v.fillna(False), dtype=bool) for k, v in S.items()}


def main(data: str, out: str, cells: str = "DEV", only: str = "") -> int:
    t0 = time.time()
    p = build_panel(pd.read_pickle(data))
    print(f"panel {p.c.shape}, eligible {p.eligible.sum():,}", flush=True)
    I = indicators(p)
    sig = {**signals(p, I), **long_signals(p, I)}
    dbh = day_baseline_halves(p, holds=HOLDS5)
    base_dummy = {}
    allt = {}
    for name, s in sig.items():
        if only and not any(o in name for o in only.split(",")):
            continue
        tr = simulate(p, s, holds=HOLDS5, busy_hold=10)
        if tr.empty:
            continue
        tr = add_half_day_excess(add_context(p, tr, base_dummy), dbh)
        allt[name] = tr
        for cell in cells.split(","):
            d = tr[tr.cell == cell]
            line = f"{cell:<6}{name:<26} n={len(d):>6}"
            for H in HOLDS5:
                st = cell_stats(d, H)
                if st.get("n", 0) >= 30:
                    line += f" | H{H} R {st['R']:+.3f} X {st['X']:+.3f} t {st['t']:+.1f} y {st['yrs+'] * 100:3.0f}%"
            print(line, flush=True)
    pd.to_pickle({"trades": allt}, out)
    print(f"done {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
