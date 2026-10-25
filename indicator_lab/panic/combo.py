"""Trend + small panic buys: SPY while SPY > SMA200 (else T-bills) as the base, plus Bollinger dips bought ONLY on
market-wide washout days, each with a SMALL position (1/k of equity) funded from the parked SPY / T-bill money.

    python -m indicator_lab.panic.combo        # development grid (NASDAQ dev universe, 2015 .. 2024-10-21)

Why: in panic/dev.py the washout buys had the best trades of every test (+1.7-1.9% per taken trade, ~70% win), but 10%
positions bought into falling markets pushed the max drawdown to -41..-47%. Smaller positions keep the edge per trade
and should cut that drawdown, on top of the SPY trend rule (10.4%/yr, max DD -18%, the best Sharpe/MAR so far).

Pre-declared acceptance (before the run): Sharpe (excess) AND MAR above BOTH SPY buy & hold and the SPY-trend base, in
both ticker halves, at two neighbouring grid points (plateau). Then one run on the sealed never-used stocks.
Free parameters: washout threshold X and position size 1/k (2).
"""
from __future__ import annotations

import os

import pandas as pd

from indicator_lab.panic import dev as D

GRID = [(x, k) for x in (0.15, 0.20) for k in (20, 40)]   # 5% or 2.5% per position


def main():
    from indicator_lab.h4 import classics as C
    fr = C.frames()
    start, end = C.PERIOD_DAY
    pre, breadth = D.prepare(fr, start, end)
    tick = sorted(pre)
    halves = (tick[0::2], tick[1::2])
    rows, idx = [], None
    for x, k in GRID:
        res = D.run(pre, breadth, x, False, start, end)
        ts = D.trade_stats(res)
        a = D.account(res, True, k=k)
        idx = a["port0"].index
        hv = [D.account({t: res[t] for t in h}, True, seeds=5, k=k) for h in halves]
        rows.append({"x": x, "k": k, **ts, **{m: a[m] for m in ("cagr", "maxdd", "mar", "sharpe_rf", "invested", "taken_mean")},
                     "half_sharpe": (hv[0]["sharpe_rf"], hv[1]["sharpe_rf"]), "half_mar": (hv[0]["mar"], hv[1]["mar"])})
        D.P4.log({"phase": "combo-dev", "idea": f"trend + panic >= {x:.0%}, 1/{k} per position", "params": {"x": x, "k": k},
                  "new_free_params": 2, "universe": f"NASDAQ-dev {len(pre)}", "period": f"{start.date()}..{end.date()}",
                  "n": ts["n"], "win": ts["win"], "exp_pct": ts["mean"], "cagr": a["cagr"], "maxdd": a["maxdd"],
                  "mar": a["mar"], "exposure": a["invested"], "accepted": "n/a",
                  "notes": f"sharpe {a['sharpe_rf']:.3f} halves {rows[-1]['half_sharpe']} {rows[-1]['half_mar']}"}, D.EXP_LOG)
    bench = D.spy_rows(idx)
    spy, base = bench["SPY kopen en vasthouden"], bench["SPY alleen boven SMA200, anders T-bills"]
    bar_sh, bar_mar = max(spy["sharpe_rf"], base["sharpe_rf"]), max(spy["mar"], base["mar"])
    for r in rows:
        r["pass"] = (r["sharpe_rf"] > bar_sh and r["mar"] > bar_mar and min(r["half_sharpe"]) > bar_sh
                     and min(r["half_mar"]) > bar_mar)
    d = pd.DataFrame([{"variant": f"trend + paniek >= {r['x']:.0%}, {100 / r['k']:.1f}% per positie", "trades": r["n"],
                       "winrate": f"{r['win'] * 100:.0f}%", "gem. genomen trade": f"{r['taken_mean'] * 100:+.2f}%",
                       "in paniekposities": f"{r['invested'] * 100:.0f}%", "CAGR": f"{r['cagr'] * 100:.1f}%",
                       "max DD": f"{r['maxdd'] * 100:.1f}%", "Sharpe": f"{r['sharpe_rf']:.2f}", "MAR": f"{r['mar']:.2f}",
                       "Sharpe helften": f"{r['half_sharpe'][0]:.2f} / {r['half_sharpe'][1]:.2f}",
                       "MAR helften": f"{r['half_mar'][0]:.2f} / {r['half_mar'][1]:.2f}",
                       "voldoet": "JA" if r["pass"] else "nee"} for r in rows])
    b = pd.DataFrame([{"variant": kk, "CAGR": f"{s['cagr'] * 100:.1f}%", "max DD": f"{s['maxdd'] * 100:.1f}%",
                       "Sharpe": f"{s['sharpe_rf']:.2f}", "MAR": f"{s['mar']:.2f}"} for kk, s in bench.items()])
    plateau = any(rows[i]["pass"] and rows[j]["pass"] for i in range(len(rows)) for j in range(i + 1, len(rows))
                  if rows[i]["x"] == rows[j]["x"] or rows[i]["k"] == rows[j]["k"])
    txt = (f"# Trend + kleine paniekaankopen — ontwikkeling ({len(pre)} NASDAQ-aandelen, {start.date()} .. {end.date()})\n\n"
           + d.to_markdown(index=False) + "\n\nBenchmarks:\n\n" + b.to_markdown(index=False)
           + f"\n\nVooraf vastgelegde eis gehaald op een plateau (2 buurpunten): **{'JA' if plateau else 'NEE'}**\n")
    os.makedirs(D.OUT, exist_ok=True)
    with open(os.path.join(D.OUT, "combo_dev.md"), "w") as fh:
        fh.write(txt)
    print(txt)
    return plateau, rows


if __name__ == "__main__":
    main()
