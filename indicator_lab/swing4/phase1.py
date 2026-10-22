"""Phase 1 of the swing v4 round: diagnosis of v3 on the development data (no holdout).

    python -m indicator_lab.swing4.phase1      # writes reports/phase1.md + figures, logs the baselines

Runs with `protocol.install_dev_cutoff()`: every series ends on 2024-10-21 and holdout tickers are refused.
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from indicator_lab.swing4 import protocol as P

P.install_dev_cutoff()

from indicator_lab import data, ind, meta
from indicator_lab.evaluate import get
from indicator_lab.swing4 import core as C

OUT = os.path.join(P.HERE, "reports")
PERIOD = P.DEV_PERIOD
STABLE = ["rvol", "spy_roc63", "er20"]
SEEDS = 20


def auc(y, s) -> float:
    from sklearn.metrics import roc_auc_score
    y, s = np.asarray(y), np.asarray(s, float)
    ok = np.isfinite(s)
    y, s = y[ok], s[ok]
    return float(roc_auc_score(y, s)) if len(set(y)) == 2 else np.nan


def candidates(univ, models: dict) -> pd.DataFrame:
    """Every base candidate (breakout + IBS + SMA200) in the dev period, its single-trade outcome with the v3 exits
    (each candidate on its own, overlap ignored) and the OOS probability of each model."""
    rows = []
    rules = meta.ExitRules(trail_atr=4.0, stop_atr=4.0)
    for t in univ:
        df = get(t)
        f = meta.feature_frame(df)
        cand = meta.base_candidates(df, 20, 0.7, 200).to_numpy()
        ex = (df["close"] < df["low"].rolling(20).min().shift(1)).to_numpy()
        o, h, lo, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
        a = ind.atr(df, 14).to_numpy()
        probs = {k: m.prob(f)[0] for k, m in models.items()}
        for i in np.flatnonzero(cand):
            d = df.index[i]
            if not (PERIOD[0] <= d <= PERIOD[1]) or not np.isfinite(a[i]):
                continue
            r, xi = meta.single_trade(o, h, lo, c, a, ex, i, rules)
            if xi == len(c) - 1 or not np.isfinite(r):
                continue
            rows.append({"ticker": t, "date": d, "year": d.year, "ret": r, "R": r / (4 * a[i] / o[i + 1]),
                         **{f"p_{k}": float(v[i]) for k, v in probs.items()}})
    return pd.DataFrame(rows)


def system(res) -> dict:
    tt = C.trade_table(res)
    runs = [C.portfolio(res, 10, s) for s in range(SEEDS)]
    pf = {m: float(np.mean([x[m] for x in runs])) for m in ("cagr", "maxdd", "mar", "sharpe", "exposure", "taken",
                                                              "skipped", "signal_days", "crowded_days")}
    pf.update({f"{m}_min": float(np.min([x[m] for x in runs])) for m in ("cagr", "mar")})
    pf.update({f"{m}_max": float(np.max([x[m] for x in runs])) for m in ("cagr", "mar")})
    return {**C.trade_metrics(tt), **pf, "ci_pct": P.bootstrap_ci(tt["ret"]), "ci_R": P.bootstrap_ci(tt["R"]),
            "tt": tt, "equity": runs[0]["equity"], "res": res}


def fmt_sys(name, s) -> str:
    return (f"| {name} | {s['n']} | {s['win']*100:.1f}% | {s['exp_pct']*100:.2f}% [{s['ci_pct'][0]*100:.2f}, "
            f"{s['ci_pct'][1]*100:.2f}] | {s['exp_R']:.3f} [{s['ci_R'][0]:.3f}, {s['ci_R'][1]:.3f}] | {s['pf']:.2f} | "
            f"{s['avg_win']*100:.1f}% / {s['avg_loss']*100:.1f}% ({s['avg_win_R']:.2f}R / {s['avg_loss_R']:.2f}R) | "
            f"{s['cagr']*100:.1f}% ({s['cagr_min']*100:.1f}–{s['cagr_max']*100:.1f}) | {s['maxdd']*100:.1f}% | "
            f"{s['mar']:.2f} ({s['mar_min']:.2f}–{s['mar_max']:.2f}) | {s['hold']:.0f} | {s['exposure']*100:.0f}% |")


SYS_HEAD = ("| system | trades | win | exp % [95% CI] | exp R [95% CI] | PF | avg win / avg loss | CAGR (range over "
            f"{SEEDS} orders) | max DD | MAR (range) | hold (bars) | exposure |\n|" + "---|" * 12)


def anatomy(tt: pd.DataFrame) -> dict:
    out = {"levels": []}
    for k in C.LEVELS:
        hit = tt["touch"].apply(lambda d, k=k: d[k] is not None)
        s = tt[hit]
        out["levels"].append({"level": k, "share": hit.mean(), "n": int(hit.sum()), "end_loss": (s.R <= 0).mean(),
                              "end_flat": (s.R.abs() < 0.25).mean(), "end_below_half": (s.R < 0.5).mean(),
                              "final_R": s.R.mean()})
    never = tt["touch"].apply(lambda d: d[0.5] is None)
    out["never_half"] = (never.mean(), tt[never].R.mean())
    w = tt[tt.R > 0]
    gb = w.mfe_R - w.R_gross
    out["winners"] = (w.mfe_R.mean(), w.R_gross.mean(), gb.mean(), (gb / w.mfe_R).mean(), (gb / w.mfe_R).median())
    srt = tt.sort_values("ret", ascending=False)
    n10 = round(0.1 * len(tt))
    top = srt.head(n10)
    out["top10"] = (n10, top.ret.sum() / tt.ret.sum(), top.R.sum() / tt.R.sum(), top.R.mean(), top.bars.mean(),
                    top.mfe_R.mean(), srt.iloc[n10:].R.mean(), (srt.iloc[n10:].ret > 0).mean())
    out["top5_1"] = (srt.head(int(0.05 * len(tt))).ret.sum() / tt.ret.sum(),
                     srt.head(int(0.01 * len(tt))).ret.sum() / tt.ret.sum())
    b1 = tt["touch"].apply(lambda d: d[1.0]).dropna()
    out["bars_1R"] = (b1.median(), (tt["touch"].apply(lambda d: d[0.5] is None or d[0.5] > 10)).mean())
    out["reasons"] = tt.reason.value_counts().to_dict()
    return out


def buy_profile(tt: pd.DataFrame) -> pd.DataFrame:
    f = pd.DataFrame(list(tt.feat))
    f["prob"] = tt.prob.values
    extra = {"atr1y_pct": [], "roc252": [], "log_dollar_vol": []}
    cache = {}
    for t, ei in zip(tt.ticker, tt.entry_i):
        if t not in cache:
            df = get(t)
            atrp = ind.atr(df, 14) / df["close"] * 100
            cache[t] = (atrp.rolling(252, min_periods=200).mean().to_numpy(),
                        (df["close"] / df["close"].shift(252) - 1).to_numpy(),
                        np.log10((df["close"] * df["volume"]).rolling(50).mean().to_numpy()))
        for j, k in enumerate(extra):
            extra[k].append(cache[t][j][ei - 1])
    for k, v in extra.items():
        f[k] = v
    win = (tt.R > 0).to_numpy()
    rows = []
    for c in [c for c in f.columns if "*" not in c and "^" not in c]:
        x = f[c].astype(float).to_numpy()
        ok = np.isfinite(x)
        sd = np.std(x[ok])
        rows.append({"feature": c, "winners": np.mean(x[ok & win]), "losers": np.mean(x[ok & ~win]),
                     "d": (np.mean(x[ok & win]) - np.mean(x[ok & ~win])) / sd if sd > 0 else 0.0,
                     "AUC": auc(win[ok], x[ok]),
                     "rho_R": pd.Series(x[ok]).corr(pd.Series(tt.R.to_numpy()[ok]), method="spearman")})
    return pd.DataFrame(rows).assign(absd=lambda d: d.d.abs()).sort_values("absd", ascending=False).drop(columns="absd")


def figures(coef: pd.DataFrame, q: pd.DataFrame, systems: dict, tt: pd.DataFrame) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(9, 6))
    v = np.abs(coef.values).max()
    im = ax.imshow(coef.values, cmap="RdBu_r", vmin=-v, vmax=v, aspect="auto")
    ax.set_xticks(range(coef.shape[1]), coef.columns)
    ax.set_yticks(range(coef.shape[0]), coef.index)
    for i in range(coef.shape[0]):
        for j in range(coef.shape[1]):
            ax.text(j, i, f"{coef.values[i, j] * 100:.0f}", ha="center", va="center", fontsize=7)
    fig.colorbar(im, ax=ax, label="standardised coefficient")
    ax.set_title("v3 model: coefficient per walk-forward year (x100)")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "p1_coefficients.png"), dpi=110)
    plt.close(fig)

    fig, ax = plt.subplots(1, 2, figsize=(10, 3.5))
    ax[0].bar(q.index.astype(str), q["exp_R"], color="#4a7bd0")
    ax[0].set_title("expectancy (R) per v3 quality quintile")
    ax[0].set_xlabel("quintile within year (5 = best score)")
    ax[1].bar(q.index.astype(str), q["win"], color="#4a7bd0")
    ax[1].set_title("win rate % per quintile")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "p1_quintiles.png"), dpi=110)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 4))
    for nm, s in systems.items():
        ax.plot(s["equity"].index, s["equity"].values, label=f"{nm} (seed 0)")
    ax.set_yscale("log")
    ax.legend()
    ax.set_title("10-position portfolio, development period (one random selection order)")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "p1_equity.png"), dpi=110)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6, 5))
    ax.scatter(tt.mfe_R, tt.R, s=3, alpha=0.25)
    ax.plot([0, 8], [0, 8], color="gray", lw=0.8)
    ax.set_xlim(-0.2, 8)
    ax.set_ylim(-1.3, 8)
    ax.set_xlabel("MFE before the exit bar (R)")
    ax.set_ylabel("final result (R, net)")
    ax.set_title("v3 trades: best open profit vs result")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "p1_mfe_vs_R.png"), dpi=110)
    plt.close(fig)


def main():
    os.makedirs(OUT, exist_ok=True)
    univ = P.DEV_UNIVERSE
    L = []

    # 1. coefficient stability
    full = C.model()
    yrs = [y for y in sorted(full.models) if y <= 2024]
    coef = pd.DataFrame({y: full.models[y][2] for y in yrs}, index=meta.FEATS)
    coef.to_csv(os.path.join(OUT, "p1_coef_by_year.csv"))
    pos, neg = (coef > 0).sum(axis=1), (coef < 0).sum(axis=1)

    # 2. model value
    models = {"v3": full, "stable": C.model(STABLE)}
    cd = candidates(univ, models)
    cd["win"] = (cd.ret > 0).astype(int)
    a = pd.DataFrame([{"year": y, "n": len(g), "win": g.win.mean(), "v3": auc(g.win, g.p_v3),
                       "stable": auc(g.win, g.p_stable)} for y, g in cd.groupby("year")])
    cd["q"] = cd.groupby("year")["p_v3"].transform(lambda s: pd.qcut(s.rank(method="first"), 5, labels=False) + 1)
    cd["qs"] = cd.groupby("year")["p_stable"].transform(lambda s: pd.qcut(s.rank(method="first"), 5, labels=False) + 1)
    q = cd.groupby("q").agg(n=("ret", "size"), win=("win", "mean"), exp_pct=("ret", "mean"), exp_R=("R", "mean"))
    qs = cd.groupby("qs").agg(n=("ret", "size"), win=("win", "mean"), exp_pct=("ret", "mean"), exp_R=("R", "mean"))
    for d in (q, qs):
        d["win"] *= 100
        d["exp_pct"] *= 100
    q51 = cd.groupby(["year", "q"]).R.mean().unstack()
    q51 = (q51[5] - q51[1])

    systems = {"v2 (no model)": system(C.run_universe(univ, use_model=False, period=PERIOD)),
               "v3 (baseline)": system(C.run_universe(univ, period=PERIOD)),
               "v3 stable features": system(C.run_universe(univ, feats=STABLE, period=PERIOD))}
    base = systems["v3 (baseline)"]["tt"]
    for nm, s in systems.items():
        cmp = C.compare(s["tt"], base, P.HALF_A, P.HALF_B) if nm != "v3 (baseline)" else {}
        P.log({"phase": "P1", "idea": nm, "params": {"model": nm}, "new_free_params": 0, "universe": "DEV-U 253",
               "period": "2015-01-01..2024-10-21", "n": s["n"], "win": s["win"], "exp_pct": s["exp_pct"],
               "exp_R": s["exp_R"], "pf": s["pf"], "avg_win": s["avg_win"], "avg_loss": s["avg_loss"],
               "cagr": s["cagr"], "maxdd": s["maxdd"], "mar": s["mar"], "hold": s["hold"], "exposure": s["exposure"],
               "exp_ci_lo": s["ci_R"][0], "exp_ci_hi": s["ci_R"][1], **cmp, "accepted": "baseline" if not cmp else "n/a (diagnosis)",
               "notes": f"portfolio = mean of {SEEDS} random selection orders"})

    # 3. anatomy, 4. profile
    tt = systems["v3 (baseline)"]["tt"]
    an = anatomy(tt)
    prof = buy_profile(tt)
    prof.to_csv(os.path.join(OUT, "p1_buy_profile.csv"), index=False)
    yearly = tt.groupby(tt.entry_date.dt.year).agg(n=("R", "size"), win=("R", lambda x: (x > 0).mean() * 100),
                                                   exp_R=("R", "mean"))

    # survivorship
    groups = {"DEV (mega caps, hindsight)": data.DEV, "old HOLDOUT (large caps)": data.HOLDOUT,
              "TRAIN_EXTRA (large caps)": data.TRAIN_EXTRA, "VOLATILE (incl. later collapses)": data.VOLATILE,
              "LOCKBOX (2015-25 winners, hindsight)": data.LOCKBOX, "LOCKBOX2 (quality compounders)": data.LOCKBOX2}
    surv = [(g, tt[tt.ticker.isin(ts)]) for g, ts in groups.items()]
    ends = [t for t in univ if get(t).index[-1] < pd.Timestamp("2024-10-01")]

    figures(coef, q, {k: v for k, v in systems.items()}, tt)

    # ---------------- report
    L.append("# Swing v4 — phase 1: diagnosis of v3 (development data only)\n")
    L.append(f"Development data: {len(univ)} tickers (every ticker used in earlier sessions), entries 2015-01-01 .. "
             "2024-10-21; every series is cut before the holdout start (2024-10-22) and the 84 holdout tickers are "
             "refused by the data loader. Costs 0.1% per side. R = 4 x ATR(signal bar) = the initial stop distance. "
             f"Portfolio: max 10 positions of 10% each, same-day signals in random order, averaged over {SEEDS} orders. "
             "Model trained on DEV (15 tickers) and refit every year on trades closed before 1 January.\n")
    L.append("## Baselines\n")
    L.append(SYS_HEAD)
    for nm, s in systems.items():
        L.append(fmt_sys(nm, s))
    b3 = systems["v3 (baseline)"]
    L.append(f"\nPortfolio crowding (v3): {b3['taken']:.0f} of {b3['n']} trades taken ({100 * b3['taken'] / b3['n']:.0f}%), "
             f"{b3['crowded_days']:.0f} of {b3['signal_days']:.0f} signal days had more signals than free slots.")
    L.append("\nv3 per year (trade level):\n")
    L.append("| year | trades | win % | exp R |\n|---|---|---|---|")
    for y, r in yearly.iterrows():
        L.append(f"| {y} | {r.n:.0f} | {r.win:.1f} | {r.exp_R:.3f} |")

    L.append("\n## 1. Feature stability (standardised coefficient x100 per walk-forward fit)\n")
    L.append("| feature | " + " | ".join(str(y) for y in yrs) + " | + years | − years |\n|" + "---|" * (len(yrs) + 3))
    for f_ in coef.abs().mean(axis=1).sort_values(ascending=False).index:
        L.append(f"| {f_} | " + " | ".join(f"{v * 100:.1f}" for v in coef.loc[f_]) + f" | {pos[f_]} | {neg[f_]} |")
    L.append("\n![coefficients](p1_coefficients.png)\n")

    L.append("## 2. What the model adds out of sample\n")
    L.append("AUC (win/loss of each candidate traded on its own) per year:\n")
    L.append("| year | candidates | win % | AUC v3 (17 features) | AUC 3 stable features |\n|---|---|---|---|---|")
    for _, r in a.iterrows():
        L.append(f"| {r.year:.0f} | {r.n:.0f} | {r.win * 100:.1f} | {r.v3:.3f} | {r.stable:.3f} |")
    L.append(f"| mean | | | {a.v3.mean():.3f} | {a.stable.mean():.3f} |")
    L.append("\nQuality quintiles (ranked within each year; each candidate traded on its own):\n")
    L.append("| quintile | v3: n | win % | exp % | exp R | stable: win % | exp % | exp R |\n|---|---|---|---|---|---|---|---|")
    for i in q.index:
        L.append(f"| Q{i} | {q.n[i]} | {q.win[i]:.1f} | {q.exp_pct[i]:.2f} | {q.exp_R[i]:.3f} | {qs.win[i]:.1f} | "
                 f"{qs.exp_pct[i]:.2f} | {qs.exp_R[i]:.3f} |")
    L.append("\nQ5 − Q1 (exp R) per year, v3: " + ", ".join(f"{y}: {v:+.2f}" for y, v in q51.items()))
    L.append("\n![quintiles](p1_quintiles.png)\n")

    L.append("## 3. Trade anatomy (v3, MFE/MAE in R; path = bars before the exit bar)\n")
    L.append("| touched before exit | share of trades | of those: end as loss | end within ±0.25R | end below +0.5R | "
             "mean final R |\n|---|---|---|---|---|---|")
    for lv in an["levels"]:
        L.append(f"| +{lv['level']}R | {lv['share'] * 100:.1f}% ({lv['n']}) | {lv['end_loss'] * 100:.1f}% | "
                 f"{lv['end_flat'] * 100:.1f}% | {lv['end_below_half'] * 100:.1f}% | {lv['final_R']:.2f} |")
    w = an["winners"]
    t10 = an["top10"]
    L.append(f"\n- Never touched +0.5R: {an['never_half'][0] * 100:.1f}% of trades, mean result {an['never_half'][1]:.2f}R.")
    L.append(f"- Winners: mean MFE {w[0]:.2f}R, mean exit {w[1]:.2f}R → give back {w[2]:.2f}R = {w[3] * 100:.0f}% of "
             f"their best open profit (median {w[4] * 100:.0f}%).")
    L.append(f"- Top 10% trades ({t10[0]}): **{t10[1] * 100:.0f}% of the total net P&L** ({t10[2] * 100:.0f}% of total R); "
             f"mean {t10[3]:.2f}R, hold {t10[4]:.0f} bars, MFE {t10[5]:.2f}R. The other 90%: {t10[6]:.3f}R per trade, "
             f"win {t10[7] * 100:.1f}%. Top 5%: {an['top5_1'][0] * 100:.0f}%, top 1%: {an['top5_1'][1] * 100:.0f}% of P&L.")
    L.append(f"- Median bars to +1R (if reached): {an['bars_1R'][0]:.0f}; {an['bars_1R'][1] * 100:.0f}% of trades had not "
             f"touched +0.5R within 10 bars. Exit reasons: {an['reasons']}.")
    L.append("\n![mfe](p1_mfe_vs_R.png)\n")

    L.append("## 4. Winners vs losers at the BUY (v3 trades; d = standardised mean difference)\n")
    L.append("| feature | winners | losers | d | AUC | Spearman with R |\n|---|---|---|---|---|---|")
    for _, r in prof.head(16).iterrows():
        L.append(f"| {r.feature} | {r.winners:.3f} | {r.losers:.3f} | {r.d:+.3f} | {r.AUC:.3f} | {r.rho_R:+.3f} |")

    L.append("\n## 5. Portfolio\n")
    for nm, s in systems.items():
        L.append(f"- {nm}: CAGR {s['cagr'] * 100:.1f}% (range {s['cagr_min'] * 100:.1f}–{s['cagr_max'] * 100:.1f}% over "
                 f"{SEEDS} random orders), MAR {s['mar']:.2f} ({s['mar_min']:.2f}–{s['mar_max']:.2f}); "
                 f"{s['taken']:.0f} of {s['n']} signals taken, {s['crowded_days']:.0f}/{s['signal_days']:.0f} signal days crowded.")
    L.append("\n![equity](p1_equity.png)\n")

    L.append("## Survivorship\n")
    L.append(f"- Tickers in the development universe whose data stops before the cutoff (delisted): {len(ends)}. "
             "yfinance has no delisted symbols, so every universe here consists of survivors.")
    L.append("| group | trades | win % | exp R |\n|---|---|---|---|")
    for g, s in surv:
        L.append(f"| {g} | {len(s)} | {(s.R > 0).mean() * 100:.1f} | {s.R.mean():.3f} |")
    L.append(f"\nExperiments logged so far: {P.n_trials()}.")
    with open(os.path.join(OUT, "phase1.md"), "w") as fh:
        fh.write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
