"""Post-earnings gap setup on the two effects that held up: the market regime (SPY > SMA200) and post-earnings drift.
Win rate is no goal; the goal is expectancy > 0 and PF >= 1.3 after costs, better than random with the same exits.

    python -m indicator_lab.week.pead_week          # steps 1-4 (interim report): results/pead_week.md

Fixed before the run:
  Setup 11 (signal on the earnings REACTION day s, see earnings_eps.load for the day rule): open >= 1.05 x previous
    close, volume >= 2 x the 50-day average volume before s, close > open; SPY close > SMA200 on s (always on);
    universe on s: close > $5, 50-day average dollar volume > $20M and ADR(20) > 2% / 3% / 4% (three variants);
    EPS variant: "any" or "surprise > 0" (reported > estimate; events without EPS data are dropped in that variant).
    Entry: the open of s + 1. One open position per stock.
  Exits (initial stop for both = the gap day's low - 0.1 x ATR; gaps fill at the open; same bar: stop first):
    A-EMA20  after +1R the stop moves to break-even; exit at the next open after a close below the 20 EMA; no cap
    A-3ATR   after +1R the stop moves to break-even; chandelier stop: highest high since entry - 3 x ATR; no cap
    B        50% at +10% (stop to break-even), the rest at +20%
    all with a time exit at the close of day 10 / 20 / 40.
  Costs: commission 0.05% per side + 2 ticks ($0.02) slippage per side. Win = net result > 0.
  Train = signals 2015-01-01 .. 2022-12-31, test = 2023-01-01 .. 2026-10-23.
  Random control: for every signal date, a random stock of the same universe that day (regime is a date filter, so it
  is identical), entry next open, stop below that day's low - 0.1 ATR, same exits; 20 runs.
  Account max drawdown: 10 positions of 10%, trades in entry order (capacity not modelled).
Every variant is reported and counted: 3 universes x 2 EPS variants x 3 exits x 3 holding periods = 54.
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
from indicator_lab.week import earnings_eps as E
from indicator_lab.week import run as W

try:
    from numba import njit
except ImportError:
    def njit(*a, **k):
        return (lambda f: f) if not a or not callable(a[0]) else a[0]

OUT = os.path.join(os.path.dirname(W.LOG), "pead_week.md")
TRAIN_END = pd.Timestamp("2022-12-31")
ADRS = (2.0, 3.0, 4.0)
EXITS = ("A-EMA20", "A-3ATR", "B")
HOLDS = (10, 20, 40)
RUNS = 20


@njit(cache=True)
def exit_sim(o, h, lo, c, e20, a, d, fill, stop, mode, hold):
    """mode 0 = A-EMA20, 1 = A-3ATR, 2 = B. Returns (net return, bars held)."""
    n = len(c)
    buy = (fill + 0.02) * 1.0005
    r1 = fill - stop
    left = 1.0
    got = 0.0
    half = False
    hh = fill
    pend = False
    for k in range(hold):
        day = d + k
        if day >= n:
            got += left * (c[n - 1] - 0.02) * 0.9995
            return got / buy - 1, k
        op = fill if k == 0 else o[day]
        if pend:                                   # A-EMA20: sell at this open
            got += left * (op - 0.02) * 0.9995
            return got / buy - 1, k + 1
        if lo[day] <= stop:
            px = stop if k == 0 else min(op, stop)
            got += left * (px - 0.02) * 0.9995
            return got / buy - 1, k + 1
        newstop = stop
        hh = max(hh, h[day])
        if mode == 2:
            if not half and h[day] >= fill * 1.10:
                px = fill * 1.10 if k == 0 else max(op, fill * 1.10)
                got += 0.5 * (px - 0.02) * 0.9995
                left = 0.5
                half = True
                newstop = max(newstop, fill)
            if half and h[day] >= fill * 1.20:
                px = fill * 1.20 if k == 0 else max(op, fill * 1.20)
                got += left * (px - 0.02) * 0.9995
                return got / buy - 1, k + 1
        else:
            if h[day] >= fill + r1:
                newstop = max(newstop, fill)
            if mode == 1:
                newstop = max(newstop, hh - 3.0 * a[day])
            elif c[day] < e20[day]:
                pend = True
        if k == hold - 1:
            got += left * (c[day] - 0.02) * 0.9995
            return got / buy - 1, k + 1
        stop = newstop
    return got / buy - 1, hold


def load():
    data20.final_mode()
    spy = R.load("SPY")
    spy_up = spy > spy.rolling(200).mean()
    earn = E.load()
    arrs, events, pool = {}, [], {a: {} for a in ADRS}
    tickers = sorted(set(data20.DEV) | data20.H_TICKERS)
    for j, t in enumerate(tickers):
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
        atr = sr.atr(h, lo, c)
        arrs[t] = {"idx": df.index, "o": o, "h": h, "l": lo, "c": c, "atr": atr, "adr": adr, "base": base,
                   "e20": pd.Series(c).ewm(span=20, adjust=False, min_periods=20).mean().to_numpy()}
        for a in ADRS:
            for i in np.where(base & (adr > a))[0]:
                pool[a].setdefault(df.index[i], []).append((t, int(i)))
        va50 = B.prev(B.sma(v, 50))
        reg = spy_up.reindex(df.index).ffill().fillna(False).to_numpy(bool)
        for ts, rule, est, rep in earn.get(t, []):
            i = int(df.index.searchsorted(ts))
            if i < len(df) and df.index[i] == ts and rule == "next":
                i += 1                                # (a report on a non-trading day already maps to the next session)
            if i < 1 or i + 1 >= len(df) or not base[i] or not reg[i]:
                continue
            if not (o[i] >= 1.05 * c[i - 1] and v[i] >= 2 * va50[i] and c[i] > o[i]):
                continue
            sur = (rep - est) if est is not None and rep is not None else None
            events.append({"ticker": t, "s": i, "day": df.index[i], "adr": adr[i], "surprise": sur,
                           "split": "train" if df.index[i] <= TRAIN_END else "test"})
        if j % 500 == 0:
            print(f"load {j}/{len(tickers)}: {len(events)} events", flush=True)
    return arrs, events, pool


def simulate(ar, s, mode, hold, gap_low=None):
    d = s + 1
    if d + hold > len(ar["c"]):
        return None
    fill = ar["o"][d]
    a = ar["atr"][s]
    if not (fill > 0 and a > 0):
        return None
    stop = (ar["l"][s] if gap_low is None else gap_low) - 0.1 * a
    if stop >= fill:
        stop = fill - a                                 # opened below the gap-day low: 1 ATR stop
    r, bars = exit_sim(ar["o"], ar["h"], ar["l"], ar["c"], ar["e20"], ar["atr"], d, fill, stop, mode, hold)
    return r, bars, 1 - stop / fill, ar["idx"][d], ar["idx"][min(d + bars - 1, len(ar["c"]) - 1)]


def stats(v) -> dict:
    if not v:
        return {"n": 0}
    r = np.array([x[0] for x in v])
    risk = np.array([x[2] for x in v])
    w, lz = r[r > 0], r[r <= 0]
    top = np.sort(r)[::-1]
    rest = top[max(1, len(r) // 20):]
    pf = w.sum() / -lz.sum() if lz.sum() < 0 else np.inf
    pf95 = rest[rest > 0].sum() / -rest[rest <= 0].sum() if rest[rest <= 0].sum() < 0 else np.inf
    eq = np.cumprod(1 + 0.1 * r[np.argsort([x[3] for x in v])])
    return {"n": len(r), "win": (r > 0).mean(), "pf": pf, "pf_ex5": pf95, "exp": r.mean(), "exp_R": (r / risk).mean(),
            "dd": float((eq / np.maximum.accumulate(eq) - 1).min()), "bars": np.mean([x[1] for x in v]),
            "risk": risk.mean()}


def run_variant(arrs, events, adr_min, eps, mode, hold) -> dict:
    sel = [e for e in events if e["adr"] > adr_min and (eps == "any" or (e["surprise"] is not None and e["surprise"] > 0))]
    sel.sort(key=lambda e: (e["day"], e["ticker"]))
    last: dict = {}
    out = {"train": [], "test": [], "dates": {"train": [], "test": []}}
    for e in sel:
        ar = arrs[e["ticker"]]
        if e["ticker"] in last and ar["idx"][e["s"] + 1] <= last[e["ticker"]]:
            continue
        res = simulate(ar, e["s"], mode, hold)
        if res is None:
            continue
        last[e["ticker"]] = res[4]
        out[e["split"]].append(res)
        out["dates"][e["split"]].append(e["day"])
    return out


def random_ctrl(arrs, pool, dates, mode, hold, seed=3) -> dict:
    rng = np.random.default_rng(seed)
    wins, pfs = [], []
    for _ in range(RUNS):
        v = []
        for day in dates:
            p = pool.get(day)
            if not p:
                continue
            t, s = p[rng.integers(len(p))]
            res = simulate(arrs[t], s, mode, hold)
            if res is not None:
                v.append(res)
        st = stats(v)
        wins.append(st.get("win", np.nan))
        pfs.append(st.get("pf", np.nan))
    return {"win": float(np.nanmean(wins)), "pf": float(np.nanmean(pfs))}


def main():
    cache = os.path.join(B.CACHE, "pead_week_inputs.pkl")
    if os.path.exists(cache):
        with open(cache, "rb") as fh:
            arrs, events, pool = pickle.load(fh)
    else:
        arrs, events, pool = load()
        with open(cache, "wb") as fh:
            pickle.dump((arrs, events, pool), fh)
    rows = []
    for adr_min in ADRS:
        for eps in ("any", "surprise > 0"):
            for mi, ex in enumerate(EXITS):
                for hold in HOLDS:
                    v = run_variant(arrs, events, adr_min, eps, mi, hold)
                    tr, te = stats(v["train"]), stats(v["test"])
                    rnd = random_ctrl(arrs, pool[adr_min], v["dates"]["test"], mi, hold)
                    row = {"ADR >": f"{adr_min:.0f}%", "EPS": eps, "exit": ex, "dagen": hold,
                           "train trades": tr["n"], "train PF": f"{tr.get('pf', 0):.2f}"}
                    if te["n"]:
                        row.update({"test trades": te["n"], "winrate": f"{te['win'] * 100:.0f}%", "PF": f"{te['pf']:.2f}",
                                    "PF zonder top 5%": f"{te['pf_ex5']:.2f}", "exp.": f"{te['exp'] * 100:+.2f}%",
                                    "exp. (R)": f"{te['exp_R']:+.2f}", "gem. risico": f"{te['risk'] * 100:.1f}%",
                                    "max DD": f"{te['dd'] * 100:.1f}%", "dagen gem.": f"{te['bars']:.1f}",
                                    "random winrate / PF": f"{rnd['win'] * 100:.0f}% / {rnd['pf']:.2f}",
                                    "PF - random": f"{te['pf'] - rnd['pf']:+.2f}"})
                    rows.append(row)
                    print(adr_min, eps, ex, hold, tr["n"], te["n"], f"test PF {te.get('pf', 0):.2f}", flush=True)
    d = pd.DataFrame(rows).fillna("–")
    txt = ("# Post-earnings gap (setup 11) — stap 1-4 (tussenrapport)\n\nZie `indicator_lab/week/pead_week.py` voor de "
           f"vooraf vastgelegde regels. {len(rows)} varianten. Train 2015-2022, test 2023-2026; marktregime SPY > SMA200 "
           "altijd aan; kosten 0,05%/kant + 2 ticks.\n\n" + d.to_markdown(index=False) + "\n")
    with open(OUT, "w") as fh:
        fh.write(txt)
    with open(W.LOG, "a") as fh:
        fh.write(f"\n## Post-earnings gap (setup 11), stap 1-4: {len(rows)} varianten — zie results/pead_week.md\n")
    print(txt[-3000:])


if __name__ == "__main__":
    main()
