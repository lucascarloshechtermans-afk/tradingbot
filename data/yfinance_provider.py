from __future__ import annotations

import logging
import time
from datetime import datetime

import pandas as pd

from data.cache import DiskCache
from data.provider import DataProvider, DataUnavailable, TickerInfo

logger = logging.getLogger(__name__)

EXPECTED_FUNDAMENTAL_FIELDS = {
    "trailing_pe": "trailingPE",
    "forward_pe": "forwardPE",
    "revenue_growth": "revenueGrowth",
    "earnings_growth": "earningsGrowth",
    "profit_margins": "profitMargins",
    "return_on_equity": "returnOnEquity",
    "debt_to_equity": "debtToEquity",
    "held_percent_institutions": "heldPercentInstitutions",
}


class YFinanceProvider(DataProvider):
    """Free, keyless data source via the `yfinance` package.

    Known limitations of this specific provider (not a design choice of ours):
    - Intraday history (1h and below) is only available for roughly the last 60 days.
    - Fundamentals/`held_percent_institutions` are frequently missing or stale.
    - No true market-breadth (advance/decline) data.
    These are surfaced via `TickerInfo.missing_fields` rather than being papered over.
    """

    def __init__(self, cache: DiskCache | None = None, max_retries: int = 3, retry_backoff_seconds: float = 2.0):
        self.cache = cache
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds

    def _retry(self, fn, *, description: str):
        last_exc = None
        for attempt in range(1, self.max_retries + 1):
            try:
                return fn()
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "%s failed (attempt %d/%d): %s", description, attempt, self.max_retries, exc
                )
                if attempt < self.max_retries:
                    time.sleep(self.retry_backoff_seconds * attempt)
        raise DataUnavailable(f"{description} failed after {self.max_retries} attempts: {last_exc}")

    def get_history(self, ticker: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
        cache_key = f"hist_{ticker}_{period}_{interval}"
        if self.cache is not None:
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached

        import yfinance as yf

        def _fetch():
            df = yf.Ticker(ticker).history(period=period, interval=interval, auto_adjust=False)
            if df is None or df.empty:
                raise DataUnavailable(f"No history returned for {ticker}")
            return df

        raw = self._retry(_fetch, description=f"get_history({ticker}, {period}, {interval})")

        df = raw.rename(columns=str.lower).rename(columns={"adj close": "adj_close"})
        for col in ["open", "high", "low", "close", "volume"]:
            if col not in df.columns:
                raise DataUnavailable(f"{ticker} history missing expected column '{col}'")
        if "adj_close" not in df.columns:
            df["adj_close"] = df["close"]

        if df.index.tz is None:
            df.index = df.index.tz_localize("UTC")
        else:
            df.index = df.index.tz_convert("UTC")
        df.index.name = "timestamp"

        df = df[["open", "high", "low", "close", "adj_close", "volume"]].sort_index()
        df = df[~df.index.duplicated(keep="last")]
        df = df.dropna(subset=["open", "high", "low", "close"])

        if self.cache is not None:
            self.cache.set(cache_key, df)
        return df

    def get_info(self, ticker: str) -> TickerInfo:
        import yfinance as yf

        missing: list[str] = []
        try:
            raw_info = self._retry(lambda: yf.Ticker(ticker).get_info(), description=f"get_info({ticker})")
        except DataUnavailable:
            return TickerInfo(
                ticker=ticker,
                missing_fields=["sector", "industry", "market_cap", *EXPECTED_FUNDAMENTAL_FIELDS],
            )

        sector = raw_info.get("sector")
        industry = raw_info.get("industry")
        market_cap = raw_info.get("marketCap")
        shares_outstanding = raw_info.get("sharesOutstanding")
        float_shares = raw_info.get("floatShares")
        short_percent_of_float = raw_info.get("shortPercentOfFloat")
        if sector is None:
            missing.append("sector")
        if industry is None:
            missing.append("industry")
        if market_cap is None:
            missing.append("market_cap")
        if shares_outstanding is None:
            missing.append("shares_outstanding")
        if float_shares is None:
            missing.append("float_shares")
        if short_percent_of_float is None:
            missing.append("short_percent_of_float")

        fundamentals = {}
        for local_name, yf_key in EXPECTED_FUNDAMENTAL_FIELDS.items():
            value = raw_info.get(yf_key)
            if value is None:
                missing.append(local_name)
            else:
                fundamentals[local_name] = value

        return TickerInfo(
            ticker=ticker,
            sector=sector,
            industry=industry,
            market_cap=market_cap,
            shares_outstanding=shares_outstanding,
            float_shares=float_shares,
            short_percent_of_float=float(short_percent_of_float * 100) if short_percent_of_float is not None else None,
            fundamentals=fundamentals,
            missing_fields=missing,
        )

    def get_earnings_dates(self, ticker: str) -> list[datetime]:
        import yfinance as yf

        try:
            df = self._retry(
                lambda: yf.Ticker(ticker).get_earnings_dates(limit=12),
                description=f"get_earnings_dates({ticker})",
            )
        except DataUnavailable:
            logger.info("no earnings dates available for %s", ticker)
            return []
        if df is None or df.empty:
            return []
        return [ts.to_pydatetime() for ts in df.index]

    def get_dividends(self, ticker: str) -> pd.Series:
        import yfinance as yf

        try:
            return self._retry(lambda: yf.Ticker(ticker).dividends, description=f"get_dividends({ticker})")
        except DataUnavailable:
            return pd.Series(dtype=float)

    def get_splits(self, ticker: str) -> pd.Series:
        import yfinance as yf

        try:
            return self._retry(lambda: yf.Ticker(ticker).splits, description=f"get_splits({ticker})")
        except DataUnavailable:
            return pd.Series(dtype=float)
