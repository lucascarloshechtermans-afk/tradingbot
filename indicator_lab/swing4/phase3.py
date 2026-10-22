"""Phase 3 of the swing v4 round: the ONE holdout run of the frozen spec (final_spec.json) against baseline v3.

    python -m indicator_lab.swing4.phase3

After this run nothing is fitted or changed any more. Results: reports/phase3.md + figures.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

from indicator_lab.swing4 import protocol as P

DRY = bool(os.environ.get("SWING4_DRYRUN"))   # code check on development data only: no holdout, nothing logged
if DRY:
    P.install_dev_cutoff()
else:
    P.install_final()

from indicator_lab.swing4 import lab as L

OUT = os.path.join(P.HERE, "reports") if not os.environ.get("SWING4_DRYRUN") else os.environ.get("SWING4_CACHE", "/tmp")
SPEC = json.load(open(os.path.join(P.HERE, "final_spec.json")))  # noqa: SIM115
F1_MAX = SPEC["new_free_parameters"]["spy_roc63_max"]
H = sorted(P.H_TICKERS)
DEV = P.DEV_UNIVERSE
D0, D1 = P.DEV_PERIOD
HS = P.H_START
END = pd.Timestamp("2100-01-01")


def v4_entry(cx):
    with np.errstate(invalid="ignore"):
        return L.v3_entry(cx) & (np.nan_to_num(cx["x"]["spy_roc63"], nan=9) <= F1_MAX)


if DRY:
    H = P.HALF_B[:40]
    DEV = P.HALF_A
    HS = pd.Timestamp("2023-01-01")
    D1 = pd.Timestamp("2022-12-31")
CELLS = {  # name: (universe, period)
    "DEV tickers, development period (OOS walk-forward)": (DEV, (D0, D1)),
    "TIME holdout: DEV tickers, 2024-10-22 → now": (DEV, (HS, END)),
    "TICKER holdout: 84 new tickers, 2015 → 2024-10-21": (H, (D0, D1)),
    "TICKER + TIME holdout: 84 new tickers, 2024-10-22 → now": (H, (HS, END)),
}


def stats(ctx, entry, univ, period):
    res = L.run(ctx, entry, univ=univ, period=period)
    tt = L.C.trade_table(res)
    t = L.tstats(tt)
    p = L.pstats(res)
    ci = P.bootstrap_ci(tt["R"]) if len(tt) > 2 else (np.nan, np.nan)
    srt = tt.sort_values("ret", ascending=False)
    n10 = max(1, round(0.1 * len(tt)))
    top = (srt.head(n10).ret.sum() / tt.ret.sum() if tt.ret.sum() != 0 else np.nan, srt.head(n10).R.mean())
    return {"t": t, "p": p, "ci": ci, "tt": tt, "top": top}


def row(name, s):
    t, p = s["t"], s["p"]
    if t["n"] == 0:
        return f"| {name} | 0 | – | – | – | – | – | – | – | – | – | – |"
    return (f"| {name} | {t['n']} | {t['win'] * 100:.1f}% | {t['exp_pct'] * 100:.2f}% | {t['exp_R']:.3f} "
            f"[{s['ci'][0]:.2f}, {s['ci'][1]:.2f}] | {t['pf']:.2f} | {t['avg_win'] * 100:.1f}% / {t['avg_loss'] * 100:.1f}% | "
            f"{p['cagr'] * 100:.1f}% | {p['maxdd'] * 100:.1f}% | {p['mar']:.2f} | {t['hold']:.0f} | {p['exposure'] * 100:.0f}% | "
            f"{s['top'][0] * 100:.0f}% / {s['top'][1]:.2f}R |")


def main():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    path = os.path.join(os.environ.get("SWING4_CACHE", "/tmp"), "swing4_ctx_dry.pkl" if DRY else "swing4_ctx_final.pkl")
    ctx = L.load_ctx(rebuild=True, univ=DEV + H, path=path)
    out = {}
    for cell, (u, per) in CELLS.items():
        out[cell] = {"v3": stats(ctx, L.v3_entry, u, per), "v4": stats(ctx, v4_entry, u, per)}
        print(cell, {k: (v["t"]["n"], round(v["t"]["win"], 3), round(v["t"]["exp_R"], 3), round(v["p"]["mar"], 2))
                     for k, v in out[cell].items()}, flush=True)
        for k, v in out[cell].items():
            if DRY:
                continue
            P.log({"phase": "P3-holdout", "idea": f"{k} | {cell}", "params": {"spy_roc63_max": F1_MAX if k == "v4" else None},
                   "new_free_params": 1 if k == "v4" else 0, "universe": f"{len(u)} tickers", "period": f"{per[0].date()}..",
                   "n": v["t"]["n"], "win": v["t"].get("win"), "exp_pct": v["t"].get("exp_pct"), "exp_R": v["t"].get("exp_R"),
                   "pf": v["t"].get("pf"), "avg_win": v["t"].get("avg_win"), "avg_loss": v["t"].get("avg_loss"),
                   "cagr": v["p"]["cagr"], "maxdd": v["p"]["maxdd"], "mar": v["p"]["mar"], "hold": v["t"].get("hold"),
                   "exposure": v["p"]["exposure"], "exp_ci_lo": v["ci"][0], "exp_ci_hi": v["ci"][1],
                   "accepted": "holdout", "notes": "single final run, no fitting afterwards"})

    # figures: equity curves per cell, R histograms
    fig, axes = plt.subplots(2, 2, figsize=(12, 7))
    for ax, (cell, d) in zip(axes.ravel(), out.items()):
        for k, col in (("v3", "#888"), ("v4", "#1f6fd1")):
            eq = d[k]["p"]["equity"]
            ax.plot(eq.index, eq.values, color=col, label=f"{k}: CAGR {d[k]['p']['cagr'] * 100:.1f}%, "
                                                          f"DD {d[k]['p']['maxdd'] * 100:.0f}%")
        ax.set_title(cell, fontsize=9)
        ax.legend(fontsize=8)
    fig.suptitle("10-position portfolio equity (one random selection order), v3 vs v4")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "p3_equity.png"), dpi=100)
    plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(12, 3.8))
    for ax, cell in zip(axes, list(out)[:3:2]):
        bins = np.linspace(-1.5, 6, 46)
        for k, col in (("v3", "#888"), ("v4", "#1f6fd1")):
            r = out[cell][k]["tt"]["R"].clip(-1.5, 6)
            ax.hist(r, bins=bins, alpha=0.55, color=col, density=True, label=f"{k} (n={len(r)})")
        ax.set_title("trade results in R: " + cell, fontsize=9)
        ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "p3_hist.png"), dpi=100)
    plt.close(fig)

    L_ = ["# Swing v4 — phase 3: the single holdout run\n",
          (f"Frozen spec (`final_spec.json`, committed before this run): v3 + only take a breakout when SPY's 63-day "
           f"return ≤ {F1_MAX:.2f}. Exits unchanged. Costs 0.1% per side; R = 4 x ATR(signal bar); portfolio max 10 "
           "positions (mean of 20 random selection orders). Model: v3's walk-forward yearly fits on DEV (the 2025/2026 "
           "fits now see data up to their year start, as in real use). Trades still open at the last bar are not counted.\n"),
          "| cell / system | trades | win | exp % | exp R [95% CI] | PF | avg win / loss | CAGR | max DD | MAR | hold | expo | top-10% share / mean R |",
          "|" + "---|" * 13]
    for cell, d in out.items():
        L_.append(f"| **{cell}** |" + " |" * 12)
        for k in ("v3", "v4"):
            L_.append(row(k, d[k]))
    L_.append("\n![equity](p3_equity.png)\n\n![hist](p3_hist.png)\n")
    with open(os.path.join(OUT, "phase3.md"), "w") as fh:
        fh.write("\n".join(L_) + "\n")
    print("\n".join(L_))


if __name__ == "__main__":
    main()
