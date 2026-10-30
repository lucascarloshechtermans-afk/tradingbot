"""The user's strategy: support zone touched, daily close above the zone, a tap of an EMA (50/100/200) above the zone with
a close through it, low RSI. Rules: indicator_lab/week/support_ema_rules.md (committed before the first run).

    python -m indicator_lab.week.support_ema         # results/support_ema.md (inputs cached in /tmp)
"""
from __future__ import annotations

import os
import pickle
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

from indicator_lab import sr
from indicator_lab.twenty import data20
from indicator_lab.week import build as B
from indicator_lab.week import exit_test as X
from indicator_lab.week import run as W
from indicator_lab.week import three_week as T

OUT = os.path.join(os.path.dirname(W.LOG), "support_ema.md")
CACHE = os.path.join(B.CACHE, "support_ema_inputs.pkl")
UNIVS = {"U4": "ADR > 4% (zoals de vorige tests)", "UL": "alle liquide aandelen (> $5, > $20M/dag)"}
EMAS = {"E1": (50, 100, 200), "E2": (100, 200)}
RSIS = (30, 35, 40)
RND_N = 60
RUNS = 20
TRAIN_END = X.TRAIN_END


def signals(df):
    """(arrays, {(univ, ema set, rsi): signal bars}, {univ: eligible bars}) for one ticker."""
    df = df[(df[["open", "high", "low", "close"]] > 0).all(axis=1) & (df.index <= B.END)]
    o, h, lo, c, v = (df[k].to_numpy(float) for k in ("open", "high", "low", "close", "volume"))
    with np.errstate(invalid="ignore"):
        liquid = (c > 5) & (B.sma(c * v, 50) > 20e6) & np.asarray(df.index >= B.START)
        univ = {"UL": liquid, "U4": liquid & (B.sma(h / lo - 1, 20) * 100 > 4)}
    if not liquid.any():
        return None
    lv = sr.levels(df)
    sup, sup_lo, st = lv["sup"].to_numpy(), lv["sup_lo"].to_numpy(), lv["sup_str"].to_numpy()
    top = 2 * sup - sup_lo
    rsi_min = B.rmin(B.rsi(c, 14), 5)
    with np.errstate(invalid="ignore"):
        base = (st >= 2) & (B.rmin(lo, 3) <= top) & (c > top)
        tap = {n: (e > top) & (lo <= e) & (c > e) for n in (50, 100, 200) for e in [B.ema(c, n)]}
        sig = {}
        for u, um in univ.items():
            for en, ns in EMAS.items():
                e_ok = np.logical_or.reduce([tap[n] for n in ns])
                for r in RSIS:
                    sig[(u, en, r)] = np.where(base & e_ok & (rsi_min <= r) & um)[0]
    n = len(c)
    arr = {"idx": df.index, "o": o, "h": h, "l": lo, "c": c, "atr": lv["atr"].to_numpy(), "sup_lo": sup_lo}
    elig = {u: np.where(um[: n - 1])[0] for u, um in univ.items()}
    return arr, sig, elig


def _one(t):
    try:
        df = data20.load(t)
    except PermissionError:
        return t, None
    if df is None or len(df) < 300:
        return t, None
    return t, signals(df)


def load():
    if os.path.exists(CACHE):
        with open(CACHE, "rb") as fh:
            return pickle.load(fh)
    data20.final_mode()
    tk = T.tickers()
    arrs, sigs, elig = {}, {}, {}
    with ProcessPoolExecutor(4, initializer=data20.final_mode) as ex:
        for j, (t, res) in enumerate(ex.map(_one, tk, chunksize=20)):
            if res is not None:
                arrs[t], sigs[t], elig[t] = res
            if j % 500 == 0:
                print(f"load {j}/{len(tk)}", flush=True)
    with open(CACHE, "wb") as fh:
        pickle.dump((arrs, sigs, elig), fh, protocol=pickle.HIGHEST_PROTOCOL)
    return arrs, sigs, elig


def rnd_pool(arrs, elig, u, seed=11):
    """{entry day: up to RND_N random (t, s, 'open', nan, sup_lo) of the universe}; fixed sample (seeded)."""
    rows = [(arrs[t]["idx"][s + 1], t, s) for t, e in elig.items() for s in e[u]]
    d = pd.DataFrame(rows, columns=["day", "t", "s"])
    d = d.sample(frac=1.0, random_state=seed).groupby("day").head(RND_N)
    out: dict = {}
    for day, t, s in d.itertuples(index=False):
        out.setdefault(day, []).append((t, int(s), "open", np.nan, arrs[t]["sup_lo"][s]))
    return out


