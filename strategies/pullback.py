from __future__ import annotations

import pandas as pd

from price_action.patterns import is_pullback_to_ma
from strategies.base import Strategy, StrategySignal
from strategies.context import TickerContext


class PullbackStrategy(Strategy):
    """Buy-the-dip in an established uptrend: price pulls back to a moving average
    (EMA21) without breaking trend structure, RSI cools off without crashing."""

    name = "Bullish Pullback"

    def __init__(self, tolerance_pct: float = 1.5):
        self.tolerance_pct = tolerance_pct

    def evaluate(self, ctx: TickerContext) -> StrategySignal:
        reasons: list[str] = []
        risks: list[str] = []

        uptrend = (
            pd.notna(ctx.sma200.iloc[-1])
            and ctx.last_close > ctx.sma50.iloc[-1] > ctx.sma200.iloc[-1]
        )
        pullback = is_pullback_to_ma(ctx.close, ctx.ema21, tolerance_pct=self.tolerance_pct)
        rsi_cooled = 35 <= ctx.rsi14.iloc[-1] <= 58

        matched = bool(uptrend and pullback and rsi_cooled)
        if not matched:
            return StrategySignal(strategy=self.name, matched=False, confidence=0.0)

        confidence = 50.0
        reasons.append("Above 50/200 SMA (established uptrend)")
        reasons.append(f"Pulled back to EMA21 (within {self.tolerance_pct}%)")
        reasons.append(f"RSI cooled to {ctx.rsi14.iloc[-1]:.0f} without breaking down")
        confidence += 20

        if ctx.structure == "higher_highs_higher_lows":
            reasons.append("Market structure: higher highs, higher lows")
            confidence += 15
        elif ctx.structure == "lower_highs_lower_lows":
            risks.append("Swing structure has turned to lower highs/lower lows")
            confidence -= 15

        if ctx.bullish_rsi_divergence:
            reasons.append("Bullish RSI divergence at recent swing low")
            confidence += 10

        support = next((lv for lv in ctx.levels if lv.kind == "support" and lv.price <= ctx.last_close), None)
        if support:
            dist_pct = (ctx.last_close - support.price) / support.price * 100
            if dist_pct < 3:
                reasons.append(f"Near support at {support.price:.2f} ({support.touches} touches)")
                confidence += 10

        if ctx.rvol.iloc[-1] > 1.8:
            risks.append(f"Elevated volume ({ctx.rvol.iloc[-1]:.1f}x) on the pullback — watch for distribution")

        return StrategySignal(
            strategy=self.name,
            matched=True,
            confidence=max(0.0, min(confidence, 100.0)),
            reasons=reasons,
            risks=risks,
        )
