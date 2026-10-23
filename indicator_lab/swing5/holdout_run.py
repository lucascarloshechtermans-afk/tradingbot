"""The ONE holdout run of the swing v5 round: frozen spec final_spec_v5.json (v4 + relative-strength line at a new
63-day high) against v4 and SPY, as the complete system is traded (swing5/port.py).

    SWING5_DRYRUN=1 python -m indicator_lab.swing5.holdout_run   # code check on development data, nothing logged
    python -m indicator_lab.swing5.holdout_run                   # the real run (once)

Cells: TICKER holdout (155 never-used tickers, 2015 -> 2024-10-21) is clean; TICKER + TIME (same tickers, 2024-10-22
-> now) is clean for the tickers, but the market path and the regime rule's result in that period were known.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

from indicator_lab.swing5 import protocol5 as P

DRY = bool(os.environ.get("SWING5_DRYRUN"))
if DRY:
    P.install_dev()
else:
    P.install_final()

from indicator_lab.swing4 import lab as L
from indicator_lab.swing4 import sim2 as S2
from indicator_lab.swing5 import feats5
from indicator_lab.swing5 import port as PT

SPEC = json.load(open(os.path.join(P.HERE, "final_spec_v5.json")))  # noqa: SIM115
K_RS = SPEC["new_free_parameters"]["rs_high_lookback"]
REGIME_MAX = 0.03
SLIP = 0.001
H = sorted(P.H_TICKERS)
D0, D1 = P.DEV_PERIOD
HS = P.CUTOFF
END = pd.Timestamp("2100-01-01")
OUT = os.path.join(P.HERE, "reports")
if DRY:
    H = P.HALF_B[:60]
    HS, D1 = pd.Timestamp("2022-01-01"), pd.Timestamp("2021-12-31")
CELLS = {"TICKER holdout: 155 new tickers, 2015 → 2024-10-21": (D0, D1),
         "TICKER + TIME holdout: 155 new tickers, 2024-10-22 → now": (HS, END)}


def v4_entry(cx):
    with np.errstate(invalid="ignore"):
        return L.v3_entry(cx) & (np.nan_to_num(cx["x"]["spy_roc63"], nan=9) <= REGIME_MAX)


def v5_entry(cx):
    return v4_entry(cx) & (np.nan_to_num(cx["x"][f"rs_hi{K_RS}"], nan=0) >= 1)


def cell(ctx, entry, period):
    res = L.run(ctx, entry, S2.DEFAULT, univ=H, period=period, slip=SLIP)
    tt = L.C.trade_table(res)
    t = L.tstats(tt)
    s = PT.system(res, seeds=20)
    ci = P.bootstrap_ci(tt["R"]) if len(tt) > 2 else (np.nan, np.nan)
    return {"t": t, "s": s, "ci": ci, "res": res}


def spy_row(idx):
    bench, m = PT.benchmarks(idx)
    return PT.stats(bench["SPY buy & hold"], m)


def main():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    path = os.path.join(os.environ.get("SWING4_CACHE", "/tmp"), "swing5_ctx_dry.pkl" if DRY else "swing5_ctx_final.pkl")
    ctx = feats5.add(L.load_ctx(rebuild=True, univ=H, path=path))
    out = ["# Swing v5 — the single holdout run" + (" (DRY RUN on development data)" if DRY else "") + "\n",
           (f"Frozen spec `final_spec_v5.json` ({SPEC['frozen']}): v5 = v4 + {SPEC['new_rule']}. System as traded: "
           f"{SPEC['portfolio_as_traded']}; mean of 20 random orders of same-day signals.\n"),
           "| cell | system | trades | win | exp R [95% CI] | CAGR | max DD | MAR | Sharpe (excess) | alpha / yr (t) | beta |",
           "|---|---|---|---|---|---|---|---|---|---|---|"]
    curves = {}
    for name, period in CELLS.items():
        r4, r5 = cell(ctx, v4_entry, period), cell(ctx, v5_entry, period)
        idx = r4["s"]["port0"].index
        sp = spy_row(idx)
        for sysname, r in (("v4", r4), ("v5", r5)):
            t, s = r["t"], r["s"]
            out.append(f"| {name} | {sysname} | {t['n']} | {t['win'] * 100:.1f}% | {t['exp_R']:.3f} [{r['ci'][0]:.2f}, "
                       f"{r['ci'][1]:.2f}] | {s['cagr'] * 100:.1f}% | {s['maxdd'] * 100:.1f}% | {s['mar']:.2f} | "
                       f"{s['sharpe_rf']:.2f} | {s['alpha'] * 100:+.1f}% ({s['alpha_t']:.1f}) | {s['beta']:.2f} |")
            if not DRY:
                P.log({"phase": "P3-holdout", "idea": f"{sysname} | {name}", "params": {"rs_high": K_RS if sysname == 'v5' else None},
                       "new_free_params": 1 if sysname == "v5" else 0, "universe": f"HOLDOUT5 {len(H)}",
                       "period": f"{period[0].date()}..{min(period[1], idx[-1]).date()}", "n": t["n"], "win": t["win"],
                       "exp_pct": t["exp_pct"], "exp_R": t["exp_R"], "pf": t["pf"], "avg_win": t["avg_win"],
                       "avg_loss": t["avg_loss"], "cagr": s["cagr"], "maxdd": s["maxdd"], "mar": s["mar"], "hold": t["hold"],
                       "exposure": s["invested"], "exp_ci_lo": r["ci"][0], "exp_ci_hi": r["ci"][1],
                       "accepted": "holdout", "notes": f"alpha {s['alpha']:.4f} beta {s['beta']:.2f}"})
        out.append(f"| {name} | SPY buy & hold | – | – | – | {sp['cagr'] * 100:.1f}% | {sp['maxdd'] * 100:.1f}% | "
                   f"{sp['mar']:.2f} | {sp['sharpe_rf']:.2f} | – | 1.00 |")
        curves[name] = {"v4": r4["s"]["port0"], "v5": r5["s"]["port0"], "SPY": PT.benchmarks(idx)[0]["SPY buy & hold"]}
    os.makedirs(OUT, exist_ok=True)
    fig, axes = plt.subplots(1, len(curves), figsize=(13, 4))
    for ax, (name, cv) in zip(np.atleast_1d(axes), curves.items()):
        for k, r in cv.items():
            ax.plot((1 + r).cumprod(), label=k)
        ax.set_title(name, fontsize=9)
        ax.legend(fontsize=8)
    fig.tight_layout()
    fname = "holdout_v5_dry.png" if DRY else "holdout_v5.png"
    fig.savefig(os.path.join(OUT if not DRY else os.environ.get("SWING4_CACHE", "/tmp"), fname), dpi=100)
    plt.close(fig)
    out.append(f"\n![equity]({fname})\n")
    txt = "\n".join(out)
    if not DRY:
        with open(os.path.join(OUT, "holdout_v5.md"), "w") as fh:
            fh.write(txt)
    print(txt)


if __name__ == "__main__":
    main()
