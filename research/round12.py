"""Round 12: improving the momentum-only book.   python -m research.round12 BIG.pkl ETF.pkl"""
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
    elig = p.df(p.eligible)
    ret = C.pct_change()
    m12 = (C.shift(21) / C.shift(252) - 1).where(elig)
    scores = {
        "default 12-1": m12,
        "S1 6-1": (C.shift(21) / C.shift(126) - 1).where(elig),
        "S2 composite 3/6/12": (sum(C.shift(21) / C.shift(21 + h) - 1 for h in (63, 126, 231)) / 3).where(elig),
        "S3 12-1 / vol": (m12 / (ret.rolling(252).std() * np.sqrt(252))).where(elig),
        "S4 52w-high proximity": (C / C.rolling(252).max()).where(elig & (m12 > 0)),
        "S5 smooth momentum": ((m12.rank(axis=1, pct=True) + (ret > 0).rolling(252).mean().where(elig).rank(axis=1, pct=True)) / 2),
    }
    vol = ret.rolling(63).std()
    spy = p.bench["SPY"]["close"].reindex(p.dates)
    bull = (spy > spy.rolling(200).mean()).to_numpy()
    months = pd.Series(p.dates.month, index=p.dates)
    me = np.flatnonzero((months != months.shift(-1)).to_numpy())
    mid = np.array([r - 10 for r in me if r - 10 > 0])
    above50 = (C > C.rolling(50).mean()).to_numpy()
    low20 = (C < C.rolling(20).min().shift(1)).to_numpy()

    def month_id(rows):
        ids = np.full(len(p.dates), -1)
        for k, r in enumerate(rows):
            ids[r:] = k
        return ids

    def run(W, cols):
        return pd.Series(weight_returns(W, p.o[:, cols], p.c[:, cols], rf), index=p.dates)

    def show(name, fn):
        line = f"{name:<26}"
        for cell, (half, a, b) in CELLS.items():
            cols = p.half == half
            r = fn(cols)
            s = stats(r[(r.index >= a) & (r.index <= b)])
            line += f" | {cell} {s['CAGR'] * 100:5.1f}% {s['maxDD'] * 100:4.1f}% {s['sharpe']:.2f}"
        print(line, flush=True)

    print("CAGR / maxDD / Sharpe per cell (DEV = research <=2021, VAL-T research >=2022, VAL-U holdout <=2021, FINAL holdout >=2022)")
    for name, sc in scores.items():
        show(name, lambda cols, sc=sc: run(momentum_weights(p, cols, sc, vol, bull, me), cols))

    def r1(cols):  # only names above their 50d SMA
        sc = m12.where(pd.DataFrame(above50, index=p.dates, columns=p.tickers))
        return run(momentum_weights(p, cols, sc, vol, bull, me), cols)
    show("R1 only above 50d SMA", r1)

    mid_of = month_id(me)

    def r2(cols):  # daily crash exit until the next month-end
        W = momentum_weights(p, cols, m12, vol, bull, me)
        out = W.copy()
        flag = np.zeros(len(p.dates), bool)
        cur, off = -1, False
        for t in range(len(p.dates)):
            if mid_of[t] != cur:
                cur, off = mid_of[t], False
            if not bull[t]:
                off = True
            flag[t] = off
        out[flag] = 0
        return run(out, cols)
    show("R2 daily SPY crash exit", r2)

    def r3(cols):  # per-stock 20-day-low exit until month-end
        W = momentum_weights(p, cols, m12, vol, bull, me)
        out = W.copy()
        lw = low20[:, cols]
        stopped = np.zeros(W.shape[1], bool)
        cur = -1
        for t in range(len(p.dates)):
            if mid_of[t] != cur:
                cur, stopped[:] = mid_of[t], False
            stopped |= lw[t] & (W[t] > 0)
            out[t, stopped] = 0
        return run(out, cols)
    show("R3 stock 20-day-low exit", r3)

    def r4(cols):  # two tranches
        W1 = momentum_weights(p, cols, m12, vol, bull, me)
        W2 = momentum_weights(p, cols, m12, vol, bull, mid)
        return run(0.5 * W1 + 0.5 * W2, cols)
    show("R4 two tranches", r4)
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
