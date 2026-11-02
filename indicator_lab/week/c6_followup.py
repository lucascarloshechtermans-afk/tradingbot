"""Follow-up on C6 (Bollinger lower band above the SMA200): its own mean-reversion exits and new data.
Rules: indicator_lab/week/c6_rules.md (committed before the first run).

    python -m indicator_lab.week.c6_followup        # results/c6_followup.md
"""
from __future__ import annotations

import os
import pickle
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd
from scipy import stats as SS

from indicator_lab import sr
from indicator_lab.twenty import data20
from indicator_lab.week import build as B
from indicator_lab.week import exit_test as X
from indicator_lab.week import popular as P
from indicator_lab.week import run as W
from indicator_lab.week import support_ema as SE
from indicator_lab.week import three_week as T

OUT = os.path.join(os.path.dirname(W.LOG), "c6_followup.md")
CACHE_B = os.path.join(B.CACHE, "c6_band_inputs.pkl")
EXITS = {"m20": "uit na slot boven SMA20 (middenband)", "m5": "uit na slot boven SMA5 (Connors)",
         "d": "+10% en eruit", "e": "helft op +5%, rest op +10%"}
SLOTS = (3, 10)
RUNS = 20
BOOT = 10_000
TRAIN_END = X.TRAIN_END
_G: dict = {}


def band_ticker(t):
    """Dataset B: close > $5 and 50-day dollar volume $5M-$20M."""
    try:
        df = data20.load(t)
    except PermissionError:
        return t, None
    if df is None or len(df) < 300:
        return t, None
    df = df[(df[["open", "high", "low", "close"]] > 0).all(axis=1) & (df.index <= B.END)]
    c, v = df["close"].to_numpy(float), df["volume"].to_numpy(float)
    with np.errstate(invalid="ignore"):
        dv = B.sma(c * v, 50)
        m = (c > 5) & (dv >= 5e6) & (dv < 20e6) & np.asarray(df.index >= B.START)
    if not m.any():
        return t, None
    lv = sr.levels(df)
    sup_lo = lv["sup_lo"].to_numpy()
    arr = {"idx": df.index, "o": df["open"].to_numpy(float), "h": df["high"].to_numpy(float),
           "l": df["low"].to_numpy(float), "c": c, "atr": lv["atr"].to_numpy(), "sup_lo": sup_lo}
    n = len(c)
    bars = P.classics(df)["C6"][0]
    sig = [(t, int(s), "open", np.nan, sup_lo[s]) for s in bars if s + 1 < n and m[s]]
    return t, (arr, sig, {"UL": np.where(m[: n - 1])[0]})


def load_band():
    if os.path.exists(CACHE_B):
        with open(CACHE_B, "rb") as fh:
            return pickle.load(fh)
    data20.final_mode()
    tk = T.tickers()
    arrs, sigs, elig = {}, [], {}
    with ProcessPoolExecutor(4, initializer=data20.final_mode) as ex:
        for j, (t, res) in enumerate(ex.map(band_ticker, tk, chunksize=20)):
            if res is not None:
                arrs[t], s, elig[t] = res
                sigs += s
            if j % 500 == 0:
                print(f"load B {j}/{len(tk)}", flush=True)
    with open(CACHE_B, "wb") as fh:
        pickle.dump((arrs, sigs, elig), fh, protocol=pickle.HIGHEST_PROTOCOL)
    return arrs, sigs, elig


def trades(job):
    """Per trade (one open trade per stock) for one exit; part = 'all' | 'test'; 5 random same-day trades per signal."""
    ex, part = job
    arrs, pool, wl = _G["arrs"], _G["rnd"], _G["wl"]
    rng = np.random.default_rng(5)
    real, rand, clus, busy = [], [], {}, {}
    for day in sorted(_G["cand"]):
        if part == "test" and day <= TRAIN_END:
            continue
        p = pool.get(day, [])
        rr, qq = clus.setdefault(_G["wk"].get(day), ([], []))
        for t, s, et, el, an in _G["cand"][day]:
            if t in busy and day <= busy[t]:
                continue
            tr = X.make_trade(arrs[t], s, et, el, an, ex, wl)
            if tr is None:
                continue
            busy[t] = tr["exit"]
            real.append((tr["ret"], tr["hit"], tr["hit10"], tr["bars"]))
            rr.append(tr["ret"])
            for _ in range(5 if p else 0):
                t2, s2, et2, el2, an2 = p[rng.integers(len(p))]
                tq = X.make_trade(arrs[t2], s2, et2, el2, an2, ex, wl)
                if tq is not None:
                    rand.append((tq["ret"], tq["hit"], tq["hit10"], tq["bars"]))
                    qq.append(tq["ret"])
    a = np.array([(sum(x), len(x)) for x, y in clus.values() if x and y])
    b = np.array([(sum(y), len(y)) for x, y in clus.values() if x and y])
    ci = (np.nan,) * 4
    if len(a) > 5:
        idx = np.random.default_rng(7).integers(0, len(a), size=(BOOT, len(a)))
        diff = a[idx, 0].sum(1) / a[idx, 1].sum(1) - b[idx, 0].sum(1) / b[idx, 1].sum(1)
        est = a[:, 0].sum() / a[:, 1].sum() - b[:, 0].sum() / b[:, 1].sum()
        ci = (est, np.percentile(diff, 2.5), np.percentile(diff, 97.5), est / diff.std())
    return job, {"real": P.trade_stats(*zip(*real)) if real else {"n": 0},
                 "rand": P.trade_stats(*zip(*rand)) if rand else {"n": 0}, "diff": ci}


