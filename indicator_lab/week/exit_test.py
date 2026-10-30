"""Exit test: is the weekly plan's problem the EXIT (+10% / out on Friday) or the ENTRIES? Same entries, universe and
costs as three_week.py; three exits side by side. Rules: indicator_lab/week/exit_test_rules.md (committed first).

    python -m indicator_lab.week.exit_test           # results/exit_test.md (inputs cached in /tmp)
"""
from __future__ import annotations

import os
import pickle
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

from indicator_lab.twenty import data20
from indicator_lab.week import build as B
from indicator_lab.week import earnings_eps as EE
from indicator_lab.week import mfe as M
from indicator_lab.week import run as W
from indicator_lab.week import three_week as T

try:
    from numba import njit
except ImportError:
    def njit(*a, **k):
        return (lambda f: f) if not a or not callable(a[0]) else a[0]

OUT = os.path.join(os.path.dirname(W.LOG), "exit_test.md")
CACHE = os.path.join(B.CACHE, "exit_test_inputs.pkl")
RUNS = 20
BOOT = 10_000
BLOCK = 4
TRAIN_END = pd.Timestamp("2022-12-31")
EXITS = {"a": "week: +10% of vrijdag eruit", "b": "maand: +20% of na 20 dagen eruit",
         "c": "trailing: 2 x ATR onder hoogste slot, max 60 dagen"}
MODES = {"M1": "maandag", "M2": "doorlopend"}
SLOTS = 3

_G: dict = {}


def _init():
    data20.final_mode()
    _G["spy"] = T.calendar()[0]
    _G["earn"] = EE.load()


def _one(t):
    return t, T.load_ticker(t, _G["spy"], _G["earn"])


def load():
    if os.path.exists(CACHE):
        with open(CACHE, "rb") as fh:
            return pickle.load(fh)
    data20.final_mode()
    tk = T.tickers()
    arrs, cands = {}, {k: [] for k in T.NAMES}
    with ProcessPoolExecutor(4, initializer=_init) as ex:
        for j, (t, res) in enumerate(ex.map(_one, tk, chunksize=20)):
            if res is not None:
                arrs[t] = res[0]
                for sid, lst in res[1].items():
                    cands[sid] += lst
            if j % 500 == 0:
                print(f"load {j}/{len(tk)}", flush=True)
    with open(CACHE, "wb") as fh:
        pickle.dump((arrs, cands), fh, protocol=pickle.HIGHEST_PROTOCOL)
    return arrs, cands


@njit(cache=True)
def path(o, h, lo, c, a, d, fill, stop, tgt, hold, trail):
    """Exit bar index and exit price. tgt <= 0: no target; trail > 0: stop = max(stop, highest close - trail x ATR)."""
    n = len(c)
    hc = -1.0
    for k in range(hold):
        day = d + k
        if day >= n:
            return n - 1, c[n - 1]
        op = fill if k == 0 else o[day]
        if lo[day] <= stop:
            return day, (stop if k == 0 else min(op, stop))
        if tgt > 0 and h[day] >= tgt:
            return day, (tgt if k == 0 else max(op, tgt))
        if k == hold - 1:
            return day, c[day]
        if trail > 0:
            hc = max(hc, c[day])
            stop = max(stop, hc - trail * a[day])
    return min(d + hold - 1, n - 1), c[min(d + hold - 1, n - 1)]


def make_trade(ar, s, etype, elevel, anchor, ex, week_last_of):
    o, h, lo, c, a = ar["o"], ar["h"], ar["l"], ar["c"], ar["atr"]
    d, fill = M.entry(o, h, s, etype, elevel)
    if d is None or not (fill > 0 and a[s] > 0):
        return None
    stop = M.std_stop(fill, anchor, a[s])
    if ex == "a":
        last = week_last_of(ar["idx"][d])
        if last is None:
            return None
        hold = int(ar["idx"].searchsorted(last, side="right")) - d
        tgt, trail = fill * 1.10, 0.0
    elif ex == "b":
        hold, tgt, trail = 20, fill * 1.20, 0.0
    else:
        hold, tgt, trail = 60, 0.0, 2.0
    if hold < 1:
        return None
    xi, px = path(o, h, lo, c, a, d, fill, stop, tgt, hold, trail)
    buy = (fill + M.TICK2) * (1 + M.COMM)
    sell = (px - M.TICK2) * (1 - M.COMM)
    return {"entry": ar["idx"][d], "exit": ar["idx"][xi], "buy": buy, "sell": sell, "ret": sell / buy - 1,
            "bars": int(xi - d + 1), "dates": ar["idx"][d:xi + 1], "closes": c[d:xi + 1]}


def by_entry_day(arrs, lst, wk, week_first, mode):
    out: dict = {}
    for t, s, etype, elevel, anchor in lst:
        dday = arrs[t]["idx"][s + 1]
        w = wk.get(dday)
        if w is None or (mode == "M1" and dday != week_first[w]):
            continue
        out.setdefault(dday, []).append((t, s, etype, elevel, anchor))
    return out


