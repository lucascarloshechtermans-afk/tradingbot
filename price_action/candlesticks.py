from __future__ import annotations

import pandas as pd

"""Candlestick pattern detectors.

These are intentionally NOT exposed as standalone buy/sell signals anywhere in the
scanner — per the spec, a candlestick pattern only contributes meaning once it is
combined with trend, volume, and support/resistance context in a strategy module.
Every function here returns a plain bool for whether the shape is present on the
most recent bar; the caller decides what (if anything) that implies.
"""


def _body(open_: float, close: float) -> float:
    return abs(close - open_)


def _range(high: float, low: float) -> float:
    return high - low


def is_doji(open_: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series, body_ratio: float = 0.1) -> bool:
    o, h, l, c = open_.iloc[-1], high.iloc[-1], low.iloc[-1], close.iloc[-1]
    r = _range(h, l)
    if r <= 0:
        return False
    return bool((_body(o, c) / r) <= body_ratio)


def is_hammer(open_: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series) -> bool:
    o, h, l, c = open_.iloc[-1], high.iloc[-1], low.iloc[-1], close.iloc[-1]
    r = _range(h, l)
    if r <= 0:
        return False
    body = _body(o, c)
    upper_shadow = h - max(o, c)
    lower_shadow = min(o, c) - l
    return bool(lower_shadow >= 2 * body and upper_shadow <= 0.25 * r and body > 0)


def is_shooting_star(open_: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series) -> bool:
    o, h, l, c = open_.iloc[-1], high.iloc[-1], low.iloc[-1], close.iloc[-1]
    r = _range(h, l)
    if r <= 0:
        return False
    body = _body(o, c)
    upper_shadow = h - max(o, c)
    lower_shadow = min(o, c) - l
    return bool(upper_shadow >= 2 * body and lower_shadow <= 0.25 * r and body > 0)


def is_bullish_engulfing(open_: pd.Series, close: pd.Series) -> bool:
    if len(close) < 2:
        return False
    prev_open, prev_close = open_.iloc[-2], close.iloc[-2]
    today_open, today_close = open_.iloc[-1], close.iloc[-1]
    prev_bearish = prev_close < prev_open
    today_bullish = today_close > today_open
    engulfs = today_open <= prev_close and today_close >= prev_open
    return bool(prev_bearish and today_bullish and engulfs)


def is_bearish_engulfing(open_: pd.Series, close: pd.Series) -> bool:
    if len(close) < 2:
        return False
    prev_open, prev_close = open_.iloc[-2], close.iloc[-2]
    today_open, today_close = open_.iloc[-1], close.iloc[-1]
    prev_bullish = prev_close > prev_open
    today_bearish = today_close < today_open
    engulfs = today_open >= prev_close and today_close <= prev_open
    return bool(prev_bullish and today_bearish and engulfs)


def is_inside_bar(high: pd.Series, low: pd.Series) -> bool:
    if len(high) < 2:
        return False
    return bool(high.iloc[-1] < high.iloc[-2] and low.iloc[-1] > low.iloc[-2])


def is_outside_bar(high: pd.Series, low: pd.Series) -> bool:
    if len(high) < 2:
        return False
    return bool(high.iloc[-1] > high.iloc[-2] and low.iloc[-1] < low.iloc[-2])


def is_morning_star(open_: pd.Series, close: pd.Series) -> bool:
    """3-bar bullish reversal: long bearish body, small-bodied 'star', then a
    bullish body closing back into the first bar's range."""
    if len(close) < 3:
        return False
    o1, c1 = open_.iloc[-3], close.iloc[-3]
    o2, c2 = open_.iloc[-2], close.iloc[-2]
    o3, c3 = open_.iloc[-1], close.iloc[-1]
    day1_bearish_body = o1 - c1
    day2_body = abs(c2 - o2)
    day3_bullish_body = c3 - o3
    if day1_bearish_body <= 0 or day3_bullish_body <= 0:
        return False
    star_is_small = day2_body <= 0.5 * day1_bearish_body
    closes_into_day1 = c3 >= (o1 + c1) / 2
    return bool(star_is_small and closes_into_day1)


def is_evening_star(open_: pd.Series, close: pd.Series) -> bool:
    if len(close) < 3:
        return False
    o1, c1 = open_.iloc[-3], close.iloc[-3]
    o2, c2 = open_.iloc[-2], close.iloc[-2]
    o3, c3 = open_.iloc[-1], close.iloc[-1]
    day1_bullish_body = c1 - o1
    day2_body = abs(c2 - o2)
    day3_bearish_body = o3 - c3
    if day1_bullish_body <= 0 or day3_bearish_body <= 0:
        return False
    star_is_small = day2_body <= 0.5 * day1_bullish_body
    closes_into_day1 = c3 <= (o1 + c1) / 2
    return bool(star_is_small and closes_into_day1)


def detect_all(open_: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series) -> list[str]:
    """Return the names of every candlestick pattern present on the latest bar."""
    detectors = {
        "doji": lambda: is_doji(open_, high, low, close),
        "hammer": lambda: is_hammer(open_, high, low, close),
        "shooting_star": lambda: is_shooting_star(open_, high, low, close),
        "bullish_engulfing": lambda: is_bullish_engulfing(open_, close),
        "bearish_engulfing": lambda: is_bearish_engulfing(open_, close),
        "inside_bar": lambda: is_inside_bar(high, low),
        "outside_bar": lambda: is_outside_bar(high, low),
        "morning_star": lambda: is_morning_star(open_, close),
        "evening_star": lambda: is_evening_star(open_, close),
    }
    return [name for name, fn in detectors.items() if fn()]
