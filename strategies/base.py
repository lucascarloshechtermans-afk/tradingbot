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

    @abstractmethod
    def evaluate(self, ctx: TickerContext) -> StrategySignal:
        """Evaluate this strategy's setup against the latest bar in ctx.history.

        Must never look beyond the last row of ctx.history — every indicator series
        already stops there, so simply reading `.iloc[-1]` keeps this look-ahead-safe.
        """
