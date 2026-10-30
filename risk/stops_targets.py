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
    allow_tight_structure_stop: bool = False,
) -> StopLevels:
    """Combine an ATR-based stop with a structure-based stop.

    The structure stop is used when it is at least as wide as the ATR stop and
    not unreasonably far (at most `max_structure_distance_multiple` times the
    ATR-stop distance); otherwise the ATR stop is used. In other words the
    stop is never TIGHTER than the ATR stop.

    Why: on the full 134-ticker/5y backtest, the nearest support + 0.3% buffer
    sat a median 0.87 ATR from entry. Those trades won 38% vs 50% for 2-ATR
    stops, and the tightest stop-distance quintile (<0.71 ATR) was the only
    losing one, -0.22R/trade -- normal daily noise stopped them out, and
    risk-based sizing made those the LARGEST positions. The tight stops also
    produced the highest R:R ratios, so the risk_reward score category was
    rewarding the worst trades. `allow_tight_structure_stop=True` restores the
    old "prefer structure whenever it's not too far" behavior for A/B runs.
    """
    atr_stop_price = compute_atr_stop(entry, atr, atr_multiplier, direction)
    structure_stop_price = compute_structure_stop(entry, levels, direction, buffer_pct)

    if structure_stop_price is not None:
        atr_distance = abs(entry - atr_stop_price)
        structure_distance = abs(entry - structure_stop_price)
        wide_enough = allow_tight_structure_stop or structure_distance >= atr_distance
        if atr_distance > 0 and wide_enough and structure_distance <= atr_distance * max_structure_distance_multiple:
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


def expected_move_for_horizon(atr: float, holding_days: int, volatility_multiplier: float = 1.5) -> float:
    """Estimate a realistic price move over `holding_days` trading days from ATR.

    ATR is a per-bar (daily) volatility measure; scaling it by sqrt(time) is the
    standard heuristic for projecting volatility over a longer horizon (the same
    idea behind annualizing daily volatility by sqrt(252)). `volatility_multiplier`
    (default 1.5x) gives some room above the "average" expected move, since a
    genuine trending swing typically moves more than a purely random walk would —
    but this is an estimate, not a guarantee, and should be read as such.
    """
    return atr * (holding_days ** 0.5) * volatility_multiplier


def cap_target_to_horizon(
    entry: float, target: float, atr: float, holding_days: int, direction: str = "long",
    volatility_multiplier: float = 1.5,
) -> float:
    """Cap a target so it's realistically reachable within `holding_days` trading
    days — a target computed purely from a fixed R:R multiple can imply a move that
    historically takes far longer than the intended holding period to play out.
    Never moves the target further away, only pulls it in when it's unrealistic.
    """
    max_move = expected_move_for_horizon(atr, holding_days, volatility_multiplier)
    if direction == "long":
        return min(target, entry + max_move)
    return max(target, entry - max_move)


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


@dataclass
class TradeLevels:
    stop_levels: StopLevels
    target1: float
    target2: float
    risk_reward: float


def plan_trade_levels(
    entry: float,
    atr: float,
    levels: list[Level],
    max_holding_days: int,
    direction: str = "long",
    rr_multiples: tuple[float, float] = (1.5, 3.0),
    target_volatility_multiplier: float = 1.5,
    allow_tight_structure_stop: bool = False,
) -> TradeLevels | None:
    """The full stop/target/R:R pipeline shared by the live scanner and the
    backtest: ATR+structure stop, then the further of a fixed-R:R target or the
    nearest structure level, both capped to what's realistically reachable within
    `max_holding_days` (see `cap_target_to_horizon`). Returns None only when the
    resulting risk is zero/invalid (division-by-zero guard)."""
    stop_levels = compute_stop(entry, atr, levels, direction=direction, allow_tight_structure_stop=allow_tight_structure_stop)
    structure_target = nearest_structure_target(entry, levels, direction=direction)
    rr_targets = compute_rr_targets(entry, stop_levels.final_stop, direction=direction, rr_multiples=rr_multiples)
    target1 = rr_targets[0].price
    target2 = structure_target.price if structure_target and structure_target.price > target1 else rr_targets[1].price

    target1 = cap_target_to_horizon(entry, target1, atr, max_holding_days, direction=direction, volatility_multiplier=target_volatility_multiplier)
    target2 = cap_target_to_horizon(entry, target2, atr, max_holding_days, direction=direction, volatility_multiplier=target_volatility_multiplier)
    target2 = max(target2, target1) if direction == "long" else min(target2, target1)

    try:
        rr = risk_reward_ratio(entry, stop_levels.final_stop, target2)
    except ValueError:
        return None
    return TradeLevels(stop_levels=stop_levels, target1=target1, target2=target2, risk_reward=rr)
