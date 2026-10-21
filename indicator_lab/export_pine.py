"""Refresh the v3 quality model and write it into every Pine file that embeds it.

    python -m indicator_lab.export_pine            # retrain on all closed DEV breakouts, update files
    python -m indicator_lab.export_pine --check    # only report whether the files are in sync

Run it once a year (or after adding data) so the live TradingView model includes the latest
closed trades, the same way the backtest refit the model every year.
"""
from __future__ import annotations

import json
import os
import re
import sys

from indicator_lab import meta

PINE_DIR = os.path.join(os.path.dirname(__file__), "pine")
FILES = ["swing_v3_quality_model.pine", "swing_v3_strategy.pine", "swing_v3_watchlist_dashboard.pine"]
VAR = {"ibs": "ibs", "rvol": "rvol", "roc21": "roc21", "roc63": "roc63", "roc126": "roc126", "atr_pct": "atrPct",
       "rsi14": "rsi14", "ext50": "ext50", "rs63": "rs63", "dist52": "dist52", "bbw_pct": "bbwPct", "gap": "gapAtr",
       "spy_up": "spyUp", "spy_roc63": "spyRoc63", "range_atr": "rangeAtr", "brk_atr": "brkAtr", "er20": "er20"}
SCORE_BLOCK = re.compile(r"^( *)score = [-+]?\d+\.\d+\n(?:\1 +\+ .*\n)+", re.M)
THRESHOLD = re.compile(r"(minQual   = input\.float\()\d+(?:\.\d+)?")


def render(model: dict, indent: str) -> str:
    lines = [f"{indent}score = {model['b']:+.6f}"]
    for f, mu, sd, w in zip(model["feats"], model["mu"], model["sd"], model["w"]):
        lines.append(f"{indent}     + {w:+.6f} * f_z({VAR[f]}, {mu:.6f}, {sd:.6f})")
    return "\n".join(lines) + "\n"


def apply(model: dict, src: str) -> str:
    src, n = SCORE_BLOCK.subn(lambda m: render(model, m.group(1)), src)
    if n != 1:
        raise ValueError(f"expected exactly one score block, found {n}")
    thr = round(model["thr"] * 100, 4)
    src, n = THRESHOLD.subn(lambda m: m.group(1) + f"{thr}", src)
    if n != 1:
        raise ValueError(f"expected exactly one minQual input, found {n}")
    return src


def main(argv: list[str]) -> int:
    path = os.path.join(PINE_DIR, "v3_model.json")
    if "--check" in argv:
        model = json.load(open(path))
        stale = [f for f in FILES if apply(model, open(os.path.join(PINE_DIR, f)).read())
                 != open(os.path.join(PINE_DIR, f)).read()]
        print("in sync" if not stale else f"out of sync: {stale}")
        return 1 if stale else 0
    model = meta.export_final()
    # render every file first (read fully before writing), so a failure leaves all files untouched
    out = {}
    for f in FILES:
        fp = os.path.join(PINE_DIR, f)
        with open(fp) as fh:
            out[fp] = apply(model, fh.read())
    for fp, src in out.items():
        with open(fp, "w") as fh:
            fh.write(src)
    with open(path, "w") as fh:
        json.dump(model, fh, indent=1)
    print(f"model refit on {model['n_train']} closed breakouts; threshold {model['thr']:.4f}; updated {FILES}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
