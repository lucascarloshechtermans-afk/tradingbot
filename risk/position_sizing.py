from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class PositionSize:
    shares: int
    risk_amount: float
    entry: float
    stop: float
    stop_distance: float
    position_value: float
    position_pct_of_account: float
    capped_by_max_position: bool


def compute_position_size(
    entry: float,
    stop: float,
    account_size: float,
    risk_per_trade_pct: float,
    max_position_pct: float = 20.0,
) -> PositionSize:
    """Size a position so a stop-out loses exactly `risk_per_trade_pct` of the
    account (before the max-position-size cap, which can reduce that further but
    never increase it).
    """
    stop_distance = abs(entry - stop)
    if stop_distance <= 0:
        raise ValueError("stop_distance must be positive (entry and stop cannot be equal)")
    if entry <= 0:
        raise ValueError("entry must be positive")

    risk_amount = account_size * (risk_per_trade_pct / 100)
    shares = math.floor(risk_amount / stop_distance)

    position_value = shares * entry
    max_position_value = account_size * (max_position_pct / 100)
    capped = False
    if position_value > max_position_value:
        shares = math.floor(max_position_value / entry)
        position_value = shares * entry
        capped = True

    position_pct = (position_value / account_size * 100) if account_size else 0.0

    return PositionSize(
        shares=shares,
        risk_amount=risk_amount,
        entry=entry,
        stop=stop,
        stop_distance=stop_distance,
        position_value=position_value,
        position_pct_of_account=position_pct,
        capped_by_max_position=capped,
    )
