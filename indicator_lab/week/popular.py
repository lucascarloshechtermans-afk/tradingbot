"""30 popular strategies (internet research + earlier work), all with the user's exit: +10% and out (stop below
support, max 20 days). Rules: indicator_lab/week/popular_rules.md (committed before the first run).

    python -m indicator_lab.week.popular            # results/popular_strategies.md (inputs cached in /tmp)
"""
from __future__ import annotations

import os
import pickle
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd
from scipy import stats as SS

from indicator_lab import pine_sim as PS
from indicator_lab import sr
from indicator_lab.twenty import data20
from indicator_lab.week import build as B
from indicator_lab.week import earnings_eps as EE
from indicator_lab.week import exit_test as X
from indicator_lab.week import run as W
from indicator_lab.week import support_ema as SE
from indicator_lab.week import three_week as T

try:
    from numba import njit
except ImportError:
    def njit(*a, **k):
        return (lambda f: f) if not a or not callable(a[0]) else a[0]

OUT = os.path.join(os.path.dirname(W.LOG), "popular_strategies.md")
CACHE = os.path.join(B.CACHE, "popular_inputs.pkl")
TRAIN_END = X.TRAIN_END
EX = "d"
RUNS = 20
BOOT = 10_000
NAMES = {**{f"W{k}": v for k, v in B.NAMES.items()},
         "S11": "Earnings-gap", "S12": "Jouw indicator v4.1", "S13": "Jouw support + EMA-tap + RSI <= 35",
         "C1": "Connors RSI(2) < 10", "C2": "Connors RSI(2) < 5", "C3": "Double 7s", "C4": "IBS < 0,25 + RSI(21) < 45",
         "C5": "5 dalingen op rij", "C6": "Bollinger onderband (boven SMA200)", "C7": "Williams %R < -90 (boven SMA200)",
         "C8": "Golden cross 50/200", "C9": "MACD-crossover", "C10": "Donchian 20 breakout (Turtle 1)",
         "C11": "Turtle 55 breakout", "C12": "52-weeks-hoog", "C13": "Holy Grail (Raschke)", "C14": "Supertrend (10, 3)",
         "C15": "Stochastic (14, 3) uit oversold", "C16": "Pocket pivot", "C17": "NR7 (Crabel)",
         "RND": "Willekeurig (controle)"}


@njit(cache=True)
def wilder(x, n):
    out = np.full(len(x), np.nan)
    s, cnt = 0.0, 0
    for i in range(len(x)):
        if np.isnan(x[i]):
            continue
        cnt += 1
        if cnt <= n:
            s += x[i]
            if cnt == n:
                s /= n
                out[i] = s
        else:
            s = (s * (n - 1) + x[i]) / n
            out[i] = s
    return out


def adx(h, lo, c, n=14):
    up, dn = np.diff(h, prepend=np.nan), -np.diff(lo, prepend=np.nan)
    pdm = np.where((up > dn) & (up > 0), up, 0.0)
    mdm = np.where((dn > up) & (dn > 0), dn, 0.0)
    pc = np.r_[np.nan, c[:-1]]
    tr = np.nanmax(np.vstack([h - lo, np.abs(h - pc), np.abs(lo - pc)]), axis=0)
    tr[0] = np.nan
    pdm[0] = mdm[0] = np.nan
    a = wilder(tr, n)
    with np.errstate(invalid="ignore", divide="ignore"):
        pdi = 100 * wilder(pdm, n) / a
        mdi = 100 * wilder(mdm, n) / a
        dx = 100 * np.abs(pdi - mdi) / (pdi + mdi)
    return wilder(dx, n)