def account(job):
    key, ex, slots = job
    X.SLOTS = slots
    cand = _G["rnd"] if key == "RND" else _G["cand"]
    cache: dict = {}
    weekly, sharpe, stats = [], [], []
    for run in range(RUNS):
        eq, tr = X.simulate(_G["arrs"], _G["days"], cand, ex, _G["wk"], _G["week_last"], np.random.default_rng(run), cache)
        wr = X.weekly(eq, _G["wk"])
        weekly.append(wr)
        sharpe.append(float(wr.mean() / wr.std() * np.sqrt(52)) if wr.std() > 0 else np.nan)
        stats.append((X.part_stats(eq, wr, tr, False), X.part_stats(eq, wr, tr, True), eq))
    eqs = [s[2] for s in stats]
    full_cagr = float(np.mean([(e.iloc[-1] / e.iloc[0]) ** (52 / len(weekly[0])) - 1 for e in eqs]))
    full_dd = float(np.mean([(e / e.cummax() - 1).min() for e in eqs]))
    return job, {"weekly": pd.concat(weekly, axis=1).mean(axis=1), "sharpe_full": float(np.nanmean(sharpe)),
                 "cagr_full": full_cagr, "dd_full": full_dd,
                 "test": {k: float(np.nanmean([s[1][k] for s in stats])) for k in stats[0][1]}}


def run_dataset(name, arrs, cand_list, elig, spy_w):
    spy, wk, _wf, week_last = T.calendar()
    _G.clear()
    _G.update({"arrs": arrs, "days": spy.index, "wk": wk, "week_last": week_last,
               "wl": lambda dt: week_last.get(wk.get(dt)), "cand": P.by_day(arrs, cand_list),
               "rnd": SE.rnd_pool(arrs, elig, "UL")})
    tr_res, ac_res = {}, {}
    with ProcessPoolExecutor(4) as pool:
        for job, r in pool.map(trades, [(ex, part) for ex in EXITS for part in ("all", "test")]):
            tr_res[job] = r
            print(name, job, r["real"].get("n"), f"{r['real'].get('exp', np.nan) * 100:+.2f}%", flush=True)
        for job, r in pool.map(account, [(k, ex, sl) for sl in SLOTS for ex in EXITS for k in ("C6", "RND")]):
            ac_res[job] = r
            print(name, job, f"{r['test']['wk'] * 100:+.2f}%/wk", flush=True)
    return tr_res, ac_res


