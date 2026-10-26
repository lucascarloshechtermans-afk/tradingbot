"""Faber (2010), "Relative Strength Strategies for Investing" (data to December 2009), tested only on 2010-2026.

    python -m indicator_lab.timing.sectors      # ONE run (marker file blocks reruns)

Rules as published, on the 9 original SPDR sector ETFs (XLB XLE XLF XLI XLK XLP XLU XLV XLY) instead of the 10
French-Fama industries: at each month end rank the sectors by the average of their 1, 3, 6, 9 and 12-month total
returns; hold the top 3 in equal weight until the next month end.
  S3   top 3                                  S3H  top 3 only while SPY's month-end close > its 10-month SMA, else T-bills
Execution as in allocation.py (decided on the month-end close, traded on the next close, 0.1% per unit of weight
changed, cash at the T-bill rate). Fixed before the run. PASS = Sharpe AND MAR above SPY buy & hold over
2010-01-04 .. 2026-10-23. Also shown: the 9 sectors in equal weight, and the SPY-only SMA200 rule (T1).
"""
from __future__ import annotations

import json
import os

import pandas as pd

from indicator_lab.timing import allocation as A
from indicator_lab.timing import regime as R

SECT = ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"]
START = "2010-01-04"
MARK = os.path.join(R.HERE, "sectors_used.json")


def top3(px: pd.DataFrame, hedge: bool) -> pd.DataFrame:
    me = R.month_end(px.index)
    mc = px[me]
    score = sum(mc[SECT] / mc[SECT].shift(k) - 1 for k in (1, 3, 6, 9, 12)) / 5
    w = pd.DataFrame(0.0, index=mc.index, columns=px.columns)
    ok = score.notna().all(axis=1)
    for d in mc.index[ok]:
        best = score.loc[d].nlargest(3).index
        w.loc[d, best] = 1 / 3
    if hedge:
        up = mc["SPY"] > mc["SPY"].rolling(10).mean()
        w = w.mul(up.astype(float), axis=0)
    return w.reindex(px.index).ffill().fillna(0)


def main():
    if os.path.exists(MARK):
        raise SystemExit("already run")
    with open(MARK, "w") as fh:
        json.dump({"used": pd.Timestamp.now().isoformat()}, fh)
    px = A.closes(["SPY", "AGG", *SECT])
    px = px[px.index <= A.END]
    rf = A.rf_series(px.index)
    m = (px.index >= START) & (px.index <= A.END)
    rules = {"S3 top 3 sectoren": top3(px, False), "S3H top 3, alleen SPY > 10-maands SMA": top3(px, True),
             "9 sectoren gelijk gewogen": A.fixed(px, dict.fromkeys(SECT, 1 / 9))}
    res = {k: R.stats(A.simulate(px, w, rf)[m], rf[m]) for k, w in rules.items()}
    res["SPY kopen en vasthouden"] = R.stats(px["SPY"].pct_change().fillna(0)[m], rf[m])
    res["SPY alleen boven SMA200 (T1)"] = R.stats(R.simulate(px["SPY"], rf, R.weights(px["SPY"], rf)["T1 SMA200"])[m], rf[m])
    b = res["SPY kopen en vasthouden"]
    lines = []
    for k in ("S3 top 3 sectoren", "S3H top 3, alleen SPY > 10-maands SMA"):
        s = res[k]
        ok = s["sharpe"] > b["sharpe"] and s["mar"] > b["mar"]
        lines.append(f"- **{k}: {'GESLAAGD' if ok else 'NIET GESLAAGD'}** (Sharpe {s['sharpe']:.2f} vs {b['sharpe']:.2f}, "
                     f"MAR {s['mar']:.2f} vs {b['mar']:.2f})")
    rows = [{"regel": k, "CAGR": f"{s['cagr'] * 100:.1f}%", "max DD": f"{s['maxdd'] * 100:.1f}%", "MAR": f"{s['mar']:.2f}",
             "Sharpe": f"{s['sharpe']:.2f}"} for k, s in res.items()]
    txt = (f"# Sectorrotatie op relatieve sterkte (Faber 2010) — alleen na publicatie, {START} .. {A.END}\n\n"
           + "\n".join(lines) + "\n\n" + pd.DataFrame(rows).to_markdown(index=False) + "\n")
    with open(os.path.join(R.OUT, "sectors.md"), "w") as fh:
        fh.write(txt)
    print(txt)


if __name__ == "__main__":
    main()
