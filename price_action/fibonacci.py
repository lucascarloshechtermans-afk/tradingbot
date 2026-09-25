from __future__ import annotations

"""Fibonacci retracement levels — treated as a MINOR confluence factor, not a
primary signal.

A research pass on well-known swing-trading systems (Minervini's SEPA, Qullamaggie's
breakout criteria, retail-scanner consensus) found weak/contested evidence that
Fibonacci retracements carry standalone predictive value — the effect, where it
exists, is generally attributed to crowd behavior clustering around the same round
ratios rather than any inherent property of the ratios themselves. It's implemented
here anyway (the user asked for it) but deliberately kept as one input into
support/resistance CONFLUENCE checking (price_action/levels.py) rather than a
scored strategy of its own.
"""

FIB_RATIOS = (0.382, 0.5, 0.618, 0.786)


def fibonacci_retracement_levels(swing_high: float, swing_low: float) -> dict[float, float]:
    """Retracement price levels between a swing high and swing low, measured as a
    pullback FROM the high TOWARD the low (the common convention for an uptrend
    pullback). For a downtrend bounce, swap which point is "high"/"low" when
    calling this.
    """
    diff = swing_high - swing_low
    return {ratio: swing_high - diff * ratio for ratio in FIB_RATIOS}


def nearest_fib_ratio(price: float, fib_levels: dict[float, float], tolerance_pct: float = 1.0) -> float | None:
    for ratio, level_price in fib_levels.items():
        if level_price <= 0:
            continue
        if abs(level_price - price) / level_price * 100 <= tolerance_pct:
            return ratio
    return None
