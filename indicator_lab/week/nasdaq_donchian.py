"""Donchian 20-day breakout on every liquid NASDAQ stock, exits DC (close below the prior 20-day low) and DC+10
(+10% target or DC). Rules: indicator_lab/week/nasdaq_donchian_rules.md (committed before the first run).

    python -m indicator_lab.week.nasdaq_donchian     # results/nasdaq_donchian.md (uses the popular.py input cache)
"""
from __future__ import annotations

import os
import pickle
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

from indicator_lab.h4.nasdaq_list import nasdaq
from indicator_lab.timing import regime as R
from indicator_lab.week import build as B
from indicator_lab.week import c6_followup as C
from indicator_lab.week import exit_test as X
from indicator_lab.week import popular as P
from indicator_lab.week import run as W
from indicator_lab.week import support_ema as SE
from indicator_lab.week import three_week as T

OUT = os.path.join(os.path.dirname(W.LOG), "nasdaq_donchian.md")
EXITS = {"dc": "verkopen na slot onder 20-daagse laag", "dc10": "+10% en eruit, anders 20-daagse-laag-regel"}
SLOTS = (10, 3)


def main():
    arrs, cands, elig = P.load()
    nq = set(nasdaq(set(arrs)))
    arrs = {t: a for t, a in arrs.items() if t in nq}
    elig = {t: e for t, e in elig.items() if t in nq}
    sig = [x for x in cands["C10"] if x[0] in nq]
    del cands
    spy, wk, _wf, week_last = T.calendar()
    spy_w = X.weekly(spy / spy.iloc[0], wk)
    qqq = R.load("QQQ").reindex(spy.index).ffill()
    qqq_w = X.weekly(qqq / qqq.iloc[0], wk)
    C._G.clear()
    C._G.update({"arrs": arrs, "days": spy.index, "wk": wk, "week_last": week_last,
                 "wl": lambda dt: week_last.get(wk.get(dt)), "cand": P.by_day(arrs, sig),
                 "rnd": SE.rnd_pool(arrs, elig, "UL")})
    print(f"{len(arrs)} NASDAQ stocks, {len(sig)} breakout signals", flush=True)
    tr_res, ac_res = {}, {}
    with ProcessPoolExecutor(4) as pool:
        for job, r in pool.map(C.trades, [(ex, part) for ex in EXITS for part in ("all", "test")]):
            tr_res[job] = r
            print(job, r["real"].get("n"), f"{r['real'].get('exp', np.nan) * 100:+.2f}%", flush=True)
        for job, r in pool.map(C.account, [(k, ex, sl) for sl in SLOTS for ex in EXITS for k in ("C6", "RND")]):
            ac_res[job] = r
            print(job, f"{r['test']['wk'] * 100:+.2f}%/wk", flush=True)
    with open(os.path.join(B.CACHE, "nasdaq_donchian_results.pkl"), "wb") as fh:
        pickle.dump((tr_res, ac_res, spy_w, qqq_w), fh)
    write(tr_res, ac_res, spy_w, qqq_w, len(arrs), len(sig))


def write(tr_res, ac_res, spy_w, qqq_w, n_stocks, n_sig):
    rng = np.random.default_rng(2026)
    pc = lambda x, d=1: "-" if x is None or np.isnan(x) else f"{x * 100:.{d}f}%"
    ci = lambda t: "-" if np.isnan(t[0]) else f"{t[0] * 100:+.2f}% [{t[1] * 100:+.2f}, {t[2] * 100:+.2f}]"
    rows = []
    for ex, name in EXITS.items():
        for part, pname in (("all", "2015-2026"), ("test", "2023-2026")):
            r = tr_res[(ex, part)]
            a, q, d = r["real"], r["rand"], r["diff"]
            rows.append({"uitstap": name, "periode": pname, "trades": a.get("n", 0),
                         "+10% geraakt": pc(a.get("hit_10pct", np.nan), 0), "winrate": pc(a.get("win", np.nan), 0),
                         "gem./trade": pc(a.get("exp", np.nan), 2), "PF": f"{a.get('pf', np.nan):.2f}",
                         "gem. dagen": f"{a.get('days', np.nan):.1f}",
                         "random: winrate / gem.": f"{pc(q.get('win', np.nan), 0)} / {pc(q.get('exp', np.nan), 2)}",
                         "verschil vs random [95%]": ci(d), "t": f"{d[3]:.2f}"})
    weeks_all = list(spy_w.index)
    weeks_test = [p for p in weeks_all if p.end_time > X.TRAIN_END]
    acc = []
    for sl in SLOTS:
        for ex, name in EXITS.items():
            r, rr = ac_res[("C6", ex, sl)], ac_res[("RND", ex, sl)]
            for pname, wks in (("2015-2026", weeks_all), ("2023-2026", weeks_test)):
                x = r["weekly"].reindex(wks).fillna(0).to_numpy()
                acc.append({"posities": sl, "uitstap": name, "periode": pname,
                            "CAGR": pc((1 + x).prod() ** (52 / len(x)) - 1),
                            "max daling": pc(r["dd_full"] if pname == "2015-2026" else r["test"]["dd"]),
                            "verschil vs RND [95%]": ci(X.boot_ci(x - rr["weekly"].reindex(wks).fillna(0).to_numpy(), rng)),
                            "verschil vs SPY [95%]": ci(X.boot_ci(x - spy_w.loc[wks].to_numpy(), rng)),
                            "verschil vs QQQ [95%]": ci(X.boot_ci(x - qqq_w.loc[wks].to_numpy(), rng))})
    bench = []
    for nm, w in (("SPY", spy_w), ("QQQ", qqq_w)):
        for pname, wks in (("2015-2026", weeks_all), ("2023-2026", weeks_test)):
            x = w.loc[wks].to_numpy()
            eq = np.cumprod(1 + x)
            bench.append({"index": nm, "periode": pname, "CAGR": pc((1 + x).prod() ** (52 / len(x)) - 1),
                          "max daling (weekbasis)": pc(float((eq / np.maximum.accumulate(eq) - 1).min()))})
    txt = ("# Donchian 20-breakout op alle liquide NASDAQ-aandelen\n\n<!-- CONCLUSIE -->\n\n"
           f"Regels: `indicator_lab/week/nasdaq_donchian_rules.md` (vooraf gecommit). {n_stocks} NASDAQ-aandelen "
           f"(> $5, > $20M/dag), {n_sig} breakout-signalen 2015-2026; alleen aandelen die op 2026-10-23 genoteerd waren. "
           "Kosten 0,05% + $0,02 per kant.\n\n## Per trade\n\n" + pd.DataFrame(rows).to_markdown(index=False)
           + "\n\n## Als rekening\n\n" + pd.DataFrame(acc).to_markdown(index=False)
           + "\n\n## Ter vergelijking: kopen en vasthouden\n\n" + pd.DataFrame(bench).to_markdown(index=False) + "\n")
    with open(OUT, "w") as fh:
        fh.write(txt)
    with open(W.LOG, "a") as fh:
        fh.write("\n## Donchian 20 op NASDAQ (results/nasdaq_donchian.md, branch claude/xom-donchian)\n")
    print(txt)


if __name__ == "__main__":
    main()
