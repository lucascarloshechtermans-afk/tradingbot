from __future__ import annotations

import numpy as np
import pandas as pd

from indicators.trend import confirmed_swing_highs, confirmed_swing_lows


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


def _divergence(
    price_extreme: pd.Series,
    rsi_series: pd.Series,
    swing_mask: pd.Series,
    order: int,
    direction: str,
) -> bool:
    usable_end = max(len(price_extreme) - order, 0)
    mask = swing_mask.copy()
    mask.iloc[usable_end:] = False
    swing_positions = price_extreme[mask]
    if len(swing_positions) < 2:
        return False

    idx_a, idx_b = swing_positions.index[-2], swing_positions.index[-1]
    price_a, price_b = price_extreme.loc[idx_a], price_extreme.loc[idx_b]
    rsi_a, rsi_b = rsi_series.loc[idx_a], rsi_series.loc[idx_b]
    if pd.isna(rsi_a) or pd.isna(rsi_b):
        return False

    if direction == "bullish":
        # price makes a lower low, RSI makes a higher low -> bullish divergence
        return price_b < price_a and rsi_b > rsi_a
    # price makes a higher high, RSI makes a lower high -> bearish divergence
    return price_b > price_a and rsi_b < rsi_a


def rsi_bullish_divergence(low: pd.Series, rsi_series: pd.Series, order: int = 3) -> bool:
    swing_low_mask = confirmed_swing_lows(low, order)
    return _divergence(low, rsi_series, swing_low_mask, order, "bullish")


def rsi_bearish_divergence(high: pd.Series, rsi_series: pd.Series, order: int = 3) -> bool:
    swing_high_mask = confirmed_swing_highs(high, order)
    return _divergence(high, rsi_series, swing_high_mask, order, "bearish")
