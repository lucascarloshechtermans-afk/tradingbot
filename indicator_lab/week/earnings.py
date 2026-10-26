"""Earnings report dates for the one-week study's "no earnings in the holding period" filter.

    python -m indicator_lab.week.earnings fetch     # Yahoo get_earnings_dates(limit=60) for every universe ticker

Sources, in order: the Yahoo cache of this module, the Yahoo cache of earnings_drift/confirm.py and the Alpha Vantage
cache of indicator_lab/.cache (earn_*.json). A ticker with no dates in any source is "unknown" (run.py then does not
take its trades under the filter, conservatively).
"""
from __future__ import annotations

import glob
import json
import os
import pickle
import sys
import time

import numpy as np
import pandas as pd

from indicator_lab.week import build as B

CACHE = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".cache")
YF = os.path.join(CACHE, "earn_yf_week")


def _from_yf(p: str) -> list:
    with open(p) as fh:
        return [pd.Timestamp(e["ts"]).tz_localize(None).normalize() if pd.Timestamp(e["ts"]).tzinfo
                else pd.Timestamp(e["ts"]).normalize() for e in json.load(fh)]


def load_all() -> dict:
    out: dict = {}
    for p in glob.glob(os.path.join(CACHE, "earn_*.json")):
        t = os.path.basename(p)[5:-5]
        with open(p) as fh:
            out.setdefault(t, []).extend(pd.Timestamp(e["reportedDate"]) for e in json.load(fh))
    for d in (os.path.join(CACHE, "earn_yf_holdout"), YF):
        for p in glob.glob(os.path.join(d, "*.json")):
            out.setdefault(os.path.basename(p)[:-5], []).extend(_from_yf(p))
    return {t: np.array(sorted(set(v)), dtype="datetime64[ns]") for t, v in out.items() if v}


def fetch():
    import yfinance as yf
    with open(B.OUT, "rb") as fh:
        tickers = sorted({z["ticker"] for z in pickle.load(fh)["cands"]})
    have = set(load_all())
    os.makedirs(YF, exist_ok=True)
    todo = [t for t in tickers if t not in have and not os.path.exists(os.path.join(YF, f"{t}.json"))]
    print(f"{len(tickers)} tickers, {len(todo)} to fetch", flush=True)
    for k, t in enumerate(todo):
        for attempt in range(4):
            try:
                d = yf.Ticker(t).get_earnings_dates(limit=60)
                rows = [] if d is None else [{"ts": str(i)} for i in d.index]
                with open(os.path.join(YF, f"{t}.json"), "w") as fh:
                    json.dump(rows, fh)
                break
            except Exception:  # noqa: BLE001  Yahoo throttles and fails transiently
                time.sleep(5 * 2 ** attempt)
        if k % 100 == 0:
            print(f"{k}/{len(todo)}", flush=True)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "fetch":
        fetch()
