"""Round 6 stock systems: S3 momentum portfolio (+ controls), per ticker half.
    python -m research.stock_systems6 DATA.pkl ETF.pkl"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from research.engine2 import build_panel
from research.systems6 import fmt, weight_returns

def hold_monthly(w: pd.DataFrame, month_end: np.ndarray) -> np.ndarray:
    """Keep the month-end target weights until the next month-end."""
    w = w.copy()
    w.loc[~month_end] = np.nan
    return w.ffill().fillna(0).to_numpy().copy()


P2 = {"2008-2021": ("2008-06-01", "2021-12-31"), "2022-2026": ("2022-01-01", "2026-12-31")}


def main(data: str, etf_path: str) -> int:
    p = build_panel(pd.read_pickle(data))
    etf = pd.read_pickle(etf_path)
    rf = (etf["^IRX"]["close"].reindex(p.dates).ffill() / 100 / 252).fillna(0).to_numpy()
    C = p.df(p.c)
    spy = p.bench["SPY"]["close"].reindex(p.dates)
    bull = (spy > spy.rolling(200).mean()).to_numpy()
    month_end = (pd.Series(p.dates.month, index=p.dates) != pd.Series(p.dates.month, index=p.dates).shift(-1)).to_numpy()
    mom12 = (C.shift(21) / C.shift(252) - 1).where(p.df(p.eligible))
    mom6 = (C.shift(21) / C.shift(126) - 1).where(p.df(p.eligible))
    vol = C.pct_change().rolling(63).std()
    for half, lab in ((1, "RESEARCH half"), (0, "HOLDOUT half")):
        cols = p.half == half
        print(f"\n=== {lab} ({cols.sum()} stocks)")
        def run(score, top, filt, name, invvol=False, extra=""):
            sc = score.loc[:, cols]
            rk = sc.rank(axis=1, ascending=False)
            pick = (rk <= top)
            w = pick.astype(float)
            if invvol:
                iv = (1 / vol.loc[:, cols]).where(pick)
                w = iv.div(iv.sum(axis=1), axis=0).fillna(0)
            else:
                w = w.div(pick.sum(axis=1).replace(0, np.nan), axis=0).fillna(0)
            if filt:
                w = w.mul(bull.astype(float), axis=0)
            W = w.pipe(hold_monthly, month_end)
            r = pd.Series(weight_returns(W, p.o[:, cols], p.c[:, cols], rf), index=p.dates)
            print(fmt(name, r, P2, extra), flush=True)
            return r
        elig = p.df(p.eligible).loc[:, cols]
        ew = elig.astype(float).div(elig.sum(axis=1).replace(0, np.nan), axis=0).fillna(0)
        W = ew.pipe(hold_monthly, month_end)
        print(fmt("equal-weight all eligible (control)", pd.Series(weight_returns(W, p.o[:, cols], p.c[:, cols], rf), index=p.dates), P2))
        W2 = (ew.mul(bull.astype(float), axis=0)).pipe(hold_monthly, month_end)
        print(fmt("equal-weight, SPY>200d (control)", pd.Series(weight_returns(W2, p.o[:, cols], p.c[:, cols], rf), index=p.dates), P2))
        run(mom12, 20, True, "MOM 12-1 top20 SPY>200d", extra=" <- pre-registered")
        run(mom12, 20, False, "MOM 12-1 top20 no filter")
        run(mom12, 10, True, "MOM 12-1 top10 SPY>200d")
        run(mom12, 50, True, "MOM 12-1 top50 SPY>200d")
        run(mom6, 20, True, "MOM 6-1 top20 SPY>200d")
        run(mom12, 20, True, "MOM 12-1 top20 inv-vol SPY>200d", invvol=True)
        run(-mom12, 20, True, "LOSERS 12-1 bottom20 (control)")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
