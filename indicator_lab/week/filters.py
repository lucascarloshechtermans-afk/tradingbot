"""Steps 4 and 5 of the win-rate study: filters on setups 2 and 6 (their step-3 exits, chosen on train), each filter
on its own, then the train-helpful ones combined, then setups 2 + 6 together; random control with the SAME filters;
yearly walk-forward of the final variant; multiple-testing correction over every combination of the study.

    python -m indicator_lab.week.filters

Filters (fixed before the run):
  F1 market regime: SPY > SMA50 and EMA20 > EMA50 on the signal day
  F2 no entry when the signal day rose more than 2 ATR (close - previous close > 2 x ATR)
  F3 room to the nearest STRONG resistance (sr.py, strength >= 2) >= 1.5 x the distance to T1 (none above = room ok)
  F4 nearest support zone strength >= 2
A filter is kept for the combination when it raises the TRAIN profit factor and keeps >= 50% of the train trades.
Requirements (all on test): win rate >= 70%, expectancy > 0, PF >= 1.3, PF without the best 5% >= 1.2, >= 200 trades,
win rate and PF at least 10 points / 0.2 above the random control (20 runs, same dates, same filters, same exits).
Multiple testing: Bonferroni over all combinations of the study (step 1 + 2 + 3 + this step): the best variant's
t-statistic of the mean trade return must exceed the Bonferroni critical value at 5% family-wise.
"""
from __future__ import annotations

import os
import pickle

import numpy as np
import pandas as pd
from scipy import stats as SS

from indicator_lab import sr
from indicator_lab.timing import regime as R
from indicator_lab.twenty import data20
from indicator_lab.week import build as B
from indicator_lab.week import run as W
from indicator_lab.week import variants as V

OUT = os.path.join(os.path.dirname(W.LOG), "step4_filters.md")
PRIOR_COMBOS = 240 + 400 + 810
FNAMES = {"F1": "marktregime", "F2": "geen rally > 2 ATR", "F3": "ruimte >= 1,5x T1", "F4": "supportsterkte >= 2"}


def augment(arrs):
    """Add res_strong and the SPY regime flag to the cached arrays (one more pass over the data)."""
    data20.final_mode()
    spy = R.load("SPY")
    up = (spy > spy.rolling(50).mean()) & (spy.ewm(span=20, adjust=False).mean() > spy.ewm(span=50, adjust=False).mean())
    for j, (t, ar) in enumerate(arrs.items()):
        df = data20.load(t)
        df = df[(df[["open", "high", "low", "close"]] > 0).all(axis=1) & (df.index <= B.END)]
        lv = sr.levels(df)
        assert len(df) == len(ar["c"])
        ar["res_strong"] = lv["res_strong"].to_numpy()
        ar["reg"] = up.reindex(df.index).ffill().fillna(False).to_numpy(bool)
        if j % 400 == 0:
            print(f"augment {j}/{len(arrs)}", flush=True)


def passes(ar, s, fill, t1, flt) -> bool:
    if "F1" in flt and not ar["reg"][s]:
        return False
    if "F2" in flt and s > 0 and ar["c"][s] - ar["c"][s - 1] > 2 * ar["atr"][s]:
        return False
    if "F3" in flt:
        rs_ = ar["res_strong"][s]
        if np.isfinite(rs_) and rs_ / fill - 1 < 1.5 * t1:
            return False
    return not ("F4" in flt and not ar["sup_str"][s] >= 2)


def run(arrs, ents, cfg, flt) -> dict:
    sv, cap, t1, frac, rest, hold = cfg
    res = {"train": [], "test": []}
    for t, s, d, fill, anchor, part, day in ents:
        ar = arrs[t]
        if not passes(ar, s, fill, t1, flt):
            continue
        st = V.stop_price(sv, cap, fill, anchor, ar["atr"][s], ar["sup_lo"][s], ar["sup_str"][s])
        r, bars, _ = V.run_exit(ar["o"], ar["h"], ar["l"], ar["c"], ar["e10"], ar["atr"], d, fill, st,
                                fill * (1 + t1), frac, rest, hold)
        res[part].append((r, bars, 1 - st / fill, day))
    return res


def stats(v):
    return V.stats([x[:3] for x in v])