def cand_by_day(arrs, sigs, key):
    out: dict = {}
    for t, sg in sigs.items():
        for s in sg[key]:
            if s + 1 < len(arrs[t]["idx"]):
                out.setdefault(arrs[t]["idx"][s + 1], []).append((t, int(s), "open", np.nan, arrs[t]["sup_lo"][s]))
    return out


_G: dict = {}


def run_variant(key):
    """key = (univ, ema set or 'RND', rsi or 0, exit)."""
    u, en, r, ex = key
    cand = _G["rnd"][u] if en == "RND" else _G["cand"][(u, en, r)]
    cache: dict = {}
    runs = []
    for run in range(RUNS):
        eq, trades = X.simulate(_G["arrs"], _G["days"], cand, ex, _G["wk"], _G["week_last"], np.random.default_rng(run), cache)
        wr = X.weekly(eq, _G["wk"])
        runs.append((wr, X.part_stats(eq, wr, trades, False), X.part_stats(eq, wr, trades, True)))
    avg = lambda i, k: float(np.nanmean([q[i][k] for q in runs]))
    # every signal as a trade (no account limit), test period, and random entries on the same days and universe
    wl = lambda dt: _G["week_last"].get(_G["wk"].get(dt))
    ev, evr = [], []
    rng = np.random.default_rng(99)
    if en != "RND":
        for day, lst in cand.items():
            if day <= TRAIN_END:
                continue
            pool = _G["rnd"][u].get(day, [])
            for t, s, et, el, an in lst:
                tr = X.make_trade(_G["arrs"][t], s, et, el, an, ex, wl)
                if tr is not None:
                    ev.append(tr["ret"])
                for _ in range(5 if pool else 0):
                    t2, s2, et2, el2, an2 = pool[rng.integers(len(pool))]
                    tr2 = X.make_trade(_G["arrs"][t2], s2, et2, el2, an2, ex, wl)
                    if tr2 is not None:
                        evr.append(tr2["ret"])
    ev, evr = np.array(ev), np.array(evr)
    return key, {"weekly": pd.concat([q[0] for q in runs], axis=1).mean(axis=1), "train_wk": avg(1, "wk"),
                 "test": {k: avg(2, k) for k in runs[0][2]}, "test_sd": float(np.std([q[2]["wk"] for q in runs])),
                 "ev": (len(ev), (ev > 0).mean() if len(ev) else np.nan, ev.mean() if len(ev) else np.nan),
                 "evr": ((evr > 0).mean() if len(evr) else np.nan, evr.mean() if len(evr) else np.nan)}


def main():
    arrs, sigs, elig = load()
    spy, wk, _wf, week_last = T.calendar()
    spy_w = X.weekly(spy / spy.iloc[0], wk)
    keys_sig = [(u, en, r) for u in UNIVS for en in EMAS for r in RSIS]
    _G.update({"arrs": arrs, "days": spy.index, "wk": wk, "week_last": week_last,
               "cand": {k: cand_by_day(arrs, sigs, k) for k in keys_sig},
               "rnd": {u: rnd_pool(arrs, elig, u) for u in UNIVS}})
    nsig = {k: sum(len(v) for v in _G["cand"][k].values()) for k in keys_sig}
    print("signals:", nsig, flush=True)
    keys = [(u, en, r, ex) for u in UNIVS for en in EMAS for r in RSIS for ex in X.EXITS]
    keys += [(u, "RND", 0, ex) for u in UNIVS for ex in X.EXITS]
    res = {}
    with ProcessPoolExecutor(4) as pool:
        for key, r in pool.map(run_variant, keys):
            res[key] = r
            te = r["test"]
            print(f"{key}: train {r['train_wk'] * 100:+.2f}%/wk test {te['wk'] * 100:+.2f}%/wk win {te['win'] * 100:.0f}% "
                  f"n_ev {r.get('ev', (0,))[0]}", flush=True)
    with open(os.path.join(B.CACHE, "support_ema_results.pkl"), "wb") as fh:
        pickle.dump((res, spy_w, nsig), fh)
    write(res, spy_w, nsig, len(arrs))


