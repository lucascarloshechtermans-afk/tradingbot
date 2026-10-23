"""Swing v6 round: improve v4 where the v5 holdout showed it fails, on a BROAD universe (development half of ~3000
never-used US stocks, holdout_v6.json). Each idea is tested against v4 on the same universe and logged.

    python -m indicator_lab.swing6.improve6

Why: on 155 ordinary S&P 500 names v4 had almost no edge (0.087R, CAGR 5% vs SPY 13%), while it worked on volatile,
hand-picked names. On a broad universe a point-in-time rule can choose WHICH stocks to trade (volatility, momentum)
without leaving the 10 slots empty, which is what sank the same filter on small universes (E30).

Fixed for every variant (not free parameters, taken from the 20/21 project's config): signal-day close >= $5 and 50-day
average dollar volume >= $5M. System as traded: swing5/port.py (max 10 positions, idle cash in SPY > SMA200 else T-bills,
0.1%/side + 0.1% entry slippage), mean of 20 random orders of same-day signals.
"""
from __future__ import annotations

import json
import os
import pickle

import numpy as np
import pandas as pd

from indicator_lab.swing5 import protocol5 as P5

P5.install_dev()

from indicator_lab import evaluate as E
from indicator_lab.swing4 import lab as L
from indicator_lab.swing4 import protocol as P4
from indicator_lab.swing4 import sim2 as S2
from indicator_lab.swing5 import phase0 as P0
from indicator_lab.swing5 import port as PT
from indicator_lab.twenty import data20

HERE = os.path.dirname(__file__)
SPEC = json.load(open(os.path.join(HERE, "holdout_v6.json")))  # noqa: SIM115
H_TICKERS = set(SPEC["ticker_holdout"]["tickers"])
DEV = SPEC["development"]["tickers"]
CUTOFF = P5.CUTOFF
EXP_LOG = os.path.join(HERE, "experiments.csv")
SLIP = P0.SLIP
SEEDS = 20
MIN_PRICE, MIN_DVOL = 5.0, 5e6


def load_frames(tickers, final: bool = False) -> list[str]:
    """Put the .cache20 frames into the research engine's data cache (evaluate._DATA); development mode refuses the
    v6 holdout and cuts every series before 2024-10-22. Returns the tickers with enough history."""
    ok = []
    for t in tickers:
        if not final and t in H_TICKERS:
            raise PermissionError(f"{t} is a v6 holdout ticker")
        df = data20.load(t)
        if df is None:
            continue
        df = df[df.index < CUTOFF] if not final else df
        df = df[(df[["open", "high", "low", "close"]] > 0).all(axis=1)]
        if len(df) < 400 or df.index[-1] < pd.Timestamp("2016-01-01"):
            continue
        E._DATA[t] = df
        ok.append(t)
    return ok


def build(tickers, path):
    if os.path.exists(path):
        with open(path, "rb") as fh:
            return pickle.load(fh)
    ctx = L.build(tickers)
    with open(path, "wb") as fh:
        pickle.dump(ctx, fh, protocol=pickle.HIGHEST_PROTOCOL)
    return ctx


def prep(ctx):
    for t, cx in ctx.items():
        cx["_t"] = t
        c = cx["arr"]["c"]
        with np.errstate(invalid="ignore"):
            cx["liquid"] = (c >= MIN_PRICE) & (np.nan_to_num(cx["x"]["dvol"], nan=0) >= np.log10(MIN_DVOL))
    return ctx


def v4(cx):
    return P0.v4_entry(cx) & cx["liquid"]


def filt(fn):
    def e(cx):
        with np.errstate(invalid="ignore"):
            return v4(cx) & np.nan_to_num(fn(cx), nan=0).astype(bool)
    return e


def key_x(name):
    return lambda x: x["x"].get(name, np.nan)


def ideas():
    out = []
    for a in (2.0, 2.5, 3.0):
        out.append((f"U1 trade only stocks with 1y mean ATR% >= {a}", {"entry": filt(lambda cx, a=a: cx["x"]["atr1y"] >= a)},
                    {"atr1y_min": a}, 1, "the breakout edge per trade grows with a stock's typical volatility (E30/E56)"))
    out.append(("U2 slots full: highest 1y ATR% first", {"key": key_x("atr1y")}, {"rank": "atr1y"}, 0,
                "when slots are scarce, give them to the names where breakouts move most"))
    for a in (2.0, 2.5):
        out.append((f"U3 1y ATR% >= {a} + highest ATR% first", {"entry": filt(lambda cx, a=a: cx["x"]["atr1y"] >= a),
                                                                "key": key_x("atr1y")}, {"atr1y_min": a, "rank": "atr1y"}, 1,
                    "both of the above"))
    for q in (0.5, 0.7):
        out.append((f"U4 only the top {round((1 - q) * 100)}% by 126-day momentum (cross-section)",
                    {"entry": filt(lambda cx, q=q: cx["x"]["mom126_xs"] >= q)}, {"mom126_xs_min": q}, 1,
                    "breakouts of stocks that already lead the market keep leading (relative momentum)"))
    out.append(("U5 slots full: strongest 126-day momentum first", {"key": key_x("mom126_xs")}, {"rank": "mom126_xs"}, 0,
                "when slots are scarce, take the leaders"))
    return out