def simulate(arrs, days, cand, ex, wk, week_last, rng, cache):
    """Daily account (3 slots, 1/3 of the previous close's equity each). -> (equity Series, trades list)."""
    cash, eq_prev = 1.0, 1.0
    pos = []                                  # dicts: trade, shares, last close
    per_week: dict = {}
    eq, trades = np.empty(len(days)), []
    wl = lambda dt: week_last.get(wk.get(dt))
    for j, day in enumerate(days):
        free = SLOTS - len(pos)
        w = wk[day]
        lst = cand.get(day)
        if free > 0 and lst and (ex != "a" or per_week.get(w, 0) < SLOTS):
            held = {p["t"] for p in pos}
            for i in rng.permutation(len(lst)):
                if free == 0 or (ex == "a" and per_week.get(w, 0) >= SLOTS):
                    break
                t, s, etype, elevel, anchor = lst[i]
                if t in held:
                    continue
                key = (t, s, ex)
                if key not in cache:
                    cache[key] = make_trade(arrs[t], s, etype, elevel, anchor, ex, wl)
                tr = cache[key]
                if tr is None or tr["entry"] != day:
                    continue
                val = min(eq_prev / SLOTS, cash)
                if val <= 0:
                    break
                cash -= val
                pos.append({"t": t, "tr": tr, "sh": val / tr["buy"], "px": tr["buy"], "k": 0})
                held.add(t)
                free -= 1
                per_week[w] = per_week.get(w, 0) + 1
                trades.append(tr)
        keep = []
        for p in pos:
            tr = p["tr"]
            if tr["exit"] == day:
                cash += p["sh"] * tr["sell"]
                continue
            k = p["k"]
            while k < len(tr["dates"]) and tr["dates"][k] <= day:
                p["px"] = tr["closes"][k]
                k += 1
            p["k"] = k
            keep.append(p)
        pos = keep
        eq_prev = cash + sum(p["sh"] * p["px"] for p in pos)
        eq[j] = eq_prev
    return pd.Series(eq, index=days), trades


def weekly(eq: pd.Series, wk) -> pd.Series:
    e = eq.groupby(wk.reindex(eq.index).to_numpy()).last()
    return e.pct_change().fillna(e.iloc[0] - 1)


def boot_ci(x: np.ndarray, rng) -> tuple:
    n = len(x)
    nb = int(np.ceil(n / BLOCK))
    starts = rng.integers(0, n - BLOCK + 1, size=(BOOT, nb))
    idx = (starts[:, :, None] + np.arange(BLOCK)).reshape(BOOT, -1)[:, :n]
    m = x[idx].mean(axis=1)
    return float(x.mean()), float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def part_stats(eq, wr, trades, test: bool):
    sel = lambda ts: (ts > TRAIN_END) == test
    w = wr[[sel(p.end_time) for p in wr.index]]
    e = eq[[sel(d) for d in eq.index]]
    tr = [x for x in trades if sel(x["entry"])]
    r = np.array([x["ret"] for x in tr]) if tr else np.zeros(0)
    yrs = len(w) / 52.0
    e = e / (eq[eq.index <= TRAIN_END].iloc[-1] if test else 1.0)
    return {"wk": w.mean(), "tpw": len(tr) / max(len(w), 1), "win": (r > 0).mean() if len(r) else np.nan,
            "exp": r.mean() if len(r) else np.nan, "cagr": (1 + w).prod() ** (1 / yrs) - 1,
            "dd": float((e / e.cummax() - 1).min()), "bars": np.mean([x["bars"] for x in tr]) if tr else np.nan}


def run_variant(key):
    mode, ex, sid = key
    arrs, days, wk, week_last = _G["arrs"], _G["days"], _G["wk"], _G["week_last"]
    cache: dict = {}
    runs = []
    for run in range(RUNS):
        eq, trades = simulate(arrs, days, _G["groups"][mode][sid], ex, wk, week_last, np.random.default_rng(run), cache)
        wr = weekly(eq, wk)
        runs.append((wr, part_stats(eq, wr, trades, False), part_stats(eq, wr, trades, True)))
    avg = lambda i, k: float(np.nanmean([r[i][k] for r in runs]))
    return key, {"weekly": pd.concat([r[0] for r in runs], axis=1).mean(axis=1), "train_wk": avg(1, "wk"),
                 "test": {k: avg(2, k) for k in runs[0][2]}, "test_sd": float(np.std([r[2]["wk"] for r in runs]))}


def main():
    arrs, cands = load()
    spy, wk, week_first, week_last = T.calendar()
    spy_w = weekly(spy / spy.iloc[0], wk)
    stale = sum(1 for a in arrs.values() if a["idx"][-1] < pd.Timestamp("2026-09-01"))
    _G.update({"arrs": arrs, "days": spy.index, "wk": wk, "week_last": week_last,
               "groups": {m: {sid: by_entry_day(arrs, cands[sid], wk, week_first, m) for sid in T.NAMES} for m in MODES}})
    del cands
    keys = [(m, e, s) for m in MODES for e in EXITS for s in T.NAMES]
    res = {}
    with ProcessPoolExecutor(4) as ex:                    # fork: the workers share _G
        for key, r in ex.map(run_variant, keys):
            res[key] = r
            te = r["test"]
            print(f"{key[0]} {key[1]} {key[2]}: train {r['train_wk'] * 100:+.2f}%/wk test {te['wk'] * 100:+.2f}%/wk "
                  f"win {te['win'] * 100:.0f}% hold {te['bars']:.1f}", flush=True)
    with open(os.path.join(B.CACHE, "exit_test_results.pkl"), "wb") as fh:
        pickle.dump((res, spy_w), fh)
    write(res, spy_w, stale, len(arrs))


