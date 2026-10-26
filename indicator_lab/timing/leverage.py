"""Leverage only in an uptrend (Gayed & Bilello 2016, "Leverage for the long run"): 2x the index while it closes above
its SMA200, cash below it, against buy & hold 1x.

    python -m indicator_lab.timing.leverage         # ONE run (marker file blocks reruns)

Decided before these data were looked at:
  * Primary test, never used by this project: ^GSPC (price index, no dividends) 1929-10-21 .. 1959-12-31 (the first
    200 bars of 1928/29 are SMA warm-up).
  * Rule L2: exposure 2 while T1 (regime.py) is on, else 0; decided on a close, traded on the next close, 0.1% cost per
    unit of exposure changed; the borrowed 1x pays 3% a year plus 1% a year for a daily-reset 2x product (conservative:
    T-bill rates were 0-3% in this period); cash earns 0%.
  * PASS = L2 CAGR > buy & hold CAGR AND L2 max drawdown no deeper than buy & hold's.
  * Also reported, not judged: T1 1x and 2x buy & hold on the same period, and L2 on the 12 foreign indices of
    confirm.py (data already used for T1, so only descriptive).
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

from indicator_lab.timing import confirm as CF
from indicator_lab.timing import regime as R

PRIMARY = ("_GSPC", "1929-10-21", "1959-12-31")
BORROW, PRODUCT = 0.03, 0.01
MARK = os.path.join(R.HERE, "leverage_used.json")


def run(c: pd.Series, w_dec: np.ndarray, lev: float) -> pd.Series:
    r = c.pct_change().fillna(0).to_numpy()
    w = np.r_[0.0, 0.0, w_dec[:-2]] * lev
    dw = np.abs(np.diff(np.r_[0.0, w]))
    carry = np.maximum(w - 1, 0) * BORROW / 252 + (w > 1) * PRODUCT / 252
    return pd.Series(w * r - carry - dw * R.COST, index=c.index)


def row(name, r, rf) -> dict:
    s = R.stats(r, rf)
    return {"variant": name, "CAGR": f"{s['cagr'] * 100:.1f}%", "max DD": f"{s['maxdd'] * 100:.1f}%",
            "MAR": f"{s['mar']:.2f}", "Sharpe (kas 0%)": f"{s['sharpe']:.2f}", "_s": s}


def table(rows) -> str:
    return pd.DataFrame([{k: v for k, v in x.items() if k != "_s"} for x in rows]).to_markdown(index=False)


def main():
    if os.path.exists(MARK):
        raise SystemExit("leverage test already run")
    with open(MARK, "w") as fh:
        json.dump({"used": pd.Timestamp.now().isoformat()}, fh)
    c = R.load(PRIMARY[0])
    c = c[c.index <= PRIMARY[2]]
    rf = pd.Series(0.0, index=c.index)
    t1 = R.weights(c, rf)["T1 SMA200"]
    m = (c.index >= PRIMARY[1]) & (c.index <= PRIMARY[2])
    ones = np.ones(len(c))
    rows = [row("kopen en vasthouden 1x", c.pct_change().fillna(0)[m], rf[m]),
            row("L2: 2x boven SMA200, anders cash", run(c, t1, 2.0)[m], rf[m]),
            row("T1: 1x boven SMA200, anders cash", run(c, t1, 1.0)[m], rf[m]),
            row("2x altijd (zonder filter)", run(c, ones, 2.0)[m], rf[m])]
    bh, l2 = rows[0]["_s"], rows[1]["_s"]
    passed = l2["cagr"] > bh["cagr"] and l2["maxdd"] >= bh["maxdd"]
    parts = []
    for n in CF.NAMES:
        x = R.load(n)
        x = x[x.index <= CF.END]
        rx = pd.Series(0.0, index=x.index)
        seg = np.arange(len(x)) >= 300
        w = R.weights(x, rx)["T1 SMA200"]
        b, lv = R.stats(x.pct_change().fillna(0)[seg], rx[seg]), R.stats(run(x, w, 2.0)[seg], rx[seg])
        parts.append({"index": n.replace("_", "^"), "B&H CAGR": f"{b['cagr'] * 100:.1f}%", "B&H max DD": f"{b['maxdd'] * 100:.0f}%",
                      "L2 CAGR": f"{lv['cagr'] * 100:.1f}%", "L2 max DD": f"{lv['maxdd'] * 100:.0f}%",
                      "L2 beter (CAGR hoger, DD niet dieper)": "ja" if lv["cagr"] > b["cagr"] and lv["maxdd"] >= b["maxdd"] else "nee"})
    txt = (f"# Hefboom alleen in een uptrend — eenmalige test\n\n## S&P 500 {PRIMARY[1]} .. {PRIMARY[2]} (nooit gebruikt)\n\n"
           + table(rows) + f"\n\n**Vooraf vastgelegd criterium (CAGR hoger én max daling niet dieper dan kopen en "
           f"vasthouden): {'GESLAAGD' if passed else 'NIET GESLAAGD'}.**\n\nKosten: 3%/jaar rente op het geleende deel + "
           "1%/jaar productkosten, 0,1% per wissel per eenheid, kas 0%, prijsindex zonder dividend.\n\n"
           "## Beschrijvend (data al gebruikt voor T1): 12 buitenlandse indexen\n\n"
           + pd.DataFrame(parts).to_markdown(index=False) + "\n")
    with open(os.path.join(R.OUT, "leverage.md"), "w") as fh:
        fh.write(txt)
    print(txt)


if __name__ == "__main__":
    main()
