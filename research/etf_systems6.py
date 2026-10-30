"""Round 6 ETF systems: benchmarks, S4 sector rotation, S6 index RSI(2).
    python -m research.etf_systems6 ETF.pkl"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from research.systems6 import fmt, rsi, weight_returns

SECTORS9 = ["XLK", "XLF", "XLV", "XLE", "XLI", "XLY", "XLP", "XLU", "XLB"]


def main(path: str) -> int:
    etf = pd.read_pickle(path)
    dates = etf["SPY"].index[etf["SPY"].index >= "1998-12-01"]
    get = lambda t, k: etf[t][k].reindex(dates)  # noqa: E731
    rf = (get("^IRX", "close").ffill() / 100 / 252).fillna(0).to_numpy()
    spyO, spyC = get("SPY", "open").to_numpy()[:, None], get("SPY", "close").to_numpy()[:, None]
    spy = get("SPY", "close")
    ret = lambda W, O, C: pd.Series(weight_returns(W, O, C, rf), index=dates)  # noqa: E731
    one = np.ones((len(dates), 1))
    print("BENCHMARKS")
    print(fmt("SPY buy & hold", ret(one, spyO, spyC)))
    trend = (spy > spy.rolling(200).mean()).to_numpy()[:, None].astype(float)
    print(fmt("SPY only above 200d SMA", ret(trend, spyO, spyC)))
    qO, qC = get("QQQ", "open").to_numpy()[:, None], get("QQQ", "close").to_numpy()[:, None]
    print(fmt("QQQ buy & hold", ret(one, qO, qC)))

    print("\nS4 SECTOR ROTATION (9 sector SPDRs, month-end)")
    O = np.column_stack([get(t, "open") for t in SECTORS9])
    C = pd.DataFrame({t: get(t, "close") for t in SECTORS9})
    month_end = pd.Series(dates.month, index=dates) != pd.Series(dates.month, index=dates).shift(-1)
    for top in (3, 2, 4):
        for filt in ("own200", "none"):
            score = sum(C / C.shift(n) - 1 for n in (63, 126, 252)) / 3
            rank = score.rank(axis=1, ascending=False)
            pick = (rank <= top).astype(float) / top
            if filt == "own200":
                pick = pick * (C > C.rolling(200).mean())
            W = pick.where(month_end).ffill().fillna(0).to_numpy().copy()
            W[: 252] = 0
            tag = " <- pre-registered" if (top == 3 and filt == "own200") else ""
            print(fmt(f"top{top} filter={filt}", ret(W, O, C.to_numpy()), extra=tag))
    eqw = np.full((len(dates), 9), 1 / 9)
    print(fmt("equal-weight 9 sectors (control)", ret(eqw, O, C.to_numpy())))

    print("\nS6 INDEX RSI(2) (buy RSI2<10 above SMA200, sell after close > SMA5)")
    for t in ("SPY", "QQQ", "IWM"):
        c = get(t, "close")
        r2, s5, s200 = rsi(c), c.rolling(5).mean(), c.rolling(200).mean()
        pos = np.zeros(len(dates))
        inpos = False
        for i in range(len(dates)):
            if not inpos and c.iloc[i] > s200.iloc[i] and r2.iloc[i] < 10:
                inpos = True
            elif inpos and c.iloc[i] > s5.iloc[i]:
                inpos = False
            pos[i] = float(inpos)
        o_, c_ = get(t, "open").to_numpy()[:, None], c.to_numpy()[:, None]
        rr = ret(pos[:, None], o_, c_)
        print(fmt(f"{t} RSI2", rr, extra=f"  time-in {pos.mean() * 100:.0f}%"))
        # RSI2 in cash otherwise vs combined with trend holding
        both = np.maximum(pos, (c > s200).to_numpy().astype(float))
        print(fmt(f"{t} RSI2 + hold while >200d", ret(both[:, None], o_, c_)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
