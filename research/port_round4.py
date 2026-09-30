"""Portfolio comparison of candidate strategies, DEV cell (research half, <=2021)."""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from research.engine2 import SPLIT_DATE, build_panel, simulate_rules
from research.hypotheses4 import indicators, signals
from research.portfolio4 import run_portfolio


def main(big_path: str) -> int:
    p = build_panel(pd.read_pickle(big_path))
    I = indicators(p)  # noqa: E741
    sig = signals(p, I)
    C = I["C"]
    sma5 = C.rolling(5).mean()
    spy = p.bench["SPY"]["close"].reindex(p.dates)
    bull = (spy > spy.rolling(200).mean()).to_numpy()
    dev = (p.half[None, :] == 1) & (p.dates < SPLIT_DATE)[:, None]
    exits = {"time10": dict(max_hold=10), "SMA5exit": dict(max_hold=10, exit_cond=(C > sma5).to_numpy()),
             "RSI2>70": dict(max_hold=10, exit_cond=(I["rsi2"] > 70).to_numpy())}
    prio_mats = {"deepest": -I["ret5_atr"].to_numpy(), "mom": I["mom_rank"].to_numpy()}
    combos = {
        "H19 BASELINE": sig["H19 BASELINE"],
        "H01 LEADER_DIP": sig["H01 LEADER_DIP"],
        "H02 LEADER_DIP_DEEP": sig["H02 LEADER_DIP_DEEP"],
        "H04 RSI2_UPTREND": sig["H04 RSI2_UPTREND"],
        "H14 SECTOR_LEADER_DIP": sig["H14 SECTOR_LEADER_DIP"],
        "UNION H01|H04|H14": sig["H01 LEADER_DIP"] | sig["H04 RSI2_UPTREND"] | sig["H14 SECTOR_LEADER_DIP"],
    }
    print(f"{'strategy':<24}{'exit':<10}{'regime':<8}{'prio':<9}{'trades':>7}{'CAGR':>7}{'maxDD':>7}{'Sharpe':>7}{'open':>6}{'yrs+':>6}{'worstYr':>8}")
    for name, s in combos.items():
        for ename, kw in exits.items():
            for rname, rmask in (("all", np.ones(len(p.dates), bool)), ("bull", bull)):
                s2 = s & dev & rmask[:, None]
                tr = simulate_rules(p, s2, stop_atr=2.5, **kw)
                for pname, pm in prio_mats.items():
                    tr["pr"] = pm[tr.t.to_numpy(), tr.j.to_numpy()]
                    res = run_portfolio(p, tr, stop_atr=2.5, risk_pct=1.0, max_positions=10, priority="pr")
                    print(f"{name:<24}{ename:<10}{rname:<8}{pname:<9}{res['trades']:>7}{res['CAGR'] * 100:>6.1f}%{res['maxDD'] * 100:>6.1f}%"
                          f"{res['sharpe']:>7.2f}{res['avg_open']:>6.1f}{res['years_pos'] * 100:>5.0f}%{res['worst_year'] * 100:>7.1f}%", flush=True)
                    if name == "H19 BASELINE":
                        break
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
