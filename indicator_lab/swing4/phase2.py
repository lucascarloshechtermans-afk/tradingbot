"""Phase 2 of the swing v4 round: every idea is tested on its own against baseline v3 and logged.

    python -m indicator_lab.swing4.phase2 A        # one family (A exits, B selection, C setup, D entry, E model, F regime)

Grids are coarse on purpose; each grid point is a logged trial.
"""
from __future__ import annotations

import os
import pickle
import sys
from dataclasses import replace

import numpy as np

from indicator_lab.swing4 import lab as L
from indicator_lab.swing4.sim2 import Policy

OUT = os.path.join(L.P.HERE, "reports")
BASE = Policy()


def v3(cx):
    return L.v3_entry(cx)


def filt(fn):
    """v3 entries that also pass `fn(cx) -> bool array` (nan counts as fail)."""
    def e(cx):
        with np.errstate(invalid="ignore"):
            return L.v3_entry(cx) & np.nan_to_num(fn(cx), nan=0).astype(bool)
    return e


def ideas_A():
    s_part = "selling part of a winner at a fixed R locks in gains the trail would give back, while the rest keeps the tail"
    out = []
    for lv in (1.0, 1.5, 2.0):
        for fr in (1 / 3, 0.5):
            out.append((f"A1 partial {fr:.2f} at +{lv}R", dict(pol=replace(BASE, partial=((lv, fr),))),
                        {"level": lv, "frac": round(fr, 3)}, 2, s_part))
    for lv in (1.0, 1.5):
        out.append((f"A2 break-even stop at +{lv}R", dict(pol=replace(BASE, be_at=lv)), {"be_at": lv}, 1,
                    "a trade that has run +1R should not become a loss: move the stop to entry"))
    for at in (1.0, 1.5, 2.0):
        for mu in (2.0, 2.5, 3.0):
            out.append((f"A3 tight trail {mu}xATR after +{at}R", dict(pol=replace(BASE, tight_at=at, tight_mult=mu)),
                        {"tight_at": at, "tight_mult": mu}, 2,
                        "once in profit, protect it with a closer trail; early on keep room for noise"))
        out.append((f"A3 10-day-low trail after +{at}R", dict(pol=replace(BASE, tight_at=at, tight_low=10)),
                    {"tight_at": at, "tight_low": 10}, 1, "once in profit, exit on a break of the 10-day low"))
    for nb in (5, 10, 15):
        out.append((f"A4 time stop {nb} bars (<+0.5R)", dict(pol=replace(BASE, time_n=nb)), {"time_n": nb}, 1,
                    "a breakout that does not move within N days has failed; free the money"))
    for x in (4.0, 6.0, 8.0):
        for fr in (0.5, 1.0):
            out.append((f"A5 over-extension {fr:.1f} out at SMA50+{x}ATR", dict(pol=replace(BASE, ox_atr=x, ox_frac=fr)),
                        {"ox_atr": x, "frac": fr}, 2, "far above the 50-day average a stock tends to mean-revert"))
    for fr in (0.5, 1.0):
        out.append((f"A5 RSI>80 {fr:.1f} out", dict(pol=replace(BASE, ox_rsi=80.0, ox_frac=fr)), {"rsi": 80, "frac": fr},
                    1, "a fast run to RSI>80 is often followed by a pullback"))
    for tg in (2.0, 3.0):
        out.append((f"A6 fixed target +{tg}R (whole position)", dict(pol=replace(BASE, target=tg)), {"target": tg}, 1,
                    "comparison: bank the whole position at a fixed multiple of the risk"))
    for d in (2, 3):
        for fr in (0.5, 1.0):
            out.append((f"A7 pre-earnings {fr:.1f} out ({d}d)", dict(pol=replace(BASE, earn_days=d, earn_frac=fr)),
                        {"earn_days": d, "frac": fr}, 2, "an earnings report is a coin flip on a gap; bank a profit before it"))
    return out


