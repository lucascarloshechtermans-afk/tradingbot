from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from indicators.trend import confirmed_swing_highs, confirmed_swing_lows


@dataclass
class Level:
    price: float
    kind: str  # "support" | "resistance"
    touches: int
    strength: float  # 0-100, based on touch count (more touches = stronger)
    last_touch: pd.Timestamp


def _cluster_swings(points: list[tuple[float, pd.Timestamp]], tolerance_pct: float) -> list[list[tuple[float, pd.Timestamp]]]:
    """Group nearby swing prices into clusters. Points are grouped into the same
    cluster as long as each new point is within `tolerance_pct` of the cluster's
    running mean price — this is what turns "many similar highs" into one
    resistance level instead of a level per swing point.
    """
    if not points:
        return []
    ordered = sorted(points, key=lambda p: p[0])
    clusters: list[list[tuple[float, pd.Timestamp]]] = [[ordered[0]]]
    for price, ts in ordered[1:]:
        cluster_mean = sum(p for p, _ in clusters[-1]) / len(clusters[-1])
        if abs(price - cluster_mean) / cluster_mean * 100 <= tolerance_pct:
            clusters[-1].append((price, ts))
        else:
            clusters.append([(price, ts)])
    return clusters


def find_levels(
    high: pd.Series,
    low: pd.Series,
    order: int = 3,
    tolerance_pct: float = 0.75,
    min_touches: int = 2,
    max_levels: int = 8,
) -> list[Level]:
    """Detect support/resistance levels from confirmed swing highs and lows.

    Levels are built purely from price structure (clustered swing points), not
    drawn arbitrarily — strength is the number of swing points ("touches") that
    fall within `tolerance_pct` of each other.
    """
    swing_high_mask = confirmed_swing_highs(high, order)
    swing_low_mask = confirmed_swing_lows(low, order)

    high_points = list(zip(high[swing_high_mask].values, high[swing_high_mask].index))
    low_points = list(zip(low[swing_low_mask].values, low[swing_low_mask].index))

    levels: list[Level] = []
    for points, kind in [(high_points, "resistance"), (low_points, "support")]:
        for cluster in _cluster_swings(points, tolerance_pct):
            if len(cluster) < min_touches:
                continue
            mean_price = sum(p for p, _ in cluster) / len(cluster)
            last_touch = max(ts for _, ts in cluster)
            strength = min(len(cluster) / 5.0, 1.0) * 100
            levels.append(Level(price=mean_price, kind=kind, touches=len(cluster), strength=strength, last_touch=last_touch))

    levels.sort(key=lambda lv: lv.strength, reverse=True)
    return levels[:max_levels]


def nearest_level(levels: list[Level], price: float, kind: str | None = None) -> Level | None:
    candidates = [lv for lv in levels if kind is None or lv.kind == kind]
    if not candidates:
        return None
    return min(candidates, key=lambda lv: abs(lv.price - price))


def confluence_score(
    price: float,
    levels: list[Level],
    vwap_value: float | None = None,
    fib_levels: dict[float, float] | None = None,
    tolerance_pct: float = 1.0,
) -> tuple[int, list[str]]:
    """Count how many INDEPENDENT reference points cluster near `price` —
    multiple unrelated methods agreeing on the same zone is a stronger signal
    than any one of them alone. Returns (count, human-readable sources).
    """
    count = 0
    sources: list[str] = []

    level = nearest_level(levels, price)
    if level is not None and level.price > 0 and abs(level.price - price) / level.price * 100 <= tolerance_pct:
        count += 1
        sources.append(f"{level.kind} level ({level.touches} touches)")

    if vwap_value is not None and vwap_value == vwap_value and vwap_value > 0:  # not NaN
        if abs(vwap_value - price) / vwap_value * 100 <= tolerance_pct:
            count += 1
            sources.append("anchored VWAP")

    if fib_levels:
        from price_action.fibonacci import nearest_fib_ratio

        ratio = nearest_fib_ratio(price, fib_levels, tolerance_pct)
        if ratio is not None:
            count += 1
            sources.append(f"{ratio * 100:.1f}% Fibonacci retracement")

    if price > 0:
        round_number = round(price / 5) * 5
        if round_number > 0 and abs(round_number - price) / price * 100 <= tolerance_pct * 0.5:
            count += 1
            sources.append(f"round number (${round_number:g})")

    return count, sources
