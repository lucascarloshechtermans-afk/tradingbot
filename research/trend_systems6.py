"""Round 6 trade-based systems: S5 trend breakout with a Donchian trailing exit
(and random-entry control), S1/S2 leader-dip books, all through one account.
    python -m research.trend_systems6 DATA.pkl CAND4.pkl"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from research.engine2 import SLIP, build_panel, simulate_rules
from research.hypotheses4 import indicators, signals
from research.portfolio4 import run_portfolio


def donchian_trades(p, signal: np.ndarray, stop_atr: float = 2.5, exit_low: int = 20, max_bars: int = 250) -> pd.DataFrame:
    """Entry next open; initial stop stop_atr*ATR (intrabar, gap-aware);
    exit at the next open after a close below the lowest close of the prior
    `exit_low` sessions. One open trade per ticker."""
    T, N = p.c.shape
    C = p.df(p.c)
    low_ref = C.rolling(exit_low).min().shift(1).to_numpy()
    sig = signal & p.eligible
    rows = []
    for j in range(N):
        ts = np.flatnonzero(sig[:, j])
        busy = -1
        for t in ts:
            if t <= busy or t + 2 >= T:
                continue
            te = t + 1
            entry = p.o[te, j] * (1 + SLIP)
            dist = stop_atr * p.atr[t, j]
            if not (np.isfinite(entry) and np.isfinite(dist) and dist > 0):
                continue
            stop = entry - dist
            px, ex = None, None
            for d in range(te, min(T, te + max_bars)):
                lo, op = p.l[d, j], p.o[d, j]
                if not np.isfinite(lo):
                    continue
                if lo <= stop:
                    px = (min(op, stop) if d > te else min(entry, stop)) * (1 - SLIP)
                    ex = d
                    break
                if p.c[d, j] < low_ref[d, j] and d + 1 < T and np.isfinite(p.o[d + 1, j]):
                    px, ex = p.o[d + 1, j] * (1 - SLIP), d + 1
                    break
            if px is None:
                d = min(T - 1, te + max_bars - 1)
                px, ex = p.c[d, j] * (1 - SLIP), d
            if not np.isfinite(px):
                continue
            rows.append((t, j, (px - entry) / dist, ex))
            busy = ex
    return pd.DataFrame(rows, columns=["t", "j", "r", "exit_t"])


def report(p, name, tr, risk, maxpos, stop_atr, halves=((1, "research"), (0, "holdout"))):
    for half, lab in halves:
        for per, (a, b) in (("2008-2021", ("2008-06-01", "2021-12-31")), ("2022-2026", ("2022-01-01", "2026-12-31"))):
            dm = (p.dates >= a) & (p.dates <= b)
            sub = tr[(p.half[tr.j.to_numpy()] == half)]
            res = run_portfolio(p, sub, stop_atr=stop_atr, risk_pct=risk, max_positions=maxpos, max_heat=10,
                                priority="prio" if "prio" in sub else None, date_mask=dm)
            if res.get("trades", 0) == 0:
                continue
            yrs = (min(p.dates[-1], pd.Timestamp(b)) - pd.Timestamp(a)).days / 365.25
            print(f"{name:<34}{lab:<9}{per}: CAGR {res['CAGR'] * 100:5.1f}% DD {res['maxDD'] * 100:4.1f}% Sh {res['sharpe']:.2f} "
                  f"worst {res['worst_year'] * 100:5.1f}% meanR {res['meanR']:+.3f} trades/wk {res['trades'] / yrs / 52:.1f} "
                  f"avg open {res['avg_open']:.1f}", flush=True)


def main(data: str) -> int:
    p = build_panel(pd.read_pickle(data))
    I = indicators(p)  # noqa: E741
    C = I["C"]
    spy = p.bench["SPY"]["close"].reindex(p.dates)
    bull = (spy > spy.rolling(200).mean()).to_numpy()[:, None]
    brk = ((C >= C.rolling(50).max()) & (C.shift(1) < C.rolling(50).max().shift(1))).fillna(False).to_numpy() & bull
    rng = np.random.default_rng(7)
    rand = (rng.random(p.c.shape) < brk.sum() / (p.eligible & bull).sum()) & bull
    for name, sig in (("S5 50d breakout + Donchian20", brk), ("S5 control: random entry", rand)):
        tr = donchian_trades(p, sig)
        tr["prio"] = rng.random(len(tr))
        print(f"{name}: {len(tr)} trades, mean R {tr.r.mean():+.3f}, median bars {np.median(tr.exit_t - tr.t):.0f}", flush=True)
        report(p, name, tr, risk=0.5, maxpos=20, stop_atr=2.5)
    sig = signals(p, I)
    mom = I["mom_rank"].to_numpy()
    for name, s, hold in (("S1 leader dip 10d (all regimes)", sig["H01 LEADER_DIP"], 10),
                          ("S2 leader dip 20d, SPY>200d", sig["H01 LEADER_DIP"] & bull, 20)):
        tr = simulate_rules(p, s, stop_atr=2.5, max_hold=hold)
        tr["prio"] = mom[tr.t.to_numpy(), tr.j.to_numpy()]
        if name.startswith("S1"):
            below = ~bull[tr.t.to_numpy(), 0]
            tr["risk_mult"] = np.where(below, 0.5, 1.0)
        report(p, name, tr, risk=0.5, maxpos=10, stop_atr=2.5)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
