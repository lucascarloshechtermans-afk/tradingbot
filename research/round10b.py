"""Round 10b: momentum-book market filters and volatility targeting.
    python -m research.round10b BIG.pkl ETF.pkl"""
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
    irx = etf["^IRX"]["close"].reindex(p.dates).ffill() / 100
    C = p.df(p.c)
    mom = (C.shift(21) / C.shift(252) - 1).where(p.df(p.eligible))
    vol = C.pct_change().rolling(63).std()
    spy = p.bench["SPY"]["close"].reindex(p.dates)
    months = pd.Series(p.dates.month, index=p.dates)
    me_mask = (months != months.shift(-1)).to_numpy()
    me = np.flatnonzero(me_mask)
    spy_me = spy[me_mask]
    sma10m = spy_me.rolling(10).mean().reindex(p.dates).ffill()
    filters = {
        "F0 no filter": np.ones(len(p.dates), bool),
        "F1 SPY > 200d (default)": (spy > spy.rolling(200).mean()).to_numpy(),
        "F2 SPY > 10-month SMA": (spy > sma10m).to_numpy(),
        "F3 SPY 12m return > T-bill": ((spy / spy.shift(252) - 1) > irx).to_numpy(),
    }
    print("MOMENTUM BOOK top 20 -- CAGR / maxDD / Sharpe / worst year per cell")
    base_W = {}
    for name, bull in filters.items():
        line = f"{name:<30}"
        for cell, (half, a, b) in CELLS.items():
            cols = p.half == half
            W = momentum_weights(p, cols, mom, vol, bull, me)
            if name.startswith("F1"):
                base_W[cell] = W
            r = pd.Series(weight_returns(W, p.o[:, cols], p.c[:, cols], rf), index=p.dates)
            s = stats(r[(r.index >= a) & (r.index <= b)])
            line += f" | {cell} {s['CAGR'] * 100:5.1f}% {s['maxDD'] * 100:4.1f}% {s['sharpe']:.2f} {s['worst_yr'] * 100:5.1f}%"
        print(line, flush=True)
    for name, win in (("V1 F1 + vol target 20% (126d)", 126), ("V2 F1 + vol target 20% (63d)", 63)):
        line = f"{name:<30}"
        for cell, (half, a, b) in CELLS.items():
            cols = p.half == half
            W = base_W[cell]
            raw = pd.Series(weight_returns(W, p.o[:, cols], p.c[:, cols], np.zeros(len(p.dates))), index=p.dates)
            # realised vol of the book's holdings, known at each month-end
            invested = pd.Series(W.sum(1), index=p.dates)
            rv = (raw / invested.replace(0, np.nan)).rolling(win, min_periods=20).std() * np.sqrt(252)
            scale = (0.20 / rv).clip(upper=1.0).fillna(1.0)
            sc = pd.Series(np.nan, index=p.dates)
            sc[me_mask] = scale[me_mask]
            sc = sc.ffill().fillna(1.0).shift(0).to_numpy()
            W2 = W * sc[:, None]
            r = pd.Series(weight_returns(W2, p.o[:, cols], p.c[:, cols], rf), index=p.dates)
            s = stats(r[(r.index >= a) & (r.index <= b)])
            line += f" | {cell} {s['CAGR'] * 100:5.1f}% {s['maxDD'] * 100:4.1f}% {s['sharpe']:.2f} {s['worst_yr'] * 100:5.1f}%"
        print(line, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
