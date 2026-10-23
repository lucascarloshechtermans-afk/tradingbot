"""Price data for the Swing 20/21 project: a broad US common-stock universe in its own compressed cache
(`indicator_lab/.cache20`, gitignored). Development mode cuts every series before the time holdout and refuses
holdout tickers (holdout_20in21.json)."""
from __future__ import annotations

import json
import os

import pandas as pd

HERE = os.path.dirname(__file__)
CACHE = os.path.join(os.path.dirname(HERE), ".cache20")
with open(os.path.join(HERE, "holdout_20in21.json")) as _fh:
    HOLDOUT = json.load(_fh)
with open(os.path.join(HERE, "dev_universe.json")) as _fh:
    DEV = json.load(_fh)
H_TICKERS = set(HOLDOUT["ticker_holdout"]["tickers"])
H_START = pd.Timestamp(HOLDOUT["time_holdout"]["start"])
_MODE = {"mode": "dev"}


def path(t: str) -> str:
    return os.path.join(CACHE, f"{t}.csv.gz")


def load(t: str) -> pd.DataFrame | None:
    """Daily OHLCV (split/dividend adjusted). Development mode: refuses holdout tickers, cuts at H_START."""
    if _MODE["mode"] == "dev" and t in H_TICKERS:
        raise PermissionError(f"{t} is a 20/21 holdout ticker")
    p = path(t)
    if not os.path.exists(p):
        return None
    df = pd.read_csv(p, index_col=0, parse_dates=True)
    if _MODE["mode"] == "dev":
        df = df[df.index < H_START]
    return df


def final_mode() -> None:
    _MODE["mode"] = "final"


def download(tickers: list[str], start: str = "2012-01-01", batch: int = 80) -> dict:
    """Batch download (yfinance) into the cache; returns {ticker: rows} for what was written."""
    import yfinance as yf
    os.makedirs(CACHE, exist_ok=True)
    out = {}
    for i in range(0, len(tickers), batch):
        chunk = tickers[i:i + batch]
        try:
            raw = yf.download(chunk, start=start, auto_adjust=True, progress=False, group_by="ticker", threads=True)
        except Exception as e:  # noqa: BLE001  (network hiccup: skip the chunk, it is retried by the caller)
            print("chunk failed", i, str(e)[:80], flush=True)
            continue
        for t in chunk:
            try:
                df = raw[t].rename(columns=str.lower)[["open", "high", "low", "close", "volume"]].dropna()
            except KeyError:
                continue
            if len(df) < 60:
                continue
            df.index = pd.to_datetime(df.index).tz_localize(None)
            df.to_csv(path(t), compression="gzip")
            out[t] = len(df)
        print(f"{min(i + batch, len(tickers))}/{len(tickers)} done, {len(out)} written", flush=True)
    return out
