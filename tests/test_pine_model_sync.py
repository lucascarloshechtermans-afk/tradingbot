import json
import os
import re

PINE = os.path.join(os.path.dirname(__file__), "..", "indicator_lab", "pine")
VAR = {"ibs": "ibs", "rvol": "rvol", "roc21": "roc21", "roc63": "roc63", "roc126": "roc126", "atr_pct": "atrPct",
       "rsi14": "rsi14", "ext50": "ext50", "rs63": "rs63", "dist52": "dist52", "bbw_pct": "bbwPct", "gap": "gapAtr",
       "spy_up": "spyUp", "spy_roc63": "spyRoc63", "range_atr": "rangeAtr", "brk_atr": "brkAtr", "er20": "er20"}


def test_pine_files_embed_exactly_the_exported_v3_model():
    model = json.load(open(os.path.join(PINE, "v3_model.json")))
    for fname in ("swing_v3_quality_model.pine", "swing_v3_strategy.pine"):
        src = open(os.path.join(PINE, fname)).read()
        assert re.search(r"score = ([-+]\d+\.\d+)", src).group(1) == f"{model['b']:+.6f}"
        assert f"score >= {model['logit_thr']:.6f}" in src
        for f, mu, sd, w in zip(model["feats"], model["mu"], model["sd"], model["w"]):
            line = f"{w:+.6f} * f_z({VAR[f]}, {mu:.6f}, {sd:.6f})"
            assert line in src, (fname, line)
