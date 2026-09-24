from __future__ import annotations

from dataclasses import dataclass

from price_action.levels import Level

DEFAULT_RR_MULTIPLES = (1.0, 1.5, 2.0, 3.0)


@dataclass
class StopLevels:
    atr_stop: float
    structure_stop: float | None
    final_stop: float
    final_stop_method: str  # "structure" | "atr"


@dataclass
class TargetLevel:
    price: float
    rr: float
    method: str


def compute_atr_stop(entry: float, atr: float, multiplier: float = 2.0, direction: str = "long") -> float:
    if direction == "long":
        return entry - multiplier * atr
    return entry + multiplier * atr


def compute_structure_stop(
    entry: float, levels: list[Level], direction: str = "long", buffer_pct: float = 0.3
) -> float | None:
    """Nearest support (for a long) or resistance (for a short) below/above entry,
    with a small buffer so normal noise doesn't trigger the stop exactly at the
    level itself."""
    if direction == "long":
        candidates = [lv for lv in levels if lv.kind == "support" and lv.price < entry]
        if not candidates:
            return None
        nearest = max(candidates, key=lambda lv: lv.price)
        return nearest.price * (1 - buffer_pct / 100)

    candidates = [lv for lv in levels if lv.kind == "resistance" and lv.price > entry]
    if not candidates:
        return None
    nearest = min(candidates, key=lambda lv: lv.price)
    return nearest.price * (1 + buffer_pct / 100)


def compute_stop(
    entry: float,
    atr: float,
    levels: list[Level],
    direction: str = "long",
    atr_multiplier: float = 2.0,
    buffer_pct: float = 0.3,
    max_structure_distance_multiple: float = 2.0,
) -> StopLevels:
    """Combine an ATR-based stop with a structure-based stop.

    The structure stop is preferred (it's a real support/resistance level, more
    meaningful than a generic multiple) UNLESS it is unreasonably far from entry —
    more than `max_structure_distance_multiple` times the ATR-stop distance — in
    which case the ATR stop is used instead, to avoid an oversized, undefendable
    risk on the trade.
    """
    atr_stop_price = compute_atr_stop(entry, atr, atr_multiplier, direction)
    structure_stop_price = compute_structure_stop(entry, levels, direction, buffer_pct)

    if structure_stop_price is not None:
        atr_distance = abs(entry - atr_stop_price)
        structure_distance = abs(entry - structure_stop_price)
        if atr_distance > 0 and structure_distance <= atr_distance * max_structure_distance_multiple:
            return StopLevels(
                atr_stop=atr_stop_price,
                structure_stop=structure_stop_price,
                final_stop=structure_stop_price,
                final_stop_method="structure",
            )

    return StopLevels(
        atr_stop=atr_stop_price,
        structure_stop=structure_stop_price,
        final_stop=atr_stop_price,
        final_stop_method="atr",
    )


def compute_rr_targets(
    entry: float, stop: float, direction: str = "long", rr_multiples: tuple[float, ...] = DEFAULT_RR_MULTIPLES
) -> list[TargetLevel]:
    risk = abs(entry - stop)
    targets = []
    for rr in rr_multiples:
        price = entry + risk * rr if direction == "long" else entry - risk * rr
        targets.append(TargetLevel(price=price, rr=rr, method=f"{rr:g}:1 R:R"))
    return targets


def nearest_structure_target(entry: float, levels: list[Level], direction: str = "long") -> Level | None:
    if direction == "long":
        candidates = [lv for lv in levels if lv.kind == "resistance" and lv.price > entry]
        return min(candidates, key=lambda lv: lv.price) if candidates else None
    candidates = [lv for lv in levels if lv.kind == "support" and lv.price < entry]
    return max(candidates, key=lambda lv: lv.price) if candidates else None


def risk_reward_ratio(entry: float, stop: float, target: float) -> float:
    risk = abs(entry - stop)
    reward = abs(target - entry)
    if risk <= 0:
        raise ValueError("risk (entry - stop distance) must be positive")
    return reward / risk
