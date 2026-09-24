import pandas as pd

from price_action.candlesticks import (
    detect_all,
    is_bearish_engulfing,
    is_bullish_engulfing,
    is_doji,
    is_evening_star,
    is_hammer,
    is_inside_bar,
    is_morning_star,
    is_outside_bar,
    is_shooting_star,
)


def _s(values):
    return pd.Series(values, index=pd.date_range("2024-01-01", periods=len(values), freq="D"), dtype=float)


def test_is_doji_true_for_tiny_body():
    o, h, l, c = _s([100]), _s([102]), _s([98]), _s([100.05])
    assert is_doji(o, h, l, c) is True


def test_is_doji_false_for_large_body():
    o, h, l, c = _s([100]), _s([110]), _s([95]), _s([108])
    assert is_doji(o, h, l, c) is False


def test_is_hammer_true():
    # small body near top, long lower shadow, tiny upper shadow
    o, h, l, c = _s([100]), _s([100.5]), _s([90]), _s([100.3])
    assert is_hammer(o, h, l, c) is True


def test_is_shooting_star_true():
    o, h, l, c = _s([100]), _s([110]), _s([99.5]), _s([100.2])
    assert is_shooting_star(o, h, l, c) is True


def test_is_bullish_engulfing():
    o = _s([10, 8])
    c = _s([8, 11])
    assert is_bullish_engulfing(o, c) is True


def test_is_bearish_engulfing():
    o = _s([8, 11])
    c = _s([10, 7])
    assert is_bearish_engulfing(o, c) is True


def test_is_inside_bar():
    h = _s([100, 99])
    l = _s([90, 92])
    assert is_inside_bar(h, l) is True


def test_is_outside_bar():
    h = _s([100, 105])
    l = _s([90, 85])
    assert is_outside_bar(h, l) is True


def test_is_morning_star():
    o = _s([100, 90, 88])
    c = _s([90, 89, 99])  # day1 big bearish, day2 small, day3 big bullish closing into day1
    assert is_morning_star(o, c) is True


def test_is_evening_star():
    o = _s([90, 100, 101])
    c = _s([100, 101, 90])  # day1 big bullish, day2 small, day3 big bearish closing into day1
    assert is_evening_star(o, c) is True


def test_detect_all_returns_matching_pattern_names():
    o, h, l, c = _s([100]), _s([102]), _s([98]), _s([100.05])
    result = detect_all(o, h, l, c)
    assert "doji" in result
