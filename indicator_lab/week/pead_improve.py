"""Step 5 of the post-earnings gap study: up to 5 pre-declared one-change improvements, a fair random control,
a yearly walk-forward and a multiple-testing correction.

    python -m indicator_lab.week.pead_improve       # rebuilds the inputs (all EPS data fetched so far), then runs

Fixed before the run:
  Base = the step 1-4 variant (universe x EPS rule x exit x holding period) with the highest TRAIN profit factor,
  re-measured on the rebuilt inputs.
  Changes, in this order, each added on top of the current best and kept only when the TRAIN profit factor rises and at
  least 50% of the base's train trades remain:
    I1 strong beat: EPS surprise >= +10% of |estimate| (|estimate| >= $0.05)
    I2 strong close: gap-day close in the top 25% of its range
    I3 trend: gap-day close > the stock's SMA200
    I4 bigger gap: open >= 8% above the previous close
    I5 more volume: >= 3 x the 50-day average volume
  Fair random control: each random trade gets the SAME percentage stop distance as the setup trade of that date
  (20 runs, same dates, same universe, same exit and holding period).
  Requirements on the test (2023-2026): expectancy > 0, PF >= 1.3, PF above the random control; reported too: PF
  without the best 5%, max drawdown, yearly PF (walk-forward over 2015-2026), Bonferroni t-test over all variants
  of this study (54 + the changes tried here).
"""
from __future__ import annotations

import os
import pickle

import numpy as np
import pandas as pd
from scipy import stats as SS

from indicator_lab.week import build as B
from indicator_lab.week import pead_week as P
from indicator_lab.week import run as W

OUT = os.path.join(os.path.dirname(W.LOG), "pead_improve.md")
CHANGES = [("I1", "winstverrassing >= +10%", lambda e: e["surprise_pct"] is not None and e["surprise_pct"] >= 0.10),
           ("I2", "slot in bovenste 25% van de dag", lambda e: e["ibs"] >= 0.75),
           ("I3", "slot boven SMA200", lambda e: e["above200"]),
           ("I4", "gap >= 8%", lambda e: e["gap"] >= 0.08),
           ("I5", "volume >= 3x", lambda e: e["vol_x"] >= 3)]


def variant(arrs, events, adr_min, eps, mode, hold, extra) -> dict:
    sel = [e for e in events if all(f(e) for f in extra)]
    return P.run_variant(arrs, sel, adr_min, eps, mode, hold)


def fair_random(arrs, pool, trades_test, dates_test, mode, hold, runs=20, seed=9) -> dict:
    rng = np.random.default_rng(seed)
    risks = [x[2] for x in trades_test]
    wins, pfs = [], []
    for _ in range(runs):
        v = []
        for day, rk in zip(dates_test, risks):
            p = pool.get(day)
            if not p:
                continue
            t, s = p[rng.integers(len(p))]
            r = P.simulate(arrs[t], s, mode, hold, risk_pct=rk)
            if r is not None:
                v.append(r)
        st = P.stats(v)
        wins.append(st.get("win", np.nan))
        pfs.append(st.get("pf", np.nan))
    return {"win": float(np.nanmean(wins)), "pf": float(np.nanmean(pfs))}


