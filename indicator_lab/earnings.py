"""Historical quarterly earnings dates (Alpha Vantage EARNINGS), cached to .cache/.

`reaction_day` maps each report to the first session whose prices reflect it:
the report date itself for pre-market releases, the next session for post-market ones.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request

import pandas as pd

from indicator_lab.data import CACHE_DIR

ETFS = {"SPY", "QQQ", "IWM", "DIA", "XLE", "XLU", "TLT", "GLD", "XLF", "XLK", "XLV", "XLI", "XLY", "XLP",
        "EFA", "EEM"}


def raw(ticker: str) -> list[dict]:
    path = os.path.join(CACHE_DIR, f"earn_{ticker}.json")
    if os.path.exists(path):
        return json.load(open(path))
    url = f"https://www.alphavantage.co/query?function=EARNINGS&symbol={ticker}&apikey=ALPHA_VANTAGE_API_KEY"
    for attempt in range(4):
        with urllib.request.urlopen(url, timeout=30) as r:
            d = json.load(r)
        if "quarterlyEarnings" in d:
            q = d["quarterlyEarnings"]
            json.dump(q, open(path, "w"))
            return q
        time.sleep(2 ** (attempt + 1))
    raise RuntimeError(f"no earnings for {ticker}: {str(d)[:200]}")


def reaction_days(ticker: str, index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    if ticker in ETFS:
        return pd.DatetimeIndex([])
    out = []
    for q in raw(ticker):
        d = pd.Timestamp(q["reportedDate"])
        i = index.searchsorted(d)
        if q.get("reportTime") == "post-market":
            i += 1
        if i < len(index):
            out.append(index[i])
    return pd.DatetimeIndex(sorted(set(out)))
