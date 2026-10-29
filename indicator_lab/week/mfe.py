"""Step 1 of the win-rate study: MFE / MAE and the hit rate of a single fixed target (max +10%, whole position out)
for every setup of build.py, against random entries on the same dates.

    python -m indicator_lab.week.mfe

Rules of this study (the user's brief, fixed before the run):
  * Targets +2 / +3 / +4 / +5 / +7 / +10% (whole position out at the target: "max 10% en eruit"), time exit after
    N = 5 / 10 / 15 / 20 trading days at the close. Stop = build.trade's standard stop (below the setup's support /
    anchor - 0.25 ATR, at least 1 ATR, at most 8%). Same bar: stop first. Gaps: an open beyond the stop or the target
    fills at the open.
  * Costs: commission 0.05% per side + 2 ticks ($0.02) slippage per side. A trade is a WIN if its net result > 0.
  * Train = signals 2015-01-01 .. 2022-12-31, test = 2023-01-01 .. 2026-10-23 (entry must leave N bars of data).
  * Every candidate of a setup is used (no one-position-per-stock rule here: this step measures distributions).
  * RANDOM CONTROL per setup: for each of its signal dates a random stock that is in the universe that day, entry next
    open, stop from that stock's nearest support zone; 20 runs; same targets, stops, costs.
Every (setup, N, target) combination is reported, so the number of comparisons is visible (multiple testing).
Output: results/step1_mfe.md (and a summary line in results/strategy_log.md).
"""
from __future__ import annotations

import os
import pickle

import numpy as np
import pandas as pd

from indicator_lab import sr
from indicator_lab.timing import regime as R
from indicator_lab.twenty import data20
from indicator_lab.week import build as B
from indicator_lab.week import run as W

try:
    from numba import njit
except ImportError:
    def njit(*a, **k):
        return (lambda f: f) if not a or not callable(a[0]) else a[0]

TARGETS = np.array([0.02, 0.03, 0.04, 0.05, 0.07, 0.10])
HOLDS = (5, 10, 15, 20)
COMM, TICK2 = 0.0005, 0.02
TRAIN_END = pd.Timestamp("2022-12-31")
OUT = os.path.join(os.path.dirname(W.LOG), "step1_mfe.md")
RUNS = 20


@njit(cache=True)
def outcome(o, h, lo, c, d, fill, stop, tgt, hold):
    """Exit price, bars held, kind (0 stop, 1 target, 2 time, 3 end of data), MFE, MAE (fractions of the fill)."""
    n = len(c)
    mfe = 0.0
    mae = 0.0
    for k in range(hold):
        day = d + k
        if day >= n:
            return c[n - 1], k, 3, mfe, mae
        op = fill if k == 0 else o[day]
        if lo[day] <= stop:
            px = stop if k == 0 else min(op, stop)
            mae = min(mae, stop / fill - 1)
            return px, k + 1, 0, mfe, mae
        mfe = max(mfe, h[day] / fill - 1)
        mae = min(mae, lo[day] / fill - 1)
        if h[day] >= tgt:
            px = tgt if k == 0 else max(op, tgt)
            return px, k + 1, 1, mfe, mae
        if k == hold - 1:
            return c[day], k + 1, 2, mfe, mae
    return c[min(d + hold - 1, n - 1)], hold, 2, mfe, mae


def net(fill, px):
    return (px - TICK2) * (1 - COMM) / ((fill + TICK2) * (1 + COMM)) - 1


def std_stop(fill, anchor, atr):
    base = anchor - 0.25 * atr if np.isfinite(anchor) and anchor < fill else fill - 1.5 * atr
    return max(fill * 0.92, min(base, fill - 1.0 * atr))


def entry(o, h, s, etype, elevel):
    d = s + 1
    if d >= len(o):
        return None, None
    if etype == "stop":
        if not h[d] >= elevel:
            return None, None
        return d, max(o[d], elevel)
    return d, o[d]


