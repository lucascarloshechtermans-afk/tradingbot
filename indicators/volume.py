from __future__ import annotations

import numpy as np
import pandas as pd


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