def X(name):
    return lambda cx: cx["x"][name]


def key_x(name):
    return lambda x: x["x"].get(name, np.nan)


def ideas_B():
    out = []
    s_mom = "relative strength persists: when slots are scarce, take the strongest stocks of the universe"
    for k in ("mom126_xs", "mom252_xs", "mom_12_1_xs"):
        out.append((f"B1 rank by {k}", dict(key=key_x(k), level="portfolio"), {"rank": k}, 1, s_mom))
    out.append(("B2 rank by v3 model score", dict(key=lambda x: x["p_v3"] - x["thr_v3"], level="portfolio"),
                {"rank": "p_v3"}, 0, "the model's top quintile is the only clearly better one: give it the slots"))
    out.append(("B2 rank by stable-feature score", dict(key=lambda x: x["p_st"], level="portfolio"), {"rank": "p_st"},
                0, "same, with the 3 sign-stable features only"))
    out.append(("B3 rank by 1y ATR%", dict(key=key_x("atr1y"), level="portfolio"), {"rank": "atr1y"}, 0,
                "the edge per trade grows with a stock's typical volatility (E30/E56)"))
    for v in (1.5, 2.0, 2.5):
        out.append((f"B3 filter 1y ATR% >= {v}", dict(entry=filt(lambda cx, v=v: X("atr1y")(cx) >= v)),
                    {"atr1y_min": v}, 1, "the edge per trade grows with a stock's typical volatility (E30/E56)"))
    for v in (0.5, 0.7):
        out.append((f"B4 sector momentum rank >= {v}", dict(entry=filt(lambda cx, v=v: X("sect_rank")(cx) >= v)),
                    {"sect_min": v}, 1, "breakouts in leading sectors get industry tailwind"))
    out.append(("B4 rank by sector momentum", dict(key=key_x("sect_rank"), level="portfolio"), {"rank": "sect"}, 0,
                "breakouts in leading sectors get industry tailwind"))
    for v in (7.0, 7.5, 8.0):
        out.append((f"B5 liquidity: 50d $vol >= 10^{v}", dict(entry=filt(lambda cx, v=v: X("dvol")(cx) >= v)),
                    {"log_dvol_min": v}, 1, "only names that can be traded without moving the price"))
    return out


def ideas_C():
    out = []
    for v in (0.8, 0.9, 1.0):
        out.append((f"C1 contraction ATR10/ATR50 <= {v}", dict(entry=filt(lambda cx, v=v: X("contract")(cx) <= v)),
                    {"contract_max": v}, 1, "a tight base (shrinking range) before the breakout means supply is absorbed"))
    for v in (0.3, 0.5):
        out.append((f"C1 BB-width pct <= {v} at breakout", dict(entry=filt(lambda cx, v=v: X("bbw_pct")(cx) <= v)),
                    {"bbw_max": v}, 1, "a breakout out of a narrow Bollinger band is a volatility expansion from rest"))
    out.append(("C2 new 52-week high", dict(entry=filt(lambda cx: X("hi52")(cx) >= 1)), {"base": "52w"}, 0,
                "a breakout from a long base has no overhead supply left"))
    out.append(("C2 new 126-day high", dict(entry=filt(lambda cx: X("hi126")(cx) >= 1)), {"base": "126d"}, 0,
                "a breakout from a 6-month range has little overhead supply"))
    for d in (10, 20):
        for g in (0.0, 1.0):
            out.append((f"C3 earnings <= {d}d ago with gap > {g} ATR",
                        dict(entry=filt(lambda cx, d=d, g=g: (X("since_earn")(cx) <= d) & (X("earn_gap")(cx) > g))),
                        {"days": d, "gap": g}, 2, "post-earnings drift: a positive surprise keeps being priced in"))
    out.append(("C3 gap >1.5ATR on 2x volume in last 10d", dict(entry=filt(lambda cx: X("big_gap10")(cx) >= 1)),
                {"gap": 1.5, "rvol": 2}, 2, "post-event drift without earnings dates"))
    return out


