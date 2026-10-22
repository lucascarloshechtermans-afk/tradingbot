"""Phase 2 report: every logged trial, heatmaps of the 2-parameter grids, the accepted idea and the deflated Sharpe.

    python -m indicator_lab.swing4.report2     (after phase2.py has run; reads experiments.csv and the run pickles)
"""
from __future__ import annotations

import json
import os
import pickle

import numpy as np
import pandas as pd
from scipy.stats import norm

from indicator_lab.swing4 import protocol as P

OUT = os.path.join(P.HERE, "reports")
SCR = os.environ.get("SWING4_CACHE", "/tmp")
FLAG_NAMES = ["win↑", "exp%", "expR", "MAR", "≥70% yrs", "half A", "half B", "≤2 par"]


def deflated_sharpe(ret: pd.Series, sharpes_ann: np.ndarray) -> dict:
    """Bailey & Lopez de Prado: probability that the selected strategy's Sharpe beats the best of N unskilled trials."""
    r = ret.dropna().to_numpy()
    T = len(r)
    sr = r.mean() / r.std()
    sk = pd.Series(r).skew()
    ku = pd.Series(r).kurt() + 3
    s = np.asarray(sharpes_ann) / np.sqrt(252)
    N = len(s)
    g = 0.5772156649
    sr0 = np.sqrt(np.var(s, ddof=1)) * ((1 - g) * norm.ppf(1 - 1 / N) + g * norm.ppf(1 - 1 / (N * np.e)))
    z = (sr - sr0) * np.sqrt(T - 1) / np.sqrt(1 - sk * sr + (ku - 1) / 4 * sr ** 2)
    return {"sr_ann": sr * np.sqrt(252), "sr0_ann": sr0 * np.sqrt(252), "N": N, "dsr": float(norm.cdf(z))}


def heat(ax, df, x, y, v, fmt, title):
    piv = df.pivot_table(index=y, columns=x, values=v)
    im = ax.imshow(piv.values, cmap="viridis", aspect="auto", origin="lower")
    ax.set_xticks(range(piv.shape[1]), [str(c) for c in piv.columns])
    ax.set_yticks(range(piv.shape[0]), [str(c) for c in piv.index])
    ax.set_xlabel(x)
    ax.set_ylabel(y)
    for i in range(piv.shape[0]):
        for j in range(piv.shape[1]):
            ax.text(j, i, fmt.format(piv.values[i, j]), ha="center", va="center", color="w", fontsize=8)
    ax.set_title(title, fontsize=9)
    return im


