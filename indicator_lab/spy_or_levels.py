"""Backtest of the user's "SPY 2 Levels 0930-0945" idea on 5-minute SPY bars (Yahoo: only the last ~60 days are free).

    python -m indicator_lab.spy_or_levels       # results/spy_or_levels.md

Rules (assumed from the user's chart, fixed before the run; the indicator's own code was not available):
  * Levels: the HIGH and LOW of 09:30-09:45 New York (the first three 5-minute bars).
  * CALL: after 09:45 the price touches the LOW level -> long at the low level, target = the HIGH level.
    PUT: after 09:45 the price touches the HIGH level -> short at the high level, target = the LOW level.
    Only the first touch of each level per day. No stop in the rule: the trade is judged on whether the target is
    reached before the close (15:55 bar), and otherwise closed at the close.
  * Measured per side: % target reached the same day, % of days the level was touched, result at the close when not
    reached, max adverse move (MAE) in % and in range widths. Inside one 5-minute bar the order of high/low is unknown:
    a bar that touches the entry level is counted from the NEXT bar on (conservative, no same-bar target).
  * Costs ignored (gross), so the result is an upper bound.
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

OUT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "results", "spy_or_levels.md")


def load():
    import yfinance as yf
    d = yf.download("SPY", period="60d", interval="5m", progress=False, auto_adjust=False)
    d.columns = [c[0].lower() if isinstance(c, tuple) else c.lower() for c in d.columns]
    d.index = d.index.tz_convert("America/New_York").tz_localize(None)
    return d[["open", "high", "low", "close"]].dropna()


def side(day, lvl, tgt, long):
    rest = day[day.index.time >= pd.Timestamp("09:45").time()]
    hit = rest["low"] <= lvl if long else rest["high"] >= lvl
    if not hit.any():
        return None
    i0 = int(np.argmax(hit.to_numpy()))
    after = rest.iloc[i0 + 1:]
    if len(after) == 0:
        return None
    reach = after["high"] >= tgt if long else after["low"] <= tgt
    width = abs(tgt - lvl)
    if reach.any():
        j = int(np.argmax(reach.to_numpy()))
        seg = after.iloc[:j + 1]
        ok, res = True, width / lvl
    else:
        seg = after
        ok = False
        res = (after["close"].iloc[-1] - lvl) / lvl * (1 if long else -1)
    mae = ((seg["low"].min() - lvl) / lvl) if long else ((lvl - seg["high"].max()) / lvl)
    return {"ok": ok, "res": res, "mae": mae, "mae_w": mae * lvl / width if width > 0 else np.nan,
            "width": width / lvl, "time": rest.index[i0].time()}


def main():
    d = load()
    rows = {"CALL (koop aan het lage level, doel hoge level)": [], "PUT (short aan het hoge level, doel lage level)": []}
    days = 0
    for _, day in d.groupby(d.index.date):
        orb = day[(day.index.time >= pd.Timestamp("09:30").time()) & (day.index.time < pd.Timestamp("09:45").time())]
        if len(orb) < 3:
            continue
        days += 1
        hi, lo = orb["high"].max(), orb["low"].min()
        for name, args in (("CALL (koop aan het lage level, doel hoge level)", (lo, hi, True)),
                           ("PUT (short aan het hoge level, doel lage level)", (hi, lo, False))):
            r = side(day, *args)
            if r:
                rows[name].append(r)
    tab = []
    for name, rr in rows.items():
        x = pd.DataFrame(rr)
        tab.append({"kant": name, "dagen": days, "level geraakt": f"{len(x)} ({len(x) / days * 100:.0f}%)",
                    "doel dezelfde dag geraakt": f"{x.ok.mean() * 100:.0f}%",
                    "gem. resultaat (bruto)": f"{x.res.mean() * 100:+.2f}%",
                    "gem. resultaat als doel NIET geraakt": f"{x[~x.ok].res.mean() * 100:+.2f}%" if (~x.ok).any() else "-",
                    "gem. max tegenbeweging": f"{x.mae.mean() * 100:.2f}% ({x.mae_w.mean():.1f}x range)",
                    "gem. range 9:30-9:45": f"{x.width.mean() * 100:.2f}%"})
    txt = ("# SPY 2 Levels (opening range 9:30-9:45): raken de trades hun doel?\n\n<!-- CONCLUSIE -->\n\n"
           f"Regels: docstring van `indicator_lab/spy_or_levels.py`. Data: Yahoo 5-minutenbars SPY, {d.index[0].date()} .. "
           f"{d.index[-1].date()} ({days} handelsdagen; langere intraday-geschiedenis is niet gratis beschikbaar). "
           "Geen kosten (bruto).\n\n" + pd.DataFrame(tab).to_markdown(index=False) + "\n")
    with open(OUT, "w") as fh:
        fh.write(txt)
    print(txt)


if __name__ == "__main__":
    main()
