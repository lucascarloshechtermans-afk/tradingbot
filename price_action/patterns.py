from __future__ import annotations

import pandas as pd

from indicators.volatility import is_squeeze
from indicators.volume import relative_volume
from price_action.levels import Level, nearest_level


def is_breakout(high: pd.Series, close: pd.Series, lookback: int = 20) -> bool:
    """Close breaks above the highest high of the PRIOR `lookback` bars
    (today's own bar is excluded from that prior range, or every breakout would
    trivially compare a bar to a range that includes itself)."""
    if len(high) < lookback + 1:
        return False
    prior_high = high.iloc[-(lookback + 1):-1].max()
    return bool(close.iloc[-1] > prior_high)


def is_breakdown(low: pd.Series, close: pd.Series, lookback: int = 20) -> bool:
    if len(low) < lookback + 1:
        return False
    prior_low = low.iloc[-(lookback + 1):-1].min()
    return bool(close.iloc[-1] < prior_low)


def has_volume_confirmation(volume: pd.Series, rvol_threshold: float = 1.5, window: int = 20) -> bool:
    rvol = relative_volume(volume, window=window)
    if rvol.dropna().empty:
        return False
    return bool(rvol.iloc[-1] >= rvol_threshold)


def is_pullback_to_ma(close: pd.Series, ma: pd.Series, tolerance_pct: float = 1.5) -> bool:
    if pd.isna(ma.iloc[-1]):
        return False
    distance_pct = abs(close.iloc[-1] - ma.iloc[-1]) / ma.iloc[-1] * 100
    return bool(distance_pct <= tolerance_pct)


def is_consolidation(high: pd.Series, low: pd.Series, window: int = 10, max_range_pct: float = 6.0) -> bool:
    if len(high) < window:
        return False
    recent_high = high.iloc[-window:].max()
    recent_low = low.iloc[-window:].min()
    if recent_low <= 0:
        return False
    range_pct = (recent_high - recent_low) / recent_low * 100
    return bool(range_pct <= max_range_pct)


def is_consolidation_breakout(
    high: pd.Series, low: pd.Series, close: pd.Series, window: int = 10, max_range_pct: float = 6.0
) -> bool:
    """A tight consolidation over the PRIOR `window` bars, followed by today's
    close breaking above that consolidation's high."""
    if len(high) < window + 1:
        return False
    prior_high = high.iloc[-(window + 1):-1]
    prior_low = low.iloc[-(window + 1):-1]
    range_pct = (prior_high.max() - prior_low.min()) / prior_low.min() * 100
    was_consolidating = range_pct <= max_range_pct
    breaks_out = close.iloc[-1] > prior_high.max()
    return bool(was_consolidating and breaks_out)


def is_support_bounce(low: pd.Series, close: pd.Series, levels: list[Level], tolerance_pct: float = 1.5) -> bool:
    """Today's low touched (within tolerance) a known support level and closed
    back above it."""
    level = nearest_level(levels, close.iloc[-1], kind="support")
    if level is None:
        return False
    touched = abs(low.iloc[-1] - level.price) / level.price * 100 <= tolerance_pct
    closed_above = close.iloc[-1] > level.price
    return bool(touched and closed_above)


def is_resistance_rejection(high: pd.Series, close: pd.Series, levels: list[Level], tolerance_pct: float = 1.5) -> bool:
    level = nearest_level(levels, close.iloc[-1], kind="resistance")
    if level is None:
        return False
    touched = abs(high.iloc[-1] - level.price) / level.price * 100 <= tolerance_pct
    closed_below = close.iloc[-1] < level.price
    return bool(touched and closed_below)


def detect_gap(open_: pd.Series, close: pd.Series, threshold_pct: float = 1.0) -> str | None:
    if len(close) < 2:
        return None
    prev_close = close.iloc[-2]
    today_open = open_.iloc[-1]
    if prev_close <= 0:
        return None
    gap_pct = (today_open - prev_close) / prev_close * 100
    if gap_pct >= threshold_pct:
        return "gap_up"
    if gap_pct <= -threshold_pct:
        return "gap_down"
    return None


def is_gap_filled(open_: pd.Series, low: pd.Series, high: pd.Series, close: pd.Series, threshold_pct: float = 1.0) -> bool:
    """True if a gap from the prior bar has since been fully retraced (price
    traded back through the prior close) within the current bar."""
    gap = detect_gap(open_, close, threshold_pct)
    if gap is None or len(close) < 2:
        return False
    prev_close = close.iloc[-2]
    if gap == "gap_up":
        return bool(low.iloc[-1] <= prev_close)
    return bool(high.iloc[-1] >= prev_close)


def classify_gap(
    open_: pd.Series,
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    sma50: pd.Series,
    atr_value: float,
    threshold_pct: float = 1.0,
    consolidation_window: int = 10,
    extension_atr_threshold: float = 4.0,
) -> str | None:
    """Classify a detected gap using the state of the prior bars — an honest
    heuristic, not a certainty:

    - '{gap}_breakaway': the PRIOR bars (excluding today) were consolidating in a
      tight range — the classic gap-out-of-a-base pattern.
    - '{gap}_exhaustion': price was already far extended from its 50-day MA
      (more than `extension_atr_threshold` ATRs) before this gap — a possible
      blow-off/exhaustion gap rather than a fresh move.
    - '{gap}_continuation': neither of the above — a gap in the direction of an
      already-underway, not-yet-extended trend.

    Returns None if there's no gap at all.
    """
    gap = detect_gap(open_, close, threshold_pct)
    if gap is None or len(high) < consolidation_window + 1:
        return gap

    prior_high = high.iloc[-(consolidation_window + 1):-1]
    prior_low = low.iloc[-(consolidation_window + 1):-1]
    was_consolidating = is_consolidation(prior_high, prior_low, window=consolidation_window)

    extended = False
    prev_close = close.iloc[-2]
    prev_sma50 = sma50.iloc[-2] if len(sma50) >= 2 else float("nan")
    if pd.notna(prev_sma50) and pd.notna(atr_value) and atr_value > 0:
        extended = abs(prev_close - prev_sma50) / atr_value > extension_atr_threshold

    if was_consolidating:
        return f"{gap}_breakaway"
    if extended:
        return f"{gap}_exhaustion"
    return f"{gap}_continuation"


def is_volatility_contraction(close: pd.Series, window: int = 20, lookback: int = 120, percentile: float = 0.10) -> bool:
    squeeze = is_squeeze(close, window=window, lookback=lookback, percentile=percentile)
    if squeeze.dropna().empty:
        return False
    return bool(squeeze.iloc[-1])


def has_higher_low(low: pd.Series, order: int = 3) -> bool:
    from indicators.trend import confirmed_swing_lows

    mask = confirmed_swing_lows(low, order)
    usable_end = max(len(low) - order, 0)
    mask.iloc[usable_end:] = False
    swing_lows = low[mask]
    if len(swing_lows) < 2:
        return False
    return bool(swing_lows.iloc[-1] > swing_lows.iloc[-2])


def has_lower_high(high: pd.Series, order: int = 3) -> bool:
    from indicators.trend import confirmed_swing_highs

    mask = confirmed_swing_highs(high, order)
    usable_end = max(len(high) - order, 0)
    mask.iloc[usable_end:] = False
    swing_highs = high[mask]
    if len(swing_highs) < 2:
        return False
    return bool(swing_highs.iloc[-1] < swing_highs.iloc[-2])
