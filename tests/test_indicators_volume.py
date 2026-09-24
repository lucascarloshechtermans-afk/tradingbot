import pandas as pd
import pytest

from indicators.volume import (
    accumulation_distribution,
    on_balance_volume,
    price_volume_confirmed,
    relative_volume,
    volume_sma,
)


def _idx(n):
    return pd.date_range("2024-01-01", periods=n, freq="D")


def test_relative_volume_above_1_on_spike():
    volume = pd.Series([1000] * 20 + [5000], index=_idx(21))
    rvol = relative_volume(volume, window=20)
    assert rvol.iloc[-1] == pytest.approx(5.0)


def test_volume_sma_matches_manual_average():
    volume = pd.Series([100, 200, 300], index=_idx(3))
    result = volume_sma(volume, window=3)
    assert result.iloc[2] == pytest.approx(200.0)


def test_obv_increases_on_up_days_decreases_on_down_days():
    close = pd.Series([10, 11, 10, 12], index=_idx(4))
    volume = pd.Series([100, 100, 100, 100], index=_idx(4))
    obv = on_balance_volume(close, volume)
    assert obv.iloc[1] == 100    # up day: +100
    assert obv.iloc[2] == 0      # down day: -100
    assert obv.iloc[3] == 100    # up day: +100


def test_accumulation_distribution_positive_when_closing_near_high():
    idx = _idx(3)
    high = pd.Series([10, 10, 10], index=idx)
    low = pd.Series([8, 8, 8], index=idx)
    close = pd.Series([9.9, 9.9, 9.9], index=idx)  # closes near the high each day
    volume = pd.Series([1000, 1000, 1000], index=idx)
    ad = accumulation_distribution(high, low, close, volume)
    assert ad.iloc[-1] > 0


def test_accumulation_distribution_negative_when_closing_near_low():
    idx = _idx(3)
    high = pd.Series([10, 10, 10], index=idx)
    low = pd.Series([8, 8, 8], index=idx)
    close = pd.Series([8.1, 8.1, 8.1], index=idx)  # closes near the low each day
    volume = pd.Series([1000, 1000, 1000], index=idx)
    ad = accumulation_distribution(high, low, close, volume)
    assert ad.iloc[-1] < 0


def test_price_volume_confirmed_requires_both_conditions():
    price_change = pd.Series([1.0, -1.0, 1.0])
    rvol = pd.Series([2.0, 2.0, 0.5])
    result = price_volume_confirmed(price_change, rvol, rvol_threshold=1.5)
    assert result.tolist() == [True, False, False]
