from tests.helpers import (
    breakout_history,
    context_from,
    downtrend_oversold_history,
    flat_history,
    mean_reversion_history,
    momentum_continuation_history,
    pullback_history,
    support_bounce_history,
    volatility_contraction_history,
    zigzag_uptrend_history,
)
from strategies.base import StrategySignal
from strategies.breakout import BreakoutStrategy
from strategies.mean_reversion import MeanReversionStrategy
from strategies.momentum_continuation import MomentumContinuationStrategy
from strategies.pullback import PullbackStrategy
from strategies.support_bounce import SupportBounceStrategy
from strategies.trend_continuation import TrendContinuationStrategy
from strategies.volatility_contraction import VolatilityContractionStrategy


def test_breakout_matches_on_confirmed_breakout_with_volume():
    ctx = context_from(breakout_history())
    signal = BreakoutStrategy().evaluate(ctx)
    assert signal.matched is True
    assert signal.confidence > 0
    assert len(signal.reasons) > 0


def test_breakout_does_not_match_flat_market():
    ctx = context_from(flat_history())
    signal = BreakoutStrategy().evaluate(ctx)
    assert signal.matched is False
    assert signal.confidence == 0.0
    assert signal.reasons == []


def test_pullback_matches_on_healthy_dip_in_uptrend():
    ctx = context_from(pullback_history())
    signal = PullbackStrategy().evaluate(ctx)
    assert signal.matched is True
    assert any("EMA21" in r for r in signal.reasons)


def test_pullback_does_not_match_flat_market():
    ctx = context_from(flat_history())
    signal = PullbackStrategy().evaluate(ctx)
    assert signal.matched is False


def test_trend_continuation_matches_on_paused_uptrend():
    ctx = context_from(zigzag_uptrend_history(n=240))
    signal = TrendContinuationStrategy().evaluate(ctx)
    assert signal.matched is True
    assert any("trend" in r.lower() for r in signal.reasons)


def test_trend_continuation_does_not_match_flat_market():
    ctx = context_from(flat_history())
    signal = TrendContinuationStrategy().evaluate(ctx)
    assert signal.matched is False


def test_support_bounce_matches_on_repeated_level_touch():
    ctx = context_from(support_bounce_history())
    signal = SupportBounceStrategy().evaluate(ctx)
    assert signal.matched is True
    assert "130" in signal.reasons[0]


def test_support_bounce_does_not_match_without_levels():
    ctx = context_from(flat_history())
    signal = SupportBounceStrategy().evaluate(ctx)
    assert signal.matched is False


def test_momentum_continuation_matches_on_broadening_momentum():
    ctx = context_from(momentum_continuation_history())
    signal = MomentumContinuationStrategy().evaluate(ctx)
    assert signal.matched is True
    assert any("RSI" in r for r in signal.reasons)


def test_momentum_continuation_does_not_match_flat_market():
    ctx = context_from(flat_history())
    signal = MomentumContinuationStrategy().evaluate(ctx)
    assert signal.matched is False


def test_momentum_continuation_rejects_thin_volume():
    import pandas as pd
    from dataclasses import replace

    ctx = context_from(momentum_continuation_history())
    signal = MomentumContinuationStrategy().evaluate(ctx)
    assert signal.matched is True  # sanity: the base fixture matches

    thin = replace(ctx, rvol=pd.Series(0.3, index=ctx.rvol.index))
    thin_signal = MomentumContinuationStrategy().evaluate(thin)
    assert thin_signal.matched is False


def test_momentum_continuation_rejects_near_zero_roc():
    from dataclasses import replace

    ctx = context_from(momentum_continuation_history())
    # flatten the close column entirely so 20d ROC is ~0, via a modified history
    # frame (close is a derived property, not a settable field, so replace()
    # has to go through `history`) — other precomputed fields (rsi14, macd_hist,
    # rvol) stay from the original fixture, isolating just the ROC-magnitude gate.
    flat_history = ctx.history.copy()
    flat_history["close"] = ctx.last_close
    negligible_roc = replace(ctx, history=flat_history)
    signal = MomentumContinuationStrategy().evaluate(negligible_roc)
    assert signal.matched is False


def test_mean_reversion_matches_on_oversold_dip_in_uptrend():
    ctx = context_from(mean_reversion_history())
    signal = MeanReversionStrategy().evaluate(ctx)
    assert signal.matched is True
    assert any("oversold" in r.lower() for r in signal.reasons)


def test_mean_reversion_does_not_match_flat_market():
    ctx = context_from(flat_history())
    signal = MeanReversionStrategy().evaluate(ctx)
    assert signal.matched is False


def test_mean_reversion_does_not_match_downtrend():
    # oversold but in a longer-term DOWNtrend -> should not match (avoids catching
    # a falling knife just because RSI is low)
    ctx = context_from(downtrend_oversold_history())
    signal = MeanReversionStrategy().evaluate(ctx)
    assert signal.matched is False


def test_volatility_contraction_matches_on_squeeze_in_uptrend():
    ctx = context_from(volatility_contraction_history())
    signal = VolatilityContractionStrategy().evaluate(ctx)
    assert signal.matched is True
    assert any("squeeze" in r.lower() for r in signal.reasons)


def test_volatility_contraction_does_not_match_trending_market():
    ctx = context_from(zigzag_uptrend_history(n=240))
    signal = VolatilityContractionStrategy().evaluate(ctx)
    assert signal.matched is False


def test_all_strategies_are_registered():
    from strategies import ALL_STRATEGIES

    assert len(ALL_STRATEGIES) == 7
    names = {s.name for s in ALL_STRATEGIES}
    assert len(names) == 7  # all distinct


def test_volatility_contraction_is_tradeable_after_vcp_rework():
    # re-enabled (tradeable=True, the base-class default) after adding VCP-style
    # preconditions (prior momentum + real volume dry-up) meant to fix the
    # negative expectancy the bare-squeeze version showed in backtesting
    assert VolatilityContractionStrategy().tradeable is True


def test_best_tradeable_signal_ignores_untradeable_strategies():
    from strategies import best_tradeable_signal

    class FakeUntradeable:
        tradeable = False

    signals = [
        StrategySignal(strategy="Fake Untradeable", matched=True, confidence=99.0),
        StrategySignal(strategy="Bullish Breakout", matched=True, confidence=10.0),
    ]
    best = best_tradeable_signal(signals)
    assert best is not None
    assert best.strategy == "Bullish Breakout"


def test_best_tradeable_signal_returns_none_when_nothing_matched():
    from strategies import best_tradeable_signal

    assert best_tradeable_signal([]) is None
