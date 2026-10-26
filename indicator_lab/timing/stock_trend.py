"""Does the SMA200 trend rule also protect a SINGLE stock? Hold a stock only while it closes above its own SMA200
(optionally also requiring SPY > SMA200), else T-bills, against holding the stock.

    python -m indicator_lab.timing.stock_trend      # ONE run (marker file blocks reruns)

Stocks: the 468 NYSE / NYSE American stocks of the Swing 20/21 ticker holdout (their daily prices were used once
before, for the post-earnings drift confirmation, a different rule; disclosed). Each stock from its 250th bar or
2013-01-02, whichever is later, to 2026-10-23; only stocks with >= 3 years in that window. Mechanics exactly as
regime.py T1 (decided on the close, traded on the next close, 0.1% per switch, cash at the T-bill rate).
Fixed before the run. PASS = the median max drawdown of the rule is <= 0.75 x the median of holding AND the rule has
the higher MAR on >= 60% of the stocks. Also reported: equal-weight portfolios of all stocks under each rule.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

from indicator_lab.earnings_drift import confirm as CF
from indicator_lab.timing import allocation as A
from indicator_lab.timing import regime as R
from indicator_lab.twenty import data20

MARK = os.path.join(R.HERE, "stock_trend_used.json")
START, END = pd.Timestamp("2013-01-02"), pd.Timestamp("2026-10-23")


def main():
    if os.path.exists(MARK):
        raise SystemExit("already run")
    with open(MARK, "w") as fh:
        json.dump({"used": pd.Timestamp.now().isoformat()}, fh)
    data20.final_mode()
    spy = R.load("SPY")
    rf_all = A.rf_series(spy.index)
    spy_on = pd.Series(R.weights(spy, rf_all)["T1 SMA200"], index=spy.index)
    per, rets = [], {"kopen en vasthouden": {}, "aandeel > SMA200": {}, "aandeel > SMA200 en SPY > SMA200": {}}
    for t in CF.universe():
        d = data20.load(t)
        if d is None:
            continue
        c = d["close"][(d["close"] > 0)]
        c = c[c.index <= END]
        if len(c) < 260:
            continue
        rf = rf_all.reindex(c.index).fillna(0)
        w1 = R.weights(c, rf)["T1 SMA200"]
        w2 = w1 * spy_on.reindex(c.index).fillna(0).to_numpy()
        seg = (np.arange(len(c)) >= 250) & (c.index >= START)
        if seg.sum() < 3 * 252:
            continue
        r_bh = c.pct_change().fillna(0)
        series = {"kopen en vasthouden": r_bh[seg], "aandeel > SMA200": R.simulate(c, rf, w1)[seg],
                  "aandeel > SMA200 en SPY > SMA200": R.simulate(c, rf, w2)[seg]}
        st = {k: R.stats(v, rf[seg]) for k, v in series.items()}
        per.append({"ticker": t, **{f"{k}|{m}": st[k][m] for k in st for m in ("cagr", "maxdd", "mar")}})
        for k, v in series.items():
            rets[k][t] = v
    P = pd.DataFrame(per)
    names = list(rets)
    rows = []
    for k in names:
        rows.append({"regel": k, "aandelen": len(P), "mediaan CAGR": f"{P[f'{k}|cagr'].median() * 100:.1f}%",
                     "mediaan max DD": f"{P[f'{k}|maxdd'].median() * 100:.0f}%",
                     "hogere MAR dan vasthouden": "–" if k == names[0] else
                     f"{(P[f'{k}|mar'] > P[f'{names[0]}|mar']).mean() * 100:.0f}% van de aandelen"})
    verdict = []
    for k in names[1:]:
        ratio = P[f"{k}|maxdd"].median() / P[f"{names[0]}|maxdd"].median()
        share = (P[f"{k}|mar"] > P[f"{names[0]}|mar"]).mean()
        verdict.append(f"- **{k}: {'GESLAAGD' if ratio <= 0.75 and share >= 0.6 else 'NIET GESLAAGD'}** (mediane max "
                       f"daling {ratio:.2f} x die van vasthouden; hogere MAR op {share * 100:.0f}% van de aandelen)")
    port = []
    rf_p = rf_all[(rf_all.index >= START) & (rf_all.index <= END)]
    for k in names:
        ew = pd.concat(rets[k], axis=1).mean(axis=1).fillna(0)
        s = R.stats(ew, rf_p.reindex(ew.index).fillna(0))
        port.append({"gelijk gewogen portefeuille": k, "CAGR": f"{s['cagr'] * 100:.1f}%", "max DD": f"{s['maxdd'] * 100:.1f}%",
                     "MAR": f"{s['mar']:.2f}", "Sharpe": f"{s['sharpe']:.2f}"})
    sp = R.stats(spy.pct_change().fillna(0)[(spy.index >= START) & (spy.index <= END)], rf_p)
    port.append({"gelijk gewogen portefeuille": "SPY kopen en vasthouden", "CAGR": f"{sp['cagr'] * 100:.1f}%",
                 "max DD": f"{sp['maxdd'] * 100:.1f}%", "MAR": f"{sp['mar']:.2f}", "Sharpe": f"{sp['sharpe']:.2f}"})
    txt = (f"# Trendregel per aandeel ({len(P)} NYSE/AMEX-aandelen, {START.date()} .. {END.date()})\n\n"
           "Criterium (vooraf): mediane max daling <= 0,75 x vasthouden én hogere MAR op >= 60% van de aandelen.\n\n"
           + "\n".join(verdict) + "\n\n## Per aandeel\n\n" + pd.DataFrame(rows).to_markdown(index=False)
           + "\n\n## Portefeuille van alle aandelen\n\n" + pd.DataFrame(port).to_markdown(index=False) + "\n")
    with open(os.path.join(R.OUT, "stock_trend.md"), "w") as fh:
        fh.write(txt)
    print(txt)


if __name__ == "__main__":
    main()
