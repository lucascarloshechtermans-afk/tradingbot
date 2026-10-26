"""Confirmation of the trend filter on markets this project has never used: 12 foreign stock indices.

    python -m indicator_lab.timing.confirm          # ONE run (marker file blocks reruns)

Why: in the timing holdout (reports/holdout.md) the pre-selected variant failed, but the plainest rule, T1 "long while
close > SMA200, else cash", beat buy & hold on MAR in all three long periods. That was seen after the fact, so it is not
evidence. This test is decided before these data were looked at (only download dates and row counts were seen):
  * Indices: ^GDAXI ^FTSE ^N225 ^HSI ^GSPTSE ^AXJO ^FCHI ^SSMI ^AEX ^BVSP ^KS11 ^TWII (Yahoo, price indices, no
    dividends), each from its 300th trading day (SMA warm-up) to 2026-10-22.
  * Rule T1 exactly as in regime.py (decided on a close, traded on the next close, 0.1% per switch). Cash earns 0%
    (local deposit rates are not available), for the rule and nowhere else; the benchmark is buy & hold of the index.
  * PASS = T1 has a higher MAR than buy & hold on at least 9 of the 12 indices AND the median max drawdown of T1 is at
    most 0.75 x the median max drawdown of buy & hold. T2 (2% band) and T3 (Faber monthly) are reported, not judged.
  * Data check reported, nothing removed: days with |return| > 20% per index.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

from indicator_lab.timing import regime as R

NAMES = ["_GDAXI", "_FTSE", "_N225", "_HSI", "_GSPTSE", "_AXJO", "_FCHI", "_SSMI", "_AEX", "_BVSP", "_KS11", "_TWII"]
END = "2026-10-22"
MARK = os.path.join(R.HERE, "confirm_used.json")


def main():
    if os.path.exists(MARK):
        raise SystemExit("confirmation already run")
    with open(MARK, "w") as fh:
        json.dump({"used": pd.Timestamp.now().isoformat()}, fh)
    rows, wins, dd_t1, dd_bh = [], 0, [], []
    for n in NAMES:
        c = R.load(n)
        c = c[c.index <= END]
        rf = pd.Series(0.0, index=c.index)
        ws = R.weights(c, rf)
        seg = np.arange(len(c)) >= 300
        r_bh = c.pct_change().fillna(0)[seg]
        bh = R.stats(r_bh, rf[seg])
        out = {"index": n.replace("_", "^"), "periode": f"{c.index[300].date()} .. {c.index[-1].date()}",
               "dagen |r|>20%": int((c.pct_change().abs() > 0.2).sum()),
               "B&H CAGR": f"{bh['cagr'] * 100:.1f}%", "B&H max DD": f"{bh['maxdd'] * 100:.0f}%", "B&H MAR": f"{bh['mar']:.2f}"}
        for k, short in (("T1 SMA200", "T1"), ("T2 SMA200 met 2%-band", "T2"), ("T3 Faber 10-maands SMA", "T3")):
            s = R.stats(R.simulate(c, rf, ws[k])[seg], rf[seg])
            out.update({f"{short} CAGR": f"{s['cagr'] * 100:.1f}%", f"{short} max DD": f"{s['maxdd'] * 100:.0f}%",
                        f"{short} MAR": f"{s['mar']:.2f}"})
            if short == "T1":
                win = s["mar"] > bh["mar"]
                wins += win
                dd_t1.append(s["maxdd"])
                dd_bh.append(bh["maxdd"])
                out["T1 beter"] = "ja" if win else "nee"
        rows.append(out)
        print(out, flush=True)
    ratio = float(np.median(dd_t1) / np.median(dd_bh))
    passed = wins >= 9 and ratio <= 0.75
    txt = ("# Bevestiging trendfilter (SMA200) op 12 buitenlandse beursindexen — eenmalig\n\n"
           f"T1 hogere MAR dan kopen en vasthouden op **{wins} van 12** indexen (nodig 9); mediane max daling T1 / "
           f"kopen-en-vasthouden = **{ratio:.2f}** (nodig <= 0,75): **{'GESLAAGD' if passed else 'NIET GESLAAGD'}**.\n\n"
           "Prijsindexen zonder dividend, kas levert 0% op (nadeel voor de regel), 1 dag vertraging, 0,1% per wissel.\n\n"
           + pd.DataFrame(rows).to_markdown(index=False) + "\n")
    with open(os.path.join(R.OUT, "confirm.md"), "w") as fh:
        fh.write(txt)
    print(txt)


if __name__ == "__main__":
    main()
