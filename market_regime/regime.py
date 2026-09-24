from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from indicators.momentum import roc
from indicators.trend import sma

VIX_HIGH_VOLATILITY_THRESHOLD = 30.0
VIX_LOW_THRESHOLD = 15.0
VIX_ELEVATED_THRESHOLD = 25.0
REGIME_SCORE_BULLISH = 30.0
REGIME_SCORE_BEARISH = -30.0


@dataclass
class MarketRegime:
    label: str  # BULLISH | NEUTRAL | BEARISH | HIGH_VOLATILITY
    score: float  # -100..100, positive = more bullish factors
    factors: dict[str, str] = field(default_factory=dict)


def classify_market_regime(
    spy: pd.DataFrame,
    qqq: pd.DataFrame,
    iwm: pd.DataFrame,
    vix: pd.DataFrame,
    breadth_pct_above_50ma: float | None = None,
) -> MarketRegime:
    """Rule-based, multi-factor market regime classification.

    Every factor is a documented, reproducible calculation on SPY/QQQ/IWM/VIX (plus
    an optional breadth figure) — never a single "magic" indicator. VIX at or above
    `VIX_HIGH_VOLATILITY_THRESHOLD` overrides everything else to HIGH_VOLATILITY,
    since in that regime trend signals become unreliable regardless of direction.
    """
    factors: dict[str, str] = {}
    bull_points = 0.0
    bear_points = 0.0
    total_points = 0.0

    spy_close = spy["close"]
    spy_sma50 = sma(spy_close, 50)
    spy_sma200 = sma(spy_close, 200)
    total_points += 2
    if pd.notna(spy_sma200.iloc[-1]) and spy_close.iloc[-1] > spy_sma50.iloc[-1] > spy_sma200.iloc[-1]:
        bull_points += 2
        factors["spy_trend"] = "bullish (price > 50MA > 200MA)"
    elif pd.notna(spy_sma200.iloc[-1]) and spy_close.iloc[-1] < spy_sma50.iloc[-1] < spy_sma200.iloc[-1]:
        bear_points += 2
        factors["spy_trend"] = "bearish (price < 50MA < 200MA)"
    else:
        factors["spy_trend"] = "mixed / insufficient history"

    total_points += 1
    mom = roc(spy_close, 20).iloc[-1]
    if pd.notna(mom):
        if mom > 0:
            bull_points += 1
            factors["spy_momentum_1m"] = f"positive ({mom:.1f}%)"
        elif mom < 0:
            bear_points += 1
            factors["spy_momentum_1m"] = f"negative ({mom:.1f}%)"
        else:
            factors["spy_momentum_1m"] = "flat (0.0%)"
    else:
        factors["spy_momentum_1m"] = "insufficient history"

    vix_last = vix["close"].iloc[-1]
    high_vol_override = bool(vix_last >= VIX_HIGH_VOLATILITY_THRESHOLD)
    if high_vol_override:
        factors["vix"] = f"elevated ({vix_last:.1f}) >= {VIX_HIGH_VOLATILITY_THRESHOLD} -> high volatility regime"
    else:
        total_points += 1
        if vix_last < VIX_LOW_THRESHOLD:
            bull_points += 1
            factors["vix"] = f"low ({vix_last:.1f}), complacent/bullish"
        elif vix_last < VIX_ELEVATED_THRESHOLD:
            factors["vix"] = f"normal ({vix_last:.1f})"
        else:
            bear_points += 1
            factors["vix"] = f"elevated ({vix_last:.1f}), cautious"

    for name, df in [("qqq", qqq), ("iwm", iwm)]:
        c = df["close"]
        s50 = sma(c, 50)
        total_points += 0.5
        if pd.isna(s50.iloc[-1]):
            factors[f"{name}_trend"] = "insufficient history"
            continue
        if c.iloc[-1] > s50.iloc[-1]:
            bull_points += 0.5
            factors[f"{name}_trend"] = "above 50MA"
        elif c.iloc[-1] < s50.iloc[-1]:
            bear_points += 0.5
            factors[f"{name}_trend"] = "below 50MA"
        else:
            factors[f"{name}_trend"] = "at 50MA"

    if breadth_pct_above_50ma is not None:
        total_points += 1
        if breadth_pct_above_50ma >= 60:
            bull_points += 1
            factors["breadth"] = f"{breadth_pct_above_50ma:.0f}% of universe above 50MA (bullish)"
        elif breadth_pct_above_50ma <= 40:
            bear_points += 1
            factors["breadth"] = f"{breadth_pct_above_50ma:.0f}% of universe above 50MA (bearish)"
        else:
            factors["breadth"] = f"{breadth_pct_above_50ma:.0f}% of universe above 50MA (neutral)"

    score = ((bull_points - bear_points) / total_points * 100) if total_points else 0.0

    if high_vol_override:
        label = "HIGH_VOLATILITY"
    elif score >= REGIME_SCORE_BULLISH:
        label = "BULLISH"
    elif score <= REGIME_SCORE_BEARISH:
        label = "BEARISH"
    else:
        label = "NEUTRAL"

    return MarketRegime(label=label, score=score, factors=factors)
