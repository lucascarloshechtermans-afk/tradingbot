"""Run the one-week swing study on the candidates of build.py: filters as toggles, one change per run, a log.

    python -m indicator_lab.week.run            # all 10 strategies, up to 5 iterations each, then the ranking

Protocol (the user's brief):
  * Walk-forward: train = signals 2015-01-01 .. 2023-04-06 (70%), test = 2023-04-07 .. 2026-10-23 (30%). Only the
    test counts; the train set decides whether a change is kept.
  * Run 1 = the strategy without filters. Then each of the 5 filters ON ALONE (one change versus the baseline, so
    each filter's effect is measured apart): market regime, room >= 10% to the next strong resistance, RS top 20%,
    volume surge, no earnings in the holding period. Last run: the filters that each raised the TRAIN profit factor,
    combined. The configuration with the best TRAIN profit factor (>= 100 train trades) is the strategy's choice.
    No parameter of a strategy is tuned (0 of the allowed 3): nothing is fitted beyond the on/off filters.
  * < 100 test trades = "onvoldoende data". Test PF <= 1.3 after the last iteration = "verworpen".
  * One open position per stock (applied after the filters). Account: at most 10 positions of 10% (equal weight of
    the starting slot, rebalanced daily), idle cash 0%, mean of 5 random orders of same-day signals.
  * Every run is appended to results/strategy_log.md; a configuration already in the log is never run again.
"""
from __future__ import annotations

import os
import pickle

import numpy as np
import pandas as pd

from indicator_lab.week import build as B

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
LOG = os.path.join(ROOT, "results", "strategy_log.md")
FILTERS = ["regime", "room10", "rs_top20", "vol_surge", "no_earnings"]
FILTER_NL = {"regime": "marktregime (SPY > SMA50, EMA20 > EMA50)", "room10": "ruimte >= 10% tot sterke weerstand",
             "rs_top20": "RS top 20%", "vol_surge": "volume >= 1.5x op signaaldag",
             "no_earnings": "geen earnings in de houdtijd"}
