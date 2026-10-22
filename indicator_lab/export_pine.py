"""Generate the model-dependent parts of the v3 Pine files (never edit those parts by hand).

Every Pine file marks generated regions as

    // <<GEN:NAME>>
    ...generated code...
    // <</GEN:NAME>>

and this script rewrites the content between the markers (keeping the marker's indentation):

  TRAIN     the settings the model was trained with + the final threshold (inputs default to them)
  HELPERS   pandas-compatible helper functions (Python = reference, see pine_parity.py)
  FEATURES  the 17 model features
  MODEL     the model fits + `score`/`quality`
  DEBUG     raw features in the Data Window when the debug input is on (indicator only)

    python -m indicator_lab.export_pine            # refit the final model (+ yearly fits) and regenerate
    python -m indicator_lab.export_pine --render   # regenerate from the stored JSON, no refit
    python -m indicator_lab.export_pine --check    # exit 1 if any file is out of sync with the JSON
"""
from __future__ import annotations

import json
import os
import re
import sys

PINE_DIR = os.path.join(os.path.dirname(__file__), "pine")
FILES = ["swing_v3_quality_model.pine", "swing_v3_strategy.pine", "swing_v3_watchlist_dashboard.pine"]
FINAL = os.path.join(PINE_DIR, "v3_model.json")
YEARLY = os.path.join(PINE_DIR, "v3_model_yearly.json")
VAR = {"ibs": "ibs", "rvol": "rvol", "roc21": "roc21", "roc63": "roc63", "roc126": "roc126", "atr_pct": "atrPct",
       "rsi14": "rsi14", "ext50": "ext50", "rs63": "rs63", "dist52": "dist52", "bbw_pct": "bbwPct", "gap": "gapAtr",
       "spy_up": "spyUp", "spy_roc63": "spyRoc63", "range_atr": "rangeAtr", "brk_atr": "brkAtr", "er20": "er20"}
REGION = re.compile(r"^( *)// <<GEN:(\w+)>>\n.*?^\1// <</GEN:\2>>\n", re.MULTILINE | re.DOTALL)

HELPERS = '''\
// Python (meta.feature_frame, pandas) is the reference for every model feature; pine_parity.py checks it.
// ta.rma seeds with an SMA, pandas ewm(adjust=False) with the first value: this reproduces pandas.
f_rma_py(float src, simple int len) =>
    var float s = na
    var int cnt = 0
    if not na(src)
        s := na(s) ? src : (src + (len - 1) * s) / len
        cnt += 1
    cnt >= len ? s : na

// pandas rolling(len, min_periods = minCnt).rank(pct = True): current bar included, ties averaged
// (ta.percentrank counts only the PREVIOUS len values).
f_rank_incl(float x, simple int len, simple int minCnt) =>
    float res = na
    if not na(x)
        int cnt = 0
        int less = 0
        int eq = 0
        for i = 0 to len - 1
            v = x[i]
            if not na(v)
                cnt += 1
                less += v < x ? 1 : 0
                eq += v == x ? 1 : 0
        res := cnt >= minCnt ? (less + (eq + 1) / 2.0) / cnt : na
    res

// No nz(): a missing feature makes the score na, so quality is na and there is no BUY (the training dropped
// such rows instead of imputing them; R4 found no taken trade with a missing feature in Python either).
f_z(x, mu, sd) => (x - mu) / sd
'''