def ideas_D():
    out = []
    for buf in (0.0, 0.25):
        for d in (1, 3):
            out.append((f"D1 buy-stop signal high+{buf}ATR, {d}d", dict(pol=replace(BASE, entry="stop", e_buf=buf, e_days=d)),
                        {"e_buf": buf, "e_days": d}, 2, "a breakout that cannot clear its own high the next day has failed"))
    for d in (3, 5):
        out.append((f"D2 pullback to breakout level, {d}d", dict(pol=replace(BASE, entry="pullback", pb_mode="brk", e_days=d)),
                    {"pb": "brk", "e_days": d}, 1, "buying the retest of the breakout level gives a better price"))
        for pb in (0.5, 1.0):
            out.append((f"D2 pullback close-{pb}ATR, {d}d", dict(pol=replace(BASE, entry="pullback", pb=pb, e_days=d)),
                        {"pb": pb, "e_days": d}, 2, "a better price on the first dip lowers the risk per trade"))
    return out


def ideas_F():
    out = []
    for v in (0.0, 0.03, 0.06):
        out.append((f"F1 SPY 63d return <= {v}", dict(entry=filt(lambda cx, v=v: X("spy_roc63")(cx) <= v)),
                    {"spy_roc63_max": v}, 1, "breakouts after a weak market lead the next leg up (model sign every year)"))
    for v in (0.6, 0.7):
        out.append((f"F2 breadth200 <= {v}", dict(entry=filt(lambda cx, v=v: X("breadth200")(cx) <= v)),
                    {"breadth200_max": v}, 1, "a stock breaking out while most stocks are weak shows real strength"))
    out.append(("F2 SPY below its SMA200", dict(entry=filt(lambda cx: X("spy_up")(cx) < 0.5)), {"spy_up": 0}, 0,
                "same, in a bear market"))
    def notrend(cx):
        with np.errstate(invalid="ignore"):
            return cx["cand_notrend"] & (cx["p_v3"] >= cx["thr_v3"])
    out.append(("F3 no SMA200 filter on the stock (v3 model)", dict(entry=notrend), {"trend": None}, 0,
                "the trend filter may block early breakouts after a weak market"))
    return out


# ------------------------------------------------------------------ E: model
FEAT_IDX = {f: i for i, f in enumerate(L.meta.FEATS + ["breadth50", "breadth200", "ext200"])}


def _featmat(cx, feats):
    cols = []
    for f in feats:
        cols.append(cx["feat"][:, FEAT_IDX[f]] if f in FEAT_IDX else cx["x"][f])
    return np.column_stack(cols)


def dev_table(ctx, label: str, feats) -> "L.pd.DataFrame":
    """DEV candidates (all years) with a label and the date the label became known (no leakage in yearly refits).
    label "win": the v3 single-trade outcome > 0 (as v3);  "R1.5"/"R1.0": +x R touched before -1R (60 bars max)."""
    rows = []
    for t in L.data.DEV:
        cx = ctx[t]
        a = cx["arr"]
        o, h, lo, c, atr, ex = a["o"], a["h"], a["l"], a["c"], a["atr"], a["exit_sig"]
        X_ = _featmat(cx, feats)
        n = len(c)
        for i in np.flatnonzero(cx["cand"]):
            if i + 2 >= n or not np.isfinite(atr[i]) or not np.isfinite(X_[i]).all():
                continue
            ep, rp = o[i + 1], 4 * atr[i]
            if label == "win":
                r, xi = L.meta.single_trade(o, h, lo, c, atr, ex, i, L.meta.ExitRules(trail_atr=4.0, stop_atr=4.0))
                if xi == n - 1:
                    continue
                y, known = float(r > 0), xi
            else:
                lv = float(label[1:])
                y, known = None, None
                for j in range(i + 1, min(n, i + 61)):
                    if lo[j] <= ep - rp:
                        y, known = 0.0, j
                        break
                    if h[j] >= ep + lv * rp and j > i + 1 or (j == i + 1 and h[j] >= ep + lv * rp):
                        y, known = 1.0, j
                        break
                if y is None:
                    if i + 61 >= n:
                        continue
                    y, known = 0.0, i + 60
            rows.append({"exit_date": a["index"][known], "ret": y - 0.5, **dict(zip(feats, X_[i]))})
    return L.pd.DataFrame(rows)