def write(res, spy_w, stale, n_tickers):
    rng = np.random.default_rng(2026)
    test_idx = [p for p in spy_w.index if p.end_time > TRAIN_END]
    spy_t = spy_w.loc[test_idx]
    yrs = len(spy_t) / 52.0
    lines = ["# Exit-test: zit het probleem in de uitstap of in de instap?\n\n", "<!-- CONCLUSIE -->\n\n",
             (f"Regels: `indicator_lab/week/exit_test_rules.md` (vooraf gecommit). {n_tickers} aandelen ooit in het universum; "
              f"{stale} daarvan hebben data die vóór 2026-09 ophoudt. De data bevat alleen aandelen die op 2026-10-23 nog "
              "genoteerd waren: gedelistte aandelen ontbreken (survivorship bias). Kosten 0,05% + $0,02 per kant; "
              "max 3 posities tegelijk, elk 1/3 van de rekening; 20 runs per variant. Testperiode 2023-01 .. 2026-10 "
              f"({len(spy_t)} weken). SPY kopen en vasthouden in de testweken: {spy_t.mean() * 100:+.2f}% per week, "
              f"CAGR {((1 + spy_t).prod() ** (1 / yrs) - 1) * 100:.1f}%. Intervallen: moving-block bootstrap, blokken "
              "van 4 weken, 10.000 trekkingen. ★ = een van de 3 beste op train voor deze exit en modus. "
              "78 varianten zijn getest: een enkel interval boven 0 kan toeval zijn.\n\n")]
    summary = []
    for ex, exname in EXITS.items():
        for mode, mname in MODES.items():
            sids = [s for s in T.NAMES if s != "RND"]
            top = sorted(sids, key=lambda s: res[(mode, ex, s)]["train_wk"], reverse=True)[:3]
            rnd = res[(mode, ex, "RND")]["weekly"].loc[test_idx].to_numpy()
            rows = []
            for sid in T.NAMES:
                r = res[(mode, ex, sid)]
                te = r["test"]
                x = r["weekly"].loc[test_idx].to_numpy()
                d_r = boot_ci(x - rnd, rng) if sid != "RND" else (np.nan, np.nan, np.nan)
                d_s = boot_ci(x - spy_t.to_numpy(), rng)
                summary.append({"exit": ex, "modus": mode, "sid": sid, "top": sid in top, "test_wk": te["wk"],
                                "rnd": d_r, "spy": d_s})
                f = lambda t: "-" if np.isnan(t[0]) else f"{t[0] * 100:+.2f}% [{t[1] * 100:+.2f}, {t[2] * 100:+.2f}]"
                rows.append({"strategie": ("★ " if sid in top else "") + f"{sid} {T.NAMES[sid]}",
                             "train gem./week": f"{r['train_wk'] * 100:+.2f}%",
                             "test trades/week": f"{te['tpw']:.2f}", "test winrate": f"{te['win'] * 100:.0f}%",
                             "test gem./trade": f"{te['exp'] * 100:+.2f}%",
                             "test gem./week (± sd)": f"{te['wk'] * 100:+.2f}% ± {r['test_sd'] * 100:.2f}",
                             "verschil vs RND [95%]": f(d_r), "verschil vs SPY [95%]": f(d_s),
                             "test CAGR": f"{te['cagr'] * 100:.1f}%", "test max daling": f"{te['dd'] * 100:.1f}%",
                             "gem. houdduur (dagen)": f"{te['bars']:.1f}"})
            lines.append(f"## Exit ({ex}) {exname} — {mode} {mname}\n\n" + pd.DataFrame(rows).to_markdown(index=False) + "\n\n")
    s = pd.DataFrame(summary)
    with open(os.path.join(B.CACHE, "exit_test_summary.pkl"), "wb") as fh:
        pickle.dump(s, fh)
    with open(OUT, "w") as fh:
        fh.write("".join(lines))
    better_r = s[s["rnd"].map(lambda t: t[1] > 0)]
    better_s = s[s["spy"].map(lambda t: t[1] > 0)]
    with open(W.LOG, "a") as fh:
        fh.write(f"\n## Exit-test (results/exit_test.md, branch claude/exit-test): 78 varianten; aantoonbaar beter dan RND: "
                 f"{len(better_r)}, aantoonbaar beter dan SPY: {len(better_s)}\n")
    print("beter dan RND:", better_r[["exit", "modus", "sid"]].values.tolist())
    print("beter dan SPY:", better_s[["exit", "modus", "sid"]].values.tolist())
    print(s.groupby(["exit", "modus"])["test_wk"].mean())


if __name__ == "__main__":
    main()
