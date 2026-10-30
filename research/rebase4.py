"""Re-score round-4 hypotheses (price H01-H19 and earnings E01-E07) against the
same-day cross-sectional baseline (engine2.day_baseline). DEV cell only unless
CELLS is given.  python -m research.rebase4 BIG.pkl ROUND4.pkl EARN4.pkl [CELLS]"""
from __future__ import annotations

import sys

import pandas as pd

from research.engine2 import add_day_excess, build_panel, cell_stats, day_baseline


def main(big: str, r4: str, e4: str, cells: str = "DEV") -> int:
    p = build_panel(pd.read_pickle(big))
    db = day_baseline(p, holds=(5, 10, 20, 40))
    sets = {**pd.read_pickle(r4)["trades"], **pd.read_pickle(e4)["trades"]}
    for name, tr in sets.items():
        if tr.empty:
            continue
        tr = add_day_excess(tr, db)
        for cell in cells.split(","):
            d = tr[tr.cell == cell]
            line = f"{cell:<6}{name:<28} n={len(d):>6}"
            for H in (5, 10, 20, 40):
                if f"r{H}" not in d:
                    continue
                st = cell_stats(d, H)
                if st.get("n", 0) >= 30:
                    line += f" | H{H}: R {st['R']:+.3f} XD {st['X']:+.3f} t {st['t']:+.1f} yrs {st['yrs+'] * 100:3.0f}%"
            print(line, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
