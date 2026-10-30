"""Round 17: momentum variants vs SPY on point-in-time S&P 500 membership.
    python -m research.round17 r14.pkl r15.pkl"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from research.round14 import PERIODS
from research.round15_data import members_at
from research.systems6 import stats, weight_returns

ROOT = Path(__file__).resolve().parent.parent


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
    ok = (C.notna().cumsum() >= 253) & (dv >= 10e6) & (C >= 5)
    S = (C.shift(21) / C.shift(252) - 1).where(ok).to_numpy()
    R = C.pct_change().to_numpy()
    spy_c = spy.reindex(dates)
    bull = (spy_c > spy_c.rolling(200).mean()).to_numpy()
    months = pd.Series(dates.month, index=dates)
    rebal = np.flatnonzero((months != months.shift(-1)).to_numpy())
    rebal = rebal[rebal >= 260]
    sectors = {**json.load(open(ROOT / "data" / "sp1000_members.json"))["members"],
               **json.load(open(ROOT / "data" / "sp500_members.json"))["members"]}
    col = {t: j for j, t in enumerate(C.columns)}
    sec = np.array([sectors.get(t) or f"?{t}" for t in C.columns], dtype=object)
    base, ch = m["base"], m["changes"]
    mem_cache = {r: [col[t] for t in members_at(base, ch, dates[r]) if t in col] for r in rebal}

    def weights(cap: int | None, vt: float | None):
        W = np.full(S.shape, np.nan)
        for r in rebal:
            w = np.zeros(S.shape[1])
            if bull[r]:
                cand = sorted((j for j in mem_cache[r] if np.isfinite(S[r, j])), key=lambda j: -S[r, j])
                pick, per = [], {}
                for j in cand:
                    if len(pick) >= 20:
                        break
                    if cap and per.get(sec[j], 0) >= cap:
                        continue
                    pick.append(j)
                    per[sec[j]] = per.get(sec[j], 0) + 1
                if pick:
                    w[pick] = 1 / len(pick)
                    if vt:
                        hist = np.nan_to_num(R[max(0, r - 62):r + 1][:, pick]) @ w[pick]
                        vol = hist.std() * np.sqrt(252)
                        if vol > 0:
                            w *= min(1.0, vt / vol)
            W[r] = w
        return pd.DataFrame(W).ffill().fillna(0).to_numpy()

    o, c = O.to_numpy(), C.to_numpy()
    books = {}
    for name, cap, vt in (("M0 current rule", None, None), ("M1 max 5 per sector", 5, None),
                          ("M2 vol target 20%", None, 0.20), ("M3 sector cap + vol target", 5, 0.20)):
        books[name] = pd.Series(weight_returns(weights(cap, vt), o, c, rf, 0.001), index=dates)
    so, sc = d["spy"]["open"].reindex(dates).to_numpy()[:, None], spy_c.to_numpy()[:, None]
    books["I0 SPY buy and hold"] = spy_c.pct_change().fillna(0)
    W = np.full((len(dates), 1), np.nan)
    for r in rebal:
        W[r] = 1.0 if bull[r] else 0.0
    books["I1 SPY with 200-day filter"] = pd.Series(
        weight_returns(pd.DataFrame(W).ffill().fillna(0).to_numpy(), so, sc, rf, 0.0002), index=dates)
    print("CAGR / maxDD / Sharpe / worst year per period")
    for name, r in books.items():
        line = f"{name:<30}"
        for p, (a, b) in PERIODS.items():
            s = stats(r[(r.index >= a) & (r.index <= b)])
            line += f" | {p} {s['CAGR'] * 100:6.1f}% {s['maxDD'] * 100:5.1f}% {s['sharpe']:5.2f} {s['worst_yr'] * 100:6.1f}%"
        print(line, flush=True)
    full = {n: stats(r[(r.index >= "2011-07-01") & (r.index <= "2026-09-30")]) for n, r in books.items()}
    print("\nwhole 2011-07..2026-09: " + " | ".join(f"{n.split()[0]} {s['CAGR'] * 100:.1f}%/{s['maxDD'] * 100:.0f}%/{s['sharpe']:.2f}"
                                                  for n, s in full.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:3]))
