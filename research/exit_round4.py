"""Exit/stop grid for the passing dip hypotheses, DEV cell only."""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from research.engine2 import SPLIT_DATE, build_panel, simulate_rules
from research.hypotheses4 import indicators, signals

KEEP = ["H01 LEADER_DIP", "H02 LEADER_DIP_DEEP", "H04 RSI2_UPTREND", "H05 DOWN3_UPTREND", "H14 SECTOR_LEADER_DIP", "H19 BASELINE"]


def main(big_path: str, out: str) -> int:
    p = build_panel(pd.read_pickle(big_path))
    I = indicators(p)  # noqa: E741
    sig = signals(p, I)
    C = I["C"]
    sma5 = C.rolling(5).mean()
    rules = {
        "time10 stop2.5": dict(stop_atr=2.5, max_hold=10),
        "time5 stop2.5": dict(stop_atr=2.5, max_hold=5),
        "close>SMA5 (max10) stop2.5": dict(stop_atr=2.5, max_hold=10, exit_cond=(C > sma5).to_numpy()),
        "first up close (max10) stop2.5": dict(stop_atr=2.5, max_hold=10, exit_cond=(C > C.shift(1)).to_numpy()),
        "RSI2>70 (max10) stop2.5": dict(stop_atr=2.5, max_hold=10, exit_cond=(I["rsi2"] > 70).to_numpy()),
        "close>SMA5 (max10) stop4": dict(stop_atr=4.0, max_hold=10, exit_cond=(C > sma5).to_numpy()),
        "close>SMA5 (max10) stop1.5": dict(stop_atr=1.5, max_hold=10, exit_cond=(C > sma5).to_numpy()),
        "target1ATR (max10) stop2.5": dict(stop_atr=2.5, max_hold=10, target_atr=1.0),
        "close>SMA5 (max20) stop2.5": dict(stop_atr=2.5, max_hold=20, exit_cond=(C > sma5).to_numpy()),
    }
    dev_rows = (p.half[None, :] == 1) & (p.dates < SPLIT_DATE)[:, None]
    res = []
    for h in KEEP:
        s = sig[h] & dev_rows
        for name, kw in rules.items():
            tr = simulate_rules(p, s, **kw)
            if tr.empty:
                continue
            yrs = tr.groupby(p.dates[tr.t].year)["r"].mean()
            # R per 100 position-days: capital efficiency
            res.append({"hyp": h, "rule": name, "n": len(tr), "R": tr.r.mean(), "win": (tr.r > 0).mean(),
                        "bars": tr.bars.mean(), "R_per_day": tr.r.sum() / tr.bars.sum(), "yrs+": (yrs > 0).mean(),
                        "PF": tr.r[tr.r > 0].sum() / -tr.r[tr.r < 0].sum()})
            print(f"{h:<24} {name:<32} n={len(tr):>6} R={tr.r.mean():+.3f} win={(tr.r > 0).mean() * 100:4.1f}% "
                  f"bars={tr.bars.mean():4.1f} R/day={tr.r.sum() / tr.bars.sum():+.4f} yrs+={(yrs > 0).mean() * 100:3.0f}%", flush=True)
    pd.DataFrame(res).to_pickle(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
