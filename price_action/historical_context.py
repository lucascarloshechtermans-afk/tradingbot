from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from price_action.levels import Level

FIFTY_TWO_WEEK_TRADING_DAYS = 252
NEAR_HIGH_TOLERANCE_PCT = 1.0


@dataclass
class HistoricalContext:
    fifty_two_week_high: float | None
    fifty_two_week_low: float | None
    distance_to_52w_high_pct: float | None  # <= 0 typically: how far BELOW the 52w high price sits
    distance_to_52w_low_pct: float | None  # >= 0 typically: how far ABOVE the 52w low price sits
    all_time_high_in_window: float | None  # highest close in the FETCHED history — see docstring caveat
    is_fresh_52w_high: bool
    major_resistance_overhead: Level | None  # strongest resistance level still above price, if any
    reasons: list[str] = field(default_factory=list)


def compute_historical_context(
    close: pd.Series,
    last_close: float,
    levels: list[Level],
    window: int = FIFTY_TWO_WEEK_TRADING_DAYS,
    near_high_tolerance_pct: float = NEAR_HIGH_TOLERANCE_PCT,
) -> HistoricalContext:
    """52-week high/low context plus which strongest historical resistance level
    (from the existing swing-point clustering in price_action/levels.py) still
    sits above the current price — this is what lets a strategy tell "breaking to
    a fresh 52-week high with no overhead supply" apart from "broke today's local
    20-day high but a much bigger historical ceiling is still right above it,"
    which look identical to a bare N-day-high breakout check alone.

    `all_time_high_in_window` is honestly named: it's the highest close within
    whatever history was fetched (`config.data.period`), NOT necessarily the
    stock's real all-time high unless that period is "max" — a true ATH would
    need the full listing history, which isn't always fetched for a scan.
    """
    reasons: list[str] = []
    window_slice = close.tail(window)

    fifty_two_week_high = float(window_slice.max()) if len(window_slice) else None
    fifty_two_week_low = float(window_slice.min()) if len(window_slice) else None
    all_time_high_in_window = float(close.max()) if len(close) else None

    distance_to_high = None
    distance_to_low = None
    is_fresh_high = False
    if fifty_two_week_high is not None and fifty_two_week_high > 0:
        distance_to_high = (last_close - fifty_two_week_high) / fifty_two_week_high * 100
        is_fresh_high = distance_to_high >= -near_high_tolerance_pct
        if is_fresh_high:
            reasons.append(f"At/near its 52-week high (${fifty_two_week_high:.2f})")
        else:
            reasons.append(f"{abs(distance_to_high):.1f}% below its 52-week high (${fifty_two_week_high:.2f})")
    if fifty_two_week_low is not None and fifty_two_week_low > 0:
        distance_to_low = (last_close - fifty_two_week_low) / fifty_two_week_low * 100
        reasons.append(f"{distance_to_low:.1f}% above its 52-week low (${fifty_two_week_low:.2f})")

    resistance_above = [lv for lv in levels if lv.kind == "resistance" and lv.price > last_close]
    major_resistance = max(resistance_above, key=lambda lv: lv.strength) if resistance_above else None
    if major_resistance is not None:
        dist_pct = (major_resistance.price - last_close) / last_close * 100
        reasons.append(
            f"Historical resistance at ${major_resistance.price:.2f} ({major_resistance.touches} touches), "
            f"{dist_pct:.1f}% above current price"
        )

    return HistoricalContext(
        fifty_two_week_high=fifty_two_week_high,
        fifty_two_week_low=fifty_two_week_low,
        distance_to_52w_high_pct=distance_to_high,
        distance_to_52w_low_pct=distance_to_low,
        all_time_high_in_window=all_time_high_in_window,
        is_fresh_52w_high=is_fresh_high,
        major_resistance_overhead=major_resistance,
        reasons=reasons,
    )
