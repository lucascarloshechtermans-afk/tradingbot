"""Steps 2 and 3 of the win-rate study: stop variants, then exit variants (every target capped at +10%: the user's
"max 10% en eruit"). Inputs: the cached step-1 data (mfe.py). Costs, fills, gaps and splits as in mfe.py.

    python -m indicator_lab.week.variants step2
    python -m indicator_lab.week.variants step3

Step 2 (exit fixed: one target +3/+5/+7/+10% for the whole position, 10 trading days):
  stop variants  S0 standard (build.trade)          S1 below the nearest support zone if its strength >= 1.5
                 (zone low - 0.25 ATR), else 1.5 ATR    S2 / S3 / S4 = 1 / 1.5 / 2 x ATR below the fill
  each with a maximum risk of 5% or 8% (the stop is never further than that below the fill).
Step 3 (stop = the step-2 variant with the best TRAIN profit factor per setup):
  T1 +3 / +5 / +7%, sell 50 / 70 / 100% there, stop to break-even; the rest: T2 at +10%, or a trailing exit (close
  below the 10 EMA -> sell at that close; or a 2 ATR chandelier from the highest high), always capped at +10%, or only
  the time exit; time exit after 10 / 15 / 20 days.
Selection inside each step uses TRAIN only; the test numbers are reported next to it. The random control (20 runs,
same dates, same rules) is computed for every reported top configuration. Every combination is counted.
"""
from __future__ import annotations

import os
import pickle
import sys

import numpy as np
import pandas as pd

from indicator_lab.week import build as B
from indicator_lab.week import mfe as M
from indicator_lab.week import run as W

try:
    from numba import njit
except ImportError:
    def njit(*a, **k):
        return (lambda f: f) if not a or not callable(a[0]) else a[0]

OUT2 = os.path.join(os.path.dirname(W.LOG), "step2_stops.md")
OUT3 = os.path.join(os.path.dirname(W.LOG), "step3_exits.md")
STOPS = [(sv, cap) for sv in ("S0", "S1", "S2", "S3", "S4") for cap in (0.05, 0.08)]
CAP = 0.10


@njit(cache=True)
def run_exit(o, h, lo, c, e10, a, d, fill, stop, t1, frac, rest, hold):
    """Fractions sold at prices; returns (net return, bars, t1 hit). rest: 0 = T2 at +10%, 1 = EMA10 trail,
    2 = 2 ATR chandelier, 3 = time only (all remainders capped at +10%)."""
    n = len(c)
    buy = (fill + 0.02) * 1.0005
    left = 1.0
    got = 0.0
    half = False
    hh = fill
    t2 = fill * 1.10
    for k in range(hold):
        day = d + k
        if day >= n:
            got += left * (c[n - 1] - 0.02) * 0.9995
            return got / buy - 1, k, half
        op = fill if k == 0 else o[day]
        if lo[day] <= stop:
            px = stop if k == 0 else min(op, stop)
            got += left * (px - 0.02) * 0.9995
            return got / buy - 1, k + 1, half
        newstop = stop
        if not half and h[day] >= t1:
            px = t1 if k == 0 else max(op, t1)
            sell = min(left, frac)
            got += sell * (px - 0.02) * 0.9995
            left -= sell
            half = True
            newstop = max(stop, fill)
            if left <= 1e-9:
                return got / buy - 1, k + 1, half
        if half and h[day] >= t2:
            px = t2 if k == 0 else max(op, t2)
            got += left * (px - 0.02) * 0.9995
            return got / buy - 1, k + 1, half
        hh = max(hh, h[day])
        if half and rest == 1 and c[day] < e10[day]:
            got += left * (c[day] - 0.02) * 0.9995
            return got / buy - 1, k + 1, half
        if half and rest == 2:
            newstop = max(newstop, hh - 2.0 * a[day])
        if k == hold - 1:
            got += left * (c[day] - 0.02) * 0.9995
            return got / buy - 1, k + 1, half
        stop = newstop
    return got / buy - 1, hold, half


def stop_price(variant, cap, fill, anchor, atr, sup_lo, sup_str):
    if variant == "S0":
        st = M.std_stop(fill, anchor, atr)
    elif variant == "S1":
        st = sup_lo - 0.25 * atr if sup_str >= 1.5 and np.isfinite(sup_lo) and sup_lo < fill else fill - 1.5 * atr
    else:
        st = fill - {"S2": 1.0, "S3": 1.5, "S4": 2.0}[variant] * atr
    return max(st, fill * (1 - cap))


def entries(arrs, sigs, sid):
    """[(ticker, s, d, fill, anchor, split)] for a setup."""
    out = []
    for t, per in sigs.items():
        ar = arrs[t]
        for s, etype, elevel, anchor in per[sid]:
            d, fill = M.entry(ar["o"], ar["h"], s, etype, elevel)
            if d is None or d + 20 > len(ar["c"]) or not (fill > 0 and ar["atr"][s] > 0):
                continue
            out.append((t, s, d, fill, anchor, "train" if ar["idx"][s] <= M.TRAIN_END else "test", ar["idx"][s]))
    return out


