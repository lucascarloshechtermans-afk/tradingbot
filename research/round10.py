"""Round 10: robustness / refinements of the dip-free plan (research/HYPOTHESES.md).
    python -m research.round10 BIG.pkl ETF.pkl [momentum|breakout|all]"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from research.breakout7 import cell_of
from research.engine2 import build_panel
from research.portfolio4 import run_portfolio
from research.systems6 import stats, weight_returns
from research.trend_systems6 import donchian_trades

CELLS = {"DEV": (1, "2008-06-01", "2021-12-31"), "VAL-T": (1, "2022-01-01", "2026-12-31"),
         "VAL-U": (0, "2008-06-01", "2021-12-31"), "FINAL": (0, "2022-01-01", "2026-12-31")}


def momentum_weights(p, cols, mom, vol, bull, rebal_rows, top=20, buffer=None, sector_cap=None, invvol=False):
    T = len(p.dates)
    n = int(cols.sum())
    sectors = np.array(p.sector, dtype=object)[cols]
    m = mom.loc[:, cols].to_numpy()
    v = vol.loc[:, cols].to_numpy()
    W = np.full((T, n), np.nan)
    held: list[int] = []
    for r in rebal_rows:
        w = np.zeros(n)
        if bull[r]:
            score = m[r]
            order = [j for j in np.argsort(-np.nan_to_num(score, nan=-np.inf)) if np.isfinite(score[j])]
            rank = {j: i for i, j in enumerate(order)}
            keep = [j for j in held if j in rank and rank[j] < buffer] if buffer else []
            chosen, per_sec = list(keep), {}
            for j in chosen:
                per_sec[sectors[j]] = per_sec.get(sectors[j], 0) + 1
            for j in order:
                if len(chosen) >= top:
                    break
                if j in chosen:
                    continue
                if sector_cap and per_sec.get(sectors[j], 0) >= sector_cap:
                    continue
                chosen.append(j)
                per_sec[sectors[j]] = per_sec.get(sectors[j], 0) + 1
            if chosen:
                if invvol:
                    iv = 1 / np.where(np.isfinite(v[r, chosen]) & (v[r, chosen] > 0), v[r, chosen], np.nan)
                    iv = np.nan_to_num(iv, nan=np.nanmean(iv) if np.isfinite(iv).any() else 1.0)
                    w[chosen] = iv / iv.sum()
                else:
                    w[chosen] = 1 / len(chosen)
            held = chosen
        else:
            held = []
        W[r] = w
    return pd.DataFrame(W).ffill().fillna(0).to_numpy()


def momentum(p, etf):
    rf = (etf["^IRX"]["close"].reindex(p.dates).ffill() / 100 / 252).fillna(0).to_numpy()
    C = p.df(p.c)
    mom = (C.shift(21) / C.shift(252) - 1).where(p.df(p.eligible))
    vol = C.pct_change().rolling(63).std()
    spy = p.bench["SPY"]["close"].reindex(p.dates)
    bull = (spy > spy.rolling(200).mean()).to_numpy()
    months = pd.Series(p.dates.month, index=p.dates)
    me = np.flatnonzero((months != months.shift(-1)).to_numpy())
    every10 = np.arange(252, len(p.dates), 10)
    variants = {
        "default top20 monthly": dict(),
        "top10": dict(top=10), "top30": dict(top=30),
        "buffer: keep while in top40": dict(buffer=40),
        "max 5 per sector": dict(sector_cap=5),
        "inverse-vol weights": dict(invvol=True),
        "rebalance every 10 sessions": dict(rows=every10),
        "buffer40 + max5/sector": dict(buffer=40, sector_cap=5),
    }
    print("MOMENTUM BOOK -- CAGR / maxDD / Sharpe per cell")
    for name, kw in variants.items():
        rows = kw.pop("rows", me)
        line = f"{name:<30}"
        for cell, (half, a, b) in CELLS.items():
            cols = p.half == half
            W = momentum_weights(p, cols, mom, vol, bull, rows, **kw)
            r = pd.Series(weight_returns(W, p.o[:, cols], p.c[:, cols], rf), index=p.dates)
            s = stats(r[(r.index >= a) & (r.index <= b)])
            turn = np.abs(np.diff(W, axis=0)).sum(1)[(p.dates[1:] >= a) & (p.dates[1:] <= b)].sum() / ((pd.Timestamp(b if b < "2026" else p.dates[-1]) - pd.Timestamp(a)).days / 365.25)
            line += f" | {cell} {s['CAGR'] * 100:5.1f}% {s['maxDD'] * 100:4.1f}% {s['sharpe']:.2f} t/o {turn:3.1f}"
        print(line, flush=True)


def breakouts(p):
    C = p.df(p.c)
    mom = (C.shift(21) / C.shift(252) - 1).where(p.df(p.eligible))
    rank = mom.rank(axis=1, ascending=False)
    spy = p.bench["SPY"]["close"].reindex(p.dates)
    bull = (spy > spy.rolling(200).mean()).to_numpy()[:, None]
    base = dict(top=50, look=50, exit_low=20, stop=2.5)
    variants = [("default", {})] + [(f"{k}={v}", {k: v}) for k, vals in
                                    (("top", (30, 100)), ("look", (20, 100)), ("exit_low", (10, 50)), ("stop", (2.0, 3.5)))
                                    for v in vals]
    print("\nLEADER BREAKOUT -- mean R per trade and one-account CAGR/maxDD (0.5% risk, max 20) per cell")
    for name, ch in variants:
        prm = {**base, **ch}
        hi = C.rolling(prm["look"]).max().shift(1)
        sig = ((C > hi) & (C.shift(1) <= hi.shift(1))).fillna(False).to_numpy() & (rank <= prm["top"]).to_numpy() & bull
        tr = donchian_trades(p, sig, stop_atr=prm["stop"], exit_low=prm["exit_low"])
        tr["cell"] = cell_of(p, tr)
        tr["prio"] = -np.nan_to_num(mom.to_numpy()[tr.t.to_numpy(), tr.j.to_numpy()])
        line = f"{name:<14} n={len(tr):>5}"
        for cell, (half, a, b) in CELLS.items():
            x = tr[tr.cell == cell]
            dm = (p.dates >= a) & (p.dates <= b)
            res = run_portfolio(p, tr[p.half[tr.j.to_numpy()] == half], stop_atr=prm["stop"], risk_pct=0.5,
                                max_positions=20, priority="prio", date_mask=dm)
            line += f" | {cell} R {x.r.mean():+.3f} {res['CAGR'] * 100:5.1f}% DD {res['maxDD'] * 100:4.1f}%"
        print(line, flush=True)


def main(path: str, etf_path: str, what: str = "all") -> int:
    p = build_panel(pd.read_pickle(path))
    etf = pd.read_pickle(etf_path)
    if what in ("momentum", "all"):
        momentum(p, etf)
    if what in ("breakout", "all"):
        breakouts(p)
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
