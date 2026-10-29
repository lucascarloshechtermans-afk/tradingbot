"""Earnings dates WITH EPS estimate and reported EPS for every ticker of the Swing 20/21 daily cache (development +
holdout), for the post-earnings setup (pead_week.py).

    python -m indicator_lab.week.earnings_eps fetch     # Yahoo get_earnings_dates(limit=100), 3 threads, cached

Sources merged by load(), first one wins per ticker: Alpha Vantage cache (earn_*.json: reportedDate, reportTime, EPS),
the Yahoo caches of earnings_drift/confirm.py (earn_yf_holdout) and of this module (earn_yf_eps), and the dates-only
cache of week/earnings.py (earn_yf_week, no EPS). Reaction day rule (fixed): Alpha Vantage
"post-market" -> next session, else the report day; Yahoo timestamps: hour < 12 (New York) -> the report day, else the
next session (Yahoo's evening reports are stamped 15:00-20:00; morning ones 06:00-09:00).
"""
from __future__ import annotations

import glob
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from indicator_lab.twenty import data20

CACHE = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".cache")
YF = os.path.join(CACHE, "earn_yf_eps")


def _one(t: str):
    import yfinance as yf
    p = os.path.join(YF, f"{t}.json")
    if os.path.exists(p):
        return
    for attempt in range(4):
        try:
            d = yf.Ticker(t).get_earnings_dates(limit=100)
            rows = [] if d is None else [{"ts": str(i), "est": None if pd.isna(r["EPS Estimate"]) else float(r["EPS Estimate"]),
                                          "rep": None if pd.isna(r["Reported EPS"]) else float(r["Reported EPS"])}
                                         for i, r in d.iterrows()]
            with open(p, "w") as fh:
                json.dump(rows, fh)
            return
        except Exception:  # noqa: BLE001  Yahoo throttles and fails transiently
            time.sleep(5 * 2 ** attempt)


def fetch():
    os.makedirs(YF, exist_ok=True)
    have = {os.path.basename(p)[5:-5] for p in glob.glob(os.path.join(CACHE, "earn_*.json"))}
    have |= {os.path.basename(p)[:-5] for p in glob.glob(os.path.join(CACHE, "earn_yf_holdout", "*.json"))}
    tickers = sorted((set(data20.DEV) | data20.H_TICKERS) - have)
    todo = [t for t in tickers if os.path.exists(data20.path(t)) and not os.path.exists(os.path.join(YF, f"{t}.json"))]
    print(f"{len(todo)} tickers to fetch", flush=True)
    with ThreadPoolExecutor(3) as ex:
        for k, _ in enumerate(ex.map(_one, todo)):
            if k % 200 == 0:
                print(f"{k}/{len(todo)}", flush=True)


def load() -> dict:
    """{ticker: list of (report timestamp, reaction rule 'same'|'next', est, rep)}."""
    out: dict = {}
    for p in glob.glob(os.path.join(CACHE, "earn_*.json")):
        t = os.path.basename(p)[5:-5]
        with open(p) as fh:
            for e in json.load(fh):
                try:
                    est, rep = float(e["estimatedEPS"]), float(e["reportedEPS"])
                except (TypeError, ValueError, KeyError):
                    est = rep = None
                out.setdefault(t, []).append((pd.Timestamp(e["reportedDate"]),
                                              "next" if e.get("reportTime") == "post-market" else "same", est, rep))
    for d in (os.path.join(CACHE, "earn_yf_holdout"), YF, os.path.join(CACHE, "earn_yf_week")):  # earn_yf_week: dates only
        for p in glob.glob(os.path.join(d, "*.json")):
            t = os.path.basename(p)[:-5]
            if t in out:
                continue
            with open(p) as fh:
                for e in json.load(fh):
                    ts = pd.Timestamp(e["ts"])
                    ts = ts.tz_localize(None) if ts.tzinfo else ts
                    out.setdefault(t, []).append((ts.normalize(), "same" if ts.hour < 12 else "next",
                                                  e.get("est"), e.get("rep")))
    return out


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "fetch":
        fetch()