@njit(cache=True)
def supertrend_up(h, lo, c, atr, mult):
    """True on bars where the Supertrend direction is up (standard recursion on hl2 +- mult x ATR)."""
    n = len(c)
    up = np.zeros(n, np.bool_)
    fu, fl = np.nan, np.nan
    trend = 1
    for i in range(n):
        if np.isnan(atr[i]):
            continue
        mid = (h[i] + lo[i]) / 2
        bu, bl = mid + mult * atr[i], mid - mult * atr[i]
        if np.isnan(fu):
            fu, fl = bu, bl
        else:
            fu = bu if (bu < fu or c[i - 1] > fu) else fu
            fl = bl if (bl > fl or c[i - 1] < fl) else fl
        if trend == 1 and c[i] < fl:
            trend = -1
        elif trend == -1 and c[i] > fu:
            trend = 1
        up[i] = trend == 1
    return up


def classics(df):
    """{C-id: (signal bars, entry type, entry level array or None)} for the 17 new strategies."""
    h, lo, c, v = (df[k].to_numpy(float) for k in ("high", "low", "close", "volume"))
    p = B.prev
    s50, s200 = B.sma(c, 50), B.sma(c, 200)
    rsi2, rsi21 = B.rsi(c, 2), B.rsi(c, 21)
    with np.errstate(invalid="ignore", divide="ignore"):
        rng = h - lo
        ibs = np.where(rng > 0, (c - lo) / rng, 0.5)
        up200 = c > s200
        m20, sd20 = B.sma(c, 20), pd.Series(c).rolling(20).std(ddof=0).to_numpy()
        hh14, ll14 = B.rmax(h, 14), B.rmin(lo, 14)
        wr = -100 * (hh14 - c) / (hh14 - ll14)
        macd = B.ema(c, 12) - B.ema(c, 26)
        sig = pd.Series(macd).ewm(span=9, adjust=False, min_periods=9).mean().to_numpy()
        k = 100 * (c - ll14) / (hh14 - ll14)
        d = B.sma(k, 3)
        ax = adx(h, lo, c)
        e20 = B.ema(c, 20)
        tr = np.r_[np.nan, np.maximum.reduce([h[1:] - lo[1:], np.abs(h[1:] - c[:-1]), np.abs(lo[1:] - c[:-1])])]
        atr10 = wilder(tr, 10)
        st = supertrend_up(h, lo, c, atr10, 3.0)
        st_ok = np.isfinite(atr10) & np.isfinite(np.r_[np.nan, atr10[:-1]])
        down = c < p(c)
        dvol = np.where(down, v, 0.0)
        maxdown10 = p(B.rmax(dvol, 10))
        out = {
            "C1": up200 & (rsi2 < 10), "C2": up200 & (rsi2 < 5), "C3": up200 & (c <= B.rmin(c, 7)),
            "C4": (ibs < 0.25) & (rsi21 < 45),
            "C5": np.logical_and.reduce([np.r_[np.zeros(j, bool), down[: len(down) - j]] for j in range(5)]),
            "C6": up200 & (c < m20 - 2 * sd20), "C7": up200 & (wr < -90),
            "C8": (s50 > s200) & (p(s50) <= p(s200)), "C9": (macd > sig) & (p(macd) <= p(sig)),
            "C10": c > p(B.rmax(h, 20)), "C11": c > p(B.rmax(h, 55)), "C12": c > p(B.rmax(h, 252)),
            "C13": (ax > 30) & (ax > p(ax, 5)) & (lo <= e20) & (c > e20),
            "C14": st & ~np.r_[False, st[:-1]] & st_ok,
            "C15": (k > d) & (p(k) <= p(d)) & (k < 20),
            "C16": (c > p(c)) & (v > maxdown10) & (c > s50),
            "C17": (rng <= B.rmin(rng, 7)) & up200,
        }
    stops = {"C13", "C17"}
    return {cid: (np.where(np.nan_to_num(m, nan=0).astype(bool))[0], "stop" if cid in stops else "open",
                  h if cid in stops else None) for cid, m in out.items()}


