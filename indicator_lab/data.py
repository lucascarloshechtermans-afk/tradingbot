from __future__ import annotations

import os
import time

import pandas as pd

CACHE_DIR = os.path.join(os.path.dirname(__file__), ".cache")

# Named in the brief: SPY, QQQ, AAPL, MSFT, NVDA. The rest widen the sample across
# sectors, betas and an index/ETF mix so a rule can't win on one mega-trend alone.
CORE = ["SPY", "QQQ", "AAPL", "MSFT", "NVDA"]
DEV_EXTRA = ["IWM", "DIA", "AMZN", "GOOGL", "META", "JPM", "XOM", "JNJ", "HD", "KO"]
# Never looked at while designing/tuning an idea; only used for the final check.
HOLDOUT = ["CAT", "UNH", "V", "AMD", "COST", "PG", "NFLX", "BA", "DIS", "INTC", "WMT", "GS",
           "XLE", "XLU", "TLT", "GLD"]
DEV = CORE + DEV_EXTRA
ALL = DEV + HOLDOUT


def load(ticker: str, start: str = "2012-01-01", refresh: bool = False) -> pd.DataFrame:
    """Daily split/dividend-adjusted OHLCV, cached to disk (gitignored)."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, f"{ticker}.csv")
    if os.path.exists(path) and not refresh:
        return pd.read_csv(path, index_col=0, parse_dates=True)

    import yfinance as yf

    last_err: Exception | None = None
    for attempt in range(4):
        try:
            raw = yf.download(ticker, start=start, progress=False, auto_adjust=True)
            if raw is None or raw.empty:
                raise RuntimeError(f"no data for {ticker}")
            if isinstance(raw.columns, pd.MultiIndex):
                raw.columns = raw.columns.get_level_values(0)
            df = raw.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]].dropna()
            df.index = pd.to_datetime(df.index).tz_localize(None)
            df.to_csv(path)
            return df
        except Exception as e:  # transient Yahoo errors (429/crumb) are common
            last_err = e
            time.sleep(2 ** (attempt + 1))
    raise RuntimeError(f"failed to load {ticker}: {last_err}")


def load_many(tickers: list[str]) -> dict[str, pd.DataFrame]:
    return {t: load(t) for t in tickers}
