"""Donchian 20-day breakout on NASDAQ stocks with filters against false breakouts (daily bars).
Rules: indicator_lab/week/donchian_filters_rules.md (committed before the first run).

    python -m indicator_lab.week.donchian_filters    # results/donchian_filters.md (uses the popular.py input cache)
"""
from __future__ import annotations

import os
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

from indicator_lab.h4.nasdaq_list import nasdaq
from indicator_lab.timing import regime as R
from indicator_lab.twenty import data20
from indicator_lab.week import build as B
from indicator_lab.week import c6_followup as C
from indicator_lab.week import exit_test as X
from indicator_lab.week import popular as P
from indicator_lab.week import run as W
from indicator_lab.week import support_ema as SE
from indicator_lab.week import three_week as T

OUT = os.path.join(os.path.dirname(W.LOG), "donchian_filters.md")
FILTERS = {"F1": "trend: slot > SMA200 en SMA50 > SMA200", "F2": "volume >= 1,5x gemiddelde",
           "F3": "sterk slot (bovenste 30% van de dag)", "F4": "markt: QQQ boven SMA200",
           "F5": "niet te ver: <= 2 ATR boven het 20-daagse hoog"}
EXITS = {"dc": "verkopen na slot onder 20-daagse laag", "dc10": "+10% en eruit, anders 20-daagse-laag-regel"}


def masks(arrs, qqq_up):
    """{ticker: {F-id: bool array on the ticker's bars}} (all known at the signal close)."""
    data20.final_mode()
    out = {}
    for t, ar in arrs.items():
        df = data20.load(t)
        df = df[(df[["open", "high", "low", "close"]] > 0).all(axis=1)].reindex(ar["idx"])
        c, h, lo, v = (df[k].to_numpy(float) for k in ("close", "high", "low", "volume"))
        with np.errstate(invalid="ignore", divide="ignore"):
            s50, s200 = B.sma(c, 50), B.sma(c, 200)
            rng = h - lo
            hi20 = B.prev(B.rmax(h, 20))
            out[t] = {"F1": (c > s200) & (s50 > s200), "F2": v >= 1.5 * B.prev(B.sma(v, 50)),
                      "F3": np.where(rng > 0, (c - lo) / rng, 0.5) >= 0.7,
                      "F4": qqq_up.reindex(ar["idx"]).ffill().fillna(False).to_numpy(bool),
                      "F5": c - hi20 <= 2 * ar["atr"]}
    return out


def pick(sig, mk, codes):
    return [x for x in sig if all(mk[x[0]][f][x[1]] for f in codes)]


def tr_job(job):
    var, ex, part = job
    C._G["cand"] = C._G["cands"][var]
    return job, C.trades((ex, part))[1]


def ac_job(job):
    var, ex, slots = job
    if var != "RND":
        C._G["cand"] = C._G["cands"][var]
    return job, C.account(("RND" if var == "RND" else "C6", ex, slots))[1]


def main():
    arrs, cands, elig = P.load()
    nq = set(nasdaq(set(arrs)))
    arrs = {t: a for t, a in arrs.items() if t in nq}
    elig = {t: e for t, e in elig.items() if t in nq}
    base = [x for x in cands["C10"] if x[0] in nq]
    v41 = [x for x in cands["S12"] if x[0] in nq]
    del cands
    spy, wk, _wf, week_last = T.calendar()
    spy_w = X.weekly(spy / spy.iloc[0], wk)
    qqq = R.load("QQQ")
    qqq_w = X.weekly(qqq.reindex(spy.index).ffill() / qqq.reindex(spy.index).ffill().iloc[0], wk)
    mk = masks(arrs, qqq > qqq.rolling(200).mean())
    variants = {"base": base, "v41": v41, **{f: pick(base, mk, [f]) for f in FILTERS}}
    C._G.clear()
    C._G.update({"arrs": arrs, "days": spy.index, "wk": wk, "week_last": week_last,
                 "wl": lambda dt: week_last.get(wk.get(dt)), "rnd": SE.rnd_pool(arrs, elig, "UL"),
                 "cands": {k: P.by_day(arrs, v) for k, v in variants.items()}})
    with ProcessPoolExecutor(4) as pool:
        train = dict(pool.map(tr_job, [(v, "dc", "train") for v in ["base", *FILTERS]]))
    n0 = train[("base", "dc", "train")]["real"]["n"]
    d0 = train[("base", "dc", "train")]["diff"][0]
    kept = [f for f in FILTERS if train[(f, "dc", "train")]["diff"][0] > d0 and train[(f, "dc", "train")]["real"]["n"] >= 0.25 * n0]
    final = pick(base, mk, kept) if kept else base
    if len(kept) > 1:                         # the combination must still keep 25% of the base trades on train
        C._G["cands"]["final"] = P.by_day(arrs, final)
        with ProcessPoolExecutor(4) as pool:
            chk = dict(pool.map(tr_job, [("final", "dc", "train")]))
        if chk[("final", "dc", "train")]["real"]["n"] < 0.25 * n0:
            best = max(kept, key=lambda f: train[(f, "dc", "train")]["diff"][0])
            kept, final = [best], pick(base, mk, [best])
    C._G["cands"]["final"] = P.by_day(arrs, final)
    print("kept:", kept, flush=True)
    jobs = [(v, ex, "test") for v in ("base", "final", "v41") for ex in EXITS]
    with ProcessPoolExecutor(4) as pool:
        test = dict(pool.map(tr_job, jobs))
        acc = dict(pool.map(ac_job, [(v, ex, 10) for v in ("base", "final", "v41", "RND") for ex in EXITS]))
    write(train, test, acc, kept, spy_w, qqq_w, len(arrs))