def load_ticker(t, spy, earn):
    try:
        df = data20.load(t)
    except PermissionError:
        return None
    if df is None or len(df) < 300:
        return None
    df = df[(df[["open", "high", "low", "close"]] > 0).all(axis=1) & (df.index <= B.END)]
    o, h, lo, c, v = (df[k].to_numpy(float) for k in ("open", "high", "low", "close", "volume"))
    with np.errstate(invalid="ignore"):
        m = (c > 5) & (B.sma(c * v, 50) > 20e6) & np.asarray(df.index >= B.START)
    if not m.any():
        return None
    lv = sr.levels(df)
    sup_lo = lv["sup_lo"].to_numpy()
    arr = {"idx": df.index, "o": o, "h": h, "l": lo, "c": c, "atr": lv["atr"].to_numpy(), "sup_lo": sup_lo}
    n = len(c)
    cands = {k: [] for k in NAMES if k != "RND"}

    def add(sid, s, etype="open", elevel=np.nan, anchor=None):
        if s + 1 < n and m[s]:
            cands[sid].append((t, int(s), etype, float(elevel), sup_lo[s] if anchor is None else anchor))

    for sid, lst in B.signals(df, lv, spy.reindex(df.index).ffill().to_numpy()).items():
        for s, etype, elevel, anchor in lst:
            add(f"W{sid}", s, etype, elevel, anchor)
    va50 = B.prev(B.sma(v, 50))
    for ts, rule, _e, _r in earn.get(t, []):
        i = int(df.index.searchsorted(ts))
        if i < n and df.index[i] == ts and rule == "next":
            i += 1
        if 1 <= i < n and o[i] >= 1.05 * c[i - 1] and v[i] >= 2 * va50[i] and c[i] > o[i]:
            add("S11", i)
    for s in np.where(PS.run(df, t, PS.V41)["buy"])[0]:
        add("S12", int(s))
    # S13 = the support_ema rule (UL, E1, RSI <= 35), restated here on the already computed levels (same formulas)
    top = 2 * lv["sup"].to_numpy() - sup_lo
    with np.errstate(invalid="ignore"):
        base = (lv["sup_str"].to_numpy() >= 2) & (B.rmin(lo, 3) <= top) & (c > top)
        tap = np.logical_or.reduce([(e > top) & (lo <= e) & (c > e) for e in (B.ema(c, 50), B.ema(c, 100), B.ema(c, 200))])
        s13 = base & tap & (B.rmin(B.rsi(c, 14), 5) <= 35)
    for s in np.where(s13)[0]:
        add("S13", int(s))
    for cid, (bars, etype, lvl) in classics(df).items():
        for s in bars:
            add(cid, int(s), etype, lvl[s] if lvl is not None else np.nan)
    elig = {"UL": np.where(m[: n - 1])[0]}
    return arr, cands, elig


_G: dict = {}


def _init():
    data20.final_mode()
    _G["spy"] = T.calendar()[0]
    _G["earn"] = EE.load()


def _one(t):
    return t, load_ticker(t, _G["spy"], _G["earn"])


def load():
    if os.path.exists(CACHE):
        with open(CACHE, "rb") as fh:
            return pickle.load(fh)
    data20.final_mode()
    tk = T.tickers()
    arrs, cands, elig = {}, {k: [] for k in NAMES if k != "RND"}, {}
    with ProcessPoolExecutor(4, initializer=_init) as ex:
        for j, (t, res) in enumerate(ex.map(_one, tk, chunksize=20)):
            if res is not None:
                arrs[t], cs, elig[t] = res
                for sid, lst in cs.items():
                    cands[sid] += lst
            if j % 500 == 0:
                print(f"load {j}/{len(tk)}", flush=True)
    with open(CACHE, "wb") as fh:
        pickle.dump((arrs, cands, elig), fh, protocol=pickle.HIGHEST_PROTOCOL)
    return arrs, cands, elig


def by_day(arrs, lst):
    out: dict = {}
    for t, s, etype, elevel, anchor in lst:
        out.setdefault(arrs[t]["idx"][s + 1], []).append((t, s, etype, elevel, anchor))
    return out