class YearlyGBM:
    def __init__(self, table, feats, keep=0.75, mono=None):
        from sklearn.ensemble import HistGradientBoostingClassifier
        self.feats, self.models = feats, {}
        for y in range(2015, 2027):
            tr = table[table["exit_date"] < L.pd.Timestamp(f"{y}-01-01")]
            if len(tr) < 200:
                continue
            m = HistGradientBoostingClassifier(max_depth=2, max_iter=150, learning_rate=0.05, min_samples_leaf=80,
                                               monotonic_cst=mono, random_state=0)
            X_, yv = tr[feats].to_numpy(float), (tr["ret"] > 0).to_numpy(int)
            m.fit(X_, yv)
            p = m.predict_proba(X_)[:, 1]
            self.models[y] = (m, float(np.quantile(p, 1 - keep)))

    def prob(self, X_, years):
        pr, th = np.full(len(X_), np.nan), np.full(len(X_), np.nan)
        ok = np.isfinite(X_).all(axis=1)
        for y, (m, thr) in self.models.items():
            idx = (years == y) & ok
            if idx.any():
                pr[idx] = m.predict_proba(X_[idx])[:, 1]
                th[idx] = thr
        return pr, th


def model_entries(ctx, mdl, feats, kind="logit"):
    """Per ticker: (prob, thr) arrays of a yearly model; entry = base candidate & prob >= thr."""
    pt = {}
    for t, cx in ctx.items():
        X_ = _featmat(cx, feats)
        if kind == "logit":
            pr, th = mdl.prob(L.pd.DataFrame(X_, columns=feats, index=cx["arr"]["index"]))
        else:
            pr, th = mdl.prob(X_, cx["arr"]["index"].year.to_numpy())
        pt[t] = (pr, th)
    return pt


def ideas_E(ctx):
    out = []
    S = L.STABLE
    combos = [("E1 relabel +1.5R-before-1R, stable feats", "R1.5", S, 1),
              ("E1 relabel +1.0R-before-1R, stable feats", "R1.0", S, 1),
              ("E1 relabel +1.5R-before-1R, 17 feats", "R1.5", L.meta.FEATS, 1),
              ("E1 stable feats + breadth200 + atr1y (win label)", "win", S + ["breadth200", "atr1y"], 2)]
    for name, lab, feats, nf in combos:
        tab = dev_table(ctx, lab, feats)
        mdl = L.meta.YearlyModels(tab, feats=feats, keep=0.75, l2=100.0)
        pt = model_entries(ctx, mdl, feats)
        def ent(cx, pt=pt):
            t = next(k for k, v in ctx.items() if v is cx)
            with np.errstate(invalid="ignore"):
                return cx["cand"] & (pt[t][0] >= pt[t][1])
        out.append((name, dict(entry=ent), {"label": lab, "feats": "+".join(feats) if len(feats) < 6 else "17"}, nf,
                    "train on what the new exits need (reach +xR before the stop) instead of any small win"))
    feats = S + ["breadth200", "atr1y"]
    mono = [1, -1, -1, -1, 1]  # rvol +, spy_roc63 -, er20 -, breadth200 -, atr1y + (signs of the stories)
    for lab in ("win", "R1.5"):
        tab = dev_table(ctx, lab, feats)
        g = YearlyGBM(tab, feats, mono=mono)
        pt = model_entries(ctx, g, feats, kind="gbm")
        def ent(cx, pt=pt):
            t = next(k for k, v in ctx.items() if v is cx)
            with np.errstate(invalid="ignore"):
                return cx["cand"] & (pt[t][0] >= pt[t][1])
        out.append((f"E2 GBM depth2 monotone ({lab})", dict(entry=ent), {"model": "gbm", "label": lab}, 2,
                    "a shallow tree ensemble can capture the non-linear top quintile, with the signs fixed by the story"))
    # bet sizing on the v3 score: 0.5x .. 1.5x risk
    def sz(x):
        lg = np.log(x["p_v3"] / (1 - x["p_v3"])) - np.log(x["thr_v3"] / (1 - x["thr_v3"]))
        return 1.0 + float(np.clip(lg / 0.5, -0.5, 0.5))
    out.append(("E3 size by v3 score (0.5x-1.5x)", dict(size=sz, level="portfolio"), {"scale": 0.5}, 1,
                "put more money behind the breakouts the model likes"))
    def sz_reg(x):
        v = x["x"]["spy_roc63"]
        return 1.5 if v <= 0.0 else (1.0 if v <= 0.06 else 0.5)
    out.append(("E3 size by regime (spy_roc63: 1.5x<=0, 1x<=6%, 0.5x)", dict(size=sz_reg, level="portfolio"),
                {"cuts": [0.0, 0.06]}, 2, "more money when breakouts historically work best (weak preceding market)"))
    return out


