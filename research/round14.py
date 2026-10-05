"""Round 14: NICHE momentum (research/HYPOTHESES.md, round 14).
    python -m research.round14 r14.pkl"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from research.systems6 import stats, weight_returns

PERIODS = {"DEV": ("2011-07-01", "2018-12-31"), "VAL": ("2019-01-01", "2022-12-31"), "OOS": ("2023-01-01", "2026-09-30")}


def monthly_weights(score: pd.DataFrame, bull: np.ndarray, rebal: np.ndarray, top: int | None) -> np.ndarray:
    """Equal weight in the top `top` names by score (all finite names if top is None) at each
    month-end close where SPY is above its 200-day; held until the next month-end."""
    S = score.to_numpy()
    W = np.full(S.shape, np.nan)
    for r in rebal:
        w = np.zeros(S.shape[1])
        if bull[r]:
            ok = np.flatnonzero(np.isfinite(S[r]))
            if len(ok):
                pick = ok if top is None else ok[np.argsort(-S[r, ok])[:top]]
                w[pick] = 1 / len(pick)
        W[r] = w
    return pd.DataFrame(W).ffill().fillna(0).to_numpy()


def main(path: str) -> int:
    d = pd.read_pickle(path)
    spy = d["spy"]["close"]
    dates = spy.index[spy.index >= "2010-01-01"]
    C = d["close"].reindex(dates)
    O = d["open"].reindex(dates)
    V = d["volume"].reindex(dates)
    rf = (d["irx"].reindex(dates).ffill() / 100 / 252).fillna(0).to_numpy()
    dv = (C * V).rolling(20, min_periods=20).mean()
    nbars = C.notna().cumsum()
    big = dv.rank(axis=1, ascending=False) <= 500            # point-in-time "S&P 500" proxy
    base = (nbars >= 253) & (dv >= 10e6) & C.notna()
    niche = base & ~big & (C >= 10)
    large = base & big & (C >= 5)
    sp500_today = set(json.load(open(Path(__file__).resolve().parent.parent / "data" / "sp500_members.json"))["members"])
    niche_today = base & (C >= 10) & pd.DataFrame(~C.columns.isin(sp500_today)[None, :].repeat(len(dates), 0),
                                                  index=dates, columns=C.columns)
    sp1000_today = set(json.load(open(Path(__file__).resolve().parent.parent / "data" / "sp1000_members.json"))["members"])
    sp1000 = base & pd.DataFrame(C.columns.isin(sp1000_today)[None, :].repeat(len(dates), 0), index=dates, columns=C.columns)
    m12 = C.shift(21) / C.shift(252) - 1
    f1 = C >= 0.75 * C.rolling(252, min_periods=200).max()
    gain = np.log(C.shift(21) / C.shift(252))
    best = np.log(C).diff().shift(21).rolling(231, min_periods=200).max()
    f2 = (gain > 0) & (best < gain / 3)
    bull = (spy > spy.rolling(200).mean()).reindex(dates).to_numpy()
    months = pd.Series(dates.month, index=dates)
    rebal = np.flatnonzero((months != months.shift(-1)).to_numpy())
    rebal = rebal[rebal >= 260]
    o, c = O.to_numpy(), C.to_numpy()

    def book(score, top, cost):
        return pd.Series(weight_returns(monthly_weights(score, bull, rebal, top), o, c, rf, cost), index=dates)

    books = {
        "B0 SPY": spy.reindex(dates).pct_change().fillna(0),
        "B1 random niche (EW, SPY filter)": book(m12.where(niche).notna().astype(float).where(niche), None, 0.003),
        "B2 large-cap momentum top 20": book(m12.where(large), 20, 0.001),
        "N0 niche raw top 10": book(m12.where(niche), 10, 0.003),
        "N1 + F1 near 52w high": book(m12.where(niche & f1), 10, 0.003),
        "N2 + F2 no one-day jump": book(m12.where(niche & f2), 10, 0.003),
        "N3 + F1 + F2 (live)": book(m12.where(niche & f1 & f2), 10, 0.003),
        "N4 = N3 top 20": book(m12.where(niche & f1 & f2), 20, 0.003),
        "N3b live rule, today's S&P500 out": book(m12.where(niche_today & f1 & f2), 10, 0.003),
        # added after the pre-registration, reference only (not part of Q1-Q3):
        "R1 main list: today's S&P 500+400 top 20": book(m12.where(sp1000 & (C >= 5)), 20, 0.001),
        "R2 N1 (F1 only) top 20": book(m12.where(niche & f1), 20, 0.003),
    }
    print(f"eligible niche names per month-end: median {int(niche.iloc[rebal].sum(1).median())}, "
          f"large {int(large.iloc[rebal].sum(1).median())}; tickers in data {C.shape[1]}")
    print("CAGR / maxDD / Sharpe per period (survivorship: absolute numbers too high; compare rows)")
    for name, r in books.items():
        line = f"{name:<36}"
        for p, (a, b) in PERIODS.items():
            s = stats(r[(r.index >= a) & (r.index <= b)])
            line += f" | {p} {s['CAGR'] * 100:6.1f}% {s['maxDD'] * 100:5.1f}% {s['sharpe']:5.2f}" if s else f" | {p} -"
        print(line, flush=True)
    # what the books held: share of biotech-like one-day jumps and average name count
    pd.to_pickle(books, path.replace(".pkl", "_books.pkl"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