def trade_stats(rets, hits, days):
    r = np.asarray(rets)
    if len(r) == 0:
        return {"n": 0}
    hit, dd = np.asarray(hits), np.asarray(days)
    w, lz = r[r > 0], r[r <= 0]
    return {"n": len(r), "hit": hit.mean(), "hit5": (hit & (dd <= 5)).mean(), "hit10": (hit & (dd <= 10)).mean(),
            "win": (r > 0).mean(), "exp": r.mean(), "pf": w.sum() / -lz.sum() if lz.sum() < 0 else np.inf,
            "days": dd.mean()}


def per_trade(key):
    """Trade-level results (one open trade per stock) + 5 random same-day trades per signal; train and test by entry day."""
    arrs, wl, pool = _G["arrs"], _G["wl"], _G["rnd"]
    rng = np.random.default_rng(5)
    out = {}
    for part in ("train", "test"):
        real, rand, clus = [], [], {}
        busy: dict = {}                                  # ticker -> exit day of its open trade (one trade per stock)
        for day in sorted(_G["cand"][key]):
            if (day > TRAIN_END) != (part == "test"):
                continue
            lst = _G["cand"][key][day]
            p = pool.get(day, [])
            w = _G["wk"].get(day)
            rr, qq = clus.setdefault(w, ([], []))
            for t, s, et, el, an in lst:
                if t in busy and day <= busy[t]:
                    continue
                tr = X.make_trade(arrs[t], s, et, el, an, EX, wl)
                if tr is None:
                    continue
                busy[t] = tr["exit"]
                real.append((tr["ret"], tr["hit"], tr["bars"]))
                rr.append(tr["ret"])
                for _ in range(5 if p else 0):
                    t2, s2, et2, el2, an2 = p[rng.integers(len(p))]
                    tq = X.make_trade(arrs[t2], s2, et2, el2, an2, EX, wl)
                    if tq is not None:
                        rand.append((tq["ret"], tq["hit"], tq["bars"]))
                        qq.append(tq["ret"])
        day_r = [(sum(a), len(a)) for a, b in clus.values() if a and b]
        day_q = [(sum(b), len(b)) for a, b in clus.values() if a and b]
        st = trade_stats(*zip(*real)) if real else {"n": 0}
        sq = trade_stats(*zip(*rand)) if rand else {"n": 0}
        ci = (np.nan, np.nan, np.nan, np.nan)
        if len(day_r) > 5:
            a, b = np.array(day_r), np.array(day_q)
            idx = np.random.default_rng(7).integers(0, len(a), size=(BOOT, len(a)))
            diff = a[idx, 0].sum(1) / a[idx, 1].sum(1) - b[idx, 0].sum(1) / b[idx, 1].sum(1)
            est = a[:, 0].sum() / a[:, 1].sum() - b[:, 0].sum() / b[:, 1].sum()
            ci = (est, np.percentile(diff, 2.5), np.percentile(diff, 97.5), est / diff.std() if diff.std() > 0 else np.nan)
        out[part] = {"real": st, "rand": sq, "diff": ci}
    return key, out


def portfolio(key):
    cand = _G["rnd"] if key == "RND" else _G["cand"][key]
    cache: dict = {}
    runs = []
    for run in range(RUNS):
        eq, trades = X.simulate(_G["arrs"], _G["days"], cand, EX, _G["wk"], _G["week_last"], np.random.default_rng(run), cache)
        wr = X.weekly(eq, _G["wk"])
        te = X.part_stats(eq, wr, trades, True)
        wt = wr[[p.end_time > TRAIN_END for p in wr.index]]
        te["sharpe"] = float(wt.mean() / wt.std() * np.sqrt(52)) if wt.std() > 0 else np.nan
        runs.append((wr, X.part_stats(eq, wr, trades, False), te))
    avg = lambda i, k: float(np.nanmean([q[i][k] for q in runs]))
    return key, {"weekly": pd.concat([q[0] for q in runs], axis=1).mean(axis=1), "train_wk": avg(1, "wk"),
                 "train_cagr": avg(1, "cagr"), "test": {k: avg(2, k) for k in runs[0][2]},
                 "test_sd": float(np.std([q[2]["wk"] for q in runs]))}


