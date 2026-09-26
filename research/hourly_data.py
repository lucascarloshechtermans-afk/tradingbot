"""Download ~730 days of 1h bars (Yahoo's limit) and store them as US-session
4H bars (analysis.chart_read.resample_to_4h) for every stock in the given
datasets.   python -m research.hourly_data OUT.pkl DATA1.pkl [DATA2.pkl ...]"""
from __future__ import annotations

import os
import sys

import pandas as pd

from analysis.chart_read import resample_to_4h


def main(out: str, *datasets: str) -> int:
    import yfinance as yf

    tickers = sorted({t for d in datasets for t in pd.read_pickle(d)["stocks"]})
    res = pd.read_pickle(out) if os.path.exists(out) else {}
    todo = [t for t in tickers if t not in res]
    print(f"{len(todo)} to fetch", flush=True)
    for i in range(0, len(todo), 40):
        chunk = todo[i:i + 40]
        try:
            raw = yf.download(chunk, period="730d", interval="1h", auto_adjust=True, progress=False,
                              group_by="ticker", threads=True)
        except Exception as e:  # noqa: BLE001
            print("batch failed", e, flush=True)
            continue
        for t in chunk:
            try:
                df = raw[t] if len(chunk) > 1 else raw
                df = df.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]].dropna(subset=["close"])
                res[t] = resample_to_4h(df) if len(df) else None
            except Exception:  # noqa: BLE001
                res[t] = None
        pd.to_pickle(res, out)
        print(f"{min(i + 40, len(todo))}/{len(todo)}", flush=True)
    print("done", sum(v is not None and len(v) > 0 for v in res.values()), "with data", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
