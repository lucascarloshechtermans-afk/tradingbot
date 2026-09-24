from __future__ import annotations

from indicators.momentum import roc
from strategies.base import Strategy, StrategySignal
from strategies.context import TickerContext


class MomentumContinuationStrategy(Strategy):
    """Momentum that is persisting and broadening: RSI trending up through 50,
    MACD histogram positive and expanding, and positive returns across multiple
    lookback windows (not just a one-day spike)."""

    name = "Momentum Continuation"

    def evaluate(self, ctx: TickerContext) -> StrategySignal:
        reasons: list[str] = []
        risks: list[str] = []

        rsi_rising = ctx.rsi14.iloc[-1] > ctx.rsi14.iloc[-5] and ctx.rsi14.iloc[-1] > 50
        macd_expanding = ctx.macd_hist.iloc[-1] > 0 and ctx.macd_hist.iloc[-1] > ctx.macd_hist.iloc[-3]

        roc_5 = roc(ctx.close, 5).iloc[-1]
        roc_10 = roc(ctx.close, 10).iloc[-1]
        roc_20 = roc(ctx.close, 20).iloc[-1]
        broad_momentum = roc_5 > 0 and roc_10 > 0 and roc_20 > 0

        matched = bool(rsi_rising and macd_expanding and broad_momentum)
        if not matched:
            return StrategySignal(strategy=self.name, matched=False, confidence=0.0)

        confidence = 45.0
        reasons.append(f"RSI rising through {ctx.rsi14.iloc[-1]:.0f}")
        reasons.append("MACD histogram positive and expanding")
        reasons.append(f"Positive momentum across 5/10/20-day windows ({roc_5:.1f}% / {roc_10:.1f}% / {roc_20:.1f}%)")
        confidence += 25

        if ctx.rvol.iloc[-1] > 1.2:
            reasons.append(f"Volume supporting the move ({ctx.rvol.iloc[-1]:.1f}x)")
            confidence += 10

        if ctx.rsi14.iloc[-1] > 80:
            risks.append(f"RSI {ctx.rsi14.iloc[-1]:.0f} is deeply overbought — extended")
            confidence -= 15
        elif ctx.rsi14.iloc[-1] > 70:
            risks.append(f"RSI {ctx.rsi14.iloc[-1]:.0f} is overbought")
            confidence -= 5

        if ctx.bearish_rsi_divergence:
            risks.append("Bearish RSI divergence present — momentum may be fading")
            confidence -= 15

        return StrategySignal(
            strategy=self.name,
            matched=True,
            confidence=max(0.0, min(confidence, 100.0)),
            reasons=reasons,
            risks=risks,
        )
