"""Round 11: X1 close entry for leader breakouts; E1 ETF leader breakouts.
    python -m research.round11 BIG.pkl ETF.pkl"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from research.breakout7 import cell_of
from research.engine2 import build_panel
from research.portfolio4 import run_portfolio
from research.round10 import CELLS
from research.systems6 import stats
from research.trend_systems6 import donchian_trades

ETFS = ["SPY", "QQQ", "IWM", "DIA", "MDY", "EFA", "EEM", "TLT", "IEF", "SHY", "GLD", "DBC", "VNQ",
        "XLK", "XLF", "XLV", "XLE", "XLI", "XLY", "XLP", "XLU", "XLB", "XLRE", "XLC"]


def close_entry(p):
    C = p.df(p.c)
    mom = (C.shift(21) / C.shift(252) - 1).where(p.df(p.eligible))
    top50 = (mom.rank(axis=1, ascending=False) <= 50).to_numpy()
    spy = p.bench["SPY"]["close"].reindex(p.dates)
    bull = (spy > spy.rolling(200).mean()).to_numpy()[:, None]
    hi = C.rolling(50).max().shift(1)
    sig = ((C > hi) & (C.shift(1) <= hi.shift(1))).fillna(False).to_numpy() & top50 & bull
    print("X1 -- leader breakout, entry at next open vs at the breakout day's close")
    for mode in ("open", "close"):
        tr = donchian_trades(p, sig, entry_at=mode)
        tr["cell"] = cell_of(p, tr)
        tr["prio"] = -np.nan_to_num(mom.to_numpy()[tr.t.to_numpy(), tr.j.to_numpy()])
        line = f"entry at {mode:<6} n={len(tr):>5} win {(tr.r > 0).mean() * 100:3.0f}%"
        for cell, (half, a, b) in CELLS.items():
            x = tr[tr.cell == cell]
            dm = (p.dates >= a) & (p.dates <= b)
            res = run_portfolio(p, tr[p.half[tr.j.to_numpy()] == half], stop_atr=2.5, risk_pct=0.5, max_positions=20,
                                priority="prio", date_mask=dm)
            line += f" | {cell} R {x.r.mean():+.3f} {res['CAGR'] * 100:5.1f}% DD {res['maxDD'] * 100:4.1f}%"
        print(line, flush=True)


def etf_panel(etf: dict, big: dict):
    stocks = {t: etf[t] for t in ETFS if t in etf}
    return build_panel({"stocks": stocks, "bench": big["bench"], "sectors": {t: None for t in stocks},
                        "half": {t: "RESEARCH" for t in stocks}})


def etf_breakouts(etf: dict, big: dict):
    p = etf_panel(etf, big)
    C = p.df(p.c)
    mom = (C.shift(21) / C.shift(252) - 1).where(p.df(p.eligible))
    top8 = (mom.rank(axis=1, ascending=False) <= 8).to_numpy()
    hi = C.rolling(50).max().shift(1)
    sig = ((C > hi) & (C.shift(1) <= hi.shift(1))).fillna(False).to_numpy() & top8
    rng = np.random.default_rng(11)
    elig = p.eligible
    rnd = elig & (rng.random(p.c.shape) < sig.sum() / max(elig.sum(), 1) * 1.5)
    periods = {"2006-2014": ("2006-01-01", "2014-12-31"), "2015-2021": ("2015-01-01", "2021-12-31"),
               "2022-2026": ("2022-01-01", "2026-12-31")}
    curves = {}
    print(f"\nE1 -- ETF leader breakouts ({C.shape[1]} ETFs), 0.5% risk, max 8, no SPY filter")
    for name, s in (("ETF leader breakouts", sig), ("control: random ETF entries", rnd)):
        tr = donchian_trades(p, s)
        tr["prio"] = -np.nan_to_num(mom.to_numpy()[tr.t.to_numpy(), tr.j.to_numpy()])
        res = run_portfolio(p, tr, stop_atr=2.5, risk_pct=0.5, max_positions=8, priority="prio",
                            date_mask=p.dates >= "2006-01-01")
        e = res["curve"]
        r = e.pct_change().dropna()
        curves[name] = r
        line = f"{name:<30} n={len(tr):>4} meanR {tr.r.mean():+.3f}"
        for k, (a, b) in periods.items():
            st = stats(r[(r.index >= a) & (r.index <= b)])
            x = tr[(p.dates[tr.t.to_numpy()] >= a) & (p.dates[tr.t.to_numpy()] <= b)]
            line += f" | {k}: R {x.r.mean():+.3f} {st['CAGR'] * 100:5.1f}% DD {st['maxDD'] * 100:4.1f}% Sh {st['sharpe']:.2f}"
        print(line, flush=True)
    return curves["ETF leader breakouts"]


def main(big_path: str, etf_path: str) -> int:
    big = pd.read_pickle(big_path)
    etf = pd.read_pickle(etf_path)
    p = build_panel(big)
    close_entry(p)
    etf_r = etf_breakouts(etf, big)
    pd.to_pickle(etf_r, big_path.replace("big.pkl", "etf_breakout_returns.pkl"))
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
