"""Round 14 data: daily OHLCV (float32) (split+dividend adjusted) since 2010 for every
US-listed common stock in today's NASDAQ Trader files, plus SPY and ^IRX.
    python -m research.round14_data OUT.pkl"""
from __future__ import annotations

import sys
import time

import pandas as pd


def main(out: str) -> int:
    import yfinance as yf

    from data.us_listed import fetch_us_listed

    tickers = sorted(fetch_us_listed())
    frames = {k: {} for k in ("open", "high", "low", "close", "volume")}
    for i in range(0, len(tickers), 100):
        chunk = tickers[i:i + 100]
        for attempt in range(3):
            try:
                raw = yf.download(chunk, start="2010-01-01", auto_adjust=True, progress=False, group_by="ticker", threads=True)
                break
            except Exception as exc:  # noqa: BLE001
                print("retry", i, exc, flush=True)
                time.sleep(5 * (attempt + 1))
        else:
            continue
        for t in chunk:
            try:
                df = raw[t]
            except KeyError:
                continue
            if df["Close"].notna().sum() < 300:
                continue
            for k in frames:
                frames[k][t] = df[k.capitalize()].astype("float32")
        print(f"{i + len(chunk)}/{len(tickers)} downloaded, {len(frames['close'])} usable", flush=True)
    bench = yf.download(["SPY", "^IRX"], start="2010-01-01", auto_adjust=True, progress=False, group_by="ticker")
    data = {k: pd.DataFrame(v) for k, v in frames.items()}
    data["spy"] = bench["SPY"].rename(columns=str.lower)
    data["irx"] = bench["^IRX"]["Close"]
    for k in ("open", "high", "low", "close", "volume"):
        data[k].index = pd.DatetimeIndex(data[k].index).tz_localize(None) if data[k].index.tz is not None else data[k].index
    pd.to_pickle(data, out)
    print("saved", out, data["close"].shape, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