def write(res, spy_w, nsig, n_tickers):
    rng = np.random.default_rng(2026)
    test_idx = [p for p in spy_w.index if p.end_time > TRAIN_END]
    spy_t = spy_w.loc[test_idx]
    yrs = len(spy_t) / 52.0
    f = lambda t: "-" if np.isnan(t[0]) else f"{t[0] * 100:+.2f}% [{t[1] * 100:+.2f}, {t[2] * 100:+.2f}]"
    lines = ["# Jouw strategie: support + EMA-tap + lage RSI\n\n", "<!-- CONCLUSIE -->\n\n",
             (f"Regels: `indicator_lab/week/support_ema_rules.md` (vooraf gecommit). {n_tickers} aandelen ooit liquide in "
              "de data; alleen aandelen die op 2026-10-23 genoteerd waren (geen gedelistte aandelen). Kosten 0,05% + $0,02 "
              "per kant; max 3 posities tegelijk, elk 1/3 van de rekening; 20 runs. Test 2023-01 .. 2026-10 "
              f"({len(spy_t)} weken); SPY in die weken {spy_t.mean() * 100:+.2f}% per week, CAGR "
              f"{((1 + spy_t).prod() ** (1 / yrs) - 1) * 100:.1f}%. ★ = gekozen op train (hoogste train gem./week) voor "
              "dit universum en deze exit. Intervallen: moving-block bootstrap (4 weken, 10.000x). 36 varianten getest.\n\n"
              "Aantal signalen 2015-2026 (alle, zonder rekening-beperking): "
              + ", ".join(f"{u} {e} RSI<={r}: {n}" for (u, e, r), n in nsig.items()) + "\n\n")]
    summ = []
    for u, uname in UNIVS.items():
        for ex, exname in X.EXITS.items():
            ks = [(u, en, r, ex) for en in EMAS for r in RSIS]
            best = max(ks, key=lambda k: res[k]["train_wk"])
            rnd = res[(u, "RND", 0, ex)]["weekly"].loc[test_idx].to_numpy()
            rows = []
            for k in [*ks, (u, "RND", 0, ex)]:
                r = res[k]
                te = r["test"]
                x = r["weekly"].loc[test_idx].to_numpy()
                d_r = X.boot_ci(x - rnd, rng) if k[1] != "RND" else (np.nan, np.nan, np.nan)
                d_s = X.boot_ci(x - spy_t.to_numpy(), rng)
                summ.append({"key": k, "best": k == best, "test_wk": te["wk"], "rnd": d_r, "spy": d_s})
                name = "RND willekeurig" if k[1] == "RND" else f"EMA {'/'.join(map(str, EMAS[k[1]]))}, RSI <= {k[2]}"
                ev = r.get("ev", (0, np.nan, np.nan))
                evr = r.get("evr", (np.nan, np.nan))
                rows.append({"variant": ("★ " if k == best else "") + name, "train gem./week": f"{r['train_wk'] * 100:+.2f}%",
                             "test trades/week": f"{te['tpw']:.2f}", "test winrate": f"{te['win'] * 100:.0f}%",
                             "test gem./trade": f"{te['exp'] * 100:+.2f}%",
                             "test gem./week (± sd)": f"{te['wk'] * 100:+.2f}% ± {r['test_sd'] * 100:.2f}",
                             "verschil vs RND [95%]": f(d_r), "verschil vs SPY [95%]": f(d_s),
                             "test CAGR": f"{te['cagr'] * 100:.1f}%", "test max daling": f"{te['dd'] * 100:.1f}%",
                             "gem. houdduur (dagen)": f"{te['bars']:.1f}",
                             "alle testsignalen: n / winrate / gem.": "-" if k[1] == "RND" else
                             f"{ev[0]} / {ev[1] * 100:.0f}% / {ev[2] * 100:+.2f}%",
                             "random zelfde dagen: winrate / gem.": "-" if k[1] == "RND" else
                             f"{evr[0] * 100:.0f}% / {evr[1] * 100:+.2f}%"})
            lines.append(f"## {u} {uname} — exit ({ex}) {exname}\n\n" + pd.DataFrame(rows).to_markdown(index=False) + "\n\n")
    with open(OUT, "w") as fh:
        fh.write("".join(lines))
    s = pd.DataFrame(summ)
    with open(os.path.join(B.CACHE, "support_ema_summary.pkl"), "wb") as fh:
        pickle.dump(s, fh)
    br = s[s["rnd"].map(lambda t: t[1] > 0)]
    bs = s[s["spy"].map(lambda t: t[1] > 0)]
    with open(W.LOG, "a") as fh:
        fh.write(f"\n## Support + EMA-tap + lage RSI (results/support_ema.md, branch claude/support-ema-rsi): 36 varianten; "
                 f"aantoonbaar beter dan RND: {len(br)}, aantoonbaar beter dan SPY: {len(bs)}\n")
    print("beter dan RND:", br["key"].tolist())
    print("beter dan SPY:", bs["key"].tolist())


if __name__ == "__main__":
    main()
