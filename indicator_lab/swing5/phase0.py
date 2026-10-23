"""Phase 0 of the swing v5 round: foundation and bugs (development data only; the v5 holdout is refused).

    python -m indicator_lab.swing5.phase0        # writes swing5/reports/phase0.md + figures, logs the trials

1. the complete system as traded (breakouts + idle cash in SPY when SPY > SMA200 + regime rule) vs SPY buy & hold
   and 60/40, with the return split into beta (SPY exposure) and alpha, and into its sleeves
2. (the drawdown-convention fix is code + tests; its effect is reported here)
3. the quality model refit WITHOUT spy_roc63 / spy_up, the regime rule as a hard rule; coefficient stability
4. statistical power of the new holdout, before anything is tested on it
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from indicator_lab.swing5 import protocol5 as P

P.install_dev()

from indicator_lab import data, ind, meta  # noqa: E402
from indicator_lab.evaluate import get  # noqa: E402
from indicator_lab.metrics import equity_stats  # noqa: E402
from indicator_lab.swing4 import lab as L  # noqa: E402
from indicator_lab.swing5 import port as PT  # noqa: E402

OUT = os.path.join(P.HERE, "reports")
CACHE = os.path.join(os.environ.get("SWING4_CACHE", "/tmp"), "swing5_ctx_dev.pkl")
PERIOD = P.DEV_PERIOD
SLIP = 0.001          # extra slippage on breakout entries (on top of 0.1% cost per side)
REGIME_MAX = 0.03
NO_SPY = [f for f in meta.FEATS if f not in ("spy_roc63", "spy_up")]
NO_SPY_RS = [f for f in NO_SPY if f != "rs63"]   # rs63 = roc63 - SPY's roc63: it still carries the SPY return
YEARS = list(range(2015, 2025))


def regime(cx):
    return np.nan_to_num(cx["x"]["spy_roc63"], nan=9) <= REGIME_MAX


def v4_entry(cx):
    with np.errstate(invalid="ignore"):
        return L.v3_entry(cx) & regime(cx)


def model_entry(probs):
    """Entries for a model given {ticker: (prob, thr)} arrays: candidate & regime & prob >= thr."""
    def e(cx):
        t = cx["_t"]
        pr, th = probs[t]
        with np.errstate(invalid="ignore"):
            return cx["cand"] & regime(cx) & (pr >= th)
    return e


def model_probs(ctx, mdl, feats):
    out = {}
    cols = meta.FEATS + ["breadth50", "breadth200", "ext200"]
    for t, cx in ctx.items():
        X = pd.DataFrame(cx["feat"][:, [cols.index(f) for f in feats]], columns=feats, index=cx["arr"]["index"])
        out[t] = mdl.prob(X)
    return out


def candidates(ctx, probs: dict) -> pd.DataFrame:
    """Base candidates passing the regime rule in the dev period, single-trade outcome (v3 exits) and model probs."""
    rows = []
    rules = meta.ExitRules(trail_atr=4.0, stop_atr=4.0)
    for t, cx in ctx.items():
        a = cx["arr"]
        o, h, lo, c, atr, ex = a["o"], a["h"], a["l"], a["c"], a["atr"], a["exit_sig"]
        ok = cx["cand"] & regime(cx)
        for i in np.flatnonzero(ok):
            d = a["index"][i]
            if not (PERIOD[0] <= d <= PERIOD[1]) or not np.isfinite(atr[i]):
                continue
            r, xi = meta.single_trade(o, h, lo, c, atr, ex, i, rules)
            if xi == len(c) - 1 or not np.isfinite(r):
                continue
            rows.append({"ticker": t, "date": d, "year": d.year, "ret": r, "R": r / (4 * atr[i] / o[i + 1]),
                         **{f"p_{k}": float(v[t][0][i]) for k, v in probs.items()}})
    return pd.DataFrame(rows)


def auc(y, s):
    from sklearn.metrics import roc_auc_score
    s = np.asarray(s, float)
    ok = np.isfinite(s)
    return float(roc_auc_score(np.asarray(y)[ok], s[ok])) if len(set(np.asarray(y)[ok])) == 2 else np.nan


def coef_table(mdl, feats):
    yrs = [y for y in sorted(mdl.models) if y <= 2024]
    return pd.DataFrame({y: mdl.models[y][2] for y in yrs}, index=feats)


def stable_feats(coef: pd.DataFrame) -> list[str]:
    return [f for f in coef.index if (coef.loc[f] > 0).all() or (coef.loc[f] < 0).all()]


def sysrow(name, res, sysd):
    tt = L.C.trade_table(res)
    t = L.tstats(tt)
    ci = P.bootstrap_ci(tt["R"])
    return {"name": name, **t, "ci_R": ci, **{k: sysd[k] for k in ("cagr", "maxdd", "mar", "sharpe_rf", "alpha", "alpha_t",
                                                                   "beta", "ir", "te", "invested", "parked")},
            "contrib": sysd["contrib_ann"], "mar_range": sysd["mar_range"], "tt": tt}


def main():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    os.makedirs(OUT, exist_ok=True)
    ctx = L.load_ctx(univ=P.DEV_UNIVERSE, path=CACHE)
    for t, cx in ctx.items():
        cx["_t"] = t
    Lr = ["# Swing v5 — phase 0: foundation and bugs (development data only)\n",
          f"Development data: {len(ctx)} tickers (earlier development universe + the spent v4 holdout), entries "
          f"{PERIOD[0].date()} .. {PERIOD[1].date()}; every series is cut before 2024-10-22 and the 155 v5-holdout tickers "
          "are refused. Costs: 0.1% per side + 0.1% extra slippage on every breakout entry. Portfolio: max 10 positions "
          "of 10%; idle capital in SPY while SPY closed above its SMA200 the day before (switches cost 0.1%), otherwise in "
          "T-bills (^IRX); mean of 20 random orders of same-day signals.\n"]

    # ------------------------------------------------------------ 1. complete system
    res4 = L.run(ctx, v4_entry, slip=SLIP)
    res3 = L.run(ctx, L.v3_entry, slip=SLIP)
    S = {"v4 complete (breakouts + SPY parking + regime)": sysrow("v4", res4, PT.system(res4)),
         "v4 breakouts only (idle = T-bills)": sysrow("v4 np", res4, PT.system(res4, park=False)),
         "v3 complete (no regime rule)": sysrow("v3", res3, PT.system(res3)),
         "v3 breakouts only": sysrow("v3 np", res3, PT.system(res3, park=False))}
    sys4 = PT.system(res4)
    idx = sys4["port0"].index
    bench, m = PT.benchmarks(idx)
    Lr.append("## 1. The complete system vs SPY (development period)\n")
    Lr.append("| system | CAGR | max DD | MAR (range over orders) | Sharpe (excess) | beta | alpha / yr (t) | IR vs SPY | "
              "tracking error | in breakouts | in SPY (parked) |\n|" + "---|" * 11)
    for nm, s in S.items():
        Lr.append(f"| {nm} | {s['cagr'] * 100:.1f}% | {s['maxdd'] * 100:.1f}% | {s['mar']:.2f} ({s['mar_range'][0]:.2f}–"
                  f"{s['mar_range'][1]:.2f}) | {s['sharpe_rf']:.2f} | {s['beta']:.2f} | {s['alpha'] * 100:+.1f}% ({s['alpha_t']:.1f}) | "
                  f"{s['ir']:+.2f} | {s['te'] * 100:.1f}% | {s['invested'] * 100:.0f}% | {s['parked'] * 100:.0f}% |")
    for nm, r in bench.items():
        if nm == "T-bills":
            continue
        st = PT.stats(r, m)
        rel = (f"{st['alpha'] * 100:+.1f}% ({st['alpha_t']:.1f}) | {st['ir']:+.2f} | {st['te'] * 100:.1f}%"
               if nm != "SPY buy & hold" else "– | – | –")
        Lr.append(f"| {nm} | {st['cagr'] * 100:.1f}% | {st['maxdd'] * 100:.1f}% | {st['mar']:.2f} | {st['sharpe_rf']:.2f} | "
                  f"{st['beta']:.2f} | {rel} | – | – |")
    Lr.append("\nWhere the return comes from (annualised contribution to the portfolio return, mean of 20 orders):\n")
    Lr.append("| system | breakout positions | SPY parking (after switch costs) | T-bills | total |\n|---|---|---|---|---|")
    for nm, s in S.items():
        c = s["contrib"]
        Lr.append(f"| {nm} | {c['breakouts'] * 100:+.1f}% | {c['spy_parking'] * 100:+.1f}% | {c['cash'] * 100:+.1f}% | "
                  f"{sum(c.values()) * 100:+.1f}% |")
    # beta / alpha of the breakout sleeve on its own: daily breakout P&L per unit invested vs SPY
    runs = [PT.portfolio(res4, 10, s) for s in range(20)]
    sleeve = pd.concat([r["contrib"]["breakouts"] / np.maximum(r["invested"], 1e-9) for r in runs], axis=1).mean(axis=1)
    sleeve = sleeve.where(np.mean([r["invested"] for r in runs], axis=0) > 0.05)
    mm = m.loc[sleeve.dropna().index]
    sl = sleeve.dropna()
    b_sl = float(np.cov(sl - mm["rf"], mm["spy"] - mm["rf"])[0, 1] / np.var(mm["spy"] - mm["rf"], ddof=1))
    a_sl = float(((sl - mm["rf"]) - b_sl * (mm["spy"] - mm["rf"])).mean() * 252)
    Lr.append(f"\nThe breakout positions themselves (return per invested dollar, days with >5% invested): beta {b_sl:.2f}, "
              f"alpha {a_sl * 100:+.1f}% per year on the invested capital.\n")
    yr = pd.DataFrame({"v4 complete": sys4["port0"], "SPY": bench["SPY buy & hold"],
                       "60/40": bench["60/40 SPY / T-bills"]}).groupby(idx.year).apply(lambda d: (1 + d).prod() - 1)
    Lr.append("Calendar-year returns (one random order for v4):\n")
    Lr.append("| year | v4 complete | SPY | 60/40 |\n|---|---|---|---|")
    for y, r in yr.iterrows():
        Lr.append(f"| {y} | {r['v4 complete'] * 100:+.1f}% | {r['SPY'] * 100:+.1f}% | {r['60/40'] * 100:+.1f}% |")
    fig, ax = plt.subplots(figsize=(10, 4.5))
    for nm, r in (("v4 complete", sys4["port0"]), ("v4 breakouts only", PT.system(res4, park=False, seeds=1)["port0"]),
                  ("SPY buy & hold", bench["SPY buy & hold"]), ("60/40 SPY / T-bills", bench["60/40 SPY / T-bills"])):
        ax.plot(idx, (1 + r).cumprod(), label=nm)
    ax.set_yscale("log")
    ax.legend()
    ax.set_title("Development period: complete system vs benchmarks (costs + 0.1% entry slippage)")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "p0_equity.png"), dpi=100)
    plt.close(fig)
    for nm, s in S.items():
        P.log({"phase": "P0", "idea": nm, "params": {"slip": SLIP}, "new_free_params": 0, "universe": f"DEV5 {len(ctx)}",
               "period": "2015-01-01..2024-10-21", "n": s["n"], "win": s["win"], "exp_pct": s["exp_pct"], "exp_R": s["exp_R"],
               "pf": s["pf"], "avg_win": s["avg_win"], "avg_loss": s["avg_loss"], "cagr": s["cagr"], "maxdd": s["maxdd"],
               "mar": s["mar"], "hold": s["hold"], "exposure": s["invested"], "exp_ci_lo": s["ci_R"][0],
               "exp_ci_hi": s["ci_R"][1], "accepted": "baseline" if nm.startswith("v4 complete") else "n/a",
               "notes": f"alpha {s['alpha']:.4f} beta {s['beta']:.2f} IR {s['ir']:.2f}"})

    # ------------------------------------------------------------ 2. drawdown convention (code fix; effect measured
    # with the old and the new pine_sim on the same data, see reports/p0_ddfix.md)
    Lr.append("\n## 2. Pine engine: drawdown inside a trade on the entry bar\n")
    Lr.append("Before: on the fill bar the peak was the open and the low was compared with it (low-before-high), on later "
              "bars the high came first. Now every bar uses high-before-low (the fill bar's high counts, a stop inside the bar "
              "counts that bar's high first, an exit at the open does not), in Pine v3/v4, pine_sim and swing4.sim2; "
              "tests/test_pine_sim.py checks pine_sim = sim2 trade by trade. Trades and returns do not change.\n")
    ddf = os.path.join(OUT, "p0_ddfix.md")
    if os.path.exists(ddf):
        with open(ddf) as fh:
            Lr.append(fh.read())

    # ------------------------------------------------------------ 3. model without the SPY features
    tab = meta.candidate_table(data.DEV, 20, 20, 4.0, 0.7, 200)
    tab_reg = tab[tab["spy_roc63"] <= REGIME_MAX]
    mods = {"v4 model (17 features)": (L.C.model(), meta.FEATS),
            "without spy_roc63/spy_up (15; rs63 keeps SPY inside)": (meta.YearlyModels(tab, feats=NO_SPY, keep=0.75, l2=100.0), NO_SPY),
            "no SPY at all: also without rs63 (14)": (meta.YearlyModels(tab, feats=NO_SPY_RS, keep=0.75, l2=100.0), NO_SPY_RS),
            "no SPY at all (14), trained on regime-passing breakouts": (meta.YearlyModels(tab_reg, feats=NO_SPY_RS, keep=0.75, l2=100.0), NO_SPY_RS)}
    coefs = {k: coef_table(v[0], v[1]) for k, v in mods.items() if k.startswith("no SPY at all")}
    for k in list(coefs):
        keep = stable_feats(coefs[k])
        rounds = [keep]
        while True:  # refit on the sign-stable features until no feature flips any more
            sub = tab if "regime" not in k else tab_reg
            mm_ = meta.YearlyModels(sub, feats=keep, keep=0.75, l2=100.0)
            c2 = coef_table(mm_, keep)
            k2 = stable_feats(c2)
            if k2 == keep or not k2:
                break
            keep = k2
            rounds.append(keep)
        mods[f"{k}: sign-stable subset ({len(keep)})"] = (mm_, keep)
        coefs[f"{k}: sign-stable subset ({len(keep)})"] = c2
    probs = {k: model_probs(ctx, v[0], v[1]) for k, v in mods.items()}
    cd = candidates(ctx, probs)
    cd["win"] = (cd.ret > 0).astype(int)
    Lr.append("\n## 3. Double counting of the regime: the model without spy_roc63 / spy_up\n")
    Lr.append(f"Evaluated on the {len(cd)} base candidates that pass the regime rule (each traded on its own with the v3 exits).\n")
    names = list(mods)
    Lr.append("| model | " + " | ".join(str(y) for y in YEARS) + " | mean AUC | Q5 − Q1 exp R | Q5 win |\n|" + "---|" * (len(YEARS) + 4))
    for k in names:
        aucs = [auc(g.win, g[f"p_{k}"]) for _, g in cd.groupby("year")]
        q = cd.groupby("year")[f"p_{k}"].transform(
            lambda s: pd.qcut(s.rank(method="first"), 5, labels=False) + 1 if s.notna().sum() >= 5 else s * np.nan)
        qq = cd.groupby(q).agg(R=("R", "mean"), win=("win", "mean"))
        Lr.append(f"| {k} | " + " | ".join(f"{v:.3f}" for v in aucs) + f" | {np.nanmean(aucs):.3f} | "
                  f"{qq.R.iloc[-1] - qq.R.iloc[0]:+.3f} | {qq.win.iloc[-1] * 100:.1f}% |")
    Lr.append("\nThe same models as the v4 entry filter (candidate & regime & top 75% of the model), complete system:\n")
    Lr.append("| model | trades | win | exp R [95% CI] | exp % | PF | CAGR | max DD | MAR | alpha | IR |\n|" + "---|" * 11)
    sysm = {}
    for k in names:
        r_ = L.run(ctx, model_entry(probs[k]), slip=SLIP)
        sysm[k] = sysrow(k, r_, PT.system(r_))
        s = sysm[k]
        Lr.append(f"| {k} | {s['n']} | {s['win'] * 100:.1f}% | {s['exp_R']:.3f} [{s['ci_R'][0]:.2f}, {s['ci_R'][1]:.2f}] | "
                  f"{s['exp_pct'] * 100:.2f}% | {s['pf']:.2f} | {s['cagr'] * 100:.1f}% | {s['maxdd'] * 100:.1f}% | {s['mar']:.2f} | "
                  f"{s['alpha'] * 100:+.1f}% | {s['ir']:+.2f} |")
        P.log({"phase": "P0-model", "idea": k, "params": {"feats": mods[k][1]}, "new_free_params": 0,
               "universe": f"DEV5 {len(ctx)}", "period": "2015-01-01..2024-10-21", "n": s["n"], "win": s["win"],
               "exp_pct": s["exp_pct"], "exp_R": s["exp_R"], "pf": s["pf"], "avg_win": s["avg_win"],
               "avg_loss": s["avg_loss"], "cagr": s["cagr"], "maxdd": s["maxdd"], "mar": s["mar"], "hold": s["hold"],
               "exposure": s["invested"], "exp_ci_lo": s["ci_R"][0], "exp_ci_hi": s["ci_R"][1], "accepted": "diagnosis"})
    for k, c in coefs.items():
        pos, neg = (c > 0).sum(axis=1), (c < 0).sum(axis=1)
        Lr.append(f"\nCoefficients x100 per walk-forward year — {k}:\n")
        Lr.append("| feature | " + " | ".join(str(y) for y in c.columns) + " | + | − |\n|" + "---|" * (len(c.columns) + 3))
        for f in c.abs().mean(axis=1).sort_values(ascending=False).index:
            Lr.append(f"| {f} | " + " | ".join(f"{v * 100:.1f}" for v in c.loc[f]) + f" | {pos[f]} | {neg[f]} |")

    # ------------------------------------------------------------ 4. power of the new holdout
    tt4 = S["v4 complete (breakouts + SPY parking + regime)"]["tt"]
    tyears = sum(max(0.0, (min(PERIOD[1], cx["arr"]["index"][-1]) - max(PERIOD[0], cx["arr"]["index"][0])).days / 365.25)
                 for cx in ctx.values())
    rate = len(tt4) / tyears
    sdR = float(tt4.R.std())
    n_tick = rate * len(P.H_TICKERS) * 9.8
    n_tt = rate * len(P.H_TICKERS) * 2.0
    z = 1.96 + 0.84
    port = sys4["port0"]
    te = S["v4 complete (breakouts + SPY parking + regime)"]["te"]
    Lr.append("\n## 4. Statistical power of the new holdout (computed before any test)\n")
    Lr.append(f"- v4 takes {rate:.2f} trades per ticker-year (development), SD of a trade result {sdR:.2f}R.")
    Lr.append(f"- Expected trades: ticker holdout (155 tickers x 9.8 y) ≈ **{n_tick:.0f}**; ticker + time holdout (2 y) ≈ "
              f"**{n_tt:.0f}**.")
    for nm, n in (("ticker holdout", n_tick), ("ticker + time holdout", n_tt)):
        Lr.append(f"- {nm}: minimal detectable expectancy vs 0 (80% power, 5% two-sided): {z * sdR / np.sqrt(n):.3f}R; "
                  f"difference between two independent systems of that size: {z * sdR * np.sqrt(2 / n):.3f}R "
                  "(much less when v5 and v4 share most trades and the difference is tested pairwise).")
    for nm, T in (("9.8 years", 9.8), ("2 years", 2.0)):
        Lr.append(f"- Portfolio over {nm}: alpha vs SPY is only detectable if it exceeds ≈ {z * te / np.sqrt(T) * 100:.1f}% per "
                  f"year (tracking error {te * 100:.1f}%), i.e. an information ratio of {z / np.sqrt(T):.2f}.")
    Lr.append(f"\nTrials logged in swing5/experiments.csv: {P.n_trials()}.")
    with open(os.path.join(OUT, "phase0.md"), "w") as fh:
        fh.write("\n".join(Lr) + "\n")
    print("\n".join(Lr))


if __name__ == "__main__":
    main()
