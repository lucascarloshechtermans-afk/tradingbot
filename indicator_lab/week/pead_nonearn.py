"""Control for the post-earnings gap setup: the SAME gap rules on days WITHOUT earnings.

    python -m indicator_lab.week.pead_nonearn

Fixed before the run: a gap day = open >= 1.05 x previous close, volume >= 2 x the 50-day average before it, close >
open, SPY > SMA200, universe (> $5, > $20M a day, ADR > 2 / 3 / 4%). "Earnings" gap = an earnings reaction day (as in
pead_week); "no earnings" gap = no earnings report within 3 trading days before or after. Only stocks with known
earnings dates are used for both groups. Same exits, holding periods, costs, one position per stock, splits
(train 2015-2022, test 2023-2026) as pead_week; EPS rule "any" (no EPS exists for a non-earnings gap).
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from indicator_lab import sr
from indicator_lab.timing import regime as R
from indicator_lab.twenty import data20
from indicator_lab.week import build as B
from indicator_lab.week import earnings_eps as E
from indicator_lab.week import pead_week as P
from indicator_lab.week import run as W

OUT = os.path.join(os.path.dirname(W.LOG), "pead_nonearn.md")


def load():
    data20.final_mode()
    spy = R.load("SPY")
    spy_up = spy > spy.rolling(200).mean()
    earn = E.load()
    arrs, ev = {}, {"earnings": [], "geen earnings": []}
    for j, t in enumerate(sorted(earn)):
        try:
            df = data20.load(t)
        except PermissionError:
            continue
        if df is None or len(df) < 300:
            continue
        df = df[(df[["open", "high", "low", "close"]] > 0).all(axis=1) & (df.index <= B.END)]
        o, h, lo, c, v = (df[k].to_numpy(float) for k in ("open", "high", "low", "close", "volume"))
        adr = B.sma(h / lo - 1, 20) * 100
        dv = B.sma(c * v, 50)
        base = (c > 5) & (dv > 20e6) & np.asarray(df.index >= B.START) & np.asarray(df.index <= B.END)
        if not (base & (adr > 2)).any():
            continue

        arrs[t] = {"idx": df.index, "o": o, "h": h, "l": lo, "c": c, "atr": sr.atr(h, lo, c),
                   "e20": pd.Series(c).ewm(span=20, adjust=False, min_periods=20).mean().to_numpy()}
        va50 = B.prev(B.sma(v, 50))
        reg = spy_up.reindex(df.index).ffill().fillna(False).to_numpy(bool)
        with np.errstate(invalid="ignore"):
            gap = (o >= 1.05 * B.prev(c)) & (v >= 2 * va50) & (c > o) & base & reg
        react = np.zeros(len(df), bool)
        near = np.zeros(len(df), bool)
        for ts, rule, _est, _rep in earn[t]:
            i = int(df.index.searchsorted(ts))
            if i < len(df) and df.index[i] == ts and rule == "next":
                i += 1
            if 0 <= i < len(df):
                react[i] = True
                near[max(0, i - 3):i + 4] = True
        for i in np.where(gap)[0]:
            if i + 1 >= len(df):
                continue
            grp = "earnings" if react[i] else ("geen earnings" if not near[i] else None)
            if grp:
                ev[grp].append({"ticker": t, "s": int(i), "day": df.index[i], "adr": adr[i], "surprise": None,
                                "split": "train" if df.index[i] <= P.TRAIN_END else "test"})
        if j % 500 == 0:
            print(f"load {j}/{len(earn)}: {len(ev['earnings'])} / {len(ev['geen earnings'])}", flush=True)
    return arrs, ev


def main():
    arrs, ev = load()
    rows = []
    for adr_min in P.ADRS:
        for mi, ex in enumerate(P.EXITS):
            for hold in P.HOLDS:
                for grp in ("earnings", "geen earnings"):
                    v = P.run_variant(arrs, ev[grp], adr_min, "any", mi, hold)
                    tr, te = P.stats(v["train"]), P.stats(v["test"])
                    rows.append({"ADR >": f"{adr_min:.0f}%", "exit": ex, "dagen": hold, "gaps": grp,
                                 "train trades": tr["n"], "train PF": f"{tr.get('pf', 0):.2f}",
                                 "test trades": te["n"], "winrate": f"{te.get('win', 0) * 100:.0f}%",
                                 "PF": f"{te.get('pf', 0):.2f}", "exp.": f"{te.get('exp', 0) * 100:+.2f}%",
                                 "PF zonder top 5%": f"{te.get('pf_ex5', 0):.2f}", "max DD": f"{te.get('dd', 0) * 100:.1f}%"})
                print(adr_min, ex, hold, flush=True)
    txt = ("# Controle: dezelfde gap-setup met en zonder earnings\n\nZie `indicator_lab/week/pead_nonearn.py`. "
           f"Gap-dagen: {len(ev['earnings'])} met earnings, {len(ev['geen earnings'])} zonder (geen cijfers binnen 3 dagen). "
           "EPS-regel 'any', marktregime aan, train 2015-2022, test 2023-2026.\n\n" + pd.DataFrame(rows).to_markdown(index=False) + "\n")
    with open(OUT, "w") as fh:
        fh.write(txt)
    with open(W.LOG, "a") as fh:
        fh.write("\n## Controle gap-setup zonder earnings (results/pead_nonearn.md): 27 varianten x 2 groepen\n")
    print(txt[-4000:])


if __name__ == "__main__":
    main()