def section(name, title, tr_res, ac_res, spy_w, rng):
    pc = lambda x, d=1: "-" if x is None or np.isnan(x) else f"{x * 100:.{d}f}%"
    ci = lambda t: "-" if np.isnan(t[0]) else f"{t[0] * 100:+.2f}% [{t[1] * 100:+.2f}, {t[2] * 100:+.2f}]"
    rows = []
    for ex, exname in EXITS.items():
        for part, pname in (("all", "2015-2026"), ("test", "2023-2026")):
            r = tr_res[(ex, part)]
            a, q, d = r["real"], r["rand"], r["diff"]
            rows.append({"uitstap": f"{ex}: {exname}", "periode": pname, "trades": a.get("n", 0),
                         "+10% geraakt": pc(a.get("hit_10pct", np.nan), 0), "winrate": pc(a.get("win", np.nan), 0),
                         "gem./trade": pc(a.get("exp", np.nan), 2), "PF": f"{a.get('pf', np.nan):.2f}",
                         "gem. dagen": f"{a.get('days', np.nan):.1f}",
                         "random: winrate / gem.": f"{pc(q.get('win', np.nan), 0)} / {pc(q.get('exp', np.nan), 2)}",
                         "verschil vs random [95%]": ci(d), "t": f"{d[3]:.2f}"})
    weeks_all = list(spy_w.index)
    weeks_test = [p for p in weeks_all if p.end_time > TRAIN_END]
    acc, verdict = [], {}
    for sl in SLOTS:
        for ex, exname in EXITS.items():
            r, rr = ac_res[("C6", ex, sl)], ac_res[("RND", ex, sl)]
            for pname, wks in (("2015-2026", weeks_all), ("2023-2026", weeks_test)):
                x = r["weekly"].reindex(wks).fillna(0).to_numpy()
                d_r = X.boot_ci(x - rr["weekly"].reindex(wks).fillna(0).to_numpy(), rng)
                d_s = X.boot_ci(x - spy_w.loc[wks].to_numpy(), rng)
                if sl == 10 and ex == "m20" and pname == "2015-2026":
                    verdict["acct_spy"] = d_s
                acc.append({"posities": sl, "uitstap": ex, "periode": pname, "gem./week": f"{x.mean() * 100:+.2f}%",
                            "CAGR": pc((1 + x).prod() ** (52 / len(x)) - 1),
                            "max daling (2015-2026)" if pname == "2015-2026" else "max daling (test)":
                            pc(r["dd_full"] if pname == "2015-2026" else r["test"]["dd"]),
                            "verschil vs RND [95%]": ci(d_r), "verschil vs SPY [95%]": ci(d_s)})
    verdict["trade_rnd"] = tr_res[("m20", "all")]["diff"]
    spy_all = spy_w.loc[weeks_all]
    txt = (f"## {title}\n\nSPY 2015-2026: {spy_all.mean() * 100:+.2f}% per week, CAGR "
           f"{((1 + spy_all).prod() ** (52 / len(spy_all)) - 1) * 100:.1f}%.\n\n### Per trade\n\n"
           + pd.DataFrame(rows).to_markdown(index=False) + "\n\n### Als rekening\n\n"
           + pd.DataFrame(acc).to_markdown(index=False) + "\n\n")
    return txt, verdict


def main():
    spy, wk, _wf, _wl = T.calendar()
    spy_w = X.weekly(spy / spy.iloc[0], wk)
    rng = np.random.default_rng(2026)
    arrs_a, cands_a, elig_a = P.load()
    res_a = run_dataset("A", arrs_a, cands_a["C6"], elig_a, spy_w)
    del arrs_a, cands_a, elig_a
    arrs_b, sig_b, elig_b = load_band()
    res_b = run_dataset("B", arrs_b, sig_b, elig_b, spy_w)
    with open(os.path.join(B.CACHE, "c6_results.pkl"), "wb") as fh:
        pickle.dump((res_a, res_b, spy_w), fh)
    ta, _ = section("A", "A — zelfde liquide aandelen als de vorige studie (> $20M/dag)", *res_a, spy_w, rng)
    tb, vb = section("B", "B — nieuwe data: aandelen met $5M-$20M omzet per dag", *res_b, spy_w, rng)
    ok = vb["trade_rnd"][1] > 0 and vb["acct_spy"][1] > 0
    crit = float(SS.norm.ppf(1 - 0.05 / 32))
    head = ("# C6 Bollinger-onderband: eigen uitstap en nieuwe data\n\n<!-- CONCLUSIE -->\n\n"
            "Regels: `indicator_lab/week/c6_rules.md` (vooraf gecommit). Signaal: slot > SMA200 en slot < onderste "
            "Bollinger-band (20, 2); instap volgende open; stop onder support (max 8%); max 20 dagen; kosten 0,05% + "
            "$0,02 per kant; alleen aandelen die op 2026-10-23 genoteerd waren. 16 vergelijkingen; Bonferroni-grens "
            f"|t| > {crit:.2f}.\n\n**Vooraf vastgelegd oordeel (dataset B, uitstap M20, 10 posities, 2015-2026): "
            f"{'GESLAAGD' if ok else 'NIET GESLAAGD'}** — verschil per trade vs random {vb['trade_rnd'][0] * 100:+.2f}% "
            f"[{vb['trade_rnd'][1] * 100:+.2f}, {vb['trade_rnd'][2] * 100:+.2f}], rekening vs SPY "
            f"{vb['acct_spy'][0] * 100:+.2f}% per week [{vb['acct_spy'][1] * 100:+.2f}, {vb['acct_spy'][2] * 100:+.2f}].\n\n")
    with open(OUT, "w") as fh:
        fh.write(head + ta + tb)
    with open(W.LOG, "a") as fh:
        fh.write(f"\n## C6-vervolg (results/c6_followup.md): oordeel {'geslaagd' if ok else 'niet geslaagd'}\n")
    print(head)


if __name__ == "__main__":
    main()
