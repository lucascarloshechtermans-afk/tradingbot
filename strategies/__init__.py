from strategies.base import Strategy, StrategySignal
from strategies.breakout import BreakoutStrategy
from strategies.mean_reversion import MeanReversionStrategy
from strategies.momentum_continuation import MomentumContinuationStrategy
from strategies.pullback import PullbackStrategy
from strategies.support_bounce import SupportBounceStrategy
from strategies.trend_continuation import TrendContinuationStrategy
from strategies.volatility_contraction import VolatilityContractionStrategy

ALL_STRATEGIES: list[Strategy] = [
    BreakoutStrategy(),
    PullbackStrategy(),
    TrendContinuationStrategy(),
    SupportBounceStrategy(),
    MomentumContinuationStrategy(),
    MeanReversionStrategy(),
    VolatilityContractionStrategy(),
]

# Strategies allowed to be picked as the PRIMARY setup for entry/stop/target and to
# open a backtest position on their own. See Strategy.tradeable for why
# VolatilityContractionStrategy is excluded.
TRADEABLE_STRATEGIES: list[Strategy] = [s for s in ALL_STRATEGIES if s.tradeable]


def best_tradeable_signal(signals: list[StrategySignal]) -> StrategySignal | None:
    """Pick the highest-confidence MATCHED signal among tradeable strategies only —
    the single shared rule used by both the live scanner and the backtester so they
    can never disagree on what counts as "the" setup for a ticker."""
    tradeable_names = {s.name for s in TRADEABLE_STRATEGIES}
    candidates = [s for s in signals if s.matched and s.strategy in tradeable_names]
    return max(candidates, key=lambda s: s.confidence) if candidates else None


__all__ = [
    "Strategy",
    "StrategySignal",
    "ALL_STRATEGIES",
    "TRADEABLE_STRATEGIES",
    "best_tradeable_signal",
    "BreakoutStrategy",
    "PullbackStrategy",
    "TrendContinuationStrategy",
    "SupportBounceStrategy",
    "MomentumContinuationStrategy",
    "MeanReversionStrategy",
    "VolatilityContractionStrategy",
]
