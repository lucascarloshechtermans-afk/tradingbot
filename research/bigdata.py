"""Large research dataset: daily OHLCV (split AND dividend adjusted -- an
unadjusted ex-dividend drop would look like a 'dip') from 2007 for the S&P
500 + S&P MidCap 400 + the scanner's own lists, plus benchmarks (SPY, QQQ,
IWM, ^VIX, sector ETFs). Stored as one pickle {ticker: DataFrame} with
lowercase columns and a tz-naive date index.

Also assigns every ticker to the RESEARCH or HOLDOUT half (seeded random,
stratified by sector) -- the split is fixed here, before any hypothesis is
looked at, so no result can influence it.

    python -m research.bigdata --members index_members.json --out big.pkl
"""

from __future__ import annotations

import argparse
import json
import sys

import numpy as np
import pandas as pd

BENCH = ["SPY", "QQQ", "IWM", "^VIX", "XLK", "XLF", "XLV", "XLE", "XLI", "XLY", "XLP", "XLU", "XLB", "XLRE", "XLC"]
START = "2007-01-01"


def download(tickers: list[str], batch: int = 80) -> dict[str, pd.DataFrame]:
    import yfinance as yf

    out: dict[str, pd.DataFrame] = {}
    for i in range(0, len(tickers), batch):
        chunk = tickers[i:i + batch]
        raw = yf.download(chunk, start=START, auto_adjust=True, progress=False, group_by="ticker", threads=True)
        for t in chunk:
            try:
                df = raw[t] if len(chunk) > 1 else raw
            except KeyError:
                continue
            df = df.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]].dropna(subset=["close"])
            if len(df) < 300:
                continue
            df.index = pd.DatetimeIndex(df.index).tz_localize(None) if df.index.tz is not None else pd.DatetimeIndex(df.index)
            out[t] = df[~df.index.duplicated()].sort_index()
        print(f"  {min(i + batch, len(tickers))}/{len(tickers)} downloaded, {len(out)} usable", flush=True)
    return out


def split_halves(sectors: dict[str, str | None], seed: int = 20260926) -> dict[str, str]:
    rng = np.random.default_rng(seed)
    by_sector: dict[str, list[str]] = {}
    for t, s in sectors.items():
        by_sector.setdefault(s or "?", []).append(t)
    half = {}
    for s in sorted(by_sector):
        names = sorted(by_sector[s])
        rng.shuffle(names)
        for k, t in enumerate(names):
            half[t] = "RESEARCH" if k % 2 == 0 else "HOLDOUT"
    return half


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--members", required=True)
    ap.add_argument("--extra", default="", help="comma list of extra tickers (sector unknown)")
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    members = json.load(open(args.members))
    sectors: dict[str, str | None] = {}
    for rows in members.values():
        for t, s in rows:
            sectors.setdefault(t, s)
    for t in filter(None, args.extra.split(",")):
        sectors.setdefault(t, None)
    tickers = sorted(sectors)
    data = download(tickers + BENCH)
    stocks = {t: d for t, d in data.items() if t not in BENCH}
    halves = split_halves({t: sectors[t] for t in stocks})
    pd.to_pickle({"stocks": stocks, "bench": {t: data[t] for t in BENCH if t in data},
                  "sectors": {t: sectors[t] for t in stocks}, "half": halves}, args.out)
    n_r = sum(1 for h in halves.values() if h == "RESEARCH")
    print(f"{len(stocks)} stocks ({n_r} research / {len(stocks) - n_r} holdout), {len(data) - len(stocks)} benchmarks -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