def random_ctrl(arrs, by_date, ents, cfg, flt, runs=20, seed=5):
    sv, cap, t1, frac, rest, hold = cfg
    rng = np.random.default_rng(seed)
    out = []
    dates = [e[6] for e in ents if e[5] == "test" and passes(arrs[e[0]], e[1], e[3], t1, flt)]
    for _ in range(runs):
        v = []
        for day in dates:
            pool = by_date.get(day)
            if not pool:
                continue
            for _try in range(50):                    # a random stock of that day that passes the same filters
                t, s = pool[rng.integers(len(pool))]
                ar = arrs[t]
                if s + 21 > len(ar["c"]):
                    continue
                fill = ar["o"][s + 1]
                if fill > 0 and ar["atr"][s] > 0 and passes(ar, s, fill, t1, flt):
                    break
            else:
                continue
            st = V.stop_price(sv, cap, fill, ar["sup_lo"][s], ar["atr"][s], ar["sup_lo"][s], ar["sup_str"][s])
            r, bars, _ = V.run_exit(ar["o"], ar["h"], ar["l"], ar["c"], ar["e10"], ar["atr"], s + 1, fill, st,
                                    fill * (1 + t1), frac, rest, hold)
            v.append((r, bars, 1 - st / fill))
        out.append(V.stats(v))
    return {"win": float(np.mean([x["win"] for x in out])), "pf": float(np.mean([x["pf"] for x in out]))}


def maxdd(v) -> float:
    """Account of 10 positions of 10% each, trades in entry order (no capacity limit modelled beyond the 10%)."""
    if not v:
        return np.nan
    r = np.array([x[0] for x in sorted(v, key=lambda x: x[3])])
    eq = np.cumprod(1 + 0.1 * r)
    return float((eq / np.maximum.accumulate(eq) - 1).min())


