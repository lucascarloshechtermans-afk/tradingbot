"""Independent confirmation of the post-earnings drift rules E1 and E2 (pead.py) on stocks never used by this project:
the NYSE / NYSE American part of the sealed Swing 20/21 random ticker holdout (468 stocks with data; random sample of
listed common stocks, far less popularity bias than the 131 names of pead.py).

    python -m indicator_lab.earnings_drift.confirm fetch   # cache Yahoo earnings history (no results computed)
    python -m indicator_lab.earnings_drift.confirm         # ONE run (marker file blocks reruns)

Decided before any result on these stocks:
  * Earnings: Yahoo get_earnings_dates(limit=100) (EPS estimate, reported EPS, timestamp; ~2002 .. 2026). Reaction day:
    the report day if the timestamp is before 16:00, else the next session (either way the entry is after the news).
  * Prices: the 20/21 daily cache (from 2012). Events 2013-01-01 .. 2026-07-15.
  * Liquidity on the reaction day: close >= $5, 50-day average dollar volume >= $5M, traded on each of the last 50 days.
  * Rules, holding, costs and account exactly as pead.py (E1 surprise >= +10% with |estimate| >= $0.05; E2 reaction-day
    return minus SPY >= +5% and positive surprise; 60 trading days; 10 positions; idle cash in SPY while SPY > SMA200).
  * PASS per rule = mean 60-day excess over SPY >= +1.0% with t >= 2, AND that excess at least 0.5% above the excess of
    ALL liquid reports of the same stocks (the drift itself, net of survivorship), AND account Sharpe and MAR above SPY.
"""
from __future__ import annotations

import json
import os
import sys
import time

import numpy as np
import pandas as pd

from indicator_lab.earnings_drift import pead as P
from indicator_lab.h4.nasdaq_list import LIST
from indicator_lab.swing5 import port as PT
from indicator_lab.twenty import data20

HERE = os.path.dirname(__file__)
EARN = os.path.join(P.CACHE, "earn_yf_holdout")
MARK = os.path.join(HERE, "confirm_used.json")
START, END = pd.Timestamp("2013-01-01"), pd.Timestamp("2026-07-15")


def universe() -> list[str]:
    nas = set(pd.read_csv(LIST, sep="|").Symbol.astype(str))
    return sorted(t for t in data20.H_TICKERS if t not in nas and os.path.exists(data20.path(t)))


def fetch():
    import yfinance as yf
    os.makedirs(EARN, exist_ok=True)
    for k, t in enumerate(universe()):
        p = os.path.join(EARN, f"{t}.json")
        if os.path.exists(p):
            continue
        for attempt in range(4):
            try:
                d = yf.Ticker(t).get_earnings_dates(limit=100)
                rows = [] if d is None else [{"ts": str(i), "est": None if pd.isna(r["EPS Estimate"]) else float(r["EPS Estimate"]),
                                              "rep": None if pd.isna(r["Reported EPS"]) else float(r["Reported EPS"])}
                                             for i, r in d.iterrows()]
                with open(p, "w") as fh:
                    json.dump(rows, fh)
                break
            except Exception as e:  # noqa: BLE001  Yahoo throttles (429) and fails transiently
                time.sleep(5 * 2 ** attempt)
                err = e
        else:
            print(t, "failed", err, flush=True)
        if k % 50 == 0:
            print(f"{k} fetched", flush=True)


def clean(d: pd.DataFrame) -> pd.Series:
    traded = (d["volume"] > 0).rolling(50).min() == 1
    liquid = (d["close"] * d["volume"]).rolling(50).mean() >= 5e6
    return traded & liquid & (d["close"] >= 5)


def events(t: str, d: pd.DataFrame, spy: pd.Series) -> pd.DataFrame:
    p = os.path.join(EARN, f"{t}.json")
    if not os.path.exists(p):
        return pd.DataFrame()
    with open(p) as fh:
        q = json.load(fh)
    ok = clean(d).to_numpy()
    idx, c = d.index, d["close"]
    rows = []
    for e in q:
        if e["est"] is None or e["rep"] is None:
            continue
        ts = pd.Timestamp(e["ts"]).tz_localize(None) if pd.Timestamp(e["ts"]).tzinfo else pd.Timestamp(e["ts"])
        i = idx.searchsorted(ts.normalize())
        if i < len(idx) and idx[i] == ts.normalize() and ts.hour >= 16:
            i += 1
        if i < 1 or i + 1 + P.HOLD >= len(idx) or not ok[i]:
            continue
        day = idx[i]
        if not START <= day <= END:
            continue
        s0, s1 = spy.asof(idx[i - 1]), spy.asof(day)
        rows.append({"ticker": t, "day": day, "i": i,
                     "surprise": (e["rep"] - e["est"]) / abs(e["est"]) if abs(e["est"]) >= 0.05 else np.nan,
                     "raw_surprise": e["rep"] - e["est"], "ear": c.iloc[i] / c.iloc[i - 1] - 1 - (s1 / s0 - 1)})
    return pd.DataFrame(rows)


