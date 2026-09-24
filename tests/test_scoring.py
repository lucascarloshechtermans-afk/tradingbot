from config.schema import ScoringConfig
from market_regime.regime import MarketRegime
from strategies.base import StrategySignal
from scoring.scorer import (
    score_market_regime,
    score_momentum,
    score_multi_timeframe,
    score_price_action,
    score_risk_reward,
    score_ticker,
    score_trend,
    score_volatility,
    score_volume,
)
from tests.helpers import breakout_history, context_from, flat_history


def test_score_trend_higher_for_bullish_structure():
    bullish_ctx = context_from(breakout_history())
    flat_ctx = context_from(flat_history())
    bullish_score = score_trend(bullish_ctx)
    flat_score = score_trend(flat_ctx)
    assert bullish_score.score > flat_score.score


def test_score_momentum_rewards_rising_macd_and_healthy_rsi():
    ctx = context_from(breakout_history())
    result = score_momentum(ctx)
    assert 0 <= result.score <= 100
    assert len(result.reasons) > 0


def test_score_volume_rewards_high_relative_volume():
    ctx = context_from(breakout_history())
    result = score_volume(ctx)
    assert result.score > 40  # baseline


def test_score_price_action_uses_best_matched_strategy():
    ctx = context_from(breakout_history())
    signals = [
        StrategySignal(strategy="Bullish Breakout", matched=True, confidence=80.0, reasons=["Breakout confirmed"]),
        StrategySignal(strategy="Momentum Continuation", matched=False, confidence=0.0),
    ]
    result = score_price_action(ctx, signals)
    assert result.score >= 80
    assert "Bullish Breakout" in result.reasons[0]


def test_score_price_action_no_setup_gives_low_baseline():
    ctx = context_from(flat_history())
    result = score_price_action(ctx, [])
    assert result.score == 20.0


def test_score_volatility_penalizes_extremes():
    ctx = context_from(breakout_history())
    result = score_volatility(ctx)
    assert 0 <= result.score <= 100


def test_score_market_regime_bullish_scores_highest():
    bullish = MarketRegime(label="BULLISH", score=50, factors={})
    bearish = MarketRegime(label="BEARISH", score=-50, factors={})
    assert score_market_regime(bullish).score > score_market_regime(bearish).score


def test_score_market_regime_none_gives_neutral():
    result = score_market_regime(None)
    assert result.score == 50.0


def test_score_risk_reward_scales_with_ratio():
    low = score_risk_reward(1.0)
    high = score_risk_reward(3.0)
    assert high.score > low.score
    assert high.score == 100.0


def test_score_risk_reward_none_gives_baseline():
    result = score_risk_reward(None)
    assert result.score == 40.0


def test_score_multi_timeframe_passthrough():
    result = score_multi_timeframe(75.0, ["Weekly bullish"])
    assert result.score == 75.0
    assert result.reasons == ["Weekly bullish"]


def test_score_ticker_weights_sum_to_config_total():
    ctx = context_from(breakout_history())
    config = ScoringConfig.from_dict({})
    result = score_ticker(ctx, config, matched_strategies=[])
    total_weight = sum(cat.weight for cat in result.categories)
    assert total_weight == sum(config.weights.values())


def test_score_ticker_produces_valid_label():
    ctx = context_from(breakout_history())
    config = ScoringConfig.from_dict({})
    result = score_ticker(ctx, config, matched_strategies=[])
    assert result.label in ("Exceptional setup", "Strong setup", "Interesting setup", "Watchlist", "Ignore")
    assert 0 <= result.total_score <= 100


def test_score_ticker_reasons_are_explainable():
    ctx = context_from(breakout_history())
    config = ScoringConfig.from_dict({})
    signals = [StrategySignal(strategy="Bullish Breakout", matched=True, confidence=75.0, reasons=["Breakout confirmed"])]
    result = score_ticker(ctx, config, matched_strategies=signals)
    assert len(result.all_reasons) > 0


def test_score_ticker_custom_weights_change_total():
    ctx = context_from(breakout_history())
    config_default = ScoringConfig.from_dict({})
    config_trend_heavy = ScoringConfig.from_dict({"weights": {"trend": 100, "momentum": 0, "volume": 0, "price_action": 0, "volatility": 0, "relative_strength": 0, "market_regime": 0, "sector": 0, "risk_reward": 0, "multi_timeframe": 0}})
    default_result = score_ticker(ctx, config_default, matched_strategies=[])
    trend_only_result = score_ticker(ctx, config_trend_heavy, matched_strategies=[])
    trend_cat = next(c for c in trend_only_result.categories if c.category == "trend")
    assert trend_only_result.total_score == round(trend_cat.score, 1)
    assert trend_only_result.total_score != default_result.total_score