def write(train, test, acc, kept, spy_w, qqq_w, n_stocks):
    rng = np.random.default_rng(2026)
    pc = lambda x, d=1: "-" if x is None or np.isnan(x) else f"{x * 100:.{d}f}%"
    ci = lambda t: "-" if np.isnan(t[0]) else f"{t[0] * 100:+.2f}% [{t[1] * 100:+.2f}, {t[2] * 100:+.2f}]"

    def row(name, r):
        a, d = r["real"], r["diff"]
        return {"variant": name, "trades": a.get("n", 0), "valse signalen (verlies)": pc(1 - a.get("win", np.nan), 0),
                "winrate": pc(a.get("win", np.nan), 0), "+10% geraakt": pc(a.get("hit_10pct", np.nan), 0),
                "gem./trade": pc(a.get("exp", np.nan), 2), "PF": f"{a.get('pf', np.nan):.2f}",
                "gem. dagen": f"{a.get('days', np.nan):.1f}", "verschil vs random [95%]": ci(d)}
    t1 = [row("basis (alle breakouts)", train[("base", "dc", "train")])]
    t1 += [row(f"{f} {n}" + (" — gehouden" if f in kept else ""), train[(f, "dc", "train")]) for f, n in FILTERS.items()]
    names = {"base": "basis", "final": "eindversie: " + (" + ".join(kept) or "geen filter"), "v41": "jouw v4.1"}
    t2 = [row(f"{names[v]} — {EXITS[ex]}", test[(v, ex, "test")]) for v in ("base", "final", "v41") for ex in EXITS]
    wks = [p for p in spy_w.index if p.end_time > X.TRAIN_END]
    t3 = []
    for v in ("base", "final", "v41"):
        for ex, exname in EXITS.items():
            x = acc[(v, ex, 10)]["weekly"].reindex(wks).fillna(0).to_numpy()
            xr = acc[("RND", ex, 10)]["weekly"].reindex(wks).fillna(0).to_numpy()
            t3.append({"variant": f"{names[v]} — {exname}", "CAGR": pc((1 + x).prod() ** (52 / len(x)) - 1),
                       "max daling": pc(acc[(v, ex, 10)]["test"]["dd"]),
                       "verschil vs RND [95%]": ci(X.boot_ci(x - xr, rng)),
                       "verschil vs SPY [95%]": ci(X.boot_ci(x - spy_w.loc[wks].to_numpy(), rng)),
                       "verschil vs QQQ [95%]": ci(X.boot_ci(x - qqq_w.loc[wks].to_numpy(), rng))})
    sp, qq = spy_w.loc[wks].to_numpy(), qqq_w.loc[wks].to_numpy()
    txt = ("# Donchian 20-breakout met filters tegen valse signalen (NASDAQ, dagbars)\n\n<!-- CONCLUSIE -->\n\n"
           f"Regels: `indicator_lab/week/donchian_filters_rules.md` (vooraf gecommit). {n_stocks} NASDAQ-aandelen (> $5, "
           "> $20M/dag); alleen aandelen die op 2026-10-23 genoteerd waren. Kosten 0,05% + $0,02 per kant.\n\n"
           "## 1. Elk filter apart op de trainjaren 2015-2022 (uitstap: 20-daagse laag)\n\n"
           + pd.DataFrame(t1).to_markdown(index=False)
           + "\n\n## 2. Test 2023-2026 per trade (één keer gemeten)\n\n" + pd.DataFrame(t2).to_markdown(index=False)
           + "\n\n## 3. Test 2023-2026 als rekening (10 posities, elk 1/10)\n\n" + pd.DataFrame(t3).to_markdown(index=False)
           + f"\n\nSPY 2023-2026: {((1 + sp).prod() ** (52 / len(sp)) - 1) * 100:.1f}% per jaar; QQQ: "
             f"{((1 + qq).prod() ** (52 / len(qq)) - 1) * 100:.1f}% per jaar.\n")
    with open(OUT, "w") as fh:
        fh.write(txt)
    with open(W.LOG, "a") as fh:
        fh.write(f"\n## Donchian-filters NASDAQ (results/donchian_filters.md): gehouden filters {kept or 'geen'}\n")
    print(txt)


if __name__ == "__main__":
    main()