def evaluate(arrs, ents, stop_v, cap, t1, frac, rest, hold) -> dict:
    res = {"train": [], "test": []}
    for t, s, d, fill, anchor, part, _ in ents:
        ar = arrs[t]
        st = stop_price(stop_v, cap, fill, anchor, ar["atr"][s], ar["sup_lo"][s], ar["sup_str"][s])
        r, bars, _ = run_exit(ar["o"], ar["h"], ar["l"], ar["c"], ar["e10"], ar["atr"], d, fill, st,
                                fill * (1 + t1), frac, rest, hold)
        res[part].append((r, bars, 1 - st / fill))
    return {p: stats(v) for p, v in res.items()}


def stats(v) -> dict:
    if not v:
        return {"n": 0}
    a = np.array(v)
    r = a[:, 0]
    w, lz = r[r > 0], r[r <= 0]
    top = np.sort(r)[::-1]
    k5 = max(1, len(r) // 20)
    rest = top[k5:]
    pf = w.sum() / -lz.sum() if lz.sum() < 0 else np.inf
    pf95 = rest[rest > 0].sum() / -rest[rest <= 0].sum() if rest[rest <= 0].sum() < 0 else np.inf
    return {"n": len(r), "win": (r > 0).mean(), "pf": pf, "pf_ex5": pf95, "exp": r.mean(), "exp_R": (r / a[:, 2]).mean(),
            "avg_win": w.mean() if len(w) else np.nan, "avg_loss": lz.mean() if len(lz) else np.nan, "bars": a[:, 1].mean()}


def random_control(arrs, by_date, ents, stop_v, cap, t1, frac, rest, hold, runs=20, seed=11) -> dict:
    rng = np.random.default_rng(seed)
    wins, pfs = [], []
    for _ in range(runs):
        v = []
        for *_, part, day in ents:
            if part != "test":
                continue
            pool = by_date.get(day)
            if not pool:
                continue
            t, s = pool[rng.integers(len(pool))]
            ar = arrs[t]
            if s + 21 > len(ar["c"]):
                continue
            d, fill = s + 1, ar["o"][s + 1]
            if not (fill > 0 and ar["atr"][s] > 0):
                continue
            st = stop_price(stop_v, cap, fill, ar["sup_lo"][s], ar["atr"][s], ar["sup_lo"][s], ar["sup_str"][s])
            r, bars, _ = run_exit(ar["o"], ar["h"], ar["l"], ar["c"], ar["e10"], ar["atr"], d, fill, st,
                                  fill * (1 + t1), frac, rest, hold)
            v.append((r, bars, 1 - st / fill))
        st_ = stats(v)
        wins.append(st_["win"])
        pfs.append(st_["pf"])
    return {"win": float(np.mean(wins)), "pf": float(np.mean(pfs))}


def load():
    with open(os.path.join(B.CACHE, "step1_inputs.pkl"), "rb") as fh:
        arrs, sigs, elig = pickle.load(fh)
    for ar in arrs.values():
        ar["e10"] = pd.Series(ar["c"]).ewm(span=10, adjust=False, min_periods=10).mean().to_numpy()
    by_date: dict = {}
    for t, ix in elig.items():
        idx = arrs[t]["idx"]
        for i in ix:
            by_date.setdefault(idx[i], []).append((t, int(i)))
    return arrs, sigs, by_date


def fmt(m) -> dict:
    if m["n"] == 0:
        return {"trades": 0}
    return {"trades": m["n"], "winrate": f"{m['win'] * 100:.0f}%", "PF": f"{m['pf']:.2f}", "PF zonder top 5%": f"{m['pf_ex5']:.2f}",
            "exp.": f"{m['exp'] * 100:+.2f}%", "exp. (R)": f"{m['exp_R']:+.2f}", "gem. winst": f"{m['avg_win'] * 100:+.1f}%",
            "gem. verlies": f"{m['avg_loss'] * 100:+.1f}%", "dagen": f"{m['bars']:.1f}"}


def step2():
    arrs, sigs, by_date = load()
    lines = ["# Stap 2 — stop-varianten (één doel voor de hele positie, 10 dagen)\n\n",
             (f"Combinaties: {len(B.NAMES)} setups x {len(STOPS)} stops x 4 doelen = {len(B.NAMES) * len(STOPS) * 4}. "
              "Keuze per setup op TRAIN-PF; test ernaast. Random = 20 runs, zelfde datums en regels.\n\n")]
    best = {}
    for sid in B.NAMES:
        ents = entries(arrs, sigs, sid)
        rows = []
        cand = []
        for sv, cap in STOPS:
            for t1 in (0.03, 0.05, 0.07, 0.10):
                m = evaluate(arrs, ents, sv, cap, t1, 1.0, 3, 10)
                cand.append(((sv, cap, t1), m))
                rows.append({"stop": f"{sv} max {cap * 100:.0f}%", "doel": f"+{t1 * 100:.0f}%",
                             "train winrate": f"{m['train']['win'] * 100:.0f}%", "train PF": f"{m['train']['pf']:.2f}",
                             **{f"test {k}": v for k, v in fmt(m["test"]).items()}})
        (sv, cap, t1), m = max(cand, key=lambda x: x[1]["train"]["pf"])
        rnd = random_control(arrs, by_date, ents, sv, cap, t1, 1.0, 3, 10)
        best[sid] = {"stop": sv, "cap": cap, "t1": t1, "train": m["train"], "test": m["test"], "random": rnd}
        lines.append(f"## {sid} {B.NAMES[sid]} — beste op train: {sv} max {cap * 100:.0f}%, doel +{t1 * 100:.0f}% → test "
                     f"winrate {m['test']['win'] * 100:.0f}%, PF {m['test']['pf']:.2f} (random {rnd['win'] * 100:.0f}% / "
                     f"{rnd['pf']:.2f})\n\n" + pd.DataFrame(rows).to_markdown(index=False) + "\n\n")
        print(sid, sv, cap, t1, f"test win {m['test']['win']:.2f} pf {m['test']['pf']:.2f} | random {rnd['win']:.2f} {rnd['pf']:.2f}", flush=True)
    with open(OUT2, "w") as fh:
        fh.write("".join(lines))
    with open(os.path.join(B.CACHE, "step2_best.pkl"), "wb") as fh:
        pickle.dump(best, fh)


def step3():
    arrs, sigs, by_date = load()
    with open(os.path.join(B.CACHE, "step2_best.pkl"), "rb") as fh:
        best2 = pickle.load(fh)
    grid = [(t1, frac, rest, hold) for t1 in (0.03, 0.05, 0.07) for frac in (0.5, 0.7, 1.0)
            for rest in ((0, 1, 2, 3) if frac < 1 else (3,)) for hold in (10, 15, 20)]
    rest_nl = {0: "rest op +10%", 1: "rest: trailing EMA10 (max +10%)", 2: "rest: trailing 2 ATR (max +10%)", 3: "rest: tijdsexit (max +10%)"}
    lines = ["# Stap 3 — exit-varianten (stop = beste uit stap 2 per setup; alles max +10%)\n\n",
             f"Combinaties: {len(B.NAMES)} setups x {len(grid)} exits = {len(B.NAMES) * len(grid)}. Keuze op TRAIN-PF.\n\n"]
    top_all = []
    for sid in B.NAMES:
        b = best2[sid]
        ents = entries(arrs, sigs, sid)
        rows = []
        for t1, frac, rest, hold in grid:
            m = evaluate(arrs, ents, b["stop"], b["cap"], t1, frac, rest, hold)
            rows.append(((t1, frac, rest, hold), m))
        rows.sort(key=lambda x: -x[1]["train"]["pf"])
        out = []
        for (t1, frac, rest, hold), m in rows[:5]:
            rnd = random_control(arrs, by_date, ents, b["stop"], b["cap"], t1, frac, rest, hold)
            out.append({"T1": f"+{t1 * 100:.0f}%", "verkoop op T1": f"{frac * 100:.0f}%", "rest": rest_nl[rest] if frac < 1 else "–",
                        "dagen max": hold, "train winrate": f"{m['train']['win'] * 100:.0f}%", "train PF": f"{m['train']['pf']:.2f}",
                        **{f"test {k}": v for k, v in fmt(m["test"]).items()},
                        "random winrate / PF": f"{rnd['win'] * 100:.0f}% / {rnd['pf']:.2f}"})
            top_all.append((sid, b, (t1, frac, rest, hold), m, rnd))
        lines.append(f"## {sid} {B.NAMES[sid]} (stop {b['stop']} max {b['cap'] * 100:.0f}%) — top 5 op train\n\n"
                     + pd.DataFrame(out).to_markdown(index=False) + "\n\n")
        print(sid, "done", flush=True)
    ok = [x for x in top_all if x[3]["test"]["n"] >= 200 and x[3]["test"]["win"] >= 0.70 and x[3]["test"]["pf"] >= 1.3
          and x[3]["test"]["exp"] > 0 and x[3]["test"]["pf_ex5"] >= 1.2
          and x[3]["test"]["win"] - x[4]["win"] >= 0.10 and x[3]["test"]["pf"] - x[4]["pf"] >= 0.2]
    lines.append(f"## Varianten die ALLE eisen halen (70% winrate, PF >= 1,3, exp > 0, PF zonder top 5% >= 1,2, >= 200 "
                 f"trades, 10 pp en 0,2 PF beter dan random): {len(ok)}\n")
    with open(OUT3, "w") as fh:
        fh.write("".join(lines))
    with open(os.path.join(B.CACHE, "step3_top.pkl"), "wb") as fh:
        pickle.dump(top_all, fh)


if __name__ == "__main__":
    {"step2": step2, "step3": step3}[sys.argv[1]]()
