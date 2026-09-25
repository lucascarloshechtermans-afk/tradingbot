from __future__ import annotations

import numpy as np
import pandas as pd


def true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    prev_close = close.shift(1)
    return pd.concat(
        [high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)


def atr(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.Series:
    tr = true_range(high, low, close)
    return tr.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()


def atr_percent(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.Series:
    return atr(high, low, close, window) / close * 100


def historical_volatility(close: pd.Series, window: int = 20, trading_days: int = 252) -> pd.Series:
    """Annualized historical volatility (%) from log returns."""
    log_returns = np.log(close / close.shift(1))
    return log_returns.rolling(window=window, min_periods=window).std() * np.sqrt(trading_days) * 100


def bollinger_bands(close: pd.Series, window: int = 20, num_std: float = 2.0):
    middle = close.rolling(window=window, min_periods=window).mean()
    std = close.rolling(window=window, min_periods=window).std()
    upper = middle + num_std * std
    lower = middle - num_std * std
    return upper, middle, lower


def bollinger_band_width(close: pd.Series, window: int = 20, num_std: float = 2.0) -> pd.Series:
    upper, middle, lower = bollinger_bands(close, window, num_std)
    return (upper - lower) / middle


def is_squeeze(
    close: pd.Series, window: int = 20, num_std: float = 2.0, lookback: int = 120, percentile: float = 0.10
) -> pd.Series:
    """True where current Bollinger Band width is at/near its lowest over the
    trailing `lookback` bars (bottom `percentile`) — a volatility-contraction
    ("squeeze") condition that often precedes an expansion move.
    """
    width = bollinger_band_width(close, window, num_std)
    threshold = width.rolling(window=lookback, min_periods=window).quantile(percentile)
    return width <= threshold


def is_expanding(close: pd.Series, window: int = 20, num_std: float = 2.0, lookback: int = 3) -> pd.Series:
    """True where Bollinger Band width is now wider than it was `lookback` bars
    ago — a squeeze (is_squeeze) followed by is_expanding is the "coiled, now
    releasing" pattern; a bare squeeze alone says nothing about direction or
    timing, which is why VolatilityContractionStrategy requires both.
    """
    width = bollinger_band_width(close, window, num_std)
    return width > width.shift(lookback)


def distance_in_atr(price: float, level: float, atr_value: float) -> float:
    """Signed distance between `price` and `level`, expressed in ATR units — a
    volatility-normalized way to ask "how far is X from Y, relative to how much
    this stock typically moves in a day." Used both for extension-from-moving-
    average checks and for distance-to-resistance checks. Positive means `price`
    is above `level`.
    """
    if atr_value is None or pd.isna(atr_value) or atr_value <= 0:
        return float("nan")
    return (price - level) / atr_value
