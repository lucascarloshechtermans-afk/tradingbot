"""Low-volatility anomaly (Blitz & van Vliet 2007; Frazzini & Pedersen 2014 "Betting against beta"): the calmest liquid
stocks, tested on the years after publication.

    python -m indicator_lab.rotation.lowvol        # ONE run (marker file blocks reruns)

Stocks: all 1348 tickers of the sealed Swing 20/21 random holdout (all US exchanges; their daily prices were used
before for other rules: PEAD confirmation and the per-stock trend rule on the NYSE part; disclosed).
Fixed before the run (nothing tuned):
  * Every 21 trading days pick the 30 stocks with the lowest 252-day volatility of daily returns among the eligible:
    close >= $5, 50-day average dollar volume >= $20M, traded on each of the last 50 days, >= 253 days of history.
  * Equal weight, fills at the next open, 0.1% per side + 0.1% slippage on buys (mechanics of rotation/mom.py).
  * Window 2014-01-02 .. 2026-10-22.
  * PASS = Sharpe (excess) AND MAR above SPY buy & hold. Also shown: all eligible stocks equal weight (same monthly
    rebalance and costs) and the 30 MOST volatile stocks (the other side of the anomaly).
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

from indicator_lab.rotation import mom
from indicator_lab.timing import allocation as A
from indicator_lab.timing import regime as R
from indicator_lab.twenty import data20

HERE = os.path.dirname(__file__)
MARK = os.path.join(HERE, "lowvol_used.json")
START, END = pd.Timestamp("2014-01-02"), pd.Timestamp("2026-10-22")
N = 30


def main():
    if os.path.exists(MARK):
        raise SystemExit("already run")
    with open(MARK, "w") as fh:
        json.dump({"used": pd.Timestamp.now().isoformat()}, fh)
    data20.final_mode()
    fr = {}
    for t in sorted(data20.H_TICKERS):
        d = data20.load(t)
        if d is not None and len(d) > 300:
            fr[t] = d[(d[["open", "high", "low", "close"]] > 0).all(axis=1)]
    spy = R.load("SPY")
    cal = spy.index[(spy.index >= pd.Timestamp("2012-01-03")) & (spy.index <= END)]
    M = mom.matrices(fr, cal)
    V = pd.concat({t: d["volume"] for t, d in fr.items()}, axis=1).reindex(cal)
    traded = (V > 0).astype(float).rolling(50).min() == 1
    dv = (M["C"] * V).rolling(50, min_periods=40).mean()
    M["elig"] = M["elig"] & traded & (dv >= 20e6)
    vol = M["C"].pct_change(fill_method=None).rolling(252, min_periods=200).std()
    mom.EVERY = 21
    mkt = pd.DataFrame({"rf": A.rf_series(cal), "on": 1.0, "spy": spy.pct_change().reindex(cal).fillna(0)}, index=cal)
    out = {}
    out["30 rustigste aandelen"] = mom.backtest(M, -vol, N, False, mkt, START, END)
    out["30 onrustigste aandelen"] = mom.backtest(M, vol, N, False, mkt, START, END)
    n_all = int(M["elig"].sum(axis=1).max())
    flat = pd.DataFrame(0.0, index=cal, columns=M["C"].columns)   # equal score: every eligible stock is picked
    out["alle geschikte aandelen, gelijk gewogen"] = mom.backtest(M, flat, n_all, False, mkt, START, END)
    rows = []
    for k, bt in out.items():
        s = mom.stats(bt["ret"], mkt)
        rows.append({"portefeuille": k, "CAGR": f"{s['cagr'] * 100:.1f}%", "max DD": f"{s['maxdd'] * 100:.1f}%",
                     "MAR": f"{s['mar']:.2f}", "Sharpe": f"{s['sharpe_rf']:.2f}",
                     "volatiliteit/jaar": f"{bt['ret'].std() * np.sqrt(252) * 100:.0f}%", "_s": s})
    sp_r = spy.pct_change().fillna(0)[(spy.index >= START) & (spy.index <= END)]
    sp = mom.stats(sp_r, mkt)
    rows.append({"portefeuille": "SPY kopen en vasthouden", "CAGR": f"{sp['cagr'] * 100:.1f}%", "max DD": f"{sp['maxdd'] * 100:.1f}%",
                 "MAR": f"{sp['mar']:.2f}", "Sharpe": f"{sp['sharpe_rf']:.2f}",
                 "volatiliteit/jaar": f"{sp_r.std() * np.sqrt(252) * 100:.0f}%", "_s": sp})
    lv = rows[0]["_s"]
    ok = lv["sharpe_rf"] > sp["sharpe_rf"] and lv["mar"] > sp["mar"]
    for r in rows:
        r.pop("_s")
    txt = (f"# Lage-volatiliteitsanomalie ({len(fr)} holdout-aandelen, {START.date()} .. {END.date()})\n\n"
           f"Criterium (vooraf): Sharpe én MAR van de 30 rustigste aandelen boven SPY: **{'GESLAAGD' if ok else 'NIET GESLAAGD'}**"
           f" (Sharpe {lv['sharpe_rf']:.2f} vs {sp['sharpe_rf']:.2f}, MAR {lv['mar']:.2f} vs {sp['mar']:.2f}).\n\n"
           + pd.DataFrame(rows).to_markdown(index=False) + "\n")
    os.makedirs(mom.OUT, exist_ok=True)
    with open(os.path.join(mom.OUT, "lowvol.md"), "w") as fh:
        fh.write(txt)
    print(txt)


if __name__ == "__main__":
    main()