# ------------------------------------------------------------------ G: stacking on top of the accepted F1
F1_MAX = 0.03   # middle of the accepted plateau {0.00, 0.03, 0.06}


def f1(entry=v3):
    def e(cx):
        with np.errstate(invalid="ignore"):
            return entry(cx) & (np.nan_to_num(cx["x"]["spy_roc63"], nan=9) <= F1_MAX)
    return e


def v2(cx):
    return cx["cand"].copy()


def stable(cx):
    with np.errstate(invalid="ignore"):
        return cx["cand"] & (cx["p_st"] >= cx["thr_st"])


def ideas_G():
    s = " (on top of F1)"
    return [
        ("G1 F1 + v2 (no model)", dict(entry=f1(v2)), {"model": None}, 0, "the regime rule may make the model redundant" + s),
        ("G2 F1 + stable-feature model", dict(entry=f1(stable)), {"model": "stable3"}, 0, "only the sign-stable features" + s),
        ("G3 F1 + time stop 15", dict(entry=f1(), pol=replace(BASE, time_n=15)), {"time_n": 15}, 1, "dead trades free money" + s),
        ("G3 F1 + time stop 10", dict(entry=f1(), pol=replace(BASE, time_n=10)), {"time_n": 10}, 1, "dead trades free money" + s),
        ("G4 F1 + RSI>80 half out", dict(entry=f1(), pol=replace(BASE, ox_rsi=80.0, ox_frac=0.5)), {"rsi": 80, "frac": 0.5}, 1,
         "bank half after a fast run" + s),
        ("G5 F1 + out at SMA50+8ATR", dict(entry=f1(), pol=replace(BASE, ox_atr=8.0)), {"ox_atr": 8}, 1, "extreme extension" + s),
        ("G6 F1 + 3ATR trail after +1.5R", dict(entry=f1(), pol=replace(BASE, tight_at=1.5, tight_mult=3.0)),
         {"tight_at": 1.5, "tight_mult": 3.0}, 2, "protect open profit" + s),
        ("G7 F1 + buy-stop 3d", dict(entry=f1(), pol=replace(BASE, entry="stop", e_days=3)), {"e_days": 3}, 1,
         "skip breakouts that fail the next day" + s),
        ("G8 F1 + 1/3 out at +1.5R", dict(entry=f1(), pol=replace(BASE, partial=((1.5, 1 / 3),))), {"level": 1.5, "frac": 0.333},
         2, "lock in part of the gain" + s),
        ("G9 F1 + break-even at +1R", dict(entry=f1(), pol=replace(BASE, be_at=1.0)), {"be_at": 1.0}, 1, "no winner turns into a loser" + s),
        ("G10 F1 + idle cash in SPY>SMA200", dict(entry=f1(), park=True, level="portfolio"), {"park": "SPY>SMA200"}, 0,
         "when the regime blocks breakouts (strong market), own the market instead (v3.1 rule, E48)" + s),
        ("G11 F1 + size by v3 score", dict(entry=f1(), size=lambda x: 1.0 + float(np.clip((np.log(x["p_v3"] / (1 - x["p_v3"])) - np.log(x["thr_v3"] / (1 - x["thr_v3"]))) / 0.5, -0.5, 0.5)), level="portfolio"),
         {"scale": 0.5}, 1, "more money behind the model's favourites" + s),
    ]