def yearly(sysd) -> pd.Series:
    port = pd.concat(sysd["ports"], axis=1).mean(axis=1)
    return port.groupby(port.index.year).apply(lambda r: (1 + r).prod() - 1)


HALF_A, HALF_B = None, None


def evaluate(name, res, base, params, n_free, story, key=None, log=True):
    s = PT.system(res, seeds=SEEDS, key=key)
    yb, y0 = yearly(s), base["years"]
    years_better = float((yb.loc[y0.index] >= y0 - 1e-12).mean())
    halves = {h: PT.system({t: v for t, v in res.items() if t in u}, seeds=8, key=key)["mar"] >= base["halves"][h]
              for h, u in (("a", HALF_A), ("b", HALF_B))}
    tt = L.C.trade_table(res)
    t = L.tstats(tt)
    crit = {"mar_up": s["mar"] > base["sys"]["mar"], "years70": years_better >= 0.7, "half_a": halves["a"],
            "half_b": halves["b"], "params_ok": n_free <= 2}
    row = {"name": name, "n": t["n"], "win": t["win"], "exp_R": t["exp_R"], "cagr": s["cagr"], "maxdd": s["maxdd"],
           "mar": s["mar"], "sharpe": s["sharpe_rf"], "alpha": s["alpha"], "years_better": years_better, "crit": crit,
           "accepted": all(crit.values())}
    if log:
        ci = P4.bootstrap_ci(tt["R"]) if len(tt) else (np.nan, np.nan)
        P4.log({"phase": "P1", "idea": name, "params": params, "new_free_params": n_free, "universe": f"DEV6 {len(res)}",
                "period": "2015-01-01..2024-10-21", "n": t["n"], "win": t["win"], "exp_pct": t["exp_pct"],
                "exp_R": t["exp_R"], "pf": t["pf"], "avg_win": t["avg_win"], "avg_loss": t["avg_loss"],
                "cagr": s["cagr"], "maxdd": s["maxdd"], "mar": s["mar"], "hold": t["hold"], "exposure": s["invested"],
                "exp_ci_lo": ci[0], "exp_ci_hi": ci[1], "years_better": years_better, "half_a": halves["a"],
                "half_b": halves["b"], "accepted": row["accepted"],
                "notes": f"vs v4 on DEV6; sharpe {s['sharpe_rf']:.2f} alpha {s['alpha']:.4f}; " + story}, EXP_LOG)
    return row


def fmt(r) -> str:
    flags = "".join("✓" if v else "·" for v in r["crit"].values())
    return (f"{r['name'][:60]:60s} n {r['n']:5d} win {r['win'] * 100:4.1f}% {r['exp_R']:+.3f}R | CAGR {r['cagr'] * 100:5.1f}% "
            f"DD {r['maxdd'] * 100:6.1f}% MAR {r['mar']:.2f} Sh {r['sharpe']:.2f} a {r['alpha'] * 100:+.1f}% | "
            f"yrs {r['years_better']:.2f} {flags}{' ACCEPT' if r['accepted'] else ''}")


def main():
    global HALF_A, HALF_B
    univ = load_frames(DEV)
    HALF_A, HALF_B = univ[0::2], univ[1::2]
    ctx = prep(build(univ, os.path.join(os.environ.get("SWING4_CACHE", "/tmp"), "swing6_ctx_dev.pkl")))
    res0 = L.run(ctx, v4, S2.DEFAULT, univ=univ, slip=SLIP)
    s0 = PT.system(res0, seeds=SEEDS)
    base = {"sys": s0, "years": yearly(s0),
            "halves": {h: PT.system({t: v for t, v in res0.items() if t in u}, seeds=8)["mar"]
                       for h, u in (("a", HALF_A), ("b", HALF_B))}}
    sp = PT.stats(PT.benchmarks(s0["port0"].index)[0]["SPY buy & hold"], s0["mkt"])
    t0 = L.tstats(L.C.trade_table(res0))
    print(f"universe {len(univ)} tickers | v4: n {t0['n']} {t0['exp_R']:+.3f}R CAGR {s0['cagr'] * 100:.1f}% "
          f"DD {s0['maxdd'] * 100:.1f}% MAR {s0['mar']:.2f} Sharpe {s0['sharpe_rf']:.2f} alpha {s0['alpha'] * 100:+.1f}% | "
          f"SPY CAGR {sp['cagr'] * 100:.1f}% DD {sp['maxdd'] * 100:.1f}% MAR {sp['mar']:.2f} Sharpe {sp['sharpe_rf']:.2f}",
          flush=True)
    rows = []
    for name, spec, params, n_free, story in ideas():
        res = L.run(ctx, spec.get("entry", v4), S2.DEFAULT, univ=univ, slip=SLIP)
        r = evaluate(name, res, base, params, n_free, story, key=spec.get("key"))
        print(fmt(r), flush=True)
        rows.append(r)
    return rows


if __name__ == "__main__":
    main()