def run():
    data20.final_mode()
    spy_df = P.prices("SPY")
    frames = {}
    for t in universe():
        d = data20.load(t)
        if d is not None and len(d) > 300:
            frames[t] = d[(d[["open", "high", "low", "close"]] > 0).all(axis=1)]
    ev = pd.concat([events(t, d, spy_df["close"]) for t, d in frames.items()], ignore_index=True).sort_values("day")
    PT.market = P.market_long
    out, base_excess = [], None
    masks = P.rule_masks(ev)
    for name in list(masks)[::-1]:          # baseline first
        sel = ev[masks[name].fillna(False)]
        res, busy, trs = {}, {}, []
        for _, e in sel.iterrows():
            t = e["ticker"]
            if busy.get(t) is not None and e["day"] < busy[t]:
                continue
            r, tr = P.trade(frames[t], int(e["i"]), spy_df["open"])
            busy[t] = tr["exit_date"]
            tr["ticker"] = t
            trs.append(tr)
            prev = res.get(t, (pd.Series(dtype=float), []))
            res[t] = (pd.concat([prev[0], r]), prev[1] + [tr])
        tt = pd.DataFrame(trs)
        x = tt["excess"].to_numpy()
        res = {t: (s[~s.index.duplicated(keep="last")], z) for t, (s, z) in res.items()}
        acc = PT.system(res, k=10, seeds=10, park=True)
        if base_excess is None:
            base_excess = x.mean()
        out.append({"regel": name, "trades": len(x), "aandelen": tt["ticker"].nunique(),
                    "winrate": f"{(tt['ret'] > 0).mean() * 100:.0f}%", "gem. 60d": f"{tt['ret'].mean() * 100:.2f}%",
                    "boven SPY": f"{x.mean() * 100:.2f}%", "t": round(float(x.mean() / x.std() * np.sqrt(len(x))), 1),
                    "boven alle publicaties": f"{(x.mean() - base_excess) * 100:+.2f}%", "CAGR": f"{acc['cagr'] * 100:.1f}%",
                    "max DD": f"{acc['maxdd'] * 100:.1f}%", "Sharpe": f"{acc['sharpe_rf']:.2f}", "MAR": f"{acc['mar']:.2f}",
                    "_x": x, "_acc": acc})
        print(name, len(x), flush=True)
    idx = out[0]["_acc"]["port0"].index
    bench, m = PT.benchmarks(idx)
    spy = PT.stats(bench["SPY buy & hold"], m)
    tim = PT.stats(m["spy"] * m["on"] + m["rf"] * (1 - m["on"]), m)
    for r in out:
        x, acc = r.pop("_x"), r.pop("_acc")
        judged = r["regel"].startswith(("E1", "E2"))
        ok = (x.mean() >= 0.01 and x.mean() / x.std() * np.sqrt(len(x)) >= 2 and x.mean() - base_excess >= 0.005
              and acc["sharpe_rf"] > spy["sharpe_rf"] and acc["mar"] > spy["mar"])
        r["oordeel"] = ("GESLAAGD" if ok else "niet geslaagd") if judged else "–"
    b = pd.DataFrame([{"regel": k, "CAGR": f"{s['cagr'] * 100:.1f}%", "max DD": f"{s['maxdd'] * 100:.1f}%",
                       "Sharpe": f"{s['sharpe_rf']:.2f}", "MAR": f"{s['mar']:.2f}"}
                      for k, s in (("SPY kopen en vasthouden", spy), ("SPY alleen boven SMA200, anders T-bills", tim))])
    txt = (f"# Post-earnings drift — onafhankelijke bevestiging ({len(frames)} nooit gebruikte NYSE/AMEX-aandelen, "
           f"publicaties {START.date()} .. {END.date()})\n\nVooraf vastgelegd (zie `confirm.py`). Alleen E1 en E2 worden "
           "beoordeeld.\n\n" + pd.DataFrame(out[::-1]).to_markdown(index=False) + "\n\nBenchmarks:\n\n" + b.to_markdown(index=False) + "\n")
    with open(os.path.join(P.OUT, "confirm.md"), "w") as fh:
        fh.write(txt)
    print(txt)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "fetch":
        fetch()
        return
    if os.path.exists(MARK):
        raise SystemExit("confirmation already run")
    with open(MARK, "w") as fh:
        json.dump({"used": pd.Timestamp.now().isoformat()}, fh)
    run()


if __name__ == "__main__":
    main()
