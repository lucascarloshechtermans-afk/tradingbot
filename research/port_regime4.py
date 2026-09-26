"""Portfolio test of the regime rules found in DEV (round 4, step 2).

Candidates: dip hypotheses that passed DEV (H01, H02, H04, H05, H14), one open
trade per ticker. Regime rules only use SPY/VIX data through the signal close.
Usage: python -m research.port_regime4 BIG.pkl CAND.pkl [CELL]
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from research.engine2 import build_panel
from research.portfolio4 import run_portfolio

PASSED = ["is_leader_dip", "is_leader_dip_deep", "is_rsi2_uptrend", "is_down3_uptrend", "is_sector_leader_dip"]


def regime_mult(df: pd.DataFrame, scheme: str) -> np.ndarray:
    vix, down5, bull = df.vix.to_numpy(), (df.spy_ret5 < 0).to_numpy(), (df.spy_200 > 0).to_numpy()
    one = np.ones(len(df))
    if scheme == "none":
        return one
    if scheme == "vix>=15":
        return np.where(vix >= 15, 1.0, 0.0)
    if scheme == "vix>=15 & spyDown5":
        return np.where((vix >= 15) & down5, 1.0, 0.0)
    if scheme == "scaled":  # 0 calm, 1 normal, 1.5 fear-in-bull pullback
        return np.select([vix < 15, bull & down5], [0.0, 1.5], 1.0)
    if scheme == "scaled2":
        return np.select([vix < 15, ~bull, down5], [0.0, 0.5, 1.5], 1.0)
    raise ValueError(scheme)


def main(big_path: str, cand_path: str, cell: str = "DEV") -> int:
    p = build_panel(pd.read_pickle(big_path))
    c = pd.read_pickle(cand_path)
    c = c[(c.cell == cell) & (c[PASSED].sum(axis=1) > 0)].copy()
    c["deep"] = -c.ret5_atr
    c["lowvol"] = -c.atr_pct
    print(f"cell {cell}: {len(c)} candidates")
    print(f"{'hold':<6}{'regime':<20}{'prio':<9}{'risk':>5}{'trades':>7}{'CAGR':>7}{'maxDD':>7}{'Sharpe':>7}{'open':>6}{'meanR':>7}{'yrs+':>6}{'worstYr':>8}")
    for H in (10, 20):
        tr = c.rename(columns={f"r{H}": "r", f"exit{H}": "exit_t"}).dropna(subset=["r"]).copy()
        tr["exit_t"] = tr["exit_t"].astype(int)
        for scheme in ("none", "vix>=15", "vix>=15 & spyDown5", "scaled", "scaled2"):
            tr["risk_mult"] = regime_mult(tr, scheme)
            for prio in ("mom_rank", "deep", "lowvol"):
                for risk in (1.0,):
                    res = run_portfolio(p, tr, stop_atr=2.5, risk_pct=risk, max_positions=10, priority=prio)
                    print(f"{H:<6}{scheme:<20}{prio:<9}{risk:>5.1f}{res['trades']:>7}{res['CAGR'] * 100:>6.1f}%{res['maxDD'] * 100:>6.1f}%"
                          f"{res['sharpe']:>7.2f}{res['avg_open']:>6.1f}{res['meanR']:>7.3f}{res['years_pos'] * 100:>5.0f}%{res['worst_year'] * 100:>7.1f}%", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
