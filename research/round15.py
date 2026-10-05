"""Round 15: momentum top 20 on point-in-time S&P 500 membership (research/HYPOTHESES.md).
    python -m research.round15 r14.pkl r15.pkl"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from research.round14 import PERIODS
from research.round15_data import members_at
from research.systems6 import stats, weight_returns


def main(r14: str, r15: str) -> int:
    d, m = pd.read_pickle(r14), pd.read_pickle(r15)
    spy = d["spy"]["close"]
    dates = spy.index[spy.index >= "2010-01-01"]
    C = d["close"].reindex(dates).astype(float)
    O = d["open"].reindex(dates).astype(float)
    V = d["volume"].reindex(dates).astype(float)
    for t, df in m["extra"].items():           # removed names that yfinance still has
        df.index = pd.DatetimeIndex(df.index).tz_localize(None) if df.index.tz is not None else df.index
        C[t], O[t], V[t] = (df[k].reindex(dates).astype(float) for k in ("Close", "Open", "Volume"))
    rf = (d["irx"].reindex(dates).ffill() / 100 / 252).fillna(0).to_numpy()
    dv = (C * V).rolling(20, min_periods=20).mean()
    ok = (C.notna().cumsum() >= 253) & (dv >= 10e6) & (C >= 5)
    m12 = (C.shift(21) / C.shift(252) - 1).where(ok)
    bull = (spy > spy.rolling(200).mean()).reindex(dates).to_numpy()
    months = pd.Series(dates.month, index=dates)
    rebal = np.flatnonzero((months != months.shift(-1)).to_numpy())
    rebal = rebal[rebal >= 260]
    base, ch = m["base"], m["changes"]
    today = set(base)
    cols = {t: j for j, t in enumerate(C.columns)}
    S = m12.to_numpy()

    def weights(pit: bool, top: int = 20):
        W = np.full(S.shape, np.nan)
        cov = []
        for r in rebal:
            w = np.zeros(S.shape[1])
            mem = members_at(base, ch, dates[r]) if pit else today
            idx = [cols[t] for t in mem if t in cols]
            if pit:
                has = [j for j in idx if np.isfinite(C.iat[r, j])]
                cov.append(len(has) / max(len(mem), 1))
            if bull[r]:
                cand = [j for j in idx if np.isfinite(S[r, j])]
                pick = sorted(cand, key=lambda j: -S[r, j])[:top]
                if pick:
                    w[pick] = 1 / len(pick)
            W[r] = w
        return pd.DataFrame(W).ffill().fillna(0).to_numpy(), cov

    o, c = O.to_numpy(), C.to_numpy()
    W0, _ = weights(False)
    W1, cov = weights(True)
    cov = pd.Series(cov, index=dates[rebal])
    books = {"SPY": spy.reindex(dates).pct_change().fillna(0),
             "P0 today's S&P 500 members (hindsight)": pd.Series(weight_returns(W0, o, c, rf, 0.001), index=dates),
             "P1 point-in-time S&P 500 members": pd.Series(weight_returns(W1, o, c, rf, 0.001), index=dates)}
    print("price coverage of point-in-time members at month-ends: " + ", ".join(
        f"{p} {cov[(cov.index >= a) & (cov.index <= b)].mean() * 100:.0f}%" for p, (a, b) in PERIODS.items()))
    print("CAGR / maxDD / Sharpe")
    for name, r in books.items():
        line = f"{name:<40}"
        for p, (a, b) in PERIODS.items():
            s = stats(r[(r.index >= a) & (r.index <= b)])
            line += f" | {p} {s['CAGR'] * 100:6.1f}% {s['maxDD'] * 100:5.1f}% {s['sharpe']:5.2f}"
        print(line, flush=True)
    # which picks differ: names that P0 held but were NOT members at that time
    diff = []
    for r in rebal:
        a, b = set(np.flatnonzero(W0[r] > 0)), set(np.flatnonzero(W1[r] > 0))
        diff += [C.columns[j] for j in a - b]
    print("most frequent hindsight-only picks (held by P0, not members then):",
          pd.Series(diff).value_counts().head(15).to_dict())
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:3]))