def run_stack(ctx, B0):
    BF = L.Baseline(ctx, entry=f1(), name="F1(0.03)")
    print("F1 reference: win %.1f%% exp %.2f%% %.3fR | MAR %.2f CAGR %.1f%% DD %.1f%% expo %.0f%%" % (
        BF.t["win"] * 100, BF.t["exp_pct"] * 100, BF.t["exp_R"], BF.p["mar"], BF.p["cagr"] * 100, BF.p["maxdd"] * 100,
        BF.p["exposure"] * 100))
    results = []
    for name, spec, params, n_free, story in ideas_G():
        res = L.run(ctx, spec.get("entry", v3), spec.get("pol", BASE))
        kw = dict(level=spec.get("level", "trade"), key=spec.get("key"), size=spec.get("size"), park=spec.get("park", False))
        e0 = L.evaluate(name, res, B0, params, n_free, story, log=False, **kw)
        e = L.evaluate(name, res, BF, params, n_free, story + f" | vs v3: {''.join('1' if v else '0' for v in e0['crit'].values())}",
                       phase="P2-stack", **kw)
        print(L.line(e), "| vs v3:", "".join("✓" if v else "·" for v in e0["crit"].values()), flush=True)
        e.pop("tt"), e["port"].pop("ports", None)
        results.append(e)
    with open(os.path.join(L.os.environ.get("SWING4_CACHE", "/tmp"), "p2_G.pkl"), "wb") as fh:
        pickle.dump(results, fh)


FAMILIES = {"A": ideas_A, "B": ideas_B, "C": ideas_C, "D": ideas_D, "F": ideas_F, "E": ideas_E}


def run_family(fam: str, ctx=None, B=None):
    ctx = ctx or L.load_ctx()
    B = B or L.Baseline(ctx)
    results = []
    fn = FAMILIES[fam]
    for name, spec, params, n_free, story in (fn(ctx) if fam == "E" else fn()):
        res = L.run(ctx, spec.get("entry", v3), spec.get("pol", BASE))
        e = L.evaluate(name, res, B, params, n_free, story, level=spec.get("level", "trade"), key=spec.get("key"),
                       size=spec.get("size"))
        print(L.line(e), flush=True)
        e.pop("tt")
        e["port"].pop("ports", None)
        results.append(e)
    with open(os.path.join(L.os.environ.get("SWING4_CACHE", "/tmp"), f"p2_{fam}.pkl"), "wb") as fh:
        pickle.dump(results, fh)
    return results


if __name__ == "__main__":
    ctx = L.load_ctx()
    B = L.Baseline(ctx)
    print("baseline v3: win %.1f%% exp %.2f%% %.3fR | MAR %.2f (%.2f-%.2f) CAGR %.1f%% DD %.1f%%" % (
        B.t["win"] * 100, B.t["exp_pct"] * 100, B.t["exp_R"], B.p["mar"], B.p["mar_lo"], B.p["mar_hi"],
        B.p["cagr"] * 100, B.p["maxdd"] * 100))
    print("criteria flags: win_up exp%_ok expR_ok mar_ok years70 half_a half_b params_ok")
    for fam in sys.argv[1:]:
        if fam == "G":
            run_stack(ctx, B)
        else:
            run_family(fam, ctx, B)
