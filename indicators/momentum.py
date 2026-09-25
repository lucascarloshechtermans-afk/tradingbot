from __future__ import annotations

import numpy as np
import pandas as pd

from indicators.trend import confirmed_swing_highs, confirmed_swing_lows, crossover, detect_divergence


def rsi(series: pd.Series, window: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    avg_loss = loss.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    result = 100 - (100 / (1 + rs))
    return result.where(avg_loss != 0, 100.0)


def macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    from indicators.trend import ema

    macd_line = ema(series, fast) - ema(series, slow)
    signal_line = macd_line.ewm(span=signal, adjust=False, min_periods=signal).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def roc(series: pd.Series, window: int) -> pd.Series:
    """Rate of change (%) over `window` bars."""
    return (series / series.shift(window) - 1) * 100


def multi_period_momentum(series: pd.Series, windows: tuple[int, ...] = (5, 10, 20)) -> dict[int, pd.Series]:
    return {w: roc(series, w) for w in windows}


def rsi_bullish_divergence(low: pd.Series, rsi_series: pd.Series, order: int = 3) -> bool:
    swing_low_mask = confirmed_swing_lows(low, order)
    return detect_divergence(low, rsi_series, swing_low_mask, order, "regular_bullish")


def rsi_bearish_divergence(high: pd.Series, rsi_series: pd.Series, order: int = 3) -> bool:
    swing_high_mask = confirmed_swing_highs(high, order)
    return detect_divergence(high, rsi_series, swing_high_mask, order, "regular_bearish")


def rsi_hidden_bullish_divergence(low: pd.Series, rsi_series: pd.Series, order: int = 3) -> bool:
    """Price makes a HIGHER low while RSI makes a LOWER low — a trend-continuation
    signal inside an existing uptrend (the shallower pullback is the tell), not a
    reversal signal like the regular divergence above."""
    swing_low_mask = confirmed_swing_lows(low, order)
    return detect_divergence(low, rsi_series, swing_low_mask, order, "hidden_bullish")


def rsi_hidden_bearish_divergence(high: pd.Series, rsi_series: pd.Series, order: int = 3) -> bool:
    swing_high_mask = confirmed_swing_highs(high, order)
    return detect_divergence(high, rsi_series, swing_high_mask, order, "hidden_bearish")


def macd_cross(macd_line: pd.Series, signal_line: pd.Series) -> str:
    """'bullish_cross' | 'bearish_cross' | 'none' for MACD line vs signal line."""
    return crossover(macd_line, signal_line)


def macd_above_zero(macd_line: pd.Series) -> bool:
    last = macd_line.iloc[-1]
    return bool(last > 0) if pd.notna(last) else False


def macd_histogram_accelerating(histogram: pd.Series, lookback: int = 3) -> bool:
    """True if the histogram has grown in magnitude, in the same direction, over
    each of the last `lookback` bars — momentum that is BUILDING, not merely
    present. A histogram that flipped positive but is already shrinking again
    does not count.
    """
    if len(histogram) <= lookback:
        return False
    recent = histogram.iloc[-(lookback + 1):]
    if recent.isna().any():
        return False
    diffs = recent.diff().dropna()
    if recent.iloc[-1] > 0:
        return bool((diffs > 0).all())
    if recent.iloc[-1] < 0:
        return bool((diffs < 0).all())
    return False
