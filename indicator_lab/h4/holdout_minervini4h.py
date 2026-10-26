"""ONE-SHOT holdout test of the best pro method from development: P1 Minervini trend template + VCP breakout on 4H bars
(indicator_lab/h4/pro_concepts.py, unchanged, no market filter), on the NASDAQ stocks of the sealed Swing 20/21 random
ticker holdout (never used by any test before this one).

    python -m indicator_lab.h4.holdout_minervini4h

Declared before the run (commit before the data were looked at):
  * Same window as the development run: 2024-07-03 .. 2026-10-23 (4H bars, Yahoo 60m grouped), same rules, costs,
    liquidity floor, one BUY per stock per two weeks, account of at most 10 positions of 10%, idle cash 0%, mean of 10
    random orders. RS rank is taken within the holdout stocks.
  * PASS = account Sharpe > SPY buy & hold Sharpe over the same window AND CAGR >= SPY CAGR.
    (Development: 15.3% CAGR, Sharpe 0.76 vs SPY 16.5%, 1.02 -> it already failed this on development.)
  * Also reported, not a pass: whether it holds its development level (CAGR >= 10% and Sharpe >= 0.5).
  * Only P1 is evaluated; no other rule, parameter or variant is looked at on these stocks. A marker file blocks reruns.
Caveat: this holdout is new STOCKS over the SAME period (a cross-sectional holdout), not a new time period.
"""
from __future__ import annotations

import json
import os

os.environ["PRO_TF"] = "4h"
import pandas as pd

from indicator_lab import ind
from indicator_lab.evaluate import get
from indicator_lab.h4 import classics as C
from indicator_lab.h4 import pro_concepts as PC
from indicator_lab.h4.nasdaq_list import nasdaq
from indicator_lab.h4.test4h import bars4h, download
from indicator_lab.metrics import equity_stats
from indicator_lab.swing4 import sim2 as S2
from indicator_lab.twenty import data20

START, END = pd.Timestamp("2024-07-03 09:30"), pd.Timestamp("2026-10-23 13:30")
NAME = "P1 Minervini trend template + VCP-breakout"
MARK = os.path.join(os.path.dirname(__file__), "holdout_minervini4h_used.json")


def main():
    if os.path.exists(MARK):
        raise SystemExit(f"holdout already used: {MARK}")
    univ = nasdaq(data20.H_TICKERS)
    download(univ)
    fr = {}
    for t in univ:
        df = bars4h(t)
        if df is not None and len(df) >= 400:
            fr[t] = df[(df[["open", "high", "low", "close"]] > 0).all(axis=1)]
    with open(MARK, "w") as fh:
        json.dump({"tickers": sorted(fr), "used": pd.Timestamp.now().isoformat()}, fh)
    rs = PC.rs_rank(fr)
    res = {}
    for t, df in fr.items():
        liquid = ((df["close"] >= 5) & ((df["close"] * df["volume"]).rolling(50).mean() >= 2.5e6)).to_numpy()
        inwin = (df.index >= START) & (df.index <= END)
        e, x, stop, spct = PC.signals(df, rs[t].reindex(df.index).to_numpy())[NAME]
        pol = S2.Policy(trail=1e6, stop=stop, stop_pct=spct, min_gap_days=14)
        r, tr = S2.simulate(S2.arrays(df, ind.atr(df, 14).to_numpy(), x), e & liquid & inwin, pol, slip=C.SLIP)
        for z in tr:
            z["ticker"] = t
        rr = pd.Series(r, index=df.index)
        res[t] = (rr[(rr.index >= START) & (rr.index <= END)], tr)
    row = C.summary(NAME + " (holdout)", res)
    spy = get("SPY")["close"].pct_change()
    spy = spy[(spy.index >= START.normalize()) & (spy.index <= END)].fillna(0)
    s = equity_stats(spy)
    cagr, sh = float(row["CAGR (10 pos.)"].rstrip("%")) / 100, float(row["Sharpe"])
    passed = sh > s["sharpe"] and cagr >= s["cagr"]
    holds = cagr >= 0.10 and sh >= 0.5
    rows = [{"strategie": NAME + " (ontwikkeling, 1795 aandelen)", "trades": 519, "winrate": "30%", "gem. trade": "0.99%",
             "CAGR (10 pos.)": "15.3%", "max DD": "-18.7%", "Sharpe": "0.76"}, row,
            {"strategie": "SPY kopen en vasthouden", "CAGR (10 pos.)": f"{s['cagr'] * 100:.1f}%",
             "max DD": f"{s['maxdd'] * 100:.1f}%", "Sharpe": f"{s['sharpe']:.2f}"}]
    txt = (f"# Holdout-test Minervini 4H ({len(fr)} nooit gebruikte NASDAQ-aandelen, {START.date()} .. {END.date()})\n\n"
           + pd.DataFrame(rows).fillna("–").to_markdown(index=False)
           + f"\n\n**Vooraf vastgelegd criterium (Sharpe > SPY én CAGR >= SPY): {'GESLAAGD' if passed else 'NIET GESLAAGD'}.**"
           f"\n\nHoudt ontwikkelniveau vast (CAGR >= 10% en Sharpe >= 0,5): {'ja' if holds else 'nee'}.\n\n"
           "Let op: nieuwe aandelen, maar dezelfde periode (geen nieuwe tijdsperiode). Deze holdout is nu gebruikt.\n")
    with open(os.path.join(C.OUT, "holdout_minervini4h.md"), "w") as fh:
        fh.write(txt)
    print(txt)


if __name__ == "__main__":
    main()