FEATURES = '''\
trueRange = na(close[1]) ? high - low : math.max(high - low, math.abs(high - close[1]), math.abs(low - close[1]))
atr       = f_rma_py(trueRange, 14)
chg       = ta.change(close)
rsiUp     = f_rma_py(na(chg) ? na : math.max(chg, 0), 14)
rsiDn     = f_rma_py(na(chg) ? na : math.max(-chg, 0), 14)
spyToday  = request.security(spySym, "D", close)
spyPrev   = request.security(spySym, "D", close[1])
spy       = syminfo.timezone == "America/New_York" ? spyToday : spyPrev
volRatio  = volume / ta.sma(volume, 50)
ibs       = high > low ? (close - low) / (high - low) : 0.5
rvol      = na(volRatio) ? na : math.log(math.max(volRatio, 0.05))
roc21     = close / close[21] - 1
roc63     = close / close[63] - 1
roc126    = close / close[126] - 1
atrPct    = atr / close * 100
rsi14     = na(rsiUp) or na(rsiDn) ? na : rsiDn == 0 ? 100.0 : 100 - 100 / (1 + rsiUp / rsiDn)
ext50     = (close - ta.sma(close, 50)) / atr
spyRoc63  = spy / spy[63] - 1
rs63      = roc63 - spyRoc63
hi52      = bar_index >= 199 ? ta.highest(high, math.min(bar_index + 1, 252)) : na
dist52    = close / hi52 - 1
bbw       = 4 * ta.stdev(close, 20) / ta.sma(close, 20)
bbwPct    = f_rank_incl(bbw, 252, 100)
gapAtr    = (open - close[1]) / atr[1]
spyUp     = spy > ta.sma(spy, 200) ? 1.0 : 0.0
rangeAtr  = (high - low) / atr[1]
brkAtr    = (close - ta.highest(high, TRAIN_N)[1]) / atr  // feature definition: the TRAINING lookback, not input n
er20      = math.abs(close - close[20]) / math.sum(math.abs(ta.change(close)), 20)
'''


def _expr(fit: dict, feats: list[str]) -> str:
    out = f"{fit['b']:.6f}"
    for f, mu, sd, w in zip(feats, fit["mu"], fit["sd"], fit["w"]):
        if w == 0:  # e.g. spy_up in 2015: constant in training (sd = 1e-9), weight 0 -> contributes nothing
            continue
        assert sd > 1e-6, (fit.get("year"), f, sd)
        out += f" {'+' if w >= 0 else '-'} {abs(w):.6f} * f_z({VAR[f]}, {mu:.6f}, {sd:.6f})"
    return out


def train_block(final: dict) -> str:
    p = final["params"]
    return "\n".join([
        "// The quality model was trained on breakouts with exactly these rules (v3_model.json \"params\"); the inputs",
        "// default to them, and with the model on, any other value gets a warning (the model never saw those trades).",
        f"TRAIN_N     = {p['n']}",
        f"TRAIN_M     = {p['m']}",
        f"TRAIN_TRAIL = {p['trail']:.2f}",
        f"TRAIN_IBS   = {p['ibs_min']:.2f}",
        f"TRAIN_TREND = {p['trend_len']}",
        f"TRAIN_TXT   = \"model getraind op n={p['n']}/m={p['m']}/trail={p['trail']:g}/ibs={p['ibs_min']:g}/SMA{p['trend_len']}\"",
        f"// Threshold of the final fit = v3_model.json \"thr\" {final['thr']:.6f}: the {100 * (1 - p['keep']):g}th percentile of its",
        f"// predictions on its own {final['n_train']} training breakouts (keep {p['keep']:g}). minQual defaults to it (in %).",
        f"FINAL_THR   = {final['thr']:.6f}",
    ]) + "\n"


