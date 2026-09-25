from __future__ import annotations

import pandas as pd


def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window, min_periods=window).mean()


def ema(series: pd.Series, window: int) -> pd.Series:
    return series.ewm(span=window, adjust=False, min_periods=window).mean()


def ma_slope(ma: pd.Series, lookback: int = 5) -> pd.Series:
    """Percentage change of a moving-average series over `lookback` bars.

    Positive = rising MA (uptrend), negative = falling MA (downtrend).
    """
    return (ma / ma.shift(lookback) - 1) * 100


def price_above_ma(price: pd.Series, ma: pd.Series) -> pd.Series:
    return price > ma


def ema_spread_pct(fast: pd.Series, slow: pd.Series) -> pd.Series:
    """Distance between two EMAs as a % of the slower one — a simple proxy for
    trend strength/separation: a wide, widening spread means a strong trend, a
    spread collapsing toward zero means the trend is losing momentum or the EMAs
    are about to cross.
    """
    return (fast - slow) / slow.replace(0, float("nan")) * 100


def crossover(fast: pd.Series, slow: pd.Series) -> str:
    """'bullish_cross' if `fast` crossed above `slow` on the latest bar,
    'bearish_cross' if it crossed below, else 'none'. Only looks at the last two
    bars, so it flags the cross event itself, not merely the current ordering.
    Generic enough to reuse for EMA crosses, MACD-vs-signal crosses, etc.
    """
    if len(fast) < 2 or pd.isna(fast.iloc[-2]) or pd.isna(slow.iloc[-2]) or pd.isna(fast.iloc[-1]) or pd.isna(slow.iloc[-1]):
        return "none"
    was_below_or_equal = fast.iloc[-2] <= slow.iloc[-2]
    now_above = fast.iloc[-1] > slow.iloc[-1]
    was_above_or_equal = fast.iloc[-2] >= slow.iloc[-2]
    now_below = fast.iloc[-1] < slow.iloc[-1]
    if was_below_or_equal and now_above:
        return "bullish_cross"
    if was_above_or_equal and now_below:
        return "bearish_cross"
    return "none"


def trend_alignment(price: pd.Series, ma_fast: pd.Series, ma_mid: pd.Series, ma_slow: pd.Series) -> pd.Series:
    """Classify each bar as 'bullish', 'bearish' or 'mixed' based on whether
    price > fast MA > mid MA > slow MA (bullish) or the reverse (bearish).
    """
    bullish = (price > ma_fast) & (ma_fast > ma_mid) & (ma_mid > ma_slow)
    bearish = (price < ma_fast) & (ma_fast < ma_mid) & (ma_mid < ma_slow)
    result = pd.Series("mixed", index=price.index)
    result[bullish] = "bullish"
    result[bearish] = "bearish"
    result[ma_slow.isna()] = "insufficient_data"
    return result


def _dedupe_plateaus(mask: pd.Series) -> pd.Series:
    """Collapse a run of consecutive True values to a single True at the end of the
    run. A flat-topped peak/trough (two+ adjacent bars tied at the same extreme)
    is structurally one swing point, not one per bar — counting it twice would
    double-count a level's touches and can make the last two "swing points" in a
    structure check identical values instead of two distinct swings.
    """
    is_end_of_run = mask & ~mask.shift(-1, fill_value=False)
    return is_end_of_run


def confirmed_swing_highs(high: pd.Series, order: int = 3) -> pd.Series:
    """Boolean mask: True where `high` is a local peak within a +/-order window.

    A swing high at index i can only be confirmed once `order` bars after i exist
    (the rolling window is centered), so the most recent `order` bars are never
    swing highs by construction here — that is intentional, not a bug: there is no
    way to know yet whether they will turn out to be local peaks. Flat-topped peaks
    (consecutive tied bars) are collapsed to one swing point via `_dedupe_plateaus`.
    """
    rolling_max = high.rolling(window=2 * order + 1, center=True).max()
    raw_mask = (high == rolling_max) & rolling_max.notna()
    return _dedupe_plateaus(raw_mask)


