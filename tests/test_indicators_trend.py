import numpy as np
import pandas as pd

from indicators.trend import (
    confirmed_swing_highs,
    confirmed_swing_lows,
    ema,
    ma_slope,
    market_structure,
    price_above_ma,
    sma,
    trend_alignment,
)


def _series(values):
    idx = pd.date_range("2024-01-01", periods=len(values), freq="D")
    return pd.Series(values, index=idx, dtype=float)


def test_sma_matches_manual_average():
    s = _series([1, 2, 3, 4, 5])
    result = sma(s, window=3)
    assert np.isnan(result.iloc[1])
    assert result.iloc[2] == 2.0
    assert result.iloc[4] == 4.0


def test_ema_reacts_faster_than_sma_to_recent_move():
    s = _series([10] * 20 + [20] * 5)
    sma_val = sma(s, 10).iloc[-1]
    ema_val = ema(s, 10).iloc[-1]
    assert ema_val > sma_val


def test_ma_slope_positive_for_uptrend():
    s = _series(list(range(1, 30)))
    ma = sma(s, 5)
    slope = ma_slope(ma, lookback=5)
    assert slope.iloc[-1] > 0


def test_ma_slope_negative_for_downtrend():
    s = _series(list(range(30, 1, -1)))
    ma = sma(s, 5)
    slope = ma_slope(ma, lookback=5)
    assert slope.iloc[-1] < 0


def test_price_above_ma():
    price = _series([10, 20])
    ma = _series([15, 15])
    result = price_above_ma(price, ma)
    assert result.iloc[0] is np.True_ or result.iloc[0] == False
    assert bool(result.iloc[0]) is False
    assert bool(result.iloc[1]) is True


def test_trend_alignment_bullish():
    n = 60
    price = _series(list(range(1, n + 1)))
    fast = sma(price, 5)
    mid = sma(price, 10)
    slow = sma(price, 20)
    result = trend_alignment(price, fast, mid, slow)
    assert result.iloc[-1] == "bullish"


def test_trend_alignment_bearish():
    n = 60
    price = _series(list(range(n, 0, -1)))
    fast = sma(price, 5)
    mid = sma(price, 10)
    slow = sma(price, 20)
    result = trend_alignment(price, fast, mid, slow)
    assert result.iloc[-1] == "bearish"


def test_confirmed_swing_highs_detects_local_peak():
    high = _series([1, 2, 3, 5, 3, 2, 1, 2, 3, 4])
    mask = confirmed_swing_highs(high, order=2)
    assert bool(mask.iloc[3]) is True  # the "5"


def test_confirmed_swing_highs_excludes_unconfirmed_tail():
    high = _series([1, 2, 3, 5, 3, 2, 1])
    mask = confirmed_swing_highs(high, order=3)
    # last 3 bars cannot be confirmed swing highs at order=3 without future data
    assert mask.iloc[-3:].sum() == 0


def test_confirmed_swing_lows_detects_local_trough():
    low = _series([5, 4, 3, 1, 3, 4, 5, 4, 3, 2])
    mask = confirmed_swing_lows(low, order=2)
    assert bool(mask.iloc[3]) is True  # the "1"


def test_market_structure_higher_highs_higher_lows():
    # zigzag with clearly rising peaks and troughs
    high = _series([5, 3, 6, 4, 7, 5, 8, 6, 9, 7, 10])
    low = _series([3, 1, 4, 2, 5, 3, 6, 4, 7, 5, 8])
    result = market_structure(high, low, order=1)
    assert result == "higher_highs_higher_lows"


def test_market_structure_lower_highs_lower_lows():
    high = _series([10, 7, 9, 6, 8, 5, 7, 4, 6, 3, 5])
    low = _series([8, 5, 7, 4, 6, 3, 5, 2, 4, 1, 3])
    result = market_structure(high, low, order=1)
    assert result == "lower_highs_lower_lows"


def test_market_structure_insufficient_data():
    high = _series([1, 2, 3])
    low = _series([1, 2, 3])
    assert market_structure(high, low, order=3) == "insufficient_data"
