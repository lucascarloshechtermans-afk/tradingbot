"""Volatility compression breakout on NASDAQ stocks (daily bars). Rules: indicator_lab/week/vcb_rules.md (committed first).

    python -m indicator_lab.week.vcb          # results/vcb.md (uses the popular.py input cache)
"""
from __future__ import annotations

import os
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

from indicator_lab.h4.nasdaq_list import nasdaq
from indicator_lab.timing import regime as R
from indicator_lab.week import build as B
from indicator_lab.week import c6_followup as C
from indicator_lab.week import donchian_filters as DF
from indicator_lab.week import exit_test as X
from indicator_lab.week import popular as P
from indicator_lab.week import run as W
from indicator_lab.week import support_ema as SE
from indicator_lab.week import three_week as T

OUT = os.path.join(os.path.dirname(W.LOG), "vcb.md")
VARS = {"base": "kale 20-daagse breakout", "V1": "compressie + breakout", "V2": "compressie + breakout + trend"}


def masks(arrs):
    out = {}
    for t, ar in arrs.items():
        c = pd.Series(ar["c"])
        bbw = 4 * c.rolling(20).std(ddof=0) / c.rolling(20).mean()
        q20 = bbw.rolling(252, min_periods=200).quantile(0.2)
        comp = (bbw <= q20).shift(1, fill_value=False).to_numpy()
        with np.errstate(invalid="ignore"):
            s50, s200 = B.sma(ar["c"], 50), B.sma(ar["c"], 200)
            trend = (ar["c"] > s200) & (s50 > s200)
        out[t] = {"comp": comp, "trend": trend}
    return out


def main():
    arrs, cands, elig = P.load()
    nq = set(nasdaq(set(arrs)))
    arrs = {t: a for t, a in arrs.items() if t in nq}
    elig = {t: e for t, e in elig.items() if t in nq}
    base = [x for x in cands["C10"] if x[0] in nq]
    del cands
    mk = masks(arrs)
    v1 = [x for x in base if mk[x[0]]["comp"][x[1]]]
    v2 = [x for x in v1 if mk[x[0]]["trend"][x[1]]]
    spy, wk, _wf, week_last = T.calendar()
    spy_w = X.weekly(spy / spy.iloc[0], wk)
    qqq = R.load("QQQ").reindex(spy.index).ffill()
    qqq_w = X.weekly(qqq / qqq.iloc[0], wk)
    C._G.clear()
    C._G.update({"arrs": arrs, "days": spy.index, "wk": wk, "week_last": week_last,
                 "wl": lambda dt: week_last.get(wk.get(dt)), "rnd": SE.rnd_pool(arrs, elig, "UL"),
                 "cands": {"base": P.by_day(arrs, base), "V1": P.by_day(arrs, v1), "V2": P.by_day(arrs, v2)}})
    jobs = [(v, ex, part) for v in VARS for ex in DF.EXITS for part in ("train", "test")]
    with ProcessPoolExecutor(4) as pool:
        tr = dict(pool.map(DF.tr_job, jobs))
        acc = dict(pool.map(DF.ac_job, [(v, ex, 10) for v in [*VARS, "RND"] for ex in DF.EXITS]))
    write(tr, acc, spy_w, qqq_w, len(arrs), {k: len(v) for k, v in (("base", base), ("V1", v1), ("V2", v2))})


def write(tr, acc, spy_w, qqq_w, n_stocks, n_sig):
    rng = np.random.default_rng(2026)
    pc = lambda x, d=1: "-" if x is None or np.isnan(x) else f"{x * 100:.{d}f}%"
    ci = lambda t: "-" if np.isnan(t[0]) else f"{t[0] * 100:+.2f}% [{t[1] * 100:+.2f}, {t[2] * 100:+.2f}]"
    rows = []
    for v, vn in VARS.items():
        for ex, exn in DF.EXITS.items():
            for part, pn in (("train", "2015-2022"), ("test", "2023-2026")):
                a, d = tr[(v, ex, part)]["real"], tr[(v, ex, part)]["diff"]
                rows.append({"variant": vn, "uitstap": exn, "periode": pn, "trades": a.get("n", 0),
                             "winrate": pc(a.get("win", np.nan), 0), "+10% geraakt": pc(a.get("hit_10pct", np.nan), 0),
                             "gem./trade": pc(a.get("exp", np.nan), 2), "PF": f"{a.get('pf', np.nan):.2f}",
                             "gem. dagen": f"{a.get('days', np.nan):.1f}", "verschil vs random [95%]": ci(d)})
    wks = [p for p in spy_w.index if p.end_time > X.TRAIN_END]
    accr = []
    for v, vn in VARS.items():
        for ex, exn in DF.EXITS.items():
            x = acc[(v, ex, 10)]["weekly"].reindex(wks).fillna(0).to_numpy()
            xr = acc[("RND", ex, 10)]["weekly"].reindex(wks).fillna(0).to_numpy()
            accr.append({"variant": vn, "uitstap": exn, "CAGR 2023-2026": pc((1 + x).prod() ** (52 / len(x)) - 1),
                         "max daling": pc(acc[(v, ex, 10)]["test"]["dd"]),
                         "verschil vs RND [95%]": ci(X.boot_ci(x - xr, rng)),
                         "verschil vs SPY [95%]": ci(X.boot_ci(x - spy_w.loc[wks].to_numpy(), rng)),
                         "verschil vs QQQ [95%]": ci(X.boot_ci(x - qqq_w.loc[wks].to_numpy(), rng))})
    sp, qq = spy_w.loc[wks].to_numpy(), qqq_w.loc[wks].to_numpy()
    txt = ("# Volatility compression breakout (NASDAQ, dagbars)\n\n<!-- CONCLUSIE -->\n\n"
           f"Regels: `indicator_lab/week/vcb_rules.md` (vooraf gecommit). {n_stocks} NASDAQ-aandelen; signalen 2015-2026: "
           f"kale breakout {n_sig['base']}, V1 {n_sig['V1']}, V2 {n_sig['V2']}. Kosten 0,05% + $0,02 per kant.\n\n"
           "## Per trade\n\n" + pd.DataFrame(rows).to_markdown(index=False)
           + "\n\n## Als rekening (10 posities, test 2023-2026)\n\n" + pd.DataFrame(accr).to_markdown(index=False)
           + f"\n\nSPY 2023-2026: {((1 + sp).prod() ** (52 / len(sp)) - 1) * 100:.1f}% per jaar; QQQ "
             f"{((1 + qq).prod() ** (52 / len(qq)) - 1) * 100:.1f}%.\n")
    with open(OUT, "w") as fh:
        fh.write(txt)
    print("done", flush=True)


if __name__ == "__main__":
    main()
