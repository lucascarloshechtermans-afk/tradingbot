"""Post-earnings-announcement drift (PEAD) as a swing strategy: one of the few stock anomalies that survives large
replication studies (Ball & Brown 1968; Bernard & Thomas 1989; Chan, Jegadeesh & Lakonishok 1996 on the earnings
announcement return; Hou, Xue & Zhang 2017 replication: survives, smaller than first reported).

    python -m indicator_lab.earnings_drift.pead dev       # events 1997-01-01 .. 2011-12-31
    python -m indicator_lab.earnings_drift.pead holdout   # ONE run: events 2012-01-01 .. 2026-07-15

Data: the 131 stocks with Alpha Vantage quarterly EPS + consensus estimate history in indicator_lab/.cache (large,
popular US names, still listed in 2026: survivorship and selection bias, which flatter every long rule, so the
benchmark is the same stocks' 60-day return at random times as well as SPY). Prices: Yahoo, adjusted, from 1995.
Reaction day: the report date for pre-market / during-session reports, the next session for post-market reports.

Fixed before any result (no parameter is tuned):
  E1 earnings surprise:   surprise >= +10% of the estimate (|estimate| >= $0.05)
  E2 announcement return: reaction-day return minus SPY's >= +5% and a positive surprise
  E3 both
  Entry at the open after the reaction day; exit at the open 60 trading days later; 0.1% per side + 0.1% slippage;
  one position per stock at a time. Account: at most 10 positions of 10%, idle cash in SPY while SPY > SMA200, else
  T-bills; mean of 10 random orders of same-day signals.
PASS (per rule, on dev; then the same on the holdout): mean 60-day return in excess of SPY over the same days
>= +1.0% with t >= 2, positive in >= 60% of the years, AND account Sharpe and MAR above SPY buy & hold.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

from indicator_lab.swing5 import port as PT

HERE = os.path.dirname(__file__)
OUT = os.path.join(HERE, "reports")
CACHE = os.path.join(os.path.dirname(HERE), ".cache")
PX = os.path.join(CACHE, "px95")
HOLD, COST, SLIP = 60, 0.001, 0.001
PERIODS = {"dev": ("1997-01-01", "2011-12-31"), "holdout": ("2012-01-01", "2026-07-15")}


def prices(t: str) -> pd.DataFrame | None:
    p = os.path.join(PX, f"{t}.csv.gz")
    if not os.path.exists(p):
        return None
    d = pd.read_csv(p, index_col=0, parse_dates=True)
    return d[(d[["open", "close"]] > 0).all(axis=1)]


def tickers() -> list[str]:
    return sorted(f[5:-5] for f in os.listdir(CACHE) if f.startswith("earn_") and f.endswith(".json"))


def events(t: str, d: pd.DataFrame, spy: pd.Series) -> pd.DataFrame:
    with open(os.path.join(CACHE, f"earn_{t}.json")) as fh:
        q = json.load(fh)
    rows = []
    idx = d.index
    c = d["close"]
    for e in q:
        try:
            est, rep = float(e["estimatedEPS"]), float(e["reportedEPS"])
        except (TypeError, ValueError, KeyError):
            continue
        i = idx.searchsorted(pd.Timestamp(e["reportedDate"]))
        if e.get("reportTime") == "post-market":
            i += 1
        if i < 1 or i + 1 + HOLD >= len(idx):
            continue
        day = idx[i]
        r_stock = c.iloc[i] / c.iloc[i - 1] - 1
        s0, s1 = spy.asof(idx[i - 1]), spy.asof(day)
        surprise = (rep - est) / abs(est) if abs(est) >= 0.05 else np.nan
        rows.append({"ticker": t, "day": day, "i": i, "surprise": surprise, "raw_surprise": rep - est,
                     "ear": r_stock - (s1 / s0 - 1)})
    return pd.DataFrame(rows)


def rule_masks(ev: pd.DataFrame) -> dict:
    e1 = ev["surprise"] >= 0.10
    e2 = (ev["ear"] >= 0.05) & (ev["raw_surprise"] > 0)
    return {"E1 winstverrassing >= +10%": e1, "E2 koersreactie >= +5% t.o.v. SPY (en positieve verrassing)": e2,
            "E3 beide": e1 & e2, "(alle publicaties, ter vergelijking)": pd.Series(True, index=ev.index)}


def trade(d: pd.DataFrame, i: int, spy_o: pd.Series):
    """Buy at the open of bar i+1, sell at the open of bar i+1+HOLD. Returns (daily return series, trade dict)."""
    o, c = d["open"].to_numpy(), d["close"].to_numpy()
    a, b = i + 1, i + 1 + HOLD
    r = np.empty(b - a + 1)
    r[0] = c[a] / (o[a] * (1 + SLIP)) - 1 - COST
    r[1:-1] = c[a + 1:b] / c[a:b - 1] - 1
    r[-1] = o[b] / c[b - 1] - 1 - COST
    ret = o[b] * (1 - COST) / (o[a] * (1 + SLIP) * (1 + COST)) - 1
    sa, sb = spy_o.asof(d.index[a]), spy_o.asof(d.index[b])
    return pd.Series(r, index=d.index[a:b + 1]), {"entry_date": d.index[a], "exit_date": d.index[b], "ret": ret,
                                                    "excess": ret - (sb / sa - 1)}


def market_long(idx: pd.DatetimeIndex) -> pd.DataFrame:
    spy = prices("SPY")["close"]
    on = (spy > spy.rolling(200).mean()).shift(1).fillna(False)
    irx = pd.read_csv(os.path.join(CACHE, "long", "_IRX.csv.gz"), index_col=0, parse_dates=True)["close"]
    rf = (irx.reindex(spy.index).ffill() / 100 / 252).shift(1)
    out = pd.DataFrame({"spy": spy.pct_change(), "on": on.astype(float), "rf": rf}).reindex(idx)
    return out.fillna({"spy": 0.0, "on": 0.0}).ffill().fillna(0.0)


def run(mode: str):
    start, end = (pd.Timestamp(x) for x in PERIODS[mode])
    spy_df = prices("SPY")
    spy_c, spy_o = spy_df["close"], spy_df["open"]
    frames = {t: d for t in tickers() if (d := prices(t)) is not None and len(d) > HOLD + 5}
    ev = pd.concat([events(t, d, spy_c) for t, d in frames.items()], ignore_index=True)
    ev = ev[(ev["day"] >= start) & (ev["day"] <= end)].sort_values("day")
    PT.market = market_long   # the account's benchmark data: long SPY / T-bill history instead of the 2012+ cache
    rows, curves = [], {}
    for name, m in rule_masks(ev).items():
        sel = ev[m.fillna(False)]
        res: dict = {}
        busy: dict = {}
        tr_all = []
        for _, e in sel.iterrows():
            t = e["ticker"]
            d = frames[t]
            if busy.get(t) is not None and e["day"] < busy[t]:
                continue
            r, tr = trade(d, int(e["i"]), spy_o)
            busy[t] = tr["exit_date"]
            tr["ticker"] = t
            tr_all.append(tr)
            prev = res.get(t, (pd.Series(dtype=float), []))
            res[t] = (pd.concat([prev[0], r]), prev[1] + [tr])
        tt = pd.DataFrame(tr_all)
        if tt.empty:
            continue
        x = tt["excess"].to_numpy()
        by_year = tt.groupby(tt["entry_date"].dt.year)["excess"].mean()
        res = {t: (s[~s.index.duplicated(keep="last")], trs) for t, (s, trs) in res.items()}
        acc = PT.system(res, k=10, seeds=10, park=True)
        curves[name] = acc["port0"]
        rows.append({"regel": name, "trades": len(x), "winrate": f"{(tt['ret'] > 0).mean() * 100:.0f}%",
                     "gem. 60d rendement": f"{tt['ret'].mean() * 100:.2f}%", "gem. boven SPY": f"{x.mean() * 100:.2f}%",
                     "t": round(float(x.mean() / x.std() * np.sqrt(len(x))), 1),
                     "jaren positief": f"{(by_year > 0).mean() * 100:.0f}%", "CAGR": f"{acc['cagr'] * 100:.1f}%",
                     "max DD": f"{acc['maxdd'] * 100:.1f}%", "Sharpe": f"{acc['sharpe_rf']:.2f}", "MAR": f"{acc['mar']:.2f}",
                     "_x": x, "_by": by_year, "_acc": acc})
    idx = next(iter(curves.values())).index
    bench, m = PT.benchmarks(idx)
    spy = PT.stats(bench["SPY buy & hold"], m)
    tim = PT.stats(m["spy"] * m["on"] + m["rf"] * (1 - m["on"]), m)
    for r in rows:
        x, by, acc = r.pop("_x"), r.pop("_by"), r.pop("_acc")
        ok = (x.mean() >= 0.01 and x.mean() / x.std() * np.sqrt(len(x)) >= 2 and (by > 0).mean() >= 0.6
              and acc["sharpe_rf"] > spy["sharpe_rf"] and acc["mar"] > spy["mar"])
        r["voldoet"] = "–" if r["regel"].startswith("(") else ("JA" if ok else "nee")
    b = pd.DataFrame([{"regel": k, "CAGR": f"{s['cagr'] * 100:.1f}%", "max DD": f"{s['maxdd'] * 100:.1f}%",
                       "Sharpe": f"{s['sharpe_rf']:.2f}", "MAR": f"{s['mar']:.2f}"}
                      for k, s in (("SPY kopen en vasthouden", spy), ("SPY alleen boven SMA200, anders T-bills", tim))])
    txt = (f"# Post-earnings drift — {mode} ({len(frames)} aandelen, publicaties {start.date()} .. {end.date()})\n\n"
           "Kopen op de open na de reactiedag, 60 handelsdagen vasthouden. Rekening max 10 posities van 10%, lege kas in "
           "SPY zolang SPY > SMA200. Criterium vooraf: gem. rendement boven SPY >= 1% met t >= 2, >= 60% van de jaren "
           "positief, én Sharpe en MAR van de rekening boven SPY.\n\n" + pd.DataFrame(rows).to_markdown(index=False)
           + "\n\nBenchmarks:\n\n" + b.to_markdown(index=False) + "\n")
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, f"{mode}.md"), "w") as fh:
        fh.write(txt)
    print(txt)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "dev"
    if mode == "holdout":
        mark = os.path.join(HERE, "holdout_used.json")
        if os.path.exists(mark):
            raise SystemExit("holdout already used")
        with open(mark, "w") as fh:
            json.dump({"used": pd.Timestamp.now().isoformat()}, fh)
    run(mode)


if __name__ == "__main__":
    main()
