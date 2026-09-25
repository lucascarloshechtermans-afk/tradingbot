from __future__ import annotations

import pandas as pd

from price_action.patterns import is_support_bounce
from strategies.base import Strategy, StrategySignal
from strategies.context import TickerContext


class SupportBounceStrategy(Strategy):
    name = "Support Bounce"
    counter_trend = True

    def __init__(self, tolerance_pct: float = 1.5, min_touches: int = 3):
        self.tolerance_pct = tolerance_pct
        self.min_touches = min_touches

    def evaluate(self, ctx: TickerContext) -> StrategySignal:
        reasons: list[str] = []
        risks: list[str] = []

        bounce = is_support_bounce(ctx.low, ctx.close, ctx.levels, tolerance_pct=self.tolerance_pct)
        support = next(
            (lv for lv in ctx.levels if lv.kind == "support" and abs(lv.price - ctx.last_close) / ctx.last_close * 100 <= 5),
            None,
        )
        not_overbought = ctx.rsi14.iloc[-1] < 70
        # This strategy had the highest trade count and lowest win rate of the 7
        # in backtesting (still net positive on R:R asymmetry alone) — a light
        # volume floor filters out bounces happening on abnormally thin
        # participation, which is a weaker signal of real buying interest than a
        # bounce most traders are actually watching and acting on.
        not_on_dead_volume = pd.notna(ctx.rvol.iloc[-1]) and ctx.rvol.iloc[-1] >= 0.8
        # A bounce off support during an established BEARISH longer-term trend is
        # much more likely to be a falling knife than a genuine reversal — this
        # was previously only a confidence penalty (risk note), letting the
        # strategy match anyway. Mean Reversion already requires the equivalent
        # (price above SMA200) as a hard condition for exactly this reason;
        # Support Bounce didn't, and had the worst loss rate of the 7 strategies
        # in backtesting. min_touches raised 2->3 for the same reason: a level
        # tested only twice is a much weaker claim of real support than one
        # tested three-plus times.
        not_established_downtrend = ctx.trend.iloc[-1] != "bearish"

        matched = bool(
            bounce and support and support.touches >= self.min_touches
            and not_overbought and not_on_dead_volume and not_established_downtrend
        )
        if not matched:
            return StrategySignal(strategy=self.name, matched=False, confidence=0.0)

        confidence = 40.0
        reasons.append(f"Bounced off support at {support.price:.2f} ({support.touches} prior touches)")
        confidence += min(support.touches * 8, 30)

        if ctx.rsi14.iloc[-1] < 40:
            reasons.append(f"RSI {ctx.rsi14.iloc[-1]:.0f} — room to run before overbought")
            confidence += 10

        if ctx.bullish_rsi_divergence:
            reasons.append("Bullish RSI divergence at this support test")
            confidence += 15

        if ctx.rvol.iloc[-1] > 1.3:
            reasons.append(f"Above-average volume on the bounce ({ctx.rvol.iloc[-1]:.1f}x)")
            confidence += 10
        else:
            risks.append("Bounce lacks volume confirmation so far")

        return StrategySignal(
            strategy=self.name,
            matched=True,
            confidence=max(0.0, min(confidence, 100.0)),
            reasons=reasons,
            risks=risks,
        )
