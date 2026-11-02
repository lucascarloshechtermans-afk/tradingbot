"""Swing v4.2 improvements (pre-registered in this docstring, committed before the run):
  I1 no model (rules + regime only; phase 1 showed the model adds nothing, AUC ~0.5)
  I2 compression: the day before the breakout the Bollinger band width is in the quietest 20% of the last 252 days
     (bbw_pct <= 0.20, the feature the model already uses; from results/vcb.md)
  I3 trend: SMA50 > SMA200 at the signal (from results/donchian_filters.md)
Each is added on top of I1; a filter is kept when, on the DEV cell (253 tickers, 2015-2024/10, costs 0.5%/side), the
portfolio MAR is higher than without it AND the expectancy per trade is at least as high. The holdout cells were already
seen (phase 3 and phase 1): they are only reported. The user's real plan (1% risk, max 10%, idle cash in SPY) is reported
for v4.1 and the final version.

    python -m indicator_lab.swing4.v42_improve       # indicator_lab/reports/v42_improve.md
"""
from __future__ import annotations

import os

import pandas as pd

from indicator_lab.swing4 import v42_phase1 as V  # installs the final data mode

L = V.L
OUT = os.path.join(os.path.dirname(V.OUT), "v42_improve.md")


def prep(ctx):
    for cx in ctx.values():
        c = pd.Series(cx["arr"]["c"])
        cx["t50"] = (c.rolling(50).mean() > c.rolling(200).mean()).to_numpy()
        bp = pd.Series(cx["x"]["bbw_pct"])
        cx["comp"] = (bp.shift(1) <= 0.20).to_numpy()


def ent(model=True, comp=False, t50=False):
    def e(cx):
        m = cx["cand"] & V.regime(cx)
        if model:
            m = m & (cx["p_v3"] >= cx["thr_v3"])
        if comp:
            m = m & cx["comp"]
        if t50:
            m = m & cx["t50"]
        return m
    return e


def main():
    ctx = L.load_ctx(univ=V.DEV + V.H, path=V.CTX)
    prep(ctx)
    dev_u, dev_p = V.CELLS["DEV (253, 2015-2024/10)"]
    base = ent(model=False)
    t0, p0, _ = V.measure(ctx, base, dev_u, dev_p)
    kept = {}
    sel = [V.fmt("I1 zonder model (regels + marktregel)", t0, p0)]
    for name, kw in (("I2 + compressie", {"comp": True}), ("I3 + SMA50 > SMA200", {"t50": True})):
        t, p, _ = V.measure(ctx, ent(model=False, **{**kept, **kw}), dev_u, dev_p)
        ok = p["mar"] > p0["mar"] and t["exp_pct"] >= t0["exp_pct"]
        sel.append({**V.fmt(name, t, p), "gehouden": "ja" if ok else "nee"})
        if ok:
            kept.update(kw)
            t0, p0 = t, p
    final = ent(model=False, **kept)
    label = "v4.2+ = zonder model" + "".join({"comp": " + compressie", "t50": " + SMA50>SMA200"}[k] for k in kept)
    md = ["# Swing v4.2 verbeteren — I1-I3 (kosten 0,5%/kant)\n\n<!-- CONCLUSIE -->\n\n"
          "Regels: docstring van `indicator_lab/swing4/v42_improve.py` (vooraf gecommit). Keuze alleen op DEV; de "
          "holdout-cellen zijn al eerder gezien en worden alleen gerapporteerd.\n\n## Keuze op DEV\n\n" + V.table(sel)]
    md.append("## Alle cellen: v4.1 tegen de eindversie\n\n")
    for cell, (u, per) in V.CELLS.items():
        rows = [V.fmt("v4.1 (met model)", *V.measure(ctx, V.V4, u, per)[:2]), V.fmt(label, *V.measure(ctx, final, u, per)[:2]),
                V.spy_row(per)]
        plan = []
        for nm, e in (("v4.1", V.V4), (label, final)):
            s = V.plan_portfolio(L.run(ctx, e, univ=u, period=per, cost=V.COST))
            plan.append({"jouw plan": nm, "CAGR": f"{s['cagr'] * 100:.1f}%", "max DD": f"{s['maxdd'] * 100:.1f}%",
                         "MAR": f"{s['mar']:.2f}", "Sharpe": f"{s['sharpe']:.2f}"})
        md.append(f"**{cell}**\n\n" + V.table(rows) + "Jouw plan (1% risico, max 10%, vrij geld in SPY > SMA200):\n\n" + V.table(plan))
        print(cell, flush=True)
    with open(OUT, "w") as fh:
        fh.write("".join(md))
    print("kept", kept, flush=True)


if __name__ == "__main__":
    main()
