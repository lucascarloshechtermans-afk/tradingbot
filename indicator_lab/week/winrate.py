"""Search for a setup with a 70% win rate, honestly: the 10 setups of build.py (and the random-entry control) with a
single fixed profit target for the whole position instead of the 50% / +10% / +20% ladder.

    python -m indicator_lab.week.winrate

Fixed before the run: targets +3%, +5%, +10% (whole position), stop and 10-day time stop as in build.trade, costs
0.1% + 0.1% slippage per side, universe ADR > 4% / > $5 / > $20M a day, one open position per stock, no filters.
QUALIFIES = test (2023-04-07 .. 2026-10-23) win rate >= 70% AND test profit factor > 1.3 AND >= 100 test trades.
A high win rate alone does not qualify: a small target with a wide stop wins often and loses big.
Results are appended to results/strategy_log.md.
"""
from __future__ import annotations

import pickle

import numpy as np
import pandas as pd

from indicator_lab import sr
from indicator_lab.timing import regime as R
from indicator_lab.twenty import data20
from indicator_lab.week import build as B
from indicator_lab.week import run as W

TARGETS = (0.03, 0.05, 0.10)


def main():
    data20.final_mode()
    spy = R.load("SPY")
    with open(B.OUT, "rb") as fh:
        tickers = sorted({z["ticker"] for z in pickle.load(fh)["cands"]})
    res: dict = {}                                     # (sid, tgt, split) -> list of returns
    for j, t in enumerate(tickers):
        df = data20.load(t)
        df = df[(df[["open", "high", "low", "close"]] > 0).all(axis=1) & (df.index <= B.END)]
        lv = sr.levels(df)
        sig = B.signals(df, lv, spy.reindex(df.index).ffill().to_numpy())
        sig[0] = [(s, "open", np.nan, lv["sup_lo"].iloc[s]) for s in range(0, len(df), 21)]   # control
        m = B.universe_mask(df)
        o, h, lo, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
        a, rs_ = lv["atr"].to_numpy(), lv["res_strong"].to_numpy()
        for sid, lst in sig.items():
            for tgt in TARGETS:
                last_exit = -1
                for s, etype, elevel, anchor in sorted(lst):
                    day = df.index[s]
                    if not (B.START <= day <= B.END) or not m[s] or s + 1 <= last_exit:
                        continue
                    tr = B.trade(o, h, lo, c, s, etype, elevel, anchor, a[s], rs_[s], tgt=tgt)
                    if tr is None:
                        continue
                    last_exit = tr["exit_i"]
                    res.setdefault((sid, tgt, "train" if day <= B.SPLIT else "test"), []).append(tr["ret"])
        if j % 400 == 0:
            print(f"{j}/{len(tickers)}", flush=True)
    rows = []
    for sid in [0, *B.NAMES]:
        for tgt in TARGETS:
            row = {"strategie": "0 Willekeurige instap (controle)" if sid == 0 else f"{sid} {B.NAMES[sid]}",
                   "doel": f"+{tgt * 100:.0f}%"}
            ok = False
            for part in ("train", "test"):
                r = np.array(res.get((sid, tgt, part), []))
                if len(r) == 0:
                    row[f"{part} trades"] = 0
                    continue
                w, lz = r[r > 0], r[r <= 0]
                pf = w.sum() / -lz.sum() if lz.sum() < 0 else np.inf
                row.update({f"{part} trades": len(r), f"{part} winrate": f"{(r > 0).mean() * 100:.0f}%",
                            f"{part} PF": f"{pf:.2f}", f"{part} per trade": f"{r.mean() * 100:+.2f}%"})
                if part == "test":
                    ok = sid != 0 and len(r) >= 100 and (r > 0).mean() >= 0.70 and pf > 1.3
            row["voldoet (test: >= 70% winrate én PF > 1,3)"] = "JA" if ok else ("–" if sid == 0 else "nee")
            rows.append(row)
    txt = ("\n## Zoektocht naar 70% winrate (indicator_lab/week/winrate.py)\n\nEén vast winstdoel voor de hele positie, "
           "verder dezelfde stop, tijdstop (10 dagen), kosten en universum; geen filters.\n\n"
           + pd.DataFrame(rows).fillna("–").to_markdown(index=False) + "\n")
    with open(W.LOG, "a") as fh:
        fh.write(txt)
    print(txt)


if __name__ == "__main__":
    main()