def confirmed_swing_lows(low: pd.Series, order: int = 3) -> pd.Series:
    rolling_min = low.rolling(window=2 * order + 1, center=True).min()
    raw_mask = (low == rolling_min) & rolling_min.notna()
    return _dedupe_plateaus(raw_mask)


def detect_divergence(
    price_extreme: pd.Series,
    oscillator: pd.Series,
    swing_mask: pd.Series,
    order: int,
    kind: str,
) -> bool:
    """Compare the last two confirmed swing points on `price_extreme` against the
    oscillator's value at those same points. `kind` is one of:

    - 'regular_bullish' (use with swing LOWS): price makes a LOWER low while the
      oscillator makes a HIGHER low — classic reversal signal at a bottom.
    - 'regular_bearish' (use with swing HIGHS): price makes a HIGHER high while
      the oscillator makes a LOWER high — classic reversal signal at a top.
    - 'hidden_bullish' (use with swing LOWS): price makes a HIGHER low (a
      shallower pullback) while the oscillator makes a LOWER low — a trend-
      CONTINUATION signal inside an existing uptrend, the opposite pairing of
      regular_bullish.
    - 'hidden_bearish' (use with swing HIGHS): price makes a LOWER high while the
      oscillator makes a HIGHER high — a continuation signal inside a downtrend.

    Reusable for any oscillator (RSI, OBV, ...) paired with price swing points.
    """
    usable_end = max(len(price_extreme) - order, 0)
    mask = swing_mask.copy()
    mask.iloc[usable_end:] = False
    swing_positions = price_extreme[mask]
    if len(swing_positions) < 2:
        return False

    idx_a, idx_b = swing_positions.index[-2], swing_positions.index[-1]
    price_a, price_b = price_extreme.loc[idx_a], price_extreme.loc[idx_b]
    osc_a, osc_b = oscillator.loc[idx_a], oscillator.loc[idx_b]
    if pd.isna(osc_a) or pd.isna(osc_b):
        return False

    if kind == "regular_bullish":
        return bool(price_b < price_a and osc_b > osc_a)
    if kind == "regular_bearish":
        return bool(price_b > price_a and osc_b < osc_a)
    if kind == "hidden_bullish":
        return bool(price_b > price_a and osc_b < osc_a)
    if kind == "hidden_bearish":
        return bool(price_b < price_a and osc_b > osc_a)
    raise ValueError(f"unknown divergence kind: {kind}")


def market_structure(high: pd.Series, low: pd.Series, order: int = 3) -> str:
    """Classify recent swing structure from the last two confirmed swing highs and
    lows: 'higher_highs_higher_lows', 'lower_highs_lower_lows', 'mixed', or
    'insufficient_data'.

    Only swings whose confirming window (order bars on each side) lies fully within
    the supplied data are used — the tail `order` bars are excluded since their
    swing status cannot yet be known without future bars.
    """
    if len(high) <= order:
        return "insufficient_data"

    swing_high_mask = confirmed_swing_highs(high, order)
    swing_low_mask = confirmed_swing_lows(low, order)

    usable_end = max(len(high) - order, 0)
    swing_high_mask.iloc[usable_end:] = False
    swing_low_mask.iloc[usable_end:] = False
    swing_high_vals = high[swing_high_mask]
    swing_low_vals = low[swing_low_mask]

    if len(swing_high_vals) < 2 or len(swing_low_vals) < 2:
        return "insufficient_data"

    higher_high = swing_high_vals.iloc[-1] > swing_high_vals.iloc[-2]
    higher_low = swing_low_vals.iloc[-1] > swing_low_vals.iloc[-2]
    lower_high = swing_high_vals.iloc[-1] < swing_high_vals.iloc[-2]
    lower_low = swing_low_vals.iloc[-1] < swing_low_vals.iloc[-2]

    if higher_high and higher_low:
        return "higher_highs_higher_lows"
    if lower_high and lower_low:
        return "lower_highs_lower_lows"
    return "mixed"