def model_block(final: dict, yearly: dict | None) -> str:
    feats = final["feats"]
    lines = [
        f"// FINAL fit: {final['n_train']} closed DEV breakouts up to {yearly['train_end'] if yearly else '?'}.",
        "scoreIs = " + _expr(final, feats),
    ]
    if yearly:
        y_end = yearly["train_end"].split("-")
        lines += [
            "// OOS: on history each bar uses the walk-forward fit of its own year, trained only on breakouts whose",
            "// trade closed before 1 Jan of that year (v3_model_yearly.json). Bars after TRAIN_END (the last bar",
            "// the final fit has seen) use the final fit. Before the first fit year there is no model (no BUY).",
            f"TRAIN_END = timestamp(\"UTC\", {int(y_end[0])}, {int(y_end[1])}, {int(y_end[2])}, 23, 59)",
            "fitYear   = year(time)",
            "scoreYear = switch fitYear",
        ]
        for fit in yearly["fits"]:
            lines.append(f"    {fit['year']} => " + _expr(fit, feats))
        lines.append("    => float(na)")
        lines.append("thrYear   = switch fitYear")
        for fit in yearly["fits"]:
            lines.append(f"    {fit['year']} => {fit['thr']:.6f}")
        lines.append("    => float(na)")
        lines += ["scoreOos  = time > TRAIN_END ? scoreIs : scoreYear",
                  "thrOos    = time > TRAIN_END ? FINAL_THR : thrYear"]
    else:
        lines += ["scoreOos  = scoreIs", "thrOos    = FINAL_THR"]
    lines += [
        "score     = scoreOos  // the signals use the out-of-sample score",
        "quality   = 1 / (1 + math.exp(-scoreOos))",
        "qualityIs = 1 / (1 + math.exp(-scoreIs))",
        "// minQual is an absolute threshold for the final fit; on OOS bars the same shift is applied to that year's own threshold",
        "qualityOk   = not useModel or (not na(quality) and quality * 100 >= thrOos * 100 + (minQual - FINAL_THR * 100))",
        "qualityOkIs = not useModel or (not na(qualityIs) and qualityIs * 100 >= minQual)",
    ]
    return "\n".join(lines) + "\n"


DEBUG = "\n".join(f'plot(debugFeat ? {v} : na, "f {k}", display = display.data_window)' for k, v in VAR.items()) + \
    '\nplot(debugFeat ? score : na, "f score (logit)", display = display.data_window)\n'


def blocks(final: dict, yearly: dict | None) -> dict:
    return {"TRAIN": train_block(final), "HELPERS": HELPERS, "FEATURES": FEATURES, "MODEL": model_block(final, yearly), "DEBUG": DEBUG}


def _indent(text: str, ind: str) -> str:
    return "".join((ind + ln if ln.strip() else ln) for ln in text.splitlines(keepends=True))


def apply(src: str, bl: dict) -> str:
    def rep(m):
        ind, name = m.group(1), m.group(2)
        if name not in bl:
            raise KeyError(f"unknown generated region {name}")
        return f"{ind}// <<GEN:{name}>>\n{_indent(bl[name], ind)}{ind}// <</GEN:{name}>>\n"
    out, n = REGION.subn(rep, src)
    if n == 0:
        raise ValueError("no generated regions found")
    return out


def _read(path: str) -> str:
    with open(path) as fh:
        return fh.read()


def _load():
    final = json.loads(_read(FINAL))
    yearly = json.loads(_read(YEARLY)) if os.path.exists(YEARLY) else None
    return final, yearly


def render() -> dict[str, str]:
    bl = blocks(*_load())
    out = {}
    for f in FILES:
        fp = os.path.join(PINE_DIR, f)
        out[fp] = apply(_read(fp), bl)
    return out


def write(out: dict[str, str]) -> None:
    for fp, src in out.items():
        with open(fp, "w") as fh:
            fh.write(src)


def main(argv: list[str]) -> int:
    if "--check" in argv:
        out = render()
        stale = [os.path.basename(fp) for fp, src in out.items() if src != _read(fp)]
        print("in sync" if not stale else f"out of sync: {stale}")
        return 1 if stale else 0
    if "--render" not in argv:
        from indicator_lab import meta
        final = meta.export_final()
        with open(FINAL, "w") as fh:
            json.dump(final, fh, indent=1)
        yearly = meta.export_yearly() if hasattr(meta, "export_yearly") else None
        if yearly:
            with open(YEARLY, "w") as fh:
                json.dump(yearly, fh, indent=1)
    out = render()  # renders every file before writing any
    write(out)
    print(f"regenerated {FILES}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
