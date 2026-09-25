from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from strategies.context import TickerContext


@dataclass
class StrategySignal:
    strategy: str
    matched: bool
    confidence: float  # 0-100, this strategy's own internal read — independent of
                        # the scanner-wide weighted score computed later
    reasons: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)


class Strategy(ABC):
    name: str
    # False marks a strategy as informational/context-only: it can still appear in
    # reasons and contribute to the price-action score, but it can never be picked
    # as the PRIMARY setup that drives entry/stop/target, and a match on a
    # non-tradeable strategy alone never opens a backtest position. Used for
    # VolatilityContractionStrategy, whose own docstring already frames it as a
    # "setup forming" watchlist signal rather than a directional entry — a 5-year,
    # 102-ticker backtest then confirmed it as the only net-losing strategy
    # (-0.22%/trade expectancy) when it WAS allowed to trigger entries.
    tradeable: bool = True

    # True marks a strategy as deliberately COUNTER-trend: it buys weakness
    # (an oversold dip, a bounce off support) rather than strength, so it should
    # be exempt from the RS-vs-universe and market-regime hard gates
    # (GatesConfig) — those gates require the stock/market to already be strong,
    # which is close to the opposite of this strategy's own entry condition. A
    # 5-year backtest confirmed this isn't theoretical: once Mean Reversion and
    # Support Bounce were subjected to the same gates as the trend-following
    # strategies, their expectancy flipped from solidly positive to negative,
    # because the gates filtered out exactly the dip-buying setups that made
    # them work. Still subject to the min-R:R gate, which is strategy-agnostic.
    counter_trend: bool = False

    @abstractmethod
    def evaluate(self, ctx: TickerContext) -> StrategySignal:
        """Evaluate this strategy's setup against the latest bar in ctx.history.

        Must never look beyond the last row of ctx.history — every indicator series
        already stops there, so simply reading `.iloc[-1]` keeps this look-ahead-safe.
        """
