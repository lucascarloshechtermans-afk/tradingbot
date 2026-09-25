from __future__ import annotations

from indicators.trend import confirmed_swing_highs, confirmed_swing_lows, market_structure
from price_action.levels import Level, nearest_level

"""Break of Structure (BOS) / Change of Character (CHOCH), and liquidity sweeps.

These are mechanical price-action definitions — a confirmed close beyond a prior
swing point, and a wick that pierces a known level then closes back inside it.
No claim is made here about market participants' intent ("smart money", "stop
hunts" as deliberate manipulation, etc.) — that framing is popular in retail
trading communities but has no empirical backing; what's implemented is just the
observable pattern, described plainly.
"""


def classify_structure_break(high, low, close, order: int = 3) -> str:
    """Classify the latest bar's close relative to swing structure:

    - 'bullish_bos': closes above the last confirmed swing high while the
      structure was already bullish (higher-highs/higher-lows) — trend
      continuation confirmation.
    - 'bearish_bos': mirror, in an already-bearish structure.
    - 'bullish_choch': closes above the last confirmed swing high while the
      structure was bearish or mixed — the first mechanical sign the downtrend
      may be reversing.
    - 'bearish_choch': mirror.
    - 'none': no structural break on this bar.
    """
    structure = market_structure(high, low, order)

    swing_high_mask = confirmed_swing_highs(high, order).copy()
    swing_low_mask = confirmed_swing_lows(low, order).copy()
    usable_end = max(len(high) - order, 0)
    swing_high_mask.iloc[usable_end:] = False
    swing_low_mask.iloc[usable_end:] = False

    swing_highs = high[swing_high_mask]
    swing_lows = low[swing_low_mask]
    last_swing_high = swing_highs.iloc[-1] if len(swing_highs) else None
    last_swing_low = swing_lows.iloc[-1] if len(swing_lows) else None

    broke_above = last_swing_high is not None and close.iloc[-1] > last_swing_high
    broke_below = last_swing_low is not None and close.iloc[-1] < last_swing_low

    if broke_above and structure == "higher_highs_higher_lows":
        return "bullish_bos"
    if broke_below and structure == "lower_highs_lower_lows":
        return "bearish_bos"
    if broke_above and structure in ("lower_highs_lower_lows", "mixed"):
        return "bullish_choch"
    if broke_below and structure in ("higher_highs_higher_lows", "mixed"):
        return "bearish_choch"
    return "none"


def is_liquidity_sweep_high(high, close, level: float) -> bool:
    """The latest bar's high pierced above `level` but closed back below it — a
    wick-based sweep of a known resistance/equal-highs level."""
    return bool(high.iloc[-1] > level and close.iloc[-1] < level)


def is_liquidity_sweep_low(low, close, level: float) -> bool:
    return bool(low.iloc[-1] < level and close.iloc[-1] > level)


def detect_liquidity_sweep(high, low, close, levels: list[Level], tolerance_pct: float = 2.0) -> str | None:
    """Checks the latest bar against the nearest resistance/support level (within
    `tolerance_pct`) for a sweep pattern. Returns 'bearish_sweep' (resistance
    swept, closed back below — rejection), 'bullish_sweep' (support swept, closed
    back above — rejection), or None.
    """
    price = close.iloc[-1]
    resistance = nearest_level(levels, price, kind="resistance")
    if resistance and abs(resistance.price - price) / price * 100 <= tolerance_pct:
        if is_liquidity_sweep_high(high, close, resistance.price):
            return "bearish_sweep"

    support = nearest_level(levels, price, kind="support")
    if support and abs(support.price - price) / price * 100 <= tolerance_pct:
        if is_liquidity_sweep_low(low, close, support.price):
            return "bullish_sweep"

    return None
