"""Round 9: (a) skip a leader breakout when the next open gaps back below the
breakout level ("failed breakout"), (b) a dip-free plan: momentum top 20 +
leader breakouts only.   python -m research.breakout9 BIG.pkl ETF.pkl"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from research.breakout7 import cell_of
from research.engine2 import build_panel
from research.portfolio4 import run_portfolio
from research.stock_systems6 import hold_monthly
from research.systems6 import stats, weight_returns
from research.trend_systems6 import donchian_trades

P2 = {"2008-2021": ("2008-06-01", "2021-12-31"), "2022-2026": ("2022-01-01", "2026-12-31")}


def main(path: str, etf_path: str) -> int:
    p = build_panel(pd.read_pickle(path))
    etf = pd.read_pickle(etf_path)
    rf = (etf["^IRX"]["close"].reindex(p.dates).ffill() / 100 / 252).fillna(0).to_numpy()
    C = p.df(p.c)
    mom = (C.shift(21) / C.shift(252) - 1).where(p.df(p.eligible))
    top50 = (mom.rank(axis=1, ascending=False) <= 50).to_numpy()
    spy = p.bench["SPY"]["close"].reindex(p.dates)
    bull = (spy > spy.rolling(200).mean()).to_numpy()
    hi50 = C.rolling(50).max().shift(1)
    b1 = ((C > hi50) & (C.shift(1) <= hi50.shift(1))).fillna(False).to_numpy() & top50 & bull[:, None]
    level = hi50.to_numpy()
    nxt_open = np.vstack([p.o[1:], np.full((1, p.o.shape[1]), np.nan)])
    held_open = b1 & (nxt_open >= level)          # next open still at/above the breakout level
    gap_back = b1 & (nxt_open < level)
    print(f"breakouts {b1.sum()}: next open >= level {held_open.sum()}, gap back below {gap_back.sum()}")
    books = {}
    for name, sig in (("all breakouts", b1), ("skip gap-back (filter)", held_open), ("gap-back only", gap_back)):
        tr = donchian_trades(p, sig)
        tr["cell"] = cell_of(p, tr)
        line = f"{name:<24} n={len(tr):>5} meanR {tr.r.mean():+.3f} win {(tr.r > 0).mean() * 100:3.0f}%"
        for cell in ("DEV", "VAL-T", "VAL-U", "FINAL"):
            x = tr[tr.cell == cell]
            line += f" | {cell} {x.r.mean():+.3f} (n {len(x)})"
        print(line, flush=True)
        books[name] = tr
    me = (pd.Series(p.dates.month, index=p.dates) != pd.Series(p.dates.month, index=p.dates).shift(-1)).to_numpy()
    print("\nDIP-FREE PLAN: momentum top 20 (SPY>200d) + leader breakouts (1% risk of sleeve, max 20), per half")
    for half, lab in ((1, "research"), (0, "holdout")):
        cols = p.half == half
        rk = mom.loc[:, cols].rank(axis=1, ascending=False) <= 20
        w = rk.astype(float).div(rk.sum(axis=1).replace(0, np.nan), axis=0).fillna(0).mul(bull.astype(float), axis=0)
        m = pd.Series(weight_returns(hold_monthly(w, me), p.o[:, cols], p.c[:, cols], rf), index=p.dates)
        out = {}
        for name in ("all breakouts", "skip gap-back (filter)"):
            tr = books[name]
            tr = tr[p.half[tr.j.to_numpy()] == half].copy()
            tr["prio"] = -np.nan_to_num(mom.to_numpy()[tr.t.to_numpy(), tr.j.to_numpy()])
            res = run_portfolio(p, tr, stop_atr=2.5, risk_pct=1.0, max_positions=20, priority="prio",
                                date_mask=p.dates >= "2008-06-01")
            out[name] = res["curve"].reindex(p.dates).ffill().pct_change().fillna(0)
        for name, r in (("momentum only", m), ("breakouts only", out["all breakouts"]),
                        ("breakouts, gap filter", out["skip gap-back (filter)"]),
                        ("50/50 momentum + breakouts", 0.5 * m + 0.5 * out["all breakouts"]),
                        ("50/50 + gap filter", 0.5 * m + 0.5 * out["skip gap-back (filter)"])):
            line = f"  {lab:<9}{name:<28}"
            for k, (a, b) in P2.items():
                s = stats(r[(r.index >= a) & (r.index <= b)])
                line += f" | {k}: {s['CAGR'] * 100:5.1f}% DD {s['maxDD'] * 100:4.1f}% Sh {s['sharpe']:.2f} worst {s['worst_yr'] * 100:5.1f}%"
            print(line, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