def main():
    arrs, cands, elig = load()
    spy, wk, _wf, week_last = T.calendar()
    spy_w = X.weekly(spy / spy.iloc[0], wk)
    _G.update({"arrs": arrs, "days": spy.index, "wk": wk, "week_last": week_last,
               "wl": lambda dt: week_last.get(wk.get(dt)),
               "cand": {k: by_day(arrs, v) for k, v in cands.items()}, "rnd": SE.rnd_pool(arrs, elig, "UL")})
    del cands
    keys = [k for k in NAMES if k != "RND"]
    tr_res, pf_res = {}, {}
    with ProcessPoolExecutor(4) as ex:
        for key, r in ex.map(per_trade, keys):
            tr_res[key] = r
            te = r["test"]["real"]
            print(f"trades {key}: n {te.get('n')} hit {te.get('hit', np.nan) * 100:.0f}% win {te.get('win', np.nan) * 100:.0f}% "
                  f"exp {te.get('exp', np.nan) * 100:+.2f}%", flush=True)
        for key, r in ex.map(portfolio, [*keys, "RND"]):
            pf_res[key] = r
            print(f"account {key}: test {r['test']['wk'] * 100:+.2f}%/wk", flush=True)
    with open(os.path.join(B.CACHE, "popular_results.pkl"), "wb") as fh:
        pickle.dump((tr_res, pf_res, spy_w), fh)
    write(tr_res, pf_res, spy_w, len(arrs))


