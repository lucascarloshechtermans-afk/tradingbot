"""Do trades taken at the support levels of sr.py reach their target on SPY? (daily bars, long only)

    python -m indicator_lab.spy_levels      # results/spy_levels.md (Yahoo SPY, adjusted; or DATA_DIR/SPY_max.pkl)

Rules (fixed before the run):
  * Levels from indicator_lab/sr.py (point in time). Support zone = [sup_lo, sup + (sup - sup_lo)] with strength >= 2.
  * SIGNAL on day t: the lowest low of t-2..t reaches the zone top and the close of t is above it (support held).
  * Entry: open of t+1. TARGET = the nearest resistance above the close of t (sr.py `res`); skipped if missing or not
    above the fill. STOP = below the support zone (mfe.std_stop: zone bottom - 0.25 ATR, at least 1 ATR, at most 8%).
    Max 60 trading days, then out at the close. Same bar: stop first; gaps fill at the open. Costs 0.1% per side.
  * Measured: % target first, % stop first, % time exit, winrate, average return, average R (return / stop distance),
    and the BREAK-EVEN hit rate (stop distance / (stop + target distance)).
  * Control: EVERY SPY day with the same target/stop construction (its own nearest resistance and support), so the
    question is whether "at support" beats "any day". Periods 1995-2014 and 2015-2026.
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from indicator_lab import sr
from indicator_lab.week import mfe as M
from indicator_lab.xom_donchian import load

OUT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "results", "spy_levels.md")
COST = 0.001
HOLD = 60


def run(df, lv, days):
    o, h, lo, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    a, res, slo = (lv[k].to_numpy() for k in ("atr", "res", "sup_lo"))
    out = []
    for t in days:
        d = t + 1
        if d + HOLD > len(c) or not np.isfinite(a[t]):
            continue
        fill = o[d]
        tgt = res[t]
        if not (np.isfinite(tgt) and tgt > fill * 1.002):
            continue
        stop = M.std_stop(fill, slo[t] if np.isfinite(slo[t]) else np.nan, a[t])
        kind, px, bars = "tijd", c[d + HOLD - 1], HOLD
        for k in range(HOLD):
            i = d + k
            op = fill if k == 0 else o[i]
            if lo[i] <= stop:
                kind, px, bars = "stop", (stop if k == 0 else min(op, stop)), k + 1
                break
            if h[i] >= tgt:
                kind, px, bars = "doel", (tgt if k == 0 else max(op, tgt)), k + 1
                break
        r = px * (1 - COST) / (fill * (1 + COST)) - 1
        risk = 1 - stop / fill
        out.append({"day": df.index[t], "kind": kind, "ret": r, "R": r / risk, "bars": bars,
                    "be": risk / (risk + tgt / fill - 1)})
    return pd.DataFrame(out)


def summary(d, name):
    if len(d) == 0:
        return {"variant": name, "trades": 0}
    return {"variant": name, "trades": len(d), "doel geraakt": f"{(d.kind == 'doel').mean() * 100:.0f}%",
            "stop geraakt": f"{(d.kind == 'stop').mean() * 100:.0f}%", "tijd (60 d)": f"{(d.kind == 'tijd').mean() * 100:.0f}%",
            "break-even %": f"{d.be.mean() * 100:.0f}%", "winrate": f"{(d.ret > 0).mean() * 100:.0f}%",
            "gem./trade": f"{d.ret.mean() * 100:+.2f}%", "gem. R": f"{d.R.mean():+.2f}", "gem. dagen": f"{d.bars.mean():.0f}"}


def main():
    df = load("SPY")
    lv = sr.levels(df)
    lo, c = df["low"].to_numpy(float), df["close"].to_numpy(float)
    sup, slo, st = lv["sup"].to_numpy(), lv["sup_lo"].to_numpy(), lv["sup_str"].to_numpy()
    top = 2 * sup - slo
    with np.errstate(invalid="ignore"):
        sig = (st >= 2) & (pd.Series(lo).rolling(3).min().to_numpy() <= top) & (c > top)
    idx = df.index
    rows = []
    for a, b in (("1995-01-01", "2014-12-31"), ("2015-01-01", "2026-12-31")):
        per = (idx >= a) & (idx <= b)
        s = run(df, lv, np.where(sig & per)[0])
        allr = run(df, lv, np.where(per & (np.arange(len(idx)) > 300))[0])
        rows += [{"periode": f"{a[:4]}-{b[:4]}", **summary(s, "aan support (signaal)")},
                 {"periode": f"{a[:4]}-{b[:4]}", **summary(allr, "elke dag (controle)")}]
    txt = ("# SPY: raken trades vanaf de support-levels hun doel?\n\n<!-- CONCLUSIE -->\n\n"
           f"Regels: docstring van `indicator_lab/spy_levels.py` (vooraf gecommit). Data SPY {idx[0].date()} .. {idx[-1].date()} "
           "(gecorrigeerd voor dividend). Doel = eerstvolgende weerstand, stop onder de support-zone (max 8%), max 60 dagen, "
           "kosten 0,1% per kant. Break-even % = hoe vaak het doel minstens geraakt moet worden om quitte te spelen.\n\n"
           + pd.DataFrame(rows).fillna("").to_markdown(index=False) + "\n")
    with open(OUT, "w") as fh:
        fh.write(txt)
    print(txt)


if __name__ == "__main__":
    main()
