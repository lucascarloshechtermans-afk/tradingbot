from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
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


BLOCKED_REGIME_LABELS = ("BEARISH", "HIGH_VOLATILITY")


def classify_market_regime_series(spy: pd.DataFrame, qqq: pd.DataFrame, iwm: pd.DataFrame, vix: pd.DataFrame) -> pd.Series:
    """Walk-forward version of `classify_market_regime`: the regime label at
    EVERY historical date, computed from data through that date only (sma/roc are
    strictly trailing, so nothing here looks ahead). Used to gate backtest entries
    on "was the market actually in a tradeable regime on this date" rather than
    only checking today's regime once, as the live scanner does.

    Simplification vs. `classify_market_regime`: breadth (% of the scanned
    universe above its 50MA) is left out here, since it would require every
    ticker's full history aligned and recomputed at every date — a large extra
    cost for one of eight factors. SPY/QQQ/IWM trend + VIX still capture the core
    "is this a market environment worth trading in" question.
    """
    spy_close = spy["close"]
    idx = spy_close.index
    spy_sma50 = sma(spy_close, 50)
    spy_sma200 = sma(spy_close, 200)

    bull = pd.Series(0.0, index=idx)
    bear = pd.Series(0.0, index=idx)
    total = pd.Series(0.0, index=idx)

    has_sma200 = spy_sma200.notna()
    total += has_sma200.astype(float) * 2
    bull += (has_sma200 & (spy_close > spy_sma50) & (spy_sma50 > spy_sma200)).astype(float) * 2
    bear += (has_sma200 & (spy_close < spy_sma50) & (spy_sma50 < spy_sma200)).astype(float) * 2

    mom = roc(spy_close, 20)
    has_mom = mom.notna()
    total += has_mom.astype(float)
    bull += (has_mom & (mom > 0)).astype(float)
    bear += (has_mom & (mom < 0)).astype(float)

    vix_close = vix["close"].reindex(idx).ffill()
    high_vol = vix_close >= VIX_HIGH_VOLATILITY_THRESHOLD
    not_high_vol_and_known = vix_close.notna() & ~high_vol
    total += not_high_vol_and_known.astype(float)
    bull += (not_high_vol_and_known & (vix_close < VIX_LOW_THRESHOLD)).astype(float)
    bear += (not_high_vol_and_known & (vix_close >= VIX_ELEVATED_THRESHOLD)).astype(float)

    for df in (qqq, iwm):
        c = df["close"].reindex(idx).ffill()
        s50 = sma(c, 50)
        has_s50 = s50.notna() & c.notna()
        total += has_s50.astype(float) * 0.5
        bull += (has_s50 & (c > s50)).astype(float) * 0.5
        bear += (has_s50 & (c < s50)).astype(float) * 0.5

    score = (bull - bear) / total.replace(0, np.nan) * 100

    label = pd.Series("NEUTRAL", index=idx)
    label[score >= REGIME_SCORE_BULLISH] = "BULLISH"
    label[score <= REGIME_SCORE_BEARISH] = "BEARISH"
    label[total == 0] = "NEUTRAL"
    label[high_vol.fillna(False)] = "HIGH_VOLATILITY"
    return label
