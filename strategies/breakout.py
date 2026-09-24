from __future__ import annotations

from price_action.patterns import is_breakout, has_volume_confirmation
from strategies.base import Strategy, StrategySignal
from strategies.context import TickerContext


class BreakoutStrategy(Strategy):
    name = "Bullish Breakout"

    def __init__(self, lookback: int = 20, rvol_threshold: float = 1.5):
        self.lookback = lookback
        self.rvol_threshold = rvol_threshold

    def evaluate(self, ctx: TickerContext) -> StrategySignal:
        reasons: list[str] = []
        risks: list[str] = []

        breakout = is_breakout(ctx.high, ctx.close, lookback=self.lookback)
        volume_confirmed = has_volume_confirmation(ctx.volume, rvol_threshold=self.rvol_threshold)
        trend_bullish = ctx.trend.iloc[-1] == "bullish"

        matched = bool(breakout and volume_confirmed)
        if not matched:
            return StrategySignal(strategy=self.name, matched=False, confidence=0.0)

        confidence = 50.0
        reasons.append(f"Close breaks above the prior {self.lookback}-day high")
        confidence += 15

        rvol_last = ctx.rvol.iloc[-1]
        reasons.append(f"Volume confirmation: {rvol_last:.1f}x average")
        confidence += min((rvol_last - self.rvol_threshold) * 10, 15)

        if trend_bullish:
            reasons.append("Above 20/50/200 SMA (bullish trend alignment)")
            confidence += 10
        else:
            risks.append("Breakout against a non-bullish longer-term trend")
            confidence -= 10

        if ctx.adx14.iloc[-1] > 25:
            reasons.append(f"ADX {ctx.adx14.iloc[-1]:.0f} confirms trend strength")
            confidence += 10

        nearest_resistance = next((lv for lv in ctx.levels if lv.kind == "resistance" and lv.price > ctx.last_close), None)
        if nearest_resistance and (nearest_resistance.price - ctx.last_close) / ctx.last_close * 100 < 2:
            risks.append(f"Resistance nearby at {nearest_resistance.price:.2f}")

        if ctx.atr_pct.iloc[-1] > 6:
            risks.append(f"ATR high ({ctx.atr_pct.iloc[-1]:.1f}% of price) — wide expected swings")

        return StrategySignal(
            strategy=self.name,
            matched=True,
            confidence=max(0.0, min(confidence, 100.0)),
            reasons=reasons,
            risks=risks,
        )
