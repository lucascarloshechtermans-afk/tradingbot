from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd


class DataUnavailable(Exception):
    """Raised when a data point genuinely cannot be obtained.

    Callers must treat this as "unknown", never fabricate a value to fill the gap.
    """


@dataclass
class TickerInfo:
    ticker: str
    sector: str | None = None
    industry: str | None = None
    market_cap: float | None = None
    shares_outstanding: float | None = None
    float_shares: float | None = None
    short_percent_of_float: float | None = None  # a point-in-time snapshot only — no free historical time series exists
    fundamentals: dict = field(default_factory=dict)
    missing_fields: list[str] = field(default_factory=list)

    @property
    def free_float_pct(self) -> float | None:
        """Free-float shares as a % of shares outstanding — context on how much of
        the company can actually trade hands, not itself a bullish/bearish signal.
        None when either input is unavailable (never guessed)."""
        if self.float_shares is None or self.shares_outstanding is None or self.shares_outstanding <= 0:
            return None
        return self.float_shares / self.shares_outstanding * 100


class DataProvider(ABC):
    """Abstraction over a market-data source.

    Swapping providers (e.g. to a paid API) means implementing this interface and
    pointing the scanner at the new class — nothing above this layer should import
    a specific provider directly.
    """

    @abstractmethod
    def get_history(self, ticker: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
        """Return OHLCV history indexed by UTC timestamp, columns:
        open, high, low, close, adj_close, volume.
        """

    @abstractmethod
    def get_info(self, ticker: str) -> TickerInfo:
        """Return sector/industry/market-cap/fundamentals, best-effort.

        Fields that are genuinely unavailable from this provider must be listed in
        `missing_fields`, never silently defaulted or fabricated.
        """

    @abstractmethod
    def get_earnings_dates(self, ticker: str) -> list[datetime]:
        """Return known past+upcoming earnings dates, best-effort (empty list if unknown)."""

    @abstractmethod
    def get_dividends(self, ticker: str) -> pd.Series:
        ...

    @abstractmethod
    def get_splits(self, ticker: str) -> pd.Series:
        ...

    def get_universe_closes(self, tickers: list[str], latest_session=None) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Adjusted daily closes and volumes (date x ticker, ~15 months) for a
        large universe in bulk -- used by the MOMENTUM TOP 20 book. Optional:
        providers that cannot do this cheaply raise NotImplementedError and
        the momentum book is skipped."""
        raise NotImplementedError
