"""Download historical earnings dates + EPS surprise (Yahoo, via yfinance) for
every stock in big.pkl. Output: {ticker: DataFrame[date_ny, hour, est, act, surprise]}.
Usage: python -m research.earnings_data BIG.pkl OUT.pkl
"""
from __future__ import annotations

import os
import sys
import time

import pandas as pd


def fetch(sym: str) -> pd.DataFrame | None:
    import yfinance as yf

    d = yf.Ticker(sym).get_earnings_dates(limit=100)
    if d is None or d.empty:
        return None
    idx = d.index.tz_convert("America/New_York")
    out = pd.DataFrame({"ts": idx, "est": d["EPS Estimate"].to_numpy(), "act": d["Reported EPS"].to_numpy(),
                        "surprise": d["Surprise(%)"].to_numpy()})
    out["date"] = out["ts"].dt.tz_localize(None).dt.normalize()
    out["hour"] = out["ts"].dt.hour
    return out.drop_duplicates("date").sort_values("date").reset_index(drop=True)


def main(big_path: str, out_path: str) -> int:
    tickers = sorted(pd.read_pickle(big_path)["stocks"])
    res = pd.read_pickle(out_path) if os.path.exists(out_path) else {}
    todo = [t for t in tickers if t not in res]
    print(f"{len(todo)} to fetch", flush=True)
    for i, t in enumerate(todo):
        for attempt in range(3):
            try:
                res[t] = fetch(t.replace(".", "-"))
                break
            except Exception as e:  # noqa: BLE001
                print(t, "retry", attempt, e, flush=True)
                time.sleep(3 * (attempt + 1))
        else:
            res[t] = None
        if i % 50 == 49:
            pd.to_pickle(res, out_path)
            print(f"{i + 1}/{len(todo)}", flush=True)
    pd.to_pickle(res, out_path)
    ok = sum(v is not None for v in res.values())
    print(f"done: {ok}/{len(res)} with data", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
