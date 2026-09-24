from __future__ import annotations

import numpy as np
import pandas as pd

from indicators.volatility import true_range


def _wilder_smooth(series: pd.Series, window: int) -> pd.Series:
    return series.ewm(alpha=1 / window, adjust=False, min_periods=window).mean()


def directional_movement(high: pd.Series, low: pd.Series):
    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=high.index)
    minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=high.index)
    return plus_dm, minus_dm


def adx(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14):
    """Returns (adx, plus_di, minus_di) using Wilder's original smoothing."""
    plus_dm, minus_dm = directional_movement(high, low)
    tr = true_range(high, low, close)

    smoothed_tr = _wilder_smooth(tr, window)
    smoothed_plus_dm = _wilder_smooth(plus_dm, window)
    smoothed_minus_dm = _wilder_smooth(minus_dm, window)

    plus_di = 100 * (smoothed_plus_dm / smoothed_tr.replace(0, np.nan))
    minus_di = 100 * (smoothed_minus_dm / smoothed_tr.replace(0, np.nan))

    di_sum = (plus_di + minus_di).replace(0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / di_sum
    adx_series = _wilder_smooth(dx, window)

    return adx_series, plus_di, minus_di