def main():
    arrs, sigs, by_date = V.load()
    augment(arrs)
    with open(os.path.join(B.CACHE, "step3_top.pkl"), "rb") as fh:
        top3 = pickle.load(fh)
    cfgs = {}
    for sid, b, (t1, frac, rest, hold), m, _ in top3:      # first entry per setup = best on train
        if sid in (2, 6) and sid not in cfgs:
            cfgs[sid] = (b["stop"], b["cap"], t1, frac, rest, hold)
    ents = {sid: V.entries(arrs, sigs, sid) for sid in (2, 6)}
    lines = ["# Stap 4 en 5 — filters en combinatie (setups 2 en 6, exits uit stap 3)\n\n"]
    log = []
    n_combos = 0
    finals = []
    for sid in (2, 6):
        cfg = cfgs[sid]
        base = run(arrs, ents[sid], cfg, ())
        bt = stats(base["train"])
        helped = []
        rows = []
        for flt in [(), ("F1",), ("F2",), ("F3",), ("F4",)]:
            r = run(arrs, ents[sid], cfg, flt)
            n_combos += 1
            mt, me = stats(r["train"]), stats(r["test"])
            if flt and mt["pf"] > bt["pf"] and mt["n"] >= 0.5 * bt["n"]:
                helped.append(flt[0])
            rows.append((flt, mt, me, r))
        if helped:
            flt = tuple(helped)
            r = run(arrs, ents[sid], cfg, flt)
            n_combos += 1
            rows.append((flt, stats(r["train"]), stats(r["test"]), r))
        best = max(rows, key=lambda x: x[1]["pf"])
        finals.append((sid, cfg, best))
        tab = []
        for flt, mt, me, r in rows:
            tab.append({"filters": " + ".join(FNAMES[f] for f in flt) or "geen", "train trades": mt["n"],
                        "train winrate": f"{mt['win'] * 100:.0f}%", "train PF": f"{mt['pf']:.2f}",
                        **{f"test {k}": v for k, v in V.fmt(me).items()}})
            log.append((sid, flt, mt, me))
        lines.append(f"## Setup {sid} {B.NAMES[sid]} — exit {cfg}\n\nFilters die op train hielpen: "
                     f"{', '.join(FNAMES[f] for f in helped) or 'geen'}.\n\n" + pd.DataFrame(tab).to_markdown(index=False) + "\n\n")
        print(sid, "done", helped, flush=True)
    # setups 2 + 6 together, each with its own exit and its chosen filters (all signals, as in steps 1-3)
    comb = {"train": [], "test": []}
    for sid, cfg, (flt, *_rest) in finals:
        r = run(arrs, ents[sid], cfg, flt)
        for part in comb:
            comb[part] += [(*x, sid) for x in r[part]]
    n_combos += 1
    comb_stats = {p: stats(v) for p, v in comb.items()}
    lines.append("## Setups 2 + 6 samen (elk met eigen exit en filters)\n\n"
                 + pd.DataFrame([{"set": p, **V.fmt(comb_stats[p])} for p in comb]).to_markdown(index=False) + "\n\n")
    # final candidate = best test-eligible by TRAIN PF among the two finals and the combination
    cands = [(f"setup {sid}, {'+'.join(flt) or 'geen filters'}", sid, cfg, flt, run(arrs, ents[sid], cfg, flt))
             for sid, cfg, (flt, *_r) in finals]
    summary = []
    total = PRIOR_COMBOS + n_combos
    crit = SS.norm.ppf(1 - 0.05 / (2 * total))
    for name, sid, cfg, flt, r in cands:
        mt, me = stats(r["train"]), stats(r["test"])
        rnd = random_ctrl(arrs, by_date, ents[sid], cfg, flt)
        rr = np.array([x[0] for x in r["test"]])
        tstat = rr.mean() / rr.std(ddof=1) * np.sqrt(len(rr)) if len(rr) > 1 else np.nan
        years = pd.Series([x[0] for x in r["train"] + r["test"]],
                          index=[x[3].year for x in r["train"] + r["test"]])
        wf = years.groupby(level=0).apply(lambda s: s[s > 0].sum() / -s[s <= 0].sum() if (s <= 0).any() else np.inf)
        ok = (me["n"] >= 200 and me["win"] >= 0.70 and me["exp"] > 0 and me["pf"] >= 1.3 and me["pf_ex5"] >= 1.2
              and me["win"] - rnd["win"] >= 0.10 and me["pf"] - rnd["pf"] >= 0.2 and tstat > crit)
        reasons = [txt for cond, txt in ((me["win"] < 0.70, f"winrate {me['win'] * 100:.0f}% < 70%"),
                                         (me["pf"] < 1.3, f"PF {me['pf']:.2f} < 1,3"),
                                         (me["pf_ex5"] < 1.2, f"PF zonder top 5% {me['pf_ex5']:.2f} < 1,2"),
                                         (me["win"] - rnd["win"] < 0.10, f"winrate maar {(me['win'] - rnd['win']) * 100:+.0f} pp vs random"),
                                         (me["pf"] - rnd["pf"] < 0.2, f"PF maar {me['pf'] - rnd['pf']:+.2f} vs random"),
                                         (not tstat > crit, f"t = {tstat:.1f} < Bonferroni-grens {crit:.1f}")) if cond]
        summary.append({"variant": name, "test trades": me["n"], "winrate": f"{me['win'] * 100:.0f}%", "PF": f"{me['pf']:.2f}",
                        "PF zonder top 5%": f"{me['pf_ex5']:.2f}", "exp.": f"{me['exp'] * 100:+.2f}%", "exp. (R)": f"{me['exp_R']:+.2f}",
                        "houdtijd": f"{me['bars']:.1f} d", "max DD (10x10%)": f"{maxdd(r['test']) * 100:.1f}%",
                        "random winrate / PF": f"{rnd['win'] * 100:.0f}% / {rnd['pf']:.2f}",
                        "train winrate / PF": f"{mt['win'] * 100:.0f}% / {mt['pf']:.2f}",
                        "jaren met PF > 1": f"{(wf > 1).sum()} / {len(wf)}",
                        "oordeel": "GOEDGEKEURD" if ok else "AFGEWEZEN: " + "; ".join(reasons)})
    lines.append(f"## Eindtabel (test 2023-2026)\n\nTotaal geteste combinaties in de winrate-studie: {total}; "
                 f"Bonferroni-grens (5% familywise, tweezijdig) voor de t-waarde van de gemiddelde trade: {crit:.2f}.\n\n"
                 + pd.DataFrame(summary).to_markdown(index=False) + "\n")
    with open(OUT, "w") as fh:
        fh.write("".join(lines))
    with open(W.LOG, "a") as fh:
        fh.write(f"\n## Winrate-studie stap 4 en 5 (indicator_lab/week/filters.py; results/step4_filters.md)\n\n"
                 f"{n_combos} extra combinaties (totaal {total}).\n\n" + pd.DataFrame(summary).to_markdown(index=False) + "\n")
    print("".join(lines[-1:]))


if __name__ == "__main__":
    main()