def simulate(arr, s, etype, elevel, anchor) -> list | None:
    """All (N, target) outcomes of one entry: list of (N, tgt, net_ret, kind, bars, mfe, mae, risk)."""
    o, h, lo, c, a = arr["o"], arr["h"], arr["l"], arr["c"], arr["atr"]
    d, fill = entry(o, h, s, etype, elevel)
    if d is None or not (fill > 0 and a[s] > 0):
        return None
    stop = std_stop(fill, anchor, a[s])
    out = []
    for hold in HOLDS:
        if d + hold > len(c):
            return None
        for tgt in TARGETS:
            px, bars, kind, mfe, mae = outcome(o, h, lo, c, d, fill, stop, fill * (1 + tgt), hold)
            out.append((hold, tgt, net(fill, px), kind, bars, mfe, mae, 1 - stop / fill))
    return out


def load_all():
    data20.final_mode()
    spy = R.load("SPY")
    with open(B.OUT, "rb") as fh:
        tickers = sorted({z["ticker"] for z in pickle.load(fh)["cands"]})
    arrs, sigs, elig = {}, {}, {}
    for j, t in enumerate(tickers):
        df = data20.load(t)
        df = df[(df[["open", "high", "low", "close"]] > 0).all(axis=1) & (df.index <= B.END)]
        lv = sr.levels(df)
        arrs[t] = {"idx": df.index, "o": df["open"].to_numpy(float), "h": df["high"].to_numpy(float),
                   "l": df["low"].to_numpy(float), "c": df["close"].to_numpy(float), "atr": lv["atr"].to_numpy(),
                   "sup_lo": lv["sup_lo"].to_numpy(), "sup_str": lv["sup_str"].to_numpy()}
        m = B.universe_mask(df)
        sigs[t] = {sid: [x for x in lst if m[x[0]] and B.START <= df.index[x[0]] <= B.END]
                   for sid, lst in B.signals(df, lv, spy.reindex(df.index).ffill().to_numpy()).items()}
        elig[t] = np.where(m & (df.index >= B.START) & (df.index <= B.END))[0]
        if j % 400 == 0:
            print(f"load {j}/{len(tickers)}", flush=True)
    return arrs, sigs, elig


def summarize(rows: list) -> dict:
    """rows: list of (N, tgt, net, kind, bars, mfe, mae, risk) -> {(N, tgt): stats}."""
    d = pd.DataFrame(rows, columns=["N", "tgt", "ret", "kind", "bars", "mfe", "mae", "risk"])
    out = {}
    for (n, tgt), g in d.groupby(["N", "tgt"]):
        r = g["ret"].to_numpy()
        w, lz = r[r > 0], r[r <= 0]
        out[(n, tgt)] = {"n": len(r), "win": (r > 0).mean(), "hit": (g["kind"] == 1).mean(), "exp": r.mean(),
                         "pf": w.sum() / -lz.sum() if lz.sum() < 0 else np.inf,
                         "exp_R": (r / g["risk"]).mean(), "bars": g["bars"].mean(),
                         "mfe_med": g["mfe"].median(), "mae_med": g["mae"].median()}
    return out


def main():
    arrs, sigs, elig = load_all()
    by_date: dict = {}
    for t, ix in elig.items():
        idx = arrs[t]["idx"]
        for i in ix:
            by_date.setdefault(idx[i], []).append((t, int(i)))
    rng = np.random.default_rng(7)
    results = {}
    for sid in B.NAMES:
        for part in ("train", "test"):
            rows, dates = [], []
            for t, lst in sigs.items():
                idx = arrs[t]["idx"]
                for s, etype, elevel, anchor in lst:
                    day = idx[s]
                    if (part == "train") != (day <= TRAIN_END):
                        continue
                    sim = simulate(arrs[t], s, etype, elevel, anchor)
                    if sim is not None:
                        rows += sim
                        dates.append(day)
            real = summarize(rows)
            rand = []
            for _ in range(RUNS):
                rr = []
                for day in dates:
                    pool = by_date.get(day)
                    if not pool:
                        continue
                    t, s = pool[rng.integers(len(pool))]
                    sim = simulate(arrs[t], s, "open", np.nan, arrs[t]["sup_lo"][s])
                    if sim is not None:
                        rr += sim
                rand.append(summarize(rr))
            results[(sid, part)] = (real, rand)
            print(f"{sid} {part}: {len(dates)} trades", flush=True)
    with open(os.path.join(B.CACHE, "step1_results.pkl"), "wb") as fh:
        pickle.dump(results, fh)
    write_report(results)


