from __future__ import annotations

import pandas as pd

from strategies.base import Strategy, StrategySignal
from strategies.context import TickerContext


class VolatilityContractionStrategy(Strategy):
    """A VCP-style ("Volatility Contraction Pattern") setup: a genuine prior
    momentum move that then consolidates in an orderly, tightening range with
    volume drying up — the classic Minervini/Qullamaggie precondition for a
    continuation breakout.

    This replaces an earlier version that only checked for a bare Bollinger
    squeeze. A 5-year, 102-ticker backtest showed that version was the only
    net-losing strategy of the 7 (-0.22%/trade): a squeeze alone says nothing
    about WHY volatility is contracting, and literature on squeeze breakouts
    generally shows only ~55-60% win rate with real whipsaw risk. Requiring an
    actual prior move AND real volume dry-up (not just low RVOL on one day) is
    meant to filter out the low-quality squeezes that were dragging the original
    version's expectancy negative — re-validate with a fresh backtest before
    trusting this version any more than the last.
    """

    name = "Volatility Contraction"

    def evaluate(self, ctx: TickerContext) -> StrategySignal:
        reasons: list[str] = []
        risks: list[str] = []

        squeezing = bool(ctx.squeeze.iloc[-1]) if pd.notna(ctx.squeeze.iloc[-1]) else False
        uptrend_bias = ctx.last_close > ctx.sma50.iloc[-1] if pd.notna(ctx.sma50.iloc[-1]) else False
        low_adx = ctx.adx14.iloc[-1] < 25 if pd.notna(ctx.adx14.iloc[-1]) else False

        # 90-day (roughly one quarter) lookback rather than a tighter window: a
        # real VCP consolidation can run 20-50+ days, and a short lookback would
        # end up measuring the flat consolidation itself instead of the move that
        # preceded it.
        prior_momentum = False
        if len(ctx.close) > 90 and ctx.close.iloc[-90] > 0:
            prior_move_pct = (ctx.last_close / ctx.close.iloc[-90] - 1) * 100
            prior_momentum = prior_move_pct > 15

        matched = bool(squeezing and uptrend_bias and low_adx and prior_momentum and ctx.volume_drying_up)
        if not matched:
            return StrategySignal(strategy=self.name, matched=False, confidence=0.0)

        confidence = 40.0
        reasons.append(f"Prior momentum: +{prior_move_pct:.0f}% over the last ~90 days")
        reasons.append("Volume drying up during the consolidation (VCP-style, not just a quiet day)")
        reasons.append(f"Tight Bollinger squeeze, ADX {ctx.adx14.iloc[-1]:.0f} (not yet trending)")
        confidence += 25

        if ctx.bb_expanding:
            reasons.append("Volatility already expanding out of the squeeze — the move may be starting now")
            confidence += 20
        else:
            risks.append("Still inside the squeeze — timing of the eventual breakout is not guaranteed")

        if ctx.structure == "higher_highs_higher_lows":
            reasons.append("Market structure: higher highs, higher lows")
            confidence += 10

        risks.append("Direction of the breakout, if/when it comes, is never guaranteed")

        return StrategySignal(
            strategy=self.name,
            matched=True,
            confidence=max(0.0, min(confidence, 100.0)),
            reasons=reasons,
            risks=risks,
        )
