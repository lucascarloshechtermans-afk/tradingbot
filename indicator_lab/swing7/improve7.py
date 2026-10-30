"""Swing v4.2 round: three rules that held up in OTHER studies, each added to v4.1 on its own, on the broad v6
development universe; accepted rules are then combined and run ONCE on the untouched v6 ticker holdout.

    python -m indicator_lab.swing7.improve7            # development run -> final_spec_v7.json + reports/dev.md
    python -m indicator_lab.swing7.improve7 holdout    # the single holdout run (refuses a second run)

Fixed before any run (no parameter is tuned here; each value comes from an earlier, separate study):
  R1 market trend: BUY only when SPY closes above its 200-day SMA at the signal close
     (timing/regime.py: the one rule that held on US 1960-2011 and 12 foreign markets).
  R2 no wild stocks: BUY only when the stock's 1-year mean ATR% <= 5
     (twenty/reports/phase0.md: expectancy ~0 for 5-7% and negative above 7%; rotation/lowvol.py: the 30 most
     volatile stocks lost 11%/year; week/pead_week: ADR > 4% was the worst universe every time).
  R3 not into earnings: no BUY when an earnings reaction day falls in the next 1..5 sessions (research E38:
     entries in the week before earnings were weaker; earnings dates from week/earnings_eps.load, ~99% coverage).
  Acceptance per rule = the v6 criteria vs v4.1 on the same universe: system MAR higher, >= 70% of the years at least
  as good, MAR higher on both ticker halves, <= 2 new free parameters. If >= 2 rules pass, their combination must pass
  the same criteria, else the single best accepted rule (by MAR) is final.
  Holdout (1586 tickers of holdout_v6.json, 2015-01-01..2024-10-21, never used to design v4/v5/v6 rules): the final
  version is approved when its system MAR AND its expectancy per trade (R) beat v4.1 on the holdout.
  Disclosure: the holdout tickers were part of the data of the later week / post-earnings studies (no v4 rule was
  designed there), so it is "never used for v4", not "never seen".
System as traded: swing5/port.py (max 10 positions, idle cash in SPY > SMA200 else T-bills, 0.1%/side + slippage).
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

from indicator_lab.swing4 import lab as L
from indicator_lab.swing4 import sim2 as S2
from indicator_lab.swing5 import port as PT
from indicator_lab.swing6 import improve6 as I6
from indicator_lab.week import earnings_eps as EE

HERE = os.path.dirname(__file__)
REP = os.path.join(HERE, "reports")
SPEC = os.path.join(HERE, "final_spec_v7.json")
USED = os.path.join(HERE, "holdout_v7_used.json")
I6.EXP_LOG = os.path.join(HERE, "experiments.csv")
CACHE = os.environ.get("SWING4_CACHE", "/tmp")


def add_earn(ctx):
    earn = EE.load()
    for t, cx in ctx.items():
        idx = cx["arr"]["index"]
        n = len(idx)
        nxt = np.full(n, 10 ** 6)
        for ts, rule, _e, _r in earn.get(t, []):
            i = int(idx.searchsorted(ts))
            if i < n and idx[i] == ts and rule == "next":
                i += 1
            if i < n:
                seg = np.arange(max(0, i - 10), i + 1)
                nxt[seg] = np.minimum(nxt[seg], i - seg)
        cx["x"]["earn_next"] = nxt.astype(float)
    return ctx


RULES = {
    "R1": ("SPY > SMA200 op het signaal", lambda cx: cx["x"]["spy_up"] == 1),
    "R2": ("1-jaars gem. ATR% <= 5", lambda cx: cx["x"]["atr1y"] <= 5.0),
    "R3": ("geen cijfers in de komende 1-5 sessies", lambda cx: ~((cx["x"]["earn_next"] >= 1) & (cx["x"]["earn_next"] <= 5))),
}


def combo(codes):
    return lambda cx: np.logical_and.reduce([np.nan_to_num(RULES[c][1](cx), nan=0).astype(bool) for c in codes])


def setup(tickers, path, final=False):
    univ = I6.load_frames(tickers, final=final)
    ctx = add_earn(I6.prep(I6.build(univ, path)))
    return univ, ctx


def baseline(ctx, univ):
    res0 = L.run(ctx, I6.v4, S2.DEFAULT, univ=univ, slip=I6.SLIP)
    s0 = PT.system(res0, seeds=I6.SEEDS)
    base = {"sys": s0, "years": I6.yearly(s0),
            "halves": {h: PT.system({t: v for t, v in res0.items() if t in u}, seeds=8)["mar"]
                       for h, u in (("a", I6.HALF_A), ("b", I6.HALF_B))}}
    return res0, s0, base


def row_txt(name, r):
    c = r["crit"]
    return (f"| {name} | {r['n']} | {r['win'] * 100:.1f}% | {r['exp_R']:+.3f} | {r['cagr'] * 100:.1f}% | {r['maxdd'] * 100:.1f}% | "
            f"{r['mar']:.2f} | {r['years_better'] * 100:.0f}% | {'ja' if c['half_a'] and c['half_b'] else 'nee'} | "
            f"{'**ja**' if r['accepted'] else 'nee'} |")


HDR = ("| versie | trades | winrate | verwachting (R) | CAGR | max daling | MAR | jaren >= v4.1 | beide helften | geaccepteerd |\n"
       "|---|---|---|---|---|---|---|---|---|---|")


def dev():
    univ, ctx = setup(I6.DEV, os.path.join(CACHE, "swing6_ctx_dev.pkl"))
    I6.HALF_A, I6.HALF_B = univ[0::2], univ[1::2]
    res0, s0, base = baseline(ctx, univ)
    t0 = L.tstats(L.C.trade_table(res0))
    sp = PT.stats(PT.benchmarks(s0["port0"].index)[0]["SPY buy & hold"], s0["mkt"])
    lines = [f"# Swing v4.2-ronde — ontwikkeling ({len(univ)} aandelen, 2015-2024-10)\n\nZie `indicator_lab/swing7/improve7.py`.\n\n",
             HDR + "\n",
             (f"| v4.1 (basis) | {t0['n']} | {t0['win'] * 100:.1f}% | {t0['exp_R']:+.3f} | {s0['cagr'] * 100:.1f}% | "
              f"{s0['maxdd'] * 100:.1f}% | {s0['mar']:.2f} | - | - | - |\n")]
    acc = []
    for code, (name, fn) in RULES.items():
        res = L.run(ctx, I6.filt(fn), S2.DEFAULT, univ=univ, slip=I6.SLIP)
        r = I6.evaluate(f"{code} {name}", res, base, {"rule": code}, 0, "v4.2 round, value fixed by an earlier study")
        print(I6.fmt(r), flush=True)
        lines.append(row_txt(f"{code} {name}", r) + "\n")
        if r["accepted"]:
            acc.append((r["mar"], code))
    final = []
    if len(acc) >= 2:
        codes = [c for _, c in acc]
        res = L.run(ctx, I6.filt(combo(codes)), S2.DEFAULT, univ=univ, slip=I6.SLIP)
        r = I6.evaluate("combinatie " + "+".join(codes), res, base, {"rules": codes}, 0, "v4.2 round, combination")
        print(I6.fmt(r), flush=True)
        lines.append(row_txt("combinatie " + "+".join(codes), r) + "\n")
        final = codes if r["accepted"] else [max(acc)[1]]
    elif acc:
        final = [acc[0][1]]
    lines.append(f"\nSPY kopen en vasthouden: CAGR {sp['cagr'] * 100:.1f}%, max daling {sp['maxdd'] * 100:.1f}%, MAR {sp['mar']:.2f}.\n\n"
                 f"**Eindversie voor de holdout: {'v4.1 + ' + ' + '.join(final) if final else 'geen regel geaccepteerd (geen holdout-run)'}**\n")
    os.makedirs(REP, exist_ok=True)
    with open(os.path.join(REP, "dev.md"), "w") as fh:
        fh.write("".join(lines))
    with open(SPEC, "w") as fh:
        json.dump({"rules": final, "frozen": pd.Timestamp.now("UTC").isoformat()}, fh, indent=1)
    print("".join(lines))


def holdout():
    if os.path.exists(USED):
        raise SystemExit("the v7 holdout has already been used")
    final = json.load(open(SPEC))["rules"]  # noqa: SIM115
    if not final:
        raise SystemExit("no accepted rule: nothing to validate")
    with open(USED, "w") as fh:
        json.dump({"used": pd.Timestamp.now("UTC").isoformat(), "rules": final}, fh)
    univ, ctx = setup(sorted(I6.H_TICKERS), os.path.join(CACHE, "swing7_ctx_holdout.pkl"), final=True)
    I6.HALF_A, I6.HALF_B = univ[0::2], univ[1::2]
    res0, s0, base = baseline(ctx, univ)
    t0 = L.tstats(L.C.trade_table(res0))
    res = L.run(ctx, I6.filt(combo(final)), S2.DEFAULT, univ=univ, slip=I6.SLIP)
    r = I6.evaluate("HOLDOUT v4.1 + " + "+".join(final), res, base, {"rules": final}, 0, "v4.2 single holdout run")
    sp = PT.stats(PT.benchmarks(s0["port0"].index)[0]["SPY buy & hold"], s0["mkt"])
    ok = r["mar"] > s0["mar"] and r["exp_R"] > t0["exp_R"]
    txt = (f"# Swing v4.2 — de enige holdout-run ({len(univ)} aandelen, 2015-2024-10)\n\n" + HDR + "\n"
           f"| v4.1 | {t0['n']} | {t0['win'] * 100:.1f}% | {t0['exp_R']:+.3f} | {s0['cagr'] * 100:.1f}% | {s0['maxdd'] * 100:.1f}% | "
           f"{s0['mar']:.2f} | - | - | - |\n" + row_txt("v4.2 = v4.1 + " + " + ".join(final), r) + "\n\n"
           f"SPY kopen en vasthouden: CAGR {sp['cagr'] * 100:.1f}%, max daling {sp['maxdd'] * 100:.1f}%, MAR {sp['mar']:.2f}.\n\n"
           f"**Oordeel: {'GOEDGEKEURD' if ok else 'NIET GOEDGEKEURD'}** (eis: MAR en verwachting per trade beter dan v4.1).\n")
    with open(os.path.join(REP, "holdout.md"), "w") as fh:
        fh.write(txt)
    print(txt)


if __name__ == "__main__":
    holdout() if len(sys.argv) > 1 and sys.argv[1] == "holdout" else dev()