def write(tr_res, pf_res, spy_w, n_tickers):
    rng = np.random.default_rng(2026)
    test_idx = [p for p in spy_w.index if p.end_time > TRAIN_END]
    spy_t = spy_w.loc[test_idx]
    yrs = len(spy_t) / 52.0
    rnd_w = pf_res["RND"]["weekly"].loc[test_idx].to_numpy()
    pc = lambda x, d=1: "-" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x * 100:.{d}f}%"
    ci = lambda t: "-" if np.isnan(t[0]) else f"{t[0] * 100:+.2f}% [{t[1] * 100:+.2f}, {t[2] * 100:+.2f}]"
    rows_t, rows_p, flags = [], [], []
    for key, name in NAMES.items():
        if key != "RND":
            r = tr_res[key]
            a, q, d = r["test"]["real"], r["test"]["rand"], r["test"]["diff"]
            tr = r["train"]["real"]
            rows_t.append({"strategie": f"{key} {name}", "train trades": tr.get("n", 0), "train winrate": pc(tr.get("win", np.nan), 0),
                           "train gem./trade": pc(tr.get("exp", np.nan), 2),
                           "test trades": a.get("n", 0), "+10% geraakt (≤5 / ≤10 / ≤20 d)":
                           f"{pc(a.get('hit5', np.nan), 0)} / {pc(a.get('hit10', np.nan), 0)} / {pc(a.get('hit', np.nan), 0)}",
                           "test winrate": pc(a.get("win", np.nan), 0), "test gem./trade": pc(a.get("exp", np.nan), 2),
                           "test PF": f"{a.get('pf', np.nan):.2f}", "gem. dagen": f"{a.get('days', np.nan):.1f}",
                           "random: +10% / winrate / gem.": f"{pc(q.get('hit', np.nan), 0)} / {pc(q.get('win', np.nan), 0)} / "
                                                             f"{pc(q.get('exp', np.nan), 2)}",
                           "verschil vs random per trade [95%]": ci(d), "t (cluster)": f"{d[3]:.2f}"})
            flags.append((key, d))
        p = pf_res[key]
        te = p["test"]
        x = p["weekly"].loc[test_idx].to_numpy()
        d_r = X.boot_ci(x - rnd_w, rng) if key != "RND" else (np.nan, np.nan, np.nan)
        d_s = X.boot_ci(x - spy_t.to_numpy(), rng)
        sharpe = te["sharpe"]
        rows_p.append({"strategie": f"{key} {name}", "train CAGR": pc(p["train_cagr"]), "test trades/week": f"{te['tpw']:.2f}",
                       "test gem./week (± sd)": f"{te['wk'] * 100:+.2f}% ± {p['test_sd'] * 100:.2f}",
                       "test CAGR": pc(te["cagr"]), "test max daling": pc(te["dd"]), "Sharpe": f"{sharpe:.2f}",
                       "verschil vs RND [95%]": ci(d_r), "verschil vs SPY [95%]": ci(d_s),
                       "_rnd_lo": d_r[1], "_spy_lo": d_s[1], "_wk": te["wk"]})
    dp = pd.DataFrame(rows_p).sort_values("_wk", ascending=False)
    better_r = [r["strategie"] for _, r in dp.iterrows() if r["_rnd_lo"] > 0]
    better_s = [r["strategie"] for _, r in dp.iterrows() if r["_spy_lo"] > 0]
    crit = float(SS.norm.ppf(1 - 0.05 / (2 * len(flags))))       # Bonferroni, 30 tests, two-sided 5%
    sig_t = [k for k, d in flags if not np.isnan(d[3]) and d[3] > crit]
    spy_sh = spy_t.mean() / spy_t.std() * np.sqrt(52)
    txt = ("# 30 populaire strategieën met jouw uitstap: +10% en eruit\n\n<!-- CONCLUSIE -->\n\n"
           f"Regels: `indicator_lab/week/popular_rules.md` (vooraf gecommit); onderzoek en bronnen: "
           f"`results/research_popular_strategies.md`. {n_tickers} liquide aandelen (> $5, > $20M/dag), alleen aandelen "
           "die op 2026-10-23 genoteerd waren (geen gedelistte aandelen). Uitstap: +10% (limiet), stop onder support "
           "(max 8%), anders na 20 handelsdagen. Kosten 0,05% + $0,02 per kant. Train 2015-2022, test 2023-01 .. 2026-10. "
           f"SPY in de testweken: {spy_t.mean() * 100:+.2f}% per week, CAGR {((1 + spy_t).prod() ** (1 / yrs) - 1) * 100:.1f}%, "
           f"Sharpe {spy_sh:.2f}.\n\n"
           f"- Per trade aantoonbaar beter dan willekeurig (hele interval > 0): "
           f"{', '.join(k for k, d in flags if d[1] > 0) or 'geen'}; ook na Bonferroni (t > {crit:.2f}): {', '.join(sig_t) or 'geen'}.\n"
           f"- Rekening aantoonbaar beter dan RND: {', '.join(better_r) or 'geen'}.\n"
           f"- Rekening aantoonbaar beter dan SPY: {', '.join(better_s) or 'geen'}.\n\n"
           "## 1. Per trade: hoe vaak +10%, winrate (testjaren 2023-2026)\n\n"
           + pd.DataFrame(rows_t).sort_values("test gem./trade", key=lambda s: s.str.rstrip("%").replace("-", "nan").astype(float),
                                              ascending=False).to_markdown(index=False)
           + "\n\n## 2. Als rekening: max 3 posities, elk 1/3 (testjaren 2023-2026, gesorteerd op gem./week)\n\n"
           + dp.drop(columns=["_rnd_lo", "_spy_lo", "_wk"]).to_markdown(index=False) + "\n")
    with open(OUT, "w") as fh:
        fh.write(txt)
    with open(W.LOG, "a") as fh:
        fh.write(f"\n## 30 populaire strategieën, +10% en eruit (results/popular_strategies.md, branch claude/popular-strategies): "
                 f"per trade beter dan random (Bonferroni): {sig_t or 'geen'}; rekening beter dan RND: {len(better_r)}, "
                 f"beter dan SPY: {len(better_s)}\n")
    print(txt[:3000])


if __name__ == "__main__":
    main()
