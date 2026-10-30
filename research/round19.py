"""Round 19: low volatility and blends vs SPY (point-in-time S&P 500).
    python -m research.round19 r14.pkl r15.pkl"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from research.round15_data import members_at
from research.systems6 import stats, weight_returns

PERIODS = {"DEV": ("2011-07-01", "2018-12-31"), "VAL": ("2019-01-01", "2022-12-31"), "OOS": ("2023-01-01", "2026-09-30")}


def main(r14: str, r15: str) -> int:
    d, m = pd.read_pickle(r14), pd.read_pickle(r15)
    spy = d["spy"]["close"]
    dates = spy.index[spy.index >= "2010-01-01"]
    C = d["close"].reindex(dates).astype(float)
    O = d["open"].reindex(dates).astype(float)
    V = d["volume"].reindex(dates).astype(float)
    for t, df in m["extra"].items():
        df.index = pd.DatetimeIndex(df.index).tz_localize(None) if df.index.tz is not None else df.index
        C[t], O[t], V[t] = (df[k].reindex(dates).astype(float) for k in ("Close", "Open", "Volume"))
    rf = (d["irx"].reindex(dates).ffill() / 100 / 252).fillna(0).to_numpy()
    dv = (C * V).rolling(20, min_periods=20).mean()
    ok = ((C.notna().cumsum() >= 253) & (dv >= 10e6) & (C >= 5)).to_numpy()
    ret = C.pct_change()
    vol = ret.rolling(252, min_periods=200).std().to_numpy()
    m12 = (C.shift(21) / C.shift(252) - 1).to_numpy()
    spy_c = spy.reindex(dates)
    bull = (spy_c > spy_c.rolling(200).mean()).to_numpy()
    mo = pd.Series(dates.month, index=dates)
    rows = np.flatnonzero((mo != mo.shift(-1)).to_numpy())
    rows = rows[rows >= 260]
    col = {t: j for j, t in enumerate(C.columns)}
    mem = {r: [col[t] for t in members_at(m["base"], m["changes"], dates[r]) if t in col] for r in rows}
    o, c = O.to_numpy(), C.to_numpy()

    def weights(kind: str) -> np.ndarray:
        W = np.full(c.shape, np.nan)
        for r in rows:
            w = np.zeros(c.shape[1])
            cand = [j for j in mem[r] if ok[r, j] and np.isfinite(vol[r, j]) and np.isfinite(m12[r, j])]
            if kind == "L1" or (kind == "L2" and bull[r]):
                pick = sorted(cand, key=lambda j: vol[r, j])[:50]
            elif kind == "L3" and bull[r]:
                calm = sorted(cand, key=lambda j: vol[r, j])[:100]
                pick = sorted(calm, key=lambda j: -m12[r, j])[:20]
            elif kind == "M0" and bull[r]:
                pick = sorted(cand, key=lambda j: -m12[r, j])[:20]
            else:
                pick = []
            if pick:
                w[pick] = 1 / len(pick)
            W[r] = w
        return pd.DataFrame(W).ffill().fillna(0).to_numpy()

    def run(W):
        return pd.Series(weight_returns(W, o, c, rf, 0.001), index=dates)

    spy_r = spy_c.pct_change().fillna(0)
    L1, M0 = run(weights("L1")), run(weights("M0"))
    books = {"SPY buy and hold": spy_r, "L1 low vol 50": L1, "L2 low vol 50 + SPY filter": run(weights("L2")),
             "L3 low-vol momentum top 20": run(weights("L3")),
             "B1 80% SPY + 20% momentum": 0.8 * spy_r + 0.2 * M0, "B2 50% SPY + 50% low vol": 0.5 * spy_r + 0.5 * L1,
             "M0 current momentum rule": M0}
    ref = {p: stats(spy_r[(spy_r.index >= a) & (spy_r.index <= b)])["sharpe"] for p, (a, b) in PERIODS.items()}
    print("CAGR / maxDD / Sharpe / worst year; verdict = higher Sharpe than SPY in DEV, VAL, OOS")
    for name, r in books.items():
        line, wins = f"{name:<30}", 0
        for p, (a, b) in PERIODS.items():
            s = stats(r[(r.index >= a) & (r.index <= b)])
            line += f" | {p} {s['CAGR'] * 100:5.1f}% {s['maxDD'] * 100:4.0f}% {s['sharpe']:4.2f} {s['worst_yr'] * 100:6.1f}%"
            wins += int(name != "SPY buy and hold" and s["sharpe"] > ref[p])
        full = stats(r[(r.index >= "2011-07-01") & (r.index <= "2026-09-30")])
        verdict = "" if name == "SPY buy and hold" else ("BEATS SPY" if wins == 3 else "possible (2/3)" if wins == 2 else f"no ({wins}/3)")
        print(line + f" | all {full['CAGR'] * 100:5.1f}% {full['maxDD'] * 100:3.0f}% {full['sharpe']:4.2f} | {verdict}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:3]))
