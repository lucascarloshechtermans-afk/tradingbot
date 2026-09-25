import pandas as pd

from price_action.levels import Level
from price_action.structure import (
    classify_structure_break,
    detect_liquidity_sweep,
    is_liquidity_sweep_high,
    is_liquidity_sweep_low,
)


def _idx(n):
    return pd.date_range("2024-01-01", periods=n, freq="D")


def test_classify_structure_break_bullish_bos_in_uptrend():
    # clean rising zigzag: HH/HL structure, then a decisive close above the last swing high
    high = pd.Series([5, 3, 6, 4, 7, 5, 8, 6, 9, 7, 15], index=_idx(11))
    low = pd.Series([3, 1, 4, 2, 5, 3, 6, 4, 7, 5, 12], index=_idx(11))
    close = pd.Series([4, 2, 5, 3, 6, 4, 7, 5, 8, 6, 14], index=_idx(11))
    result = classify_structure_break(high, low, close, order=1)
    assert result == "bullish_bos"


def test_classify_structure_break_bearish_choch_after_uptrend():
    # HH/HL structure established, then a decisive close BELOW the last swing low
    high = pd.Series([5, 3, 6, 4, 7, 5, 8, 6, 9, 7, 6], index=_idx(11))
    low = pd.Series([3, 1, 4, 2, 5, 3, 6, 4, 7, 5, 1], index=_idx(11))
    close = pd.Series([4, 2, 5, 3, 6, 4, 7, 5, 8, 6, 2], index=_idx(11))
    result = classify_structure_break(high, low, close, order=1)
    assert result == "bearish_choch"


def test_classify_structure_break_none_when_no_break():
    high = pd.Series([5, 3, 6, 4, 7, 5, 8, 6, 9, 7, 8], index=_idx(11))
    low = pd.Series([3, 1, 4, 2, 5, 3, 6, 4, 7, 5, 6], index=_idx(11))
    close = pd.Series([4, 2, 5, 3, 6, 4, 7, 5, 8, 6, 7], index=_idx(11))
    result = classify_structure_break(high, low, close, order=1)
    assert result == "none"


def test_is_liquidity_sweep_high_true_on_wick_rejection():
    high = pd.Series([100.0, 106.0])
    close = pd.Series([99.0, 103.0])  # pierces above 105 (level) but closes back below
    assert is_liquidity_sweep_high(high, close, level=105.0) is True


def test_is_liquidity_sweep_high_false_when_closes_above():
    high = pd.Series([100.0, 106.0])
    close = pd.Series([99.0, 106.0])  # closes at the high, no rejection
    assert is_liquidity_sweep_high(high, close, level=105.0) is False


def test_is_liquidity_sweep_low_true_on_wick_rejection():
    low = pd.Series([100.0, 94.0])
    close = pd.Series([101.0, 97.0])
    assert is_liquidity_sweep_low(low, close, level=95.0) is True


def test_detect_liquidity_sweep_bearish():
    levels = [Level(price=105.0, kind="resistance", touches=2, strength=40, last_touch=None)]
    high = pd.Series([100.0, 106.5])
    low = pd.Series([98.0, 103.0])
    close = pd.Series([99.0, 103.5])
    result = detect_liquidity_sweep(high, low, close, levels, tolerance_pct=5.0)
    assert result == "bearish_sweep"


def test_detect_liquidity_sweep_none_when_no_levels():
    high = pd.Series([100.0, 106.5])
    low = pd.Series([98.0, 103.0])
    close = pd.Series([99.0, 103.5])
    assert detect_liquidity_sweep(high, low, close, [], tolerance_pct=5.0) is None
