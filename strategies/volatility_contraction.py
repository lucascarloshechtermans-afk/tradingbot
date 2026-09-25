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
    version's expectancy negative.

    Re-validated across three separate 5-year, 102-ticker backtests since: it
    fires extremely rarely (26-31 trades total each time, vs. hundreds-to-
    thousands for every other strategy) and its expectancy sign FLIPPED between
    runs (+0.52%, +0.40%, +0.39%, then -0.05%) despite only small, unrelated
    changes elsewhere in the codebase — a textbook symptom of a sample too small
    to estimate a real edge from. `tradeable = False` below means it can still
    fire, appear in reasons, and contribute to the price-action score as
    confirmation, but is never picked as the primary setup that drives entry —
    exactly the "not enough data to trust alone" situation this flag exists for.
    """

    name = "Volatility Contraction"
    # Re-tested against the widened 136-ticker universe (up from 102): still
    # only 44 trades, and expectancy flipped negative again (-0.37%, having
    # been +0.52%/+0.40%/+0.39%/-0.05% across the four prior tests on the
    # smaller universe). Confirms the sample-size problem isn't fixed by a
    # wider universe -- this setup is just genuinely rare. Back to
    # tradeable=False.
    tradeable = False

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