def write_report(results):
    lines = ["# Stap 1 — MFE/MAE en kans op een vast doel (max +10%, hele positie eruit)\n\n",
             ("Train 2015-2022, test 2023-2026. Kosten 0,05%/kant + 2 ticks slippage/kant. Win = netto > 0. Random = "
             "zelfde datums, willekeurig aandeel uit het universum, 20 runs (gemiddelde). "
             f"Aantal geteste combinaties: {len(B.NAMES)} setups x {len(HOLDS)} houdtijden x {len(TARGETS)} doelen = "
             f"{len(B.NAMES) * len(HOLDS) * len(TARGETS)} (x 2 perioden).\n\n")]
    best = []
    for sid in B.NAMES:
        lines.append(f"## {sid} {B.NAMES[sid]}\n\n")
        rows = []
        for n in HOLDS:
            for tgt in TARGETS:
                tr, _ = results[(sid, "train")]
                te, rnd = results[(sid, "test")]
                a, b = tr.get((n, tgt)), te.get((n, tgt))
                if a is None or b is None:
                    continue
                rw = np.mean([x[(n, tgt)]["win"] for x in rnd if (n, tgt) in x])
                rp = np.mean([x[(n, tgt)]["pf"] for x in rnd if (n, tgt) in x])
                rows.append({"dagen": n, "doel": f"+{tgt * 100:.0f}%", "train winrate": f"{a['win'] * 100:.0f}%",
                             "train PF": f"{a['pf']:.2f}", "test trades": b["n"], "test doel geraakt": f"{b['hit'] * 100:.0f}%",
                             "test winrate": f"{b['win'] * 100:.0f}%", "test PF": f"{b['pf']:.2f}",
                             "test exp.": f"{b['exp'] * 100:+.2f}%", "test exp. (R)": f"{b['exp_R']:+.2f}",
                             "random winrate": f"{rw * 100:.0f}%", "random PF": f"{rp:.2f}",
                             "MFE / MAE mediaan": f"{b['mfe_med'] * 100:+.1f}% / {b['mae_med'] * 100:.1f}%",
                             "gem. dagen": f"{b['bars']:.1f}"})
                best.append((sid, n, tgt, a, b, rw, rp))
        lines.append(pd.DataFrame(rows).to_markdown(index=False) + "\n\n")
    ok = [x for x in best if x[4]["win"] >= 0.70]
    lines.append("## Welke combinaties halen >= 70% winrate op TEST\n\n")
    if ok:
        lines.append(pd.DataFrame([{"setup": f"{s} {B.NAMES[s]}", "dagen": n, "doel": f"+{t * 100:.0f}%",
                                    "test winrate": f"{b['win'] * 100:.0f}%", "test PF": f"{b['pf']:.2f}",
                                    "test exp.": f"{b['exp'] * 100:+.2f}%", "random winrate": f"{rw * 100:.0f}%",
                                    "random PF": f"{rp:.2f}", "trades": b["n"]}
                                   for s, n, t, a, b, rw, rp in ok]).to_markdown(index=False) + "\n")
    else:
        lines.append("_Geen enkele._\n")
    with open(OUT, "w") as fh:
        fh.write("".join(lines))
    print("".join(lines[-3:]))


if __name__ == "__main__":
    main()
