from __future__ import annotations

import numpy as np
import pandas as pd

from indicators.trend import confirmed_swing_lows

"""Anchored VWAP, approximated from DAILY bars.

True VWAP is computed from intraday tick/minute data and resets every session —
that data isn't available from this free data source (see README's documented
limitations). What's implemented here is the "anchored VWAP" variant swing
traders actually use across multi-day holds: a volume-weighted average price
computed cumulatively from a chosen anchor bar (typically a significant swing
low/high) using each daily bar's typical price (H+L+C)/3, which is a standard
and honest substitute when only daily bars are available.
"""


def anchored_vwap(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series, anchor_index: int) -> pd.Series:
    typical_price = (high + low + close) / 3
    tp_vol = typical_price * volume

    result = pd.Series(np.nan, index=close.index)
    if anchor_index >= len(close):
        return result

    cum_tp_vol = tp_vol.iloc[anchor_index:].cumsum()
    cum_vol = volume.iloc[anchor_index:].cumsum()
    result.iloc[anchor_index:] = (cum_tp_vol / cum_vol.replace(0, np.nan)).values
    return result


def default_vwap_anchor_index(low: pd.Series, order: int = 3, lookback: int = 60) -> int:
    """Positional index of the most recent confirmed swing low within the last
    `lookback` bars — used as the anchor when no specific event (earnings,
    breakout day) is supplied. Falls back to `lookback` bars ago if no swing low
    is found in that window.
    """
    mask = confirmed_swing_lows(low, order)
    window_start = max(len(low) - lookback, 0)
    mask = mask.copy()
    mask.iloc[:window_start] = False
    swing_positions = [pos for pos, is_swing in enumerate(mask.tolist()) if is_swing]
    if swing_positions:
        return swing_positions[-1]
    return window_start


def vwap_slope(vwap: pd.Series, lookback: int = 5) -> pd.Series:
    return vwap - vwap.shift(lookback)
