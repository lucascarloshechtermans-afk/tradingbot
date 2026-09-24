from __future__ import annotations

import pandas as pd

from strategies.base import Strategy, StrategySignal
from strategies.context import TickerContext


class MeanReversionStrategy(Strategy):
    """Short-term oversold bounce WITHIN a longer-term uptrend — a stretched pullback
    (RSI deeply oversold, price at/below the lower Bollinger Band) that is likely to
    revert toward the mean rather than the start of a new downtrend. The long-term
    trend filter (price above SMA200) exists specifically to avoid buying a falling
    knife in an actual downtrend.
    """

    name = "Mean Reversion"

    def evaluate(self, ctx: TickerContext) -> StrategySignal:
        reasons: list[str] = []
        risks: list[str] = []

        long_term_uptrend = pd.notna(ctx.sma200.iloc[-1]) and ctx.last_close > ctx.sma200.iloc[-1]
        oversold = ctx.rsi14.iloc[-1] < 30
        at_lower_band = pd.notna(ctx.bb_lower.iloc[-1]) and ctx.close.iloc[-1] <= ctx.bb_lower.iloc[-1] * 1.01

        matched = bool(long_term_uptrend and oversold and at_lower_band)
        if not matched:
            return StrategySignal(strategy=self.name, matched=False, confidence=0.0)

        confidence = 40.0
        reasons.append("Price above 200-day SMA (long-term uptrend intact)")
        reasons.append(f"RSI deeply oversold at {ctx.rsi14.iloc[-1]:.0f}")
        reasons.append("Price at/below the lower Bollinger Band")
        confidence += 20

        if ctx.bullish_rsi_divergence:
            reasons.append("Bullish RSI divergence supports a reversion bounce")
            confidence += 15

        if ctx.rsi14.iloc[-1] < 20:
            risks.append("RSI below 20 — extreme readings can stay extreme, no guaranteed bounce")

        if ctx.atr_pct.iloc[-1] > 6:
            risks.append(f"High ATR ({ctx.atr_pct.iloc[-1]:.1f}%) — reversion trades are volatile by nature")
            confidence -= 10

        if ctx.rvol.iloc[-1] > 2.0:
            risks.append(f"Heavy selling volume ({ctx.rvol.iloc[-1]:.1f}x) — possible capitulation, not just a dip")

        return StrategySignal(
            strategy=self.name,
            matched=True,
            confidence=max(0.0, min(confidence, 100.0)),
            reasons=reasons,
            risks=risks,
        )
