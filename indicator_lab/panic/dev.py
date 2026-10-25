"""'Buy the panic': a Bollinger-band dip is only bought on days when MANY stocks are below their lower band at once.

Hypothesis (formed from indicator_lab/h4/reports/classics_summary.md, point 3): the classic Bollinger bounce made its
money on days with > 50 simultaneous signals (+5.45% per trade) and almost nothing on quiet days (+0.23%); a capital-
limited account missed those days because it was already full. So: stay out on normal days, buy only in a washout.

    python -m indicator_lab.panic.dev                     # development grid (NASDAQ dev universe, 2015 .. 2024-10-21)

Rule: signal on the close when close < lower Bollinger band (20, 2) AND the share of liquid stocks in the universe with
close < their lower band that day >= X; optionally only above the stock's SMA200. Exit at the next open after a close
above the middle band (classic). At most one BUY per stock per two weeks, liquidity floor ($5, $5M/day), 0.1% per side +
0.1% entry slippage. Account: at most 10 positions of 10%; idle cash in T-bills, or in SPY while SPY > SMA200 (v3.1 rule).

Pre-declared acceptance (before the grid ran): account Sharpe (excess) AND MAR above SPY buy & hold on the development
data, in both ticker halves, from a flat plateau of X. Then ONE holdout run on never-used data.
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

os.environ.setdefault("CLASSIC_TF", "day")   # indicator_lab.h4.classics: daily bars, development data mode
from indicator_lab import ind
from indicator_lab.swing4 import protocol as P4
from indicator_lab.swing4 import sim2 as S2

HERE = os.path.dirname(__file__)
OUT = os.path.join(HERE, "reports")
EXP_LOG = os.environ.get("PANIC_LOG", os.path.join(HERE, "experiments.csv"))
SLIP = 0.001
POL = S2.Policy(trail=1e6, stop=1e6, min_gap_days=14)
GRID_X = (0.10, 0.15, 0.20, 0.30)


def prepare(fr: dict, start, end) -> tuple[dict, pd.Series]:
    """Per ticker arrays + the point-in-time breadth: share of liquid stocks with close < lower band."""
    pre, sig, liq = {}, {}, {}
    for t, df in fr.items():
        c = df["close"]
        low, mid, _ = ind.bbands(c, 20, 2.0)
        liquid = (c >= 5) & ((c * df["volume"]).rolling(50).mean() >= 5e6)
        below = (c < low) & liquid
        pre[t] = {"df": df, "below": below.to_numpy(), "exit": (c > mid).to_numpy(), "up": (c > ind.sma(c, 200)).to_numpy(),
                  "inwin": ((df.index >= start) & (df.index <= end)), "atr": ind.atr(df, 14).to_numpy()}
        sig[t], liq[t] = below.astype(float), liquid.astype(float)
    S = pd.concat(sig, axis=1).fillna(0)
    Lq = pd.concat(liq, axis=1).fillna(0)
    breadth = S.sum(axis=1) / Lq.sum(axis=1).replace(0, np.nan)
    return pre, breadth.fillna(0)


def run(pre: dict, breadth: pd.Series, x: float, need_up: bool, start, end) -> dict:
    res = {}
    for t, p in pre.items():
        df = p["df"]
        b = breadth.reindex(df.index).fillna(0).to_numpy()
        e = p["below"] & p["inwin"] & (b >= x)
        if need_up:
            e &= p["up"]
        r, tr = S2.simulate(S2.arrays(df, p["atr"], p["exit"]), e, POL, slip=SLIP)
        for z in tr:
            z["ticker"] = t
        rs = pd.Series(r, index=df.index)
        res[t] = (rs[(rs.index >= start) & (rs.index <= end)], tr)
    return res


def account(res: dict, park: bool, seeds: int = 10, k: int = 10) -> dict:
    from indicator_lab.swing5 import port as PT
    runs = [PT.portfolio(res, k, s, park=park) for s in range(seeds)]
    m = runs[0]["mkt"]
    st = [PT.stats(r["port"], m) for r in runs]
    out = {k: float(np.mean([s[k] for s in st])) for k in ("cagr", "maxdd", "mar", "sharpe_rf", "alpha", "beta")}
    out["invested"] = float(np.mean([r["invested"].mean() for r in runs]))
    tk = [z["ret"] for r in runs for z in r["taken"]]
    out["taken_mean"] = float(np.mean(tk)) if tk else np.nan
    out["port0"] = runs[0]["port"]
    out["mkt"] = m
    return out


def spy_rows(idx) -> dict:
    from indicator_lab.swing5 import port as PT
    bench, m = PT.benchmarks(idx)
    spy = PT.stats(bench["SPY buy & hold"], m)
    timing = (m["spy"] * m["on"] + m["rf"] * (1 - m["on"]))   # SPY while SPY > SMA200, else T-bills
    return {"SPY kopen en vasthouden": spy, "SPY alleen boven SMA200, anders T-bills": PT.stats(timing, m)}


def trade_stats(res) -> dict:
    tt = pd.DataFrame([z for _, tr in res.values() for z in tr])
    if tt.empty:
        return {"n": 0, "win": np.nan, "mean": np.nan, "pf": np.nan}
    r = tt["ret"].to_numpy()
    return {"n": len(r), "win": float((r > 0).mean()), "mean": float(r.mean()),
            "pf": float(r[r > 0].sum() / -r[r <= 0].sum()) if (r <= 0).any() else np.inf}


def main():
    from indicator_lab.h4 import classics as C
    fr = C.frames()
    start, end = C.PERIOD_DAY
    pre, breadth = prepare(fr, start, end)
    tick = sorted(pre)
    halves = (tick[0::2], tick[1::2])
    idx = None
    rows = []
    for need_up in (True, False):
        for x in GRID_X:
            res = run(pre, breadth, x, need_up, start, end)
            ts = trade_stats(res)
            for park in (False, True):
                a = account(res, park)
                idx = a["port0"].index
                hv = [account({t: res[t] for t in h}, park, seeds=5) for h in halves]
                name = (f"paniek >= {x:.0%}, {'boven SMA200' if need_up else 'ook onder SMA200'}, "
                        f"kas in {'SPY>SMA200' if park else 'T-bills'}")
                rows.append({"name": name, "x": x, "need_up": need_up, "park": park, **ts, **{k: a[k] for k in (
                    "cagr", "maxdd", "mar", "sharpe_rf", "alpha", "beta", "invested", "taken_mean")},
                    "half_sharpe": (hv[0]["sharpe_rf"], hv[1]["sharpe_rf"]), "half_mar": (hv[0]["mar"], hv[1]["mar"])})
                r = rows[-1]
                print(f"{name:70s} n {r['n']:5d} win {r['win'] * 100:4.0f}% trade {r['mean'] * 100:+.2f}% "
                      f"(taken {r['taken_mean'] * 100:+.2f}%) | CAGR {r['cagr'] * 100:5.1f}% DD {r['maxdd'] * 100:6.1f}% "
                      f"MAR {r['mar']:.2f} Sh {r['sharpe_rf']:.2f} invested {r['invested'] * 100:.0f}%", flush=True)
                P4.log({"phase": "dev", "idea": name, "params": {"x": x, "need_up": need_up, "park": park},
                        "new_free_params": 2, "universe": f"NASDAQ-dev {len(pre)}", "period": f"{start.date()}..{end.date()}",
                        "n": r["n"], "win": r["win"], "exp_pct": r["mean"], "cagr": r["cagr"], "maxdd": r["maxdd"],
                        "mar": r["mar"], "exposure": r["invested"], "accepted": "n/a",
                        "notes": f"sharpe {r['sharpe_rf']:.3f} halves sharpe {r['half_sharpe']} mar {r['half_mar']}"}, EXP_LOG)
    bench = spy_rows(idx)
    for k, s in bench.items():
        print(f"{k:70s} CAGR {s['cagr'] * 100:5.1f}% DD {s['maxdd'] * 100:6.1f}% MAR {s['mar']:.2f} Sh {s['sharpe_rf']:.2f}")
    spy = bench["SPY kopen en vasthouden"]
    for r in rows:
        r["accept"] = (r["sharpe_rf"] > spy["sharpe_rf"] and r["mar"] > spy["mar"]
                       and min(r["half_sharpe"]) > spy["sharpe_rf"] and min(r["half_mar"]) > spy["mar"])
    d = pd.DataFrame([{"variant": r["name"], "trades": r["n"], "winrate": f"{r['win'] * 100:.0f}%",
                       "gem. trade": f"{r['mean'] * 100:+.2f}%", "gem. genomen trade": f"{r['taken_mean'] * 100:+.2f}%",
                       "belegd": f"{r['invested'] * 100:.0f}%", "CAGR": f"{r['cagr'] * 100:.1f}%",
                       "max DD": f"{r['maxdd'] * 100:.1f}%", "MAR": f"{r['mar']:.2f}", "Sharpe": f"{r['sharpe_rf']:.2f}",
                       "Sharpe helften": f"{r['half_sharpe'][0]:.2f} / {r['half_sharpe'][1]:.2f}",
                       "voldoet": "JA" if r["accept"] else "nee"} for r in rows])
    b = pd.DataFrame([{"variant": k, "CAGR": f"{s['cagr'] * 100:.1f}%", "max DD": f"{s['maxdd'] * 100:.1f}%",
                       "MAR": f"{s['mar']:.2f}", "Sharpe": f"{s['sharpe_rf']:.2f}"} for k, s in bench.items()])
    os.makedirs(OUT, exist_ok=True)
    txt = (f"# 'Koop de paniek' — ontwikkeling ({len(pre)} NASDAQ-aandelen, {start.date()} .. {end.date()})\n\n"
           + d.to_markdown(index=False) + "\n\nBenchmarks:\n\n" + b.to_markdown(index=False) + "\n")
    with open(os.path.join(OUT, "dev.md"), "w") as fh:
        fh.write(txt)
    print(txt)


if __name__ == "__main__":
    main()