def main():
    cache = os.path.join(B.CACHE, "pead_week_inputs.pkl")
    arrs, events, pool = P.load()                       # rebuild: all EPS data fetched so far
    with open(cache, "wb") as fh:
        pickle.dump((arrs, events, pool), fh)
    eps_cov = np.mean([e["surprise"] is not None for e in events])
    grid = [(a, eps, mi, hold) for a in P.ADRS for eps in ("any", "surprise > 0") for mi in range(3) for hold in P.HOLDS]
    scored = []
    for g in grid:
        v = variant(arrs, events, *g, [])
        scored.append((P.stats(v["train"]).get("pf", 0), g))
    base_pf, base = max(scored)
    lines = [(f"# Post-earnings gap — stap 5 (verbeteringen, eerlijke random, walk-forward)\n\nEvents: {len(events)}; "
              f"met EPS-data: {eps_cov * 100:.0f}%. Basis (hoogste train-PF van de 54): ADR > {base[0]:.0f}%, EPS {base[1]}, "
              f"exit {P.EXITS[base[2]]}, {base[3]} dagen (train-PF {base_pf:.2f}).\n\n")]
    v0 = variant(arrs, events, *base, [])
    n0 = P.stats(v0["train"])["n"]
    kept, best_pf, rows = [], base_pf, []
    for code, name, f in CHANGES:
        trial = [*kept, f]
        v = variant(arrs, events, *base, trial)
        tr, te = P.stats(v["train"]), P.stats(v["test"])
        keep = tr.get("pf", 0) > best_pf and tr["n"] >= 0.5 * n0
        rows.append({"wijziging": f"{code} {name}", "train trades": tr["n"], "train PF": f"{tr.get('pf', 0):.2f}",
                     "test trades": te["n"], "test PF": f"{te.get('pf', 0):.2f}", "test exp.": f"{te.get('exp', 0) * 100:+.2f}%",
                     "gehouden": "ja" if keep else "nee"})
        if keep:
            kept.append(f)
            best_pf = tr["pf"]
    lines.append("## Verbeteringen (één tegelijk, gekozen op train)\n\n" + pd.DataFrame(rows).to_markdown(index=False) + "\n\n")
    final = variant(arrs, events, *base, kept)
    tr, te = P.stats(final["train"]), P.stats(final["test"])
    rnd = fair_random(arrs, pool[base[0]], final["test"], final["dates"]["test"], base[2], base[3])
    allv = final["train"] + final["test"]
    years = pd.Series([x[0] for x in allv], index=[x[3].year for x in allv])
    yearly = years.groupby(level=0).agg(lambda s: s[s > 0].sum() / -s[s <= 0].sum() if (s <= 0).any() else np.inf)
    ycount = years.groupby(level=0).size()
    rr = np.array([x[0] for x in final["test"]])
    tstat = rr.mean() / rr.std(ddof=1) * np.sqrt(len(rr)) if len(rr) > 1 else np.nan
    total = 54 + len(CHANGES)
    crit = SS.norm.ppf(1 - 0.05 / (2 * total))
    ok = te["n"] >= 100 and te["exp"] > 0 and te["pf"] >= 1.3 and te["pf"] > rnd["pf"]
    names = [n for (c, n, f) in CHANGES if f in kept]
    lines.append(f"## Eindvariant: basis + {', '.join(names) or 'geen extra filters'}\n\n" + pd.DataFrame([
        {"set": "train", "trades": tr["n"], "winrate": f"{tr['win'] * 100:.0f}%", "PF": f"{tr['pf']:.2f}",
         "PF zonder top 5%": f"{tr['pf_ex5']:.2f}", "exp.": f"{tr['exp'] * 100:+.2f}%", "exp. (R)": f"{tr['exp_R']:+.2f}",
         "max DD": f"{tr['dd'] * 100:.1f}%", "dagen": f"{tr['bars']:.1f}"},
        {"set": "test", "trades": te["n"], "winrate": f"{te['win'] * 100:.0f}%", "PF": f"{te['pf']:.2f}",
         "PF zonder top 5%": f"{te['pf_ex5']:.2f}", "exp.": f"{te['exp'] * 100:+.2f}%", "exp. (R)": f"{te['exp_R']:+.2f}",
         "max DD": f"{te['dd'] * 100:.1f}%", "dagen": f"{te['bars']:.1f}"}]).to_markdown(index=False)
        + f"\n\nEerlijke random (zelfde stopafstand): winrate {rnd['win'] * 100:.0f}%, PF {rnd['pf']:.2f}. "
        f"t-waarde gemiddelde testtrade {tstat:.2f} (Bonferroni-grens bij {total} varianten: {crit:.2f}).\n\n"
        "### Walk-forward per jaar (PF en aantal trades)\n\n"
        + pd.DataFrame({"jaar": yearly.index, "PF": yearly.round(2).values, "trades": ycount.values}).to_markdown(index=False)
        + f"\n\n**Oordeel: {'GOEDGEKEURD' if ok else 'NIET GOEDGEKEURD'}** (eisen: exp > 0, PF >= 1,3, PF > random).\n")
    with open(OUT, "w") as fh:
        fh.write("".join(lines))
    with open(W.LOG, "a") as fh:
        fh.write(f"\n## Post-earnings gap stap 5 (results/pead_improve.md): {len(CHANGES)} extra varianten; eindvariant test "
                 f"PF {te['pf']:.2f}, exp {te['exp'] * 100:+.2f}%, {te['n']} trades, random-PF {rnd['pf']:.2f}: "
                 f"{'GOEDGEKEURD' if ok else 'niet goedgekeurd'}\n")
    print("".join(lines))


if __name__ == "__main__":
    main()
