"""Round 12b: rebalance-day luck -- the same momentum book rebalanced k sessions
before each month-end (k = 0, 3, 6, 9, 12, 15), and the average of all six
schedules (= six tranches).   python -m research.round12b BIG.pkl ETF.pkl"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from research.engine2 import build_panel
from research.round10 import CELLS, momentum_weights
from research.systems6 import stats, weight_returns


def main(path: str, etf_path: str) -> int:
    p = build_panel(pd.read_pickle(path))
    etf = pd.read_pickle(etf_path)
    rf = (etf["^IRX"]["close"].reindex(p.dates).ffill() / 100 / 252).fillna(0).to_numpy()
    C = p.df(p.c)
    m12 = (C.shift(21) / C.shift(252) - 1).where(p.df(p.eligible))
    vol = C.pct_change().rolling(63).std()
    spy = p.bench["SPY"]["close"].reindex(p.dates)
    bull = (spy > spy.rolling(200).mean()).to_numpy()
    months = pd.Series(p.dates.month, index=p.dates)
    me = np.flatnonzero((months != months.shift(-1)).to_numpy())
    offsets = (0, 3, 6, 9, 12, 15)
    for cell, (half, a, b) in CELLS.items():
        cols = p.half == half
        Ws = {k: momentum_weights(p, cols, m12, vol, bull, np.array([r - k for r in me if r - k > 0])) for k in offsets}
        line = f"{cell:<6}"
        cagr = []
        for k, W in Ws.items():
            r = pd.Series(weight_returns(W, p.o[:, cols], p.c[:, cols], rf), index=p.dates)
            s = stats(r[(r.index >= a) & (r.index <= b)])
            cagr.append(s["CAGR"])
            line += f" k{k:<2} {s['CAGR'] * 100:5.1f}%/{s['sharpe']:.2f}"
        Wavg = sum(Ws.values()) / len(Ws)
        r = pd.Series(weight_returns(Wavg, p.o[:, cols], p.c[:, cols], rf), index=p.dates)
        s = stats(r[(r.index >= a) & (r.index <= b)])
        print(line + f" | spread {min(cagr) * 100:.1f}..{max(cagr) * 100:.1f}% | 6 tranches {s['CAGR'] * 100:5.1f}% "
              f"DD {s['maxDD'] * 100:4.1f}% Sh {s['sharpe']:.2f}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
