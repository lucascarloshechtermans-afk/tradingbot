"""The ten well-known swing strategies of h4/classics.py on LARGE, liquid US stocks (all exchanges) instead of the
NASDAQ universe, traded as a real account whose idle cash sits in SPY while SPY > SMA200 (else T-bills).

    python -m indicator_lab.largecap.dev        # development: 20/21 dev universe, 2015-01-01 .. 2024-10-21

Fixed before the run (nothing tuned; the strategies' published rules exactly as in classics.py):
  * Large cap, point in time: on the signal day the stock is among the 300 highest 50-day average dollar volumes of the
    whole development universe (>= $5M), closes >= $5, and passes clean(): traded on each of the last 50 days with a
    moving close (added after the smoke test exposed stale zero-volume vendor prints; before any full run).
  * At most one BUY per stock per two weeks; fills next open; 0.1% per side + 0.1% entry slippage.
  * Account: at most 10 positions of 10%; idle cash in SPY while SPY > SMA200 (previous close), else T-bills; mean of
    10 random orders of same-day signals.
  * ACCEPT = Sharpe (excess of T-bills) AND MAR above BOTH SPY buy & hold AND "SPY only above SMA200, else T-bills",
    on the full universe and on both ticker halves. An accepted rule then gets ONE test on unused data.
Survivorship: only stocks still listed in 2026 (flatters every long rule).
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

os.environ.setdefault("CLASSIC_TF", "day")
from indicator_lab import ind
from indicator_lab.h4 import classics as C  # sets the development data mode
from indicator_lab.swing4 import sim2 as S2
from indicator_lab.swing5 import port as PT
from indicator_lab.twenty import data20

HERE = os.path.dirname(__file__)
OUT = os.path.join(HERE, "reports")
TOP = 300
PERIOD = C.PERIOD_DAY


def frames() -> dict:
    out = {}
    univ = data20.DEV[:int(os.environ["LC_N"])] if os.environ.get("LC_N") else data20.DEV
    for t in univ:
        try:
            df = data20.load(t)
        except PermissionError:
            continue
        if df is None:
            continue
        df = df[(df.index < pd.Timestamp("2024-10-22")) & (df[["open", "high", "low", "close"]] > 0).all(axis=1)]
        if len(df) >= 400 and df.index[-1] >= pd.Timestamp("2016-01-01"):
            out[t] = df
    return out


def clean(d: pd.DataFrame) -> pd.Series:
    """Point-in-time data hygiene: volume on every one of the last 50 days and the close changed on >= 80% of them
    (stale vendor prints with zero volume and a sudden x1000 jump otherwise pass a pure ranking)."""
    traded = (d["volume"] > 0).rolling(50).min() == 1
    moved = (d["close"].diff() != 0).rolling(50).mean() >= 0.8
    return traded & moved


def large_mask(fr: dict) -> pd.DataFrame:
    dv = pd.concat({t: (d["close"] * d["volume"]).rolling(50, min_periods=40).mean().where(clean(d) & (d["close"] >= 5))
                    for t, d in fr.items()}, axis=1)
    rank = dv.rank(axis=1, ascending=False)
    return (rank <= TOP) & (dv >= 5e6)


def run(fr: dict, big: pd.DataFrame, name: str, tickers) -> dict:
    res = {}
    start, end = PERIOD
    for t in tickers:
        df = fr[t]
        e, x = C.strategies(df)[name]
        ok = big[t].reindex(df.index).fillna(False).to_numpy() & (df["close"] >= 5).to_numpy()
        inwin = (df.index >= start) & (df.index <= end)
        e = e & ok & inwin
        if not e.any():
            continue
        pol = S2.Policy(min_gap_days=14) if name.startswith("10 ") else C.NO_STOP

        r, tr = S2.simulate(S2.arrays(df, ind.atr(df, 14).to_numpy(), x), e, pol, slip=C.SLIP)
        if not tr:
            continue
        for z in tr:
            z["ticker"] = t
        rs = pd.Series(r, index=df.index)
        res[t] = (rs[(rs.index >= start) & (rs.index <= end)], tr)
    return res


def account(res: dict, seeds: int = 10) -> dict:
    s = PT.system(res, k=10, seeds=seeds, park=True)
    return {k: s[k] for k in ("cagr", "maxdd", "mar", "sharpe_rf", "invested", "parked")} | {"port0": s["port0"]}


def main():
    fr = frames()
    big = large_mask(fr)
    tick = sorted(fr)
    halves = (tick[0::2], tick[1::2])
    print(f"{len(fr)} stocks; large-cap days per stock (median of those ever large): "
          f"{int(big.sum()[big.sum() > 0].median())}", flush=True)
    names = list(C.strategies(next(iter(fr.values()))))
    rows, idx = [], None
    for name in names:
        res = run(fr, big, name, tick)
        tt = np.array([z["ret"] for _, tr in res.values() for z in tr])
        a = account(res)
        idx = a["port0"].index
        hv = [account({t: res[t] for t in h if t in res}, seeds=5) for h in halves]
        rows.append({"name": name, "n": len(tt), "win": float((tt > 0).mean()), "mean": float(tt.mean()), **a,
                     "half_sharpe": [h["sharpe_rf"] for h in hv], "half_mar": [h["mar"] for h in hv]})
        r = rows[-1]
        print(f"{name:60s} n {r['n']:6d} win {r['win'] * 100:3.0f}% trade {r['mean'] * 100:+.2f}% | CAGR "
              f"{r['cagr'] * 100:5.1f}% DD {r['maxdd'] * 100:6.1f}% Sh {r['sharpe_rf']:.2f} MAR {r['mar']:.2f} "
              f"halves Sh {r['half_sharpe'][0]:.2f}/{r['half_sharpe'][1]:.2f}", flush=True)
    bench, m = PT.benchmarks(idx)
    spy = PT.stats(bench["SPY buy & hold"], m)
    tim = PT.stats(m["spy"] * m["on"] + m["rf"] * (1 - m["on"]), m)
    for r in rows:
        r["accept"] = all(r["sharpe_rf"] > b["sharpe_rf"] and r["mar"] > b["mar"]
                          and min(r["half_sharpe"]) > b["sharpe_rf"] and min(r["half_mar"]) > b["mar"] for b in (spy, tim))
    d = pd.DataFrame([{"strategie": r["name"], "trades": r["n"], "winrate": f"{r['win'] * 100:.0f}%",
                       "gem. trade": f"{r['mean'] * 100:+.2f}%", "in aandelen": f"{r['invested'] * 100:.0f}%",
                       "in SPY": f"{r['parked'] * 100:.0f}%", "CAGR": f"{r['cagr'] * 100:.1f}%",
                       "max DD": f"{r['maxdd'] * 100:.1f}%", "Sharpe": f"{r['sharpe_rf']:.2f}", "MAR": f"{r['mar']:.2f}",
                       "Sharpe helften": f"{r['half_sharpe'][0]:.2f} / {r['half_sharpe'][1]:.2f}",
                       "voldoet": "JA" if r["accept"] else "nee"} for r in rows])
    b = pd.DataFrame([{"strategie": k, "CAGR": f"{s['cagr'] * 100:.1f}%", "max DD": f"{s['maxdd'] * 100:.1f}%",
                       "Sharpe": f"{s['sharpe_rf']:.2f}", "MAR": f"{s['mar']:.2f}"}
                      for k, s in (("SPY kopen en vasthouden", spy), ("SPY alleen boven SMA200, anders T-bills", tim))])
    txt = (f"# Klassieke swingstrategieën op grote aandelen — ontwikkeling ({len(fr)} aandelen, top {TOP} op "
           f"dollarvolume per dag, {PERIOD[0].date()} .. {PERIOD[1].date()})\n\nRekening max 10 posities van 10%, lege "
           "kas in SPY zolang SPY > SMA200 (anders T-bills). Criterium (vooraf): Sharpe én MAR boven beide benchmarks, "
           "ook in beide tickerhelften.\n\n" + d.to_markdown(index=False) + "\n\nBenchmarks:\n\n" + b.to_markdown(index=False) + "\n")
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "dev.md"), "w") as fh:
        fh.write(txt)
    print(txt)


if __name__ == "__main__":
    main()
