"""Two checks after the 10-strategy run (run.py), appended to results/strategy_log.md:

  1. CONTROL: random entries in the same universe with the same exits. Every 21st trading day per stock (fixed
     calendar, no signal), when the stock passes the universe filter; stop anchor = the nearest support zone
     (sr.py), as for the setups. Shows how often +10% / +20% is hit by volatility alone.
  2. COMBINATION of the top 3 strategies ranked by their TRAIN profit factor (best configuration each), one open
     position per stock; kept only if its TEST profit factor beats the best single one.

    python -m indicator_lab.week.extra
"""
from __future__ import annotations

import os
import pickle

import numpy as np
import pandas as pd

from indicator_lab import sr
from indicator_lab.timing import regime as R
from indicator_lab.twenty import data20
from indicator_lab.week import build as B
from indicator_lab.week import run as W


def control_trades() -> list:
    data20.final_mode()
    spy = R.load("SPY")
    up = (spy > spy.rolling(50).mean()) & (spy.ewm(span=20, adjust=False).mean() > spy.ewm(span=50, adjust=False).mean())
    with open(B.OUT, "rb") as fh:
        tickers = sorted({z["ticker"] for z in pickle.load(fh)["cands"]})
    out = []
    for t in tickers:
        df = data20.load(t)
        df = df[(df[["open", "high", "low", "close"]] > 0).all(axis=1) & (df.index <= B.END)]
        m = B.universe_mask(df)
        lv = sr.levels(df)
        o, h, lo, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
        a, sup_lo, rs_ = lv["atr"].to_numpy(), lv["sup_lo"].to_numpy(), lv["res_strong"].to_numpy()
        reg = up.reindex(df.index).ffill().fillna(False).to_numpy()
        for s in range(0, len(df), 21):
            day = df.index[s]
            if not (B.START <= day <= B.END) or not m[s]:
                continue
            tr = B.trade(o, h, lo, c, s, "open", np.nan, sup_lo[s], a[s], rs_[s])
            if tr is None:
                continue
            tr.update({"strategy": 0, "ticker": t, "signal": day, "entry": df.index[tr["entry_i"]],
                       "exit": df.index[tr["exit_i"]], "dates": df.index[tr["entry_i"]:tr["exit_i"] + 1],
                       "regime": bool(reg[s]), "rs_top20": True, "vol_surge": True, "room10": True,
                       "split": "train" if day <= B.SPLIT else "test"})
            out.append(tr)
    return out


def row(name, cfg, part, m) -> str:
    if m["n"] == 0:
        return f"| – | {name} | {cfg} | {part} | 0 | – | – | – | – | – | – | – | – | – | – |\n"
    return (f"| – | {name} | {cfg} | {part} | {m['n']} | {m['win'] * 100:.0f}% | {m['avg_win'] * 100:+.1f}% | "
            f"{m['avg_loss'] * 100:+.1f}% | {m['pf']:.2f} | {m['exp'] * 100:+.2f}% | {m['maxdd'] * 100:.1f}% | "
            f"{m['cagr'] * 100:.1f}% | {m['hit10'] * 100:.0f}% | {m['hit20'] * 100:.0f}% | {m['hold']:.1f} d |\n")


def main():
    tr_span = (B.START, B.SPLIT)
    te_span = (B.SPLIT + pd.Timedelta(days=1), B.END)
    ctrl = control_trades()
    ctrl_sel = W.select(ctrl, 0, (), None)
    lines = ["\n## Controle en combinatie (indicator_lab/week/extra.py)\n\n", W.HEADER]
    for part, span in (("train", tr_span), ("test", te_span)):
        m = W.metrics([z for z in ctrl_sel if z["split"] == part], *span)
        lines.append(row("0 Willekeurige instap (controle)", "elke 21e handelsdag, zelfde exits", part, m))
    with open(os.path.join(os.path.dirname(W.LOG), "week_summary.pkl"), "rb") as fh:
        summary = pickle.load(fh)
    top = sorted(summary, key=lambda s: -s["train"].get("pf", 0))[:3]
    data = W.load()
    earn = W.earnings_flags(data["cands"])
    combo = []
    for s in top:
        combo += W.select(data["cands"], s["sid"], s["flt"], earn)
    combo.sort(key=lambda z: (z["signal"], z["ticker"]))
    last, taken = {}, []
    for z in combo:
        if z["ticker"] in last and z["entry"] <= last[z["ticker"]]:
            continue
        last[z["ticker"]] = z["exit"]
        taken.append(z)
    name = "Combinatie top 3 op train: " + ", ".join(f"{s['sid']}" for s in top)
    cfg = "; ".join(f"{s['sid']}: {', '.join(s['flt']) or 'geen'}" for s in top)
    mte = None
    for part, span in (("train", tr_span), ("test", te_span)):
        m = W.metrics([z for z in taken if z["split"] == part], *span)
        lines.append(row(name, cfg, part, m))
        mte = m if part == "test" else mte
    best_single = max(s["test"].get("pf", 0) for s in summary if s["test"]["n"] >= 100)
    lines.append(f"\nCombinatie test-PF {mte['pf']:.2f} vs beste losse strategie {best_single:.2f}: "
                 f"**{'combinatie beter' if mte['pf'] > best_single else 'combinatie NIET beter, niet gebruiken'}**.\n")
    with open(W.LOG, "a") as fh:
        fh.write("".join(lines))
    print("".join(lines))


if __name__ == "__main__":
    main()
