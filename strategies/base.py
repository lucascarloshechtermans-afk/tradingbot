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

    @abstractmethod
    def evaluate(self, ctx: TickerContext) -> StrategySignal:
        """Evaluate this strategy's setup against the latest bar in ctx.history.

        Must never look beyond the last row of ctx.history — every indicator series
        already stops there, so simply reading `.iloc[-1]` keeps this look-ahead-safe.
        """
