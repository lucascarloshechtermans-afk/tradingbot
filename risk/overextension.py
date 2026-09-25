from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from indicators.volatility import distance_in_atr

STRETCHED_THRESHOLD_ATR = 3.0
SEVERE_REFERENCE_COUNT = 3  # how many independent references must agree before calling it "severe"


@dataclass
class OverextensionProfile:
    distance_from_ema8_atr: float | None
    distance_from_ema21_atr: float | None
    distance_from_ema50_atr: float | None
    distance_from_vwap_atr: float | None
    distance_from_swing_low_atr: float | None
    gain_1d_pct: float | None
    gain_3d_pct: float | None
    gain_5d_pct: float | None
    gain_20d_pct: float | None
    stretched_reference_count: int
    is_severely_overextended: bool
    reasons: list[str] = field(default_factory=list)


def _pct_gain(close: pd.Series, days: int) -> float | None:
    if len(close) <= days:
        return None
    then = close.iloc[-1 - days]
    if pd.isna(then) or then == 0:
        return None
    return float((close.iloc[-1] / then - 1) * 100)


def compute_overextension(
    close: pd.Series,
    last_close: float,
    atr_value: float,
    ema8: float | None,
    ema21: float | None,
    ema50: float | None,
    vwap: float | None,
    swing_low: float | None,
    stretched_threshold_atr: float = STRETCHED_THRESHOLD_ATR,
) -> OverextensionProfile:
    """A bullish stock isn't automatically a good NEW entry — this checks how far
    price has stretched from several independent references at once (each EMA,
    VWAP, and the most recent swing low), plus raw % gain over several windows.
    Deliberately checks MULTIPLE references rather than just one (the existing
    `extension_atr` / EMA21-only check in TickerContext): a stock can look calm
    relative to its EMA21 while still being wildly extended from its most recent
    swing low, or vice versa — agreement across references is a much stronger
    signal that a move is genuinely overextended than any single distance alone,
    consistent with how confluence is used everywhere else in this scanner.
    """
    references = {"EMA8": ema8, "EMA21": ema21, "EMA50": ema50, "VWAP": vwap, "recent swing low": swing_low}
    distances: dict[str, float | None] = {}
    stretched: list[str] = []

    for name, ref in references.items():
        if ref is None or pd.isna(ref) or ref <= 0 or pd.isna(atr_value) or atr_value <= 0:
            distances[name] = None
            continue
        dist = distance_in_atr(last_close, ref, atr_value)
        distances[name] = dist
        if pd.notna(dist) and dist >= stretched_threshold_atr:
            stretched.append(name)

    reasons: list[str] = []
    if stretched:
        reasons.append(
            f"Stretched >= {stretched_threshold_atr:g} ATRs from {len(stretched)} reference(s): {', '.join(stretched)}"
        )

    is_severe = len(stretched) >= SEVERE_REFERENCE_COUNT
    if is_severe:
        reasons.append("Multiple independent references agree the move is extended — a fresh entry here chases a stretched price, not a fresh setup")

    gain_1d = _pct_gain(close, 1)
    gain_3d = _pct_gain(close, 3)
    gain_5d = _pct_gain(close, 5)
    gain_20d = _pct_gain(close, 20)
    if gain_5d is not None:
        reasons.append(f"1D/3D/5D/20D gain: {gain_1d:+.1f}% / {gain_3d:+.1f}% / {gain_5d:+.1f}% / {gain_20d:+.1f}%" if all(g is not None for g in (gain_1d, gain_3d, gain_20d)) else f"5D gain {gain_5d:+.1f}%")

    return OverextensionProfile(
        distance_from_ema8_atr=distances["EMA8"],
        distance_from_ema21_atr=distances["EMA21"],
        distance_from_ema50_atr=distances["EMA50"],
        distance_from_vwap_atr=distances["VWAP"],
        distance_from_swing_low_atr=distances["recent swing low"],
        gain_1d_pct=gain_1d,
        gain_3d_pct=gain_3d,
        gain_5d_pct=gain_5d,
        gain_20d_pct=gain_20d,
        stretched_reference_count=len(stretched),
        is_severely_overextended=is_severe,
        reasons=reasons,
    )
