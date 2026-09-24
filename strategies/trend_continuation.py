from __future__ import annotations

import pandas as pd

from price_action.candlesticks import is_inside_bar
from strategies.base import Strategy, StrategySignal
from strategies.context import TickerContext


class TrendContinuationStrategy(Strategy):
    """An already-strong, established uptrend pauses briefly (a small consolidation
    or inside bar) rather than reversing — a continuation entry, not a fresh
    breakout or a deep pullback."""

    name = "Trend Continuation"

    def evaluate(self, ctx: TickerContext) -> StrategySignal:
        reasons: list[str] = []
        risks: list[str] = []

        strong_trend = ctx.trend.iloc[-1] == "bullish" and ctx.adx14.iloc[-1] > 25
        structure_intact = ctx.structure in ("higher_highs_higher_lows", "insufficient_data")
        pausing = is_inside_bar(ctx.high, ctx.low) or abs(ctx.close.pct_change().iloc[-1]) < 0.01

        matched = bool(strong_trend and structure_intact and pausing and ctx.structure != "insufficient_data")
        if not matched:
            return StrategySignal(strategy=self.name, matched=False, confidence=0.0)

        confidence = 45.0
        reasons.append(f"Established bullish trend, ADX {ctx.adx14.iloc[-1]:.0f}")
        reasons.append("Market structure: higher highs, higher lows")
        confidence += 20

        if is_inside_bar(ctx.high, ctx.low):
            reasons.append("Inside bar — brief pause, not a reversal")
            confidence += 10

        if ctx.plus_di.iloc[-1] > ctx.minus_di.iloc[-1]:
            reasons.append("+DI above -DI (buyers in control)")
            confidence += 10

        if pd.notna(ctx.sma20.iloc[-1]) and ctx.last_close < ctx.sma20.iloc[-1]:
            risks.append("Price dipped below the 20-day SMA during the pause")
            confidence -= 10

        if ctx.rvol.iloc[-1] < 0.7:
            risks.append(f"Low volume during pause ({ctx.rvol.iloc[-1]:.1f}x) — low conviction so far")

        return StrategySignal(
            strategy=self.name,
            matched=True,
            confidence=max(0.0, min(confidence, 100.0)),
            reasons=reasons,
            risks=risks,
        )
