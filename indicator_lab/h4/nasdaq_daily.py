"""The user's rules on DAILY bars over the NASDAQ universe: v4 (breakout + quality model + regime) with at most one BUY
signal per stock per two weeks and a profit target of +10 / +15 / +20% (or none), 2015-01-01 .. 2024-10-21.

    python -m indicator_lab.h4.nasdaq_daily

Universe: every NASDAQ-listed common stock / ADR (nasdaqlisted.txt, no ETFs, warrants, rights, units, preferreds)
with daily data in the Swing 20/21 cache: the 20/21 development universe = ~70% of NASDAQ; the other ~30% is the
20/21 project's sealed random holdout and is left out. This uses tickers of the v6 holdout, so that holdout is spent.
Survivorship: only stocks still listed in 2026, which flatters every long strategy and the average-stock benchmark.

Two views: ALL trades (as if every signal could be taken, equal weight per trade) and a real account with at most 10
or 20 positions (10% or 5% each, idle cash in SPY while SPY > SMA200 else T-bills, as v4 is traded; 0.1% per side +
0.1% entry slippage; mean of 20 random orders of same-day signals).
"""
from __future__ import annotations

import json
import os
from dataclasses import replace

import numpy as np
import pandas as pd

from indicator_lab.evaluate import _DATA, get
from indicator_lab.h4.nasdaq_list import nasdaq
from indicator_lab.metrics import equity_stats
from indicator_lab.swing4 import lab as L
from indicator_lab.swing4 import sim2 as S2
from indicator_lab.swing5 import port as PT
from indicator_lab.swing6 import improve6 as I6
from indicator_lab.twenty import data20

OUT = os.path.join(os.path.dirname(__file__), "reports")
PERIOD = (pd.Timestamp("2015-01-01"), pd.Timestamp("2024-10-21"))
SLIP = 0.001
BASE = S2.Policy(min_gap_days=14)   # at most one BUY per stock per two weeks (user rule)


def load(tickers) -> list[str]:
    ok = []
    for t in tickers:
        df = data20.load(t)
        if df is None:
            continue
        df = df[(df.index < I6.CUTOFF) & (df[["open", "high", "low", "close"]] > 0).all(axis=1)]
        if len(df) < 400 or df.index[-1] < pd.Timestamp("2016-01-01"):
            continue
        _DATA[t] = df
        ok.append(t)
    return ok


def all_trades(res) -> dict:
    tt = pd.DataFrame([x for _, tr in res.values() for x in tr])
    r = tt["ret"].to_numpy()
    w, lz = r[r > 0], r[r <= 0]
    top = np.sort(r)[::-1]
    return {"trades": len(r), "winrate": f"{(r > 0).mean() * 100:.0f}%", "gem. winst": f"{w.mean() * 100:.1f}%",
            "gem. verlies": f"{lz.mean() * 100:.1f}%", "gem. trade": f"{r.mean() * 100:.2f}%",
            "mediaan trade": f"{np.median(r) * 100:.2f}%", "PF": f"{w.sum() / -lz.sum():.2f}",
            "target geraakt": f"{(tt['reason'] == 'target').mean() * 100:.0f}%",
            "hold (dagen)": f"{tt['bars'].mean():.0f}",
            "beste 1% trades = % van winst": f"{top[:max(1, len(r) // 100)].sum() / r.sum() * 100:.0f}%"}


def account(res, k) -> dict:
    s = PT.system(res, k=k, seeds=20)
    return {"CAGR": f"{s['cagr'] * 100:.1f}%", "max DD": f"{s['maxdd'] * 100:.1f}%", "Sharpe": f"{s['sharpe_rf']:.2f}",
            "MAR": f"{s['mar']:.2f}", "port": s["port0"]}


def main():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    univ = load(nasdaq())
    ctx = I6.prep(I6.build(univ, os.path.join(os.environ.get("SWING4_CACHE", "/tmp"), "nasdaq_daily_ctx.pkl")))
    print(f"{len(univ)} NASDAQ stocks", flush=True)
    rows, acc_rows, curves = [], [], {}
    for name, pol in (("geen target", BASE), ("target +10%", replace(BASE, tgt_pct=0.10)),
                      ("target +15%", replace(BASE, tgt_pct=0.15)), ("target +20%", replace(BASE, tgt_pct=0.20))):
        res = L.run(ctx, I6.v4, pol, univ=univ, period=PERIOD, slip=SLIP)
        rows.append({"v4 dag, 1 BUY/2 weken": name, **all_trades(res)})
        for k in (10, 20):
            a = account(res, k)
            curves[f"{name}, {k} posities"] = a.pop("port")
            acc_rows.append({"systeem": f"{name}, max {k} posities", **a})
        print(rows[-1], acc_rows[-2:], flush=True)
    bench, m = PT.benchmarks(next(iter(curves.values())).index)
    s = PT.stats(bench["SPY buy & hold"], m)
    acc_rows.append({"systeem": "SPY kopen en vasthouden", "CAGR": f"{s['cagr'] * 100:.1f}%",
                     "max DD": f"{s['maxdd'] * 100:.1f}%", "Sharpe": f"{s['sharpe_rf']:.2f}", "MAR": f"{s['mar']:.2f}"})
    rets = pd.concat({t: get(t)["close"].pct_change() for t in univ}, axis=1)
    ew = rets[(rets.index >= PERIOD[0]) & (rets.index <= PERIOD[1])].mean(axis=1).fillna(0)
    e = equity_stats(ew)
    acc_rows.append({"systeem": "gemiddeld NASDAQ-aandeel kopen (gelijk gewogen, survivors)", "CAGR": f"{e['cagr'] * 100:.1f}%",
                     "max DD": f"{e['maxdd'] * 100:.1f}%", "Sharpe": f"{e['sharpe']:.2f}", "MAR": f"{e['mar']:.2f}"})
    curves["SPY"] = bench["SPY buy & hold"]
    os.makedirs(OUT, exist_ok=True)
    fig, ax = plt.subplots(figsize=(11, 5))
    for k_, r in curves.items():
        ax.plot((1 + r).cumprod(), label=k_, lw=2 if k_ == "SPY" else 1)
    ax.set_yscale("log")
    ax.legend(fontsize=7)
    ax.set_title(f"v4 op dagbars, {len(univ)} NASDAQ-aandelen, 2015-2024 (één willekeurige volgorde)")
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "nasdaq_daily.png"), dpi=100)
    txt = (f"# Jouw regels op dagbars, NASDAQ ({len(univ)} aandelen), {PERIOD[0].date()} .. {PERIOD[1].date()}\n\n"
           "## 1. Alle trades (alsof je elk signaal kon nemen)\n\n" + pd.DataFrame(rows).to_markdown(index=False) +
           "\n\n## 2. Een echte rekening\n\n" + pd.DataFrame(acc_rows).to_markdown(index=False) +
           "\n\n![equity](nasdaq_daily.png)\n")
    with open(os.path.join(OUT, "nasdaq_daily.md"), "w") as fh:
        fh.write(txt)
    print(txt)
    with open(os.path.join(OUT, "nasdaq_daily_universe.json"), "w") as fh:
        json.dump(univ, fh)


if __name__ == "__main__":
    main()
