"""Published multi-asset trend rules, tested ONLY on the years after their publication (true out of sample: the
authors could not have seen them).

    python -m indicator_lab.timing.allocation      # ONE run (marker file blocks reruns)

Fixed before the run, exactly as published (ETF proxies as in the sources):
  GTAA5  Faber (2007, "A Quantitative Approach to Tactical Asset Allocation"): 20% each in SPY, EFA, IEF, VNQ, DBC;
         each sleeve held only while its month-end close > its 10-month SMA of month-end closes, else that 20% in
         T-bills; checked at month end.                               Out of sample: 2008-01-02 .. 2026-10-23
  GEM    Antonacci (2014, "Dual Momentum Investing"): at month end, if SPY's 12-month return beats T-bills', hold the
         better of SPY and EFA (12-month return), else hold AGG.      Out of sample: 2014-01-02 .. 2026-10-23
Execution: decided on the month-end close, traded on the next close; 0.1% per unit of weight changed; cash earns the
13-week T-bill rate. Benchmarks: SPY buy & hold, 60/40 SPY/AGG rebalanced monthly, SPY-only SMA200 rule (T1), and for
GTAA5 the same five ETFs bought and held in equal weight (rebalanced monthly).
PASS per rule = Sharpe (excess) AND MAR above SPY buy & hold over its out-of-sample window.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

from indicator_lab.timing import regime as R

MARK = os.path.join(R.HERE, "allocation_used.json")
END = "2026-10-23"


def closes(names) -> pd.DataFrame:
    return pd.concat({n: R.load(n) for n in names}, axis=1).dropna()


def rf_series(idx) -> pd.Series:
    irx = R.load("_IRX")
    return (irx.reindex(idx).ffill() / 100 / 252).shift(1).fillna(0)


def simulate(px: pd.DataFrame, w_dec: pd.DataFrame, rf: pd.Series) -> pd.Series:
    """w_dec: weights decided on each close (rows sum <= 1, rest in T-bills)."""
    r = px.pct_change().fillna(0)
    w = w_dec.shift(2).fillna(0)
    cash = 1 - w.sum(axis=1)
    cost = w.diff().abs().sum(axis=1).fillna(0) * R.COST
    return (w * r).sum(axis=1) + cash * rf - cost


def month_end_hold(sig: pd.DataFrame) -> pd.DataFrame:
    me = R.month_end(sig.index)
    out = sig.where(pd.Series(me, index=sig.index), np.nan)
    return out.ffill().fillna(0)


def gtaa5(px: pd.DataFrame) -> pd.DataFrame:
    me = R.month_end(px.index)
    mc = px[me]
    sma10 = mc.rolling(10).mean()
    on = (mc > sma10).astype(float) * 0.2
    return on.reindex(px.index).ffill().fillna(0)


def gem(px: pd.DataFrame, rf: pd.Series) -> pd.DataFrame:
    r12 = px / px.shift(252) - 1
    rf12 = (1 + rf).rolling(252).apply(np.prod, raw=True) - 1
    w = pd.DataFrame(0.0, index=px.index, columns=px.columns)
    risk_on = r12["SPY"] > rf12
    pick_spy = r12["SPY"] >= r12["EFA"]
    w.loc[risk_on & pick_spy, "SPY"] = 1.0
    w.loc[risk_on & ~pick_spy, "EFA"] = 1.0
    w.loc[~risk_on & r12["SPY"].notna(), "AGG"] = 1.0
    return month_end_hold(w)


def fixed(px: pd.DataFrame, weights: dict) -> pd.DataFrame:
    w = pd.DataFrame(0.0, index=px.index, columns=px.columns)
    for k, v in weights.items():
        w[k] = v
    return month_end_hold(w)


def stats(r: pd.Series, rf: pd.Series) -> dict:
    return R.stats(r, rf)


def block(title, px, rules: dict, start, rf) -> tuple[str, dict]:
    m = (px.index >= start) & (px.index <= END)
    spy_t1 = R.weights(px["SPY"], rf)["T1 SMA200"]
    res = {k: stats(simulate(px, w, rf)[m], rf[m]) for k, w in rules.items()}
    res["SPY kopen en vasthouden"] = stats(px["SPY"].pct_change().fillna(0)[m], rf[m])
    res["60/40 SPY/AGG"] = stats(simulate(px, fixed(px, {"SPY": 0.6, "AGG": 0.4}), rf)[m], rf[m])
    res["SPY alleen boven SMA200 (T1)"] = stats(R.simulate(px["SPY"], rf, spy_t1)[m], rf[m])
    rows = [{"regel": k, "CAGR": f"{s['cagr'] * 100:.1f}%", "max DD": f"{s['maxdd'] * 100:.1f}%", "MAR": f"{s['mar']:.2f}",
             "Sharpe": f"{s['sharpe']:.2f}"} for k, s in res.items()]
    return f"## {title} — {pd.Timestamp(start).date()} .. {END}\n\n" + pd.DataFrame(rows).to_markdown(index=False) + "\n", res


def main():
    if os.path.exists(MARK):
        raise SystemExit("already run")
    with open(MARK, "w") as fh:
        json.dump({"used": pd.Timestamp.now().isoformat()}, fh)
    px = closes(["SPY", "EFA", "IEF", "VNQ", "DBC", "AGG"])
    px = px[px.index <= END]
    rf = rf_series(px.index)
    g5 = gtaa5(px[["SPY", "EFA", "IEF", "VNQ", "DBC"]]).reindex(columns=px.columns, fill_value=0.0)
    ew5 = fixed(px, dict.fromkeys(["SPY", "EFA", "IEF", "VNQ", "DBC"], 0.2))
    t1, r1 = block("GTAA5 (Faber 2007)", px, {"GTAA5 trend": g5, "dezelfde 5 ETF's kopen en vasthouden": ew5}, "2008-01-02", rf)
    t2, r2 = block("Dual Momentum GEM (Antonacci 2014)", px, {"GEM": gem(px, rf)}, "2014-01-02", rf)
    verdict = []
    for name, res, key in (("GTAA5", r1, "GTAA5 trend"), ("GEM", r2, "GEM")):
        s, b = res[key], res["SPY kopen en vasthouden"]
        ok = s["sharpe"] > b["sharpe"] and s["mar"] > b["mar"]
        verdict.append(f"- **{name}: {'GESLAAGD' if ok else 'NIET GESLAAGD'}** (Sharpe {s['sharpe']:.2f} vs SPY "
                       f"{b['sharpe']:.2f}, MAR {s['mar']:.2f} vs {b['mar']:.2f})")
    txt = ("# Gepubliceerde trendregels over meerdere beleggingscategorieën — alleen de jaren na publicatie\n\n"
           "Criterium (vooraf): Sharpe én MAR boven SPY kopen en vasthouden.\n\n" + "\n".join(verdict) + "\n\n" + t1 + "\n" + t2)
    with open(os.path.join(R.OUT, "allocation.md"), "w") as fh:
        fh.write(txt)
    print(txt)


if __name__ == "__main__":
    main()