def main():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    ex = pd.read_csv(P.EXP_LOG)
    base = ex[ex.idea == "v3 (baseline)"].iloc[0]
    runs = {}
    for fam in "ABCDEFG":
        p = os.path.join(SCR, f"p2_{fam}.pkl")
        if os.path.exists(p):
            with open(p, "rb") as fh:
                for e in pickle.load(fh):
                    runs[e["name"]] = e
    p2 = ex[ex.phase.isin(["P2", "P2-stack"])].copy()
    p2["prm"] = p2.params.apply(json.loads)
    # one table row per trial
    rows = []
    for _, r in p2.iterrows():
        e = runs.get(r.idea)
        flags = "".join("✓" if v else "·" for v in e["crit"].values()) if e else ""
        rows.append({"family": r.idea.split()[0][0], "idea": r.idea, "phase": r.phase, "n": r.n, "win": r.win,
                     "exp_pct": r.exp_pct, "exp_R": r.exp_R, "pf": r.pf, "avg_win": r.avg_win, "avg_loss": r.avg_loss,
                     "cagr": r.cagr, "maxdd": r.maxdd, "mar": r.mar, "hold": r.hold, "exposure": r.exposure,
                     "years": r.years_better, "flags": flags, "accepted": r.accepted,
                     "sharpe": e["port"]["sharpe"] if e else np.nan, "top10_R": e["top10_R"] if e else np.nan})
    tab = pd.DataFrame(rows)
    tab.to_csv(os.path.join(OUT, "p2_trials.csv"), index=False)

    # heatmaps of the 2-parameter grids (win %, exp R, MAR)
    grids = {"A1 partial": ("level", "frac"), "A3 tight trail": ("tight_at", "tight_mult"),
             "A5 over-extension": ("ox_atr", "frac"), "A7 pre-earnings": ("earn_days", "frac"),
             "C3 earnings": ("days", "gap"), "D1 buy-stop": ("e_buf", "e_days"), "D2 pullback close": ("pb", "e_days")}
    fig, axes = plt.subplots(len(grids), 3, figsize=(12, 3.0 * len(grids)))
    for k, (pref, (x, y)) in enumerate(grids.items()):
        sub = p2[p2.idea.str.startswith(pref)]
        d = pd.DataFrame([{**r.prm, "win": r.win * 100, "exp_R": r.exp_R, "mar": r.mar} for _, r in sub.iterrows()])
        if d.empty or x not in d or y not in d:
            continue
        d = d.dropna(subset=[x, y])
        heat(axes[k, 0], d, x, y, "win", "{:.1f}", f"{pref}: win % (base {base.win * 100:.1f})")
        heat(axes[k, 1], d, x, y, "exp_R", "{:.3f}", f"{pref}: exp R (base {base.exp_R:.3f}, -15% = {0.85 * base.exp_R:.3f})")
        heat(axes[k, 2], d, x, y, "mar", "{:.2f}", f"{pref}: MAR (base {base.mar:.2f})")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "p2_heatmaps.png"), dpi=100)
    plt.close(fig)

    f1 = p2[p2.idea.str.startswith("F1 SPY")].copy()
    f1["v"] = f1.prm.apply(lambda d: d["spy_roc63_max"])
    fig, ax = plt.subplots(1, 3, figsize=(11, 3))
    for a_, col, b_, ttl in ((ax[0], "win", base.win, "win rate"), (ax[1], "exp_R", base.exp_R, "exp R"),
                             (ax[2], "mar", base.mar, "MAR")):
        a_.plot(f1.v, f1[col], "o-", label="F1")
        a_.axhline(b_, color="gray", ls="--", label="v3")
        a_.set_title(f"F1: {ttl} vs max SPY 63d return", fontsize=9)
        a_.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "p2_f1_plateau.png"), dpi=100)
    plt.close(fig)

    dsr = None
    pp = os.path.join(SCR, "f1port.pkl")
    if os.path.exists(pp):
        with open(pp, "rb") as fh:
            port = pickle.load(fh)
        dsr = deflated_sharpe(port, tab.sharpe.dropna().to_numpy())

    L = ["# Swing v4 — phase 2: improvements tested one by one (development data only)\n"]
    L.append(f"Trials logged in `experiments.csv`: **{P.n_trials()}** (3 phase-1 baselines + {len(p2)} phase-2 trials). "
             "Each idea is compared with baseline v3 (win 44.1%, 2.28% / 0.200R per trade, MAR 0.60). Flags in order: "
             + ", ".join(FLAG_NAMES) + ". Trade-level ideas are judged on all trades of the 253-ticker universe; "
             "ranking / sizing ideas on the trades the 10-position portfolio really takes. MAR = mean of 20 random "
             "selection orders (its own spread between orders is about ±0.15).\n")
    for fam, title in (("A", "A. Taking profit earlier"), ("B", "B. Selection / ranking"), ("C", "C. Setup quality"),
                       ("D", "D. Entry timing"), ("E", "E. Model"), ("F", "F. Regime"),
                       ("G", "Stacking on top of F1 (compared with F1; 'vs v3' in experiments.csv notes)")):
        sub = tab[(tab.family == fam) & ((tab.phase == "P2-stack") == (fam == "G"))]
        if sub.empty:
            continue
        L.append(f"## {title}\n")
        L.append("| idea | trades | win | exp % | exp R | PF | avg win / loss | CAGR | max DD | MAR | hold | expo | "
                 "years | top-10% R | flags |\n|" + "---|" * 15)
        for _, r in sub.iterrows():
            L.append(f"| {r.idea}{' **ACCEPTED**' if str(r.accepted) == 'True' else ''} | {r.n:.0f} | {r.win * 100:.1f}% | "
                     f"{r.exp_pct * 100:.2f}% | {r.exp_R:.3f} | {r.pf:.2f} | {r.avg_win * 100:.1f}% / {r.avg_loss * 100:.1f}% | "
                     f"{r.cagr * 100:.1f}% | {r.maxdd * 100:.1f}% | {r.mar:.2f} | {r.hold:.0f} | {r.exposure * 100:.0f}% | "
                     f"{r.years:.1f} | {r.top10_R:.2f} | {r.flags} |")
        L.append("")
    L.append("Baseline top-10% trades: mean 2.71R. 'top-10% R' = the same trades (matched on ticker and signal bar) "
             "under the variant; a lower value means the variant cuts the tail that carries the system.\n")
    L.append("![heatmaps](p2_heatmaps.png)\n\n![F1](p2_f1_plateau.png)\n")
    if dsr:
        L.append(f"Deflated Sharpe of the accepted F1 portfolio: annual Sharpe {dsr['sr_ann']:.2f} vs {dsr['sr0_ann']:.2f} "
                 f"expected for the best of {dsr['N']} skill-less trials with the same spread → DSR = {dsr['dsr']:.2f} "
                 "(probability that the Sharpe is real after the selection).\n")
    with open(os.path.join(OUT, "phase2_tables.md"), "w") as fh:
        fh.write("\n".join(L) + "\n")
    print("\n".join(L[:3]))
    if dsr:
        print(dsr)


if __name__ == "__main__":
    main()
