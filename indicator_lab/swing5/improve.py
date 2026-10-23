"""Swing v5 round, phase 1: improvements to v4, each tested on its own against v4 (development data only; the v5
holdout is refused by the data loader).

    python -m indicator_lab.swing5.improve          # runs every idea, logs each trial in swing5/experiments.csv

System as traded (swing5/port.py): max 10 positions of 10%, idle cash in SPY while SPY > SMA200 (else T-bills),
0.1% cost per side + 0.1% slippage on breakout entries, mean of 20 random orders of same-day signals.

Acceptance per idea (the brief): <= 2 new free parameters, chosen from a flat plateau of its small grid, portfolio
MAR above v4, a calendar-year return at least v4's in >= 70% of the years, better MAR in both ticker halves, and an
economic story in one sentence.
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from indicator_lab.swing5 import protocol5 as P

P.install_dev()

from indicator_lab.swing4 import lab as L
from indicator_lab.swing4 import sim2 as S2
from indicator_lab.swing5 import phase0 as P0
from indicator_lab.swing5 import port as PT

SLIP = P0.SLIP
SEEDS = 20
OUT = os.path.join(P.HERE, "reports")


def load():
    from indicator_lab.swing5 import feats5
    return feats5.add(L.load_ctx(univ=P.DEV_UNIVERSE, path=P0.CACHE))


def filt(fn):
    def e(cx):
        with np.errstate(invalid="ignore"):
            return P0.v4_entry(cx) & np.nan_to_num(fn(cx), nan=0).astype(bool)
    return e


def sect_group(x):
    v = x["x"].get("sect_id", np.nan)
    return None if not np.isfinite(v) else int(v)


def ideas():
    out = []
    for d in (2, 3, 5):
        for b in (0.0, 0.5):
            out.append((f"V1 failed-breakout exit: close < breakout level - {b} ATR within {d} days",
                        {"pol": S2.Policy(fb_days=d, fb_buf=b)}, {"fb_days": d, "fb_buf": b}, 2,
                        "a real breakout holds above the level it broke; falling back below it says the buyers are gone"))
    for k in (63, 126, 252):
        out.append((f"V2 relative-strength line at a new {k}-day high",
                    {"entry": filt(lambda cx, k=k: cx["x"][f"rs_hi{k}"] >= 1)}, {"rs_high": k}, 1,
                    "institutions buying a leader push it ahead of the market before and during the breakout"))
    for cap in (2, 3):
        out.append((f"V3 at most {cap} positions per sector",
                    {"cap": cap}, {"sector_cap": cap}, 1,
                    "breakouts in one sector move together; spreading the slots lowers the shared drawdowns"))
    return out


def yearly(sysd) -> pd.Series:
    port = pd.concat(sysd["ports"], axis=1).mean(axis=1)
    return port.groupby(port.index.year).apply(lambda r: (1 + r).prod() - 1)


def evaluate(name, res, base, params, n_free, story, cap=None, log=True):
    group = sect_group if cap else None
    s = PT.system(res, seeds=SEEDS, group=group, cap=cap)
    yb = yearly(s)
    y0 = base["years"]
    years_better = float((yb.loc[y0.index] >= y0 - 1e-12).mean())
    halves = {}
    for h, u in (("a", P.HALF_A), ("b", P.HALF_B)):
        sub = {t: v for t, v in res.items() if t in u}
        halves[h] = PT.system(sub, seeds=8, group=group, cap=cap)["mar"] >= base["halves"][h]
    tt = L.C.trade_table(res)
    t = L.tstats(tt)
    crit = {"mar_up": s["mar"] > base["sys"]["mar"], "years70": years_better >= 0.7, "half_a": halves["a"],
            "half_b": halves["b"], "params_ok": n_free <= 2}
    row = {"name": name, "n": t["n"], "win": t["win"], "exp_R": t["exp_R"], "cagr": s["cagr"], "maxdd": s["maxdd"],
           "mar": s["mar"], "sharpe": s["sharpe_rf"], "alpha": s["alpha"], "beta": s["beta"],
           "years_better": years_better, "crit": crit, "accepted": all(crit.values())}
    if log:
        ci = P.bootstrap_ci(tt["R"]) if len(tt) else (np.nan, np.nan)
        P.log({"phase": "P1", "idea": name, "params": params, "new_free_params": n_free,
               "universe": f"DEV5 {len(res)}", "period": "2015-01-01..2024-10-21", "n": t["n"], "win": t["win"],
               "exp_pct": t["exp_pct"], "exp_R": t["exp_R"], "pf": t["pf"], "avg_win": t["avg_win"],
               "avg_loss": t["avg_loss"], "cagr": s["cagr"], "maxdd": s["maxdd"], "mar": s["mar"], "hold": t["hold"],
               "exposure": s["invested"], "exp_ci_lo": ci[0], "exp_ci_hi": ci[1], "years_better": years_better,
               "half_a": halves["a"], "half_b": halves["b"], "accepted": row["accepted"],
               "notes": f"vs v4 complete; alpha {s['alpha']:.4f} beta {s['beta']:.2f}; " + story})
    return row


def baseline(ctx):
    res = L.run(ctx, P0.v4_entry, S2.DEFAULT, slip=SLIP)
    s = PT.system(res, seeds=SEEDS)
    halves = {h: PT.system({t: v for t, v in res.items() if t in u}, seeds=8)["mar"]
              for h, u in (("a", P.HALF_A), ("b", P.HALF_B))}
    return {"res": res, "sys": s, "years": yearly(s), "halves": halves}


def fmt(r) -> str:
    flags = "".join("✓" if v else "·" for v in r["crit"].values())
    return (f"{r['name'][:70]:70s} n {r['n']:5d} win {r['win'] * 100:4.1f}% {r['exp_R']:+.3f}R | CAGR {r['cagr'] * 100:5.1f}% "
            f"DD {r['maxdd'] * 100:6.1f}% MAR {r['mar']:.2f} Sh {r['sharpe']:.2f} | yrs {r['years_better']:.2f} {flags}"
            f"{' ACCEPT' if r['accepted'] else ''}")


def main():
    ctx = load()
    base = baseline(ctx)
    b = base["sys"]
    print(f"v4 complete: CAGR {b['cagr'] * 100:.1f}% DD {b['maxdd'] * 100:.1f}% MAR {b['mar']:.2f} "
          f"Sharpe {b['sharpe_rf']:.2f} | halves MAR {base['halves']['a']:.2f}/{base['halves']['b']:.2f}", flush=True)
    rows = []
    for name, spec, params, n_free, story in ideas():
        res = L.run(ctx, spec.get("entry", P0.v4_entry), spec.get("pol", S2.DEFAULT), slip=SLIP)
        r = evaluate(name, res, base, params, n_free, story, cap=spec.get("cap"))
        print(fmt(r), flush=True)
        rows.append(r)
    return base, rows


if __name__ == "__main__":
    main()
