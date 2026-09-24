from __future__ import annotations

import pandas as pd

from strategies.base import Strategy, StrategySignal
from strategies.context import TickerContext


class VolatilityContractionStrategy(Strategy):
    """A Bollinger Band squeeze (volatility contraction) within an uptrend — a
    "setup forming" signal flagging a likely upcoming expansion move, rather than
    an immediate breakout (that's BreakoutStrategy's job once it actually triggers).
    """

    name = "Volatility Contraction"

    def evaluate(self, ctx: TickerContext) -> StrategySignal:
        reasons: list[str] = []
        risks: list[str] = []

        squeezing = bool(ctx.squeeze.iloc[-1]) if pd.notna(ctx.squeeze.iloc[-1]) else False
        uptrend_bias = ctx.last_close > ctx.sma50.iloc[-1] if pd.notna(ctx.sma50.iloc[-1]) else False
        low_adx = ctx.adx14.iloc[-1] < 25 if pd.notna(ctx.adx14.iloc[-1]) else False

        matched = bool(squeezing and uptrend_bias and low_adx)
        if not matched:
            return StrategySignal(strategy=self.name, matched=False, confidence=0.0)

        confidence = 35.0
        reasons.append(f"Bollinger Band width near a {120}-day low — volatility squeeze")
        reasons.append("Price above 50-day SMA — bullish bias while coiling")
        reasons.append(f"ADX {ctx.adx14.iloc[-1]:.0f} — not yet trending, energy building")
        confidence += 20

        if ctx.rvol.iloc[-1] < 0.8:
            reasons.append("Volume drying up — classic pre-breakout contraction")
            confidence += 10
        else:
            risks.append("Volume not yet contracting alongside price")

        risks.append("Direction of the eventual breakout is not guaranteed — this is a watchlist signal")

        return StrategySignal(
            strategy=self.name,
            matched=True,
            confidence=max(0.0, min(confidence, 100.0)),
            reasons=reasons,
            risks=risks,
        )
