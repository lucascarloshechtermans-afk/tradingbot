from __future__ import annotations

import pandas as pd

from strategies.base import Strategy, StrategySignal
from strategies.context import TickerContext


class EpisodicPivotStrategy(Strategy):
    """Qullamaggie-style "episodic pivot": a large, catalyst-sized gap up (well
    beyond routine daily noise) on well-above-average volume, holding above the
    gap rather than filling it back down -- the market re-rating a stock's
    expected value in one move, typically on an earnings beat/guide-up, FDA
    approval, contract win, or similar. Distinct from BreakoutStrategy, which is
    a purely technical volume/price-structure signal with no notion of a
    size-of-move "this was a real catalyst" threshold -- a routine 2% breakout
    gap and an 8%+ catalyst gap are treated identically there.

    New, unvalidated: added to test the hypothesis directly (see the "n_trades"
    and expectancy for this strategy in the next backtest run) rather than
    assumed to help just because well-known traders use something like it.
    """

    name = "Episodic Pivot"

    MIN_GAP_PCT = 8.0
    MIN_RVOL = 2.0

    def evaluate(self, ctx: TickerContext) -> StrategySignal:
        reasons: list[str] = []
        risks: list[str] = []

        history = ctx.history
        if len(history) < 2:
            return StrategySignal(strategy=self.name, matched=False, confidence=0.0)

        prev_close = history["close"].iloc[-2]
        today_open = history["open"].iloc[-1]
        if prev_close <= 0:
            return StrategySignal(strategy=self.name, matched=False, confidence=0.0)
        gap_pct = (today_open - prev_close) / prev_close * 100

        big_catalyst_gap = gap_pct >= self.MIN_GAP_PCT
        high_volume = pd.notna(ctx.rvol.iloc[-1]) and ctx.rvol.iloc[-1] >= self.MIN_RVOL
        # Holding the gap, not filling it back down through the pre-gap close --
        # a gap that's already been filled on the entry day itself is a strong
        # sign the move has already failed. (No separate "not already extended"
        # gate: ctx.overextension is computed AS OF today's bar, so a genuine
        # catalyst gap will always trip an ATR-distance overextension check by
        # construction -- that would reject every real episodic pivot, not just
        # chased ones. The gap-size risk note below covers this instead.)
        holding_gap = history["low"].iloc[-1] > prev_close

        matched = bool(big_catalyst_gap and high_volume and holding_gap)
        if not matched:
            return StrategySignal(strategy=self.name, matched=False, confidence=0.0)

        confidence = 45.0
        reasons.append(f"Catalyst-sized gap up: +{gap_pct:.1f}% on {ctx.rvol.iloc[-1]:.1f}x volume")
        reasons.append("Holding above the gap, not filling it back down")
        confidence += 25

        if ctx.trend.iloc[-1] == "bullish":
            reasons.append("Already in a confirmed uptrend before the gap")
            confidence += 15
        else:
            risks.append("Gap occurred outside an already-confirmed uptrend")

        if gap_pct >= 15.0:
            risks.append(
                f"Very large gap (+{gap_pct:.1f}%) — higher reversal/fade risk than a smaller catalyst gap"
            )

        risks.append(
            "A single-day catalyst gap can be a blow-off top as easily as a genuine "
            "re-rating — direction of continuation is never guaranteed"
        )

        return StrategySignal(
            strategy=self.name,
            matched=True,
            confidence=max(0.0, min(confidence, 100.0)),
            reasons=reasons,
            risks=risks,
        )
