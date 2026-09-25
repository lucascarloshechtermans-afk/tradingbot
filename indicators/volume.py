from __future__ import annotations

import numpy as np
import pandas as pd

from indicators.trend import confirmed_swing_highs, confirmed_swing_lows, detect_divergence


def volume_sma(volume: pd.Series, window: int = 20) -> pd.Series:
    return volume.rolling(window=window, min_periods=window).mean()


def relative_volume(volume: pd.Series, window: int = 20) -> pd.Series:
    """Today's volume as a multiple of the PRIOR `window` days' average volume
    (a.k.a. RVOL). Today's own volume is deliberately excluded from the baseline —
    including it would dilute a genuine spike and understate how unusual it is.
    """
    avg = volume.shift(1).rolling(window=window, min_periods=window).mean()
    return volume / avg.replace(0, np.nan)


def on_balance_volume(close: pd.Series, volume: pd.Series) -> pd.Series:
    direction = np.sign(close.diff()).fillna(0)
    return (direction * volume).cumsum()


def accumulation_distribution(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series) -> pd.Series:
    range_ = (high - low).replace(0, np.nan)
    money_flow_multiplier = ((close - low) - (high - close)) / range_
    money_flow_multiplier = money_flow_multiplier.fillna(0)
    money_flow_volume = money_flow_multiplier * volume
    return money_flow_volume.cumsum()


def price_volume_confirmed(price_change_pct: pd.Series, rvol: pd.Series, rvol_threshold: float = 1.5) -> pd.Series:
    """True where a positive price move is accompanied by above-average volume —
    a basic price/volume confirmation check used as context by several strategies.
    """
    return (price_change_pct > 0) & (rvol >= rvol_threshold)


def is_volume_drying_up(volume: pd.Series, window: int = 10, lookback: int = 50, threshold_pct: float = 0.70) -> bool:
    """True where recent average volume is meaningfully below its own longer-term
    average — the "volume dry-up" during a healthy, orderly consolidation that
    Minervini-style VCP setups look for before a breakout, as distinct from a bare
    Bollinger squeeze (which says nothing about WHY it's tightening).
    """
    if len(volume) < lookback:
        return False
    recent_avg = volume.tail(window).mean()
    longer_avg = volume.tail(lookback).mean()
    if pd.isna(recent_avg) or pd.isna(longer_avg) or longer_avg <= 0:
        return False
    return bool(recent_avg < longer_avg * threshold_pct)


def obv_bullish_divergence(low: pd.Series, obv: pd.Series, order: int = 3) -> bool:
    swing_low_mask = confirmed_swing_lows(low, order)
    return detect_divergence(low, obv, swing_low_mask, order, "regular_bullish")


def obv_bearish_divergence(high: pd.Series, obv: pd.Series, order: int = 3) -> bool:
    swing_high_mask = confirmed_swing_highs(high, order)
    return detect_divergence(high, obv, swing_high_mask, order, "regular_bearish")
