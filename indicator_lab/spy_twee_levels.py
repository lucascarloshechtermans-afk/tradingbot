"""Backtest of the user's Pine indicator "SPY Twee Levels" (exact level rules) on 5-minute SPY bars (Yahoo, last ~60 days).

    python -m indicator_lab.spy_twee_levels      # results/spy_twee_levels.md

Level rules = the Pine script: candidates = yesterday's high / low / close, today's opening range high / low (09:30-09:45
New York), yesterday's close +/- yesterday's daily ATR(14) (Wilder). CALL level = the highest candidate <= close - 0.10%,
PUT level = the lowest candidate >= close + 0.10%; the levels move with the price (recomputed on every bar close).
Trade rules (fixed before the run, as in the script header): entries 09:45-15:00 New York; at bar i the levels of the
close of bar i-1 are used; CALL = the low of bar i touches the CALL level -> long at that level (a gap below fills at the
open), target = the PUT level; PUT = the high touches the PUT level -> short, target = the CALL level. One trade per day,
no stop, out at the target (from the next bar on; the order inside a 5-minute bar is unknown) or at the close of the day.
A bar touching both levels is skipped. Gross (no option or trading costs). Extra variants (reported, not chosen): a stop
at the same distance as the target (1:1).
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

OUT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "results", "spy_twee_levels.md")
GAP = 0.0010


def load():
    import yfinance as yf
    m5 = yf.download("SPY", period="60d", interval="5m", progress=False, auto_adjust=False)
    dd = yf.download("SPY", period="2y", interval="1d", progress=False, auto_adjust=False)
    for d in (m5, dd):
        d.columns = [c[0].lower() if isinstance(c, tuple) else c.lower() for c in d.columns]
    m5.index = m5.index.tz_convert("America/New_York").tz_localize(None)
    dd.index = pd.to_datetime(dd.index).tz_localize(None)
    return m5[["open", "high", "low", "close"]].dropna(), dd[["high", "low", "close"]].dropna()


def wilder_atr(d, n=14):
    pc = d["close"].shift()
    tr = pd.concat([d["high"] - d["low"], (d["high"] - pc).abs(), (d["low"] - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def levels(cands, px):
    gap = px * GAP
    below = [v for v in cands if v <= px - gap]
    above = [v for v in cands if v >= px + gap]
    return (max(below) if below else np.nan), (min(above) if above else np.nan)


def day_trade(day, prev, atr, stop_mult=None):
    t = day.index.time
    orb = day[(t >= pd.Timestamp("09:30").time()) & (t < pd.Timestamp("09:45").time())]
    if len(orb) < 3:
        return None
    cands = [prev["high"], prev["low"], prev["close"], orb["high"].max(), orb["low"].min(),
             prev["close"] + atr, prev["close"] - atr]
    o, h, lo, c = (day[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    for i in range(1, len(day)):
        ti = day.index[i].time()
        if ti < pd.Timestamp("09:45").time() or ti > pd.Timestamp("15:00").time():
            continue
        callL, putL = levels(cands, c[i - 1])
        hit_c = np.isfinite(callL) and np.isfinite(putL) and lo[i] <= callL
        hit_p = np.isfinite(callL) and np.isfinite(putL) and h[i] >= putL
        if hit_c and hit_p:
            continue
        if not (hit_c or hit_p):
            continue
        long = hit_c
        entry = min(o[i], callL) if long else max(o[i], putL)
        tgt = putL if long else callL
        dist = abs(tgt - entry)
        stop = (entry - stop_mult * dist if long else entry + stop_mult * dist) if stop_mult else None
        for j in range(i + 1, len(day)):
            if stop is not None and ((long and lo[j] <= stop) or (not long and h[j] >= stop)):
                px = min(o[j], stop) if long else max(o[j], stop)
                return {"side": "CALL" if long else "PUT", "kind": "stop", "ret": (px / entry - 1) * (1 if long else -1)}
            if (long and h[j] >= tgt) or (not long and lo[j] <= tgt):
                px = max(o[j], tgt) if long else min(o[j], tgt)
                return {"side": "CALL" if long else "PUT", "kind": "doel", "ret": (px / entry - 1) * (1 if long else -1)}
        return {"side": "CALL" if long else "PUT", "kind": "slot", "ret": (c[-1] / entry - 1) * (1 if long else -1)}
    return None


def stats(tr, name):
    x = pd.DataFrame(tr)
    r = x.ret.to_numpy()
    return {"variant": name, "trades": len(x), "CALL / PUT": f"{(x.side == 'CALL').sum()} / {(x.side == 'PUT').sum()}",
            "doel gehaald": f"{(x.kind == 'doel').mean() * 100:.1f}%", "stop": f"{(x.kind == 'stop').mean() * 100:.0f}%",
            "winnaars": f"{(r > 0).mean() * 100:.0f}%", "gem./trade": f"{r.mean() * 100:+.3f}%",
            "slechtste": f"{r.min() * 100:+.2f}%", "beste": f"{r.max() * 100:+.2f}%",
            "t": f"{r.mean() / r.std(ddof=1) * np.sqrt(len(r)):.2f}"}


def main():
    m5, dd = load()
    atr = wilder_atr(dd)
    out = {}
    for name, sm in (("zoals de indicator (geen stop)", None), ("met stop 1:1", 1.0)):
        tr = []
        for d, day in m5.groupby(m5.index.date):
            ts = pd.Timestamp(d)
            prev_i = dd.index.searchsorted(ts) - 1
            if prev_i < 15:
                continue
            r = day_trade(day, dd.iloc[prev_i], atr.iloc[prev_i], sm)
            if r:
                tr.append(r)
        out[name] = stats(tr, name)
    txt = ("# SPY Twee Levels — backtest van de echte indicatorregels\n\n<!-- CONCLUSIE -->\n\n"
           f"Regels: docstring van `indicator_lab/spy_twee_levels.py`. Data: Yahoo 5-minutenbars SPY {m5.index[0].date()} .. "
           f"{m5.index[-1].date()} (gratis intraday-geschiedenis is beperkt tot ~60 dagen). Bruto, zonder optiekosten.\n\n"
           + pd.DataFrame(list(out.values())).to_markdown(index=False) + "\n")
    with open(OUT, "w") as fh:
        fh.write(txt)
    print(txt)


if __name__ == "__main__":
    main()