HEADER = ("| run | strategie | instellingen | set | trades | winrate | gem. winst | gem. verlies | PF | expectancy | "
          "max DD (rekening) | CAGR (rekening) | % +10% geraakt | % +20% geraakt | gem. houdtijd |\n"
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|\n")


def load():
    with open(B.OUT, "rb") as fh:
        return pickle.load(fh)


def earnings_flags(cands: list) -> dict | None:
    """{ticker: sorted array of reaction days} from the Yahoo earnings cache, or None if it is not there."""
    from indicator_lab.week import earnings as E
    return E.load_all()


def select(cands: list, sid: int, flt: tuple, earn: dict | None) -> list:
    out = []
    for z in cands:
        if z["strategy"] != sid:
            continue
        if "regime" in flt and not z["regime"]:
            continue
        if "room10" in flt and not z["room10"]:
            continue
        if "rs_top20" in flt and not z["rs_top20"]:
            continue
        if "vol_surge" in flt and not z["vol_surge"]:
            continue
        if "no_earnings" in flt and sid != 3:
            if earn is None or z["ticker"] not in earn:
                continue                                   # unknown earnings dates: not taken (conservative)
            ed = earn[z["ticker"]]
            i = np.searchsorted(ed, np.datetime64(z["signal"]), side="right")
            if i < len(ed) and ed[i] <= np.datetime64(z["exit"]):
                continue
        out.append(z)
    out.sort(key=lambda z: (z["signal"], z["ticker"]))
    last: dict = {}
    taken = []
    for z in out:                                          # one position per stock at a time
        if z["ticker"] in last and z["entry"] <= last[z["ticker"]]:
            continue
        last[z["ticker"]] = z["exit"]
        taken.append(z)
    return taken


def account(trades: list, start, end, k: int = 10, seeds: int = 5) -> dict:
    idx = pd.bdate_range(start, end)
    pos = {d: i for i, d in enumerate(idx)}
    cagr, dd = [], []
    for seed in range(seeds):
        rng = np.random.default_rng(seed)
        order = sorted(trades, key=lambda z: (z["entry"], rng.random()))
        port = np.zeros(len(idx))
        busy: list = []
        for z in order:
            busy = [e for e in busy if e >= z["entry"]]
            if len(busy) >= k:
                continue
            busy.append(z["exit"])
            for d, r in zip(z["dates"], z["daily"]):
                if d in pos:
                    port[pos[d]] += r / k
        eq = np.cumprod(1 + port)
        yrs = len(idx) / 261
        cagr.append(eq[-1] ** (1 / yrs) - 1)
        dd.append(float((eq / np.maximum.accumulate(eq) - 1).min()))
    return {"cagr": float(np.mean(cagr)), "maxdd": float(np.mean(dd))}


def metrics(trades: list, start, end) -> dict:
    if not trades:
        return {"n": 0}
    r = np.array([z["ret"] for z in trades])
    w, lz = r[r > 0], r[r <= 0]
    acc = account(trades, start, end)
    return {"n": len(r), "win": (r > 0).mean(), "avg_win": w.mean() if len(w) else np.nan,
            "avg_loss": lz.mean() if len(lz) else np.nan, "pf": w.sum() / -lz.sum() if lz.sum() < 0 else np.inf,
            "exp": r.mean(), "maxdd": acc["maxdd"], "cagr": acc["cagr"],
            "hit10": np.mean([z["hit10"] for z in trades]), "hit20": np.mean([z["hit20"] for z in trades]),
            "hold": np.mean([z["hold"] for z in trades])}


def fmt(run, sid, flt, part, m) -> str:
    cfg = "geen filters" if not flt else " + ".join(FILTER_NL[f] for f in flt)
    if m["n"] == 0:
        return f"| {run} | {sid} {B.NAMES[sid]} | {cfg} | {part} | 0 | – | – | – | – | – | – | – | – | – | – |\n"
    return (f"| {run} | {sid} {B.NAMES[sid]} | {cfg} | {part} | {m['n']} | {m['win'] * 100:.0f}% | "
            f"{m['avg_win'] * 100:+.1f}% | {m['avg_loss'] * 100:+.1f}% | {m['pf']:.2f} | {m['exp'] * 100:+.2f}% | "
            f"{m['maxdd'] * 100:.1f}% | {m['cagr'] * 100:.1f}% | {m['hit10'] * 100:.0f}% | {m['hit20'] * 100:.0f}% | "
            f"{m['hold']:.1f} d |\n")


def logged_keys() -> set:
    if not os.path.exists(LOG):
        return set()
    keys = set()
    with open(LOG) as fh:
        for line in fh:
            if line.startswith("| ") and "| train |" in line:
                parts = [p.strip() for p in line.split("|")]
                keys.add((parts[2], parts[3]))
    return keys


def main():
    data = load()
    cands = data["cands"]
    earn = earnings_flags(cands)
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    if not os.path.exists(LOG):
        with open(LOG, "w") as fh:
            fh.write("# Strategy log — one-week swing study (indicator_lab/week)\n\nZie `indicator_lab/week/run.py` voor het "
                     "protocol. Train = 2015-01-01 .. 2023-04-06, test (out-of-sample) = 2023-04-07 .. 2026-10-23.\n\n"
                     + HEADER)
    done = logged_keys()
    run_no = len(done) + 1
    tr_span = (B.START, B.SPLIT)
    te_span = (B.SPLIT + pd.Timedelta(days=1), B.END)
    summary = []
    for sid in B.NAMES:
        best, best_pf, history, helped = (), -1.0, [], []
        steps = [()] + [(f,) for f in FILTERS] + ["combo"]
        for it, step in enumerate(steps, 1):
            if step == "combo":
                if len(helped) < 2:
                    continue
                step = tuple(helped)
            flt = tuple(sorted(step))
            key = (f"{sid} {B.NAMES[sid]}", "geen filters" if not flt else " + ".join(FILTER_NL[f] for f in flt))
            sel = select(cands, sid, flt, earn)
            tr = [z for z in sel if z["split"] == "train"]
            te = [z for z in sel if z["split"] == "test"]
            mtr, mte = metrics(tr, *tr_span), metrics(te, *te_span)
            if key not in done:
                with open(LOG, "a") as fh:
                    fh.write(fmt(run_no, sid, flt, "train", mtr) + fmt(run_no, sid, flt, "test", mte))
                run_no += 1
                done.add(key)
            history.append((flt, mtr, mte))
            pf = mtr.get("pf", 0) if mtr["n"] >= 100 else 0
            if it == 1:
                base_pf = pf
            elif len(flt) == 1 and pf > base_pf:
                helped.append(flt[0])
            if it == 1 or pf > best_pf:
                best, best_pf = flt, pf
            print(f"{sid} it{it} {key[1]:70s} train n {mtr['n']:5d} PF {mtr.get('pf', 0):.2f} | test n {mte['n']:5d} "
                  f"PF {mte.get('pf', 0):.2f} exp {mte.get('exp', 0) * 100:+.2f}%", flush=True)
        fin = next(h for h in history if h[0] == best)
        mte = fin[2]
        verdict = ("onvoldoende data" if mte["n"] < 100 else "geaccepteerd" if mte["pf"] > 1.3 else "verworpen")
        summary.append({"sid": sid, "flt": best, "train": fin[1], "test": mte, "verdict": verdict})
    with open(os.path.join(os.path.dirname(LOG), "week_summary.pkl"), "wb") as fh:
        pickle.dump(summary, fh)
    rows = []
    for s in sorted(summary, key=lambda x: -(x["test"].get("pf", 0) if x["test"]["n"] >= 100 else -1)):
        m = s["test"]
        rows.append({"strategie": f"{s['sid']} {B.NAMES[s['sid']]}",
                     "filters (gekozen op train)": "geen" if not s["flt"] else ", ".join(s["flt"]),
                     "test trades": m["n"], "winrate": f"{m.get('win', 0) * 100:.0f}%", "PF": f"{m.get('pf', 0):.2f}",
                     "expectancy": f"{m.get('exp', 0) * 100:+.2f}%", "% +10%": f"{m.get('hit10', 0) * 100:.0f}%",
                     "% +20%": f"{m.get('hit20', 0) * 100:.0f}%", "max DD": f"{m.get('maxdd', 0) * 100:.1f}%",
                     "CAGR": f"{m.get('cagr', 0) * 100:.1f}%", "houdtijd": f"{m.get('hold', 0):.1f} d",
                     "oordeel": s["verdict"]})
    txt = ("\n## Ranglijst (out-of-sample 2023-04-07 .. 2026-10-23, beste configuratie per strategie)\n\n"
           + pd.DataFrame(rows).to_markdown(index=False) + "\n")
    with open(LOG, "a") as fh:
        fh.write(txt)
    print(txt)


if __name__ == "__main__":
    main()
