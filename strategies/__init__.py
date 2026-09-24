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

__all__ = [
    "Strategy",
    "StrategySignal",
    "ALL_STRATEGIES",
    "BreakoutStrategy",
    "PullbackStrategy",
    "TrendContinuationStrategy",
    "SupportBounceStrategy",
    "MomentumContinuationStrategy",
    "MeanReversionStrategy",
    "VolatilityContractionStrategy",
]
