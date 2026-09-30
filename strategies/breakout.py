from __future__ import annotations

import pandas as pd

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

        # A close breaking today's N-day high isn't automatically a strong
        # breakout — check the bigger historical picture too, since a 20-day
        # high can sit well below a much more significant ceiling.
        hist_ctx = ctx.historical_context
        if hist_ctx is not None:
            if hist_ctx.is_fresh_52w_high:
                reasons.append("Breaking out to a fresh 52-week high — no overhead supply from the past year")
                confidence += 12
            overhead = hist_ctx.major_resistance_overhead
            if overhead is not None:
                dist_pct = (overhead.price - ctx.last_close) / ctx.last_close * 100
                if dist_pct < 5 and overhead.touches >= 2:
                    risks.append(
                        f"A stronger historical resistance sits {dist_pct:.1f}% above at ${overhead.price:.2f} "
                        f"({overhead.touches} prior touches) — this may be a local breakout, not a break of the bigger ceiling"
                    )
                    confidence -= 12

        if ctx.atr_pct.iloc[-1] > 6:
            risks.append(f"ATR high ({ctx.atr_pct.iloc[-1]:.1f}% of price) — wide expected swings")

        # Late-entry / chase penalty (item 15 of the optimization audit): a
        # breakout that already gapped/ran several ATRs past its OWN trigger
        # level is a materially worse entry than one still close to it, even
        # when both still pass `is_breakout` -- catches the classic "huge gap
        # day, already extended" chase that a generic EMA21-relative extension
        # check can miss (EMA21 hasn't caught up yet the same day). NOTE, an
        # honestly-documented limitation found while testing this: because
        # `breakout_level` is recomputed fresh from the same trailing window
        # `is_breakout` itself uses, a slow multi-day grind (each day sets a
        # marginal new high) keeps re-anchoring the "trigger" to just behind
        # itself, understating how far price has drifted from where the move
        # actually started -- this penalty is real but narrower than "catches
        # every late entry": it reliably catches a single/few-bar extended
        # gap, not a creeping multi-day chase.
        breakout_level = ctx.high.iloc[-(self.lookback + 1):-1].max()
        atr_now = ctx.atr14.iloc[-1]
        if pd.notna(breakout_level) and pd.notna(atr_now) and atr_now > 0:
            atr_above_level = (ctx.last_close - breakout_level) / atr_now
            if atr_above_level > 2.5:
                risks.append(
                    f"Price is {atr_above_level:.1f} ATRs above its own breakout trigger "
                    f"(${breakout_level:.2f}) — this chases an already-extended move, not a fresh break"
                )
                confidence -= 15
            elif atr_above_level > 1.5:
                risks.append(f"Price is {atr_above_level:.1f} ATRs above its own breakout trigger — somewhat extended")
                confidence -= 6
            elif atr_above_level <= 0.5:
                reasons.append("Still within 0.5 ATR of the breakout trigger — a fresh entry, not a chase")
                confidence += 5

        return StrategySignal(
            strategy=self.name,
            matched=True,
            confidence=max(0.0, min(confidence, 100.0)),
            reasons=reasons,
            risks=risks,
        )
