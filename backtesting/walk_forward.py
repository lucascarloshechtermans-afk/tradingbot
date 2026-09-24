from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from backtesting.engine import SignalFn, StopFn, TargetFn, run_backtest
from backtesting.metrics import BacktestMetrics, compute_metrics

"""Walk-forward VALIDATION (not optimization).

Each window re-uses the exact same, already-fixed strategy/scoring rules — nothing
here re-fits parameters per window. That is a deliberate, documented scope limit
(see the build plan): automatic re-optimization of scoring weights per window is a
separate, much larger project (parameter search + overfitting control) and is not
implemented. What this DOES give you: honest, sequential out-of-sample performance
of one fixed rule set across different market periods, which is still far more
informative than a single backtest over the whole history at once.
"""


@dataclass
class WalkForwardWindow:
    label: str
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp
    metrics: BacktestMetrics
    trade_count: int


def split_walk_forward(
    history: pd.DataFrame, train_days: int, test_days: int, step_days: int | None = None
) -> list[tuple[pd.DataFrame, pd.DataFrame]]:
    step_days = step_days or test_days
    n = len(history)
    splits = []
    start = 0
    while start + train_days + test_days <= n:
        train = history.iloc[start : start + train_days]
        test = history.iloc[start + train_days : start + train_days + test_days]
        splits.append((train, test))
        start += step_days
    return splits


def run_walk_forward(
    history: pd.DataFrame,
    signal_fn: SignalFn,
    stop_fn: StopFn,
    target_fn: TargetFn,
    train_days: int = 252,
    test_days: int = 63,
    step_days: int | None = None,
    initial_capital: float = 10_000.0,
    **backtest_kwargs,
) -> list[WalkForwardWindow]:
    """Run the same fixed signal/stop/target rules across sequential out-of-sample
    windows. The train segment of each window exists only to give indicators (e.g.
    SMA200) their warmup history — no fitting happens on it; trading is only
    permitted, and only counted, once the bar index enters the test segment.
    """
    splits = split_walk_forward(history, train_days, test_days, step_days)
    windows: list[WalkForwardWindow] = []

    for i, (train, test) in enumerate(splits, start=1):
        combined = pd.concat([train, test])
        test_start_position = len(train)

        def windowed_signal(h: pd.DataFrame, _signal=signal_fn, _test_start=test_start_position) -> bool:
            if len(h) - 1 < _test_start:
                return False
            return _signal(h)

        result = run_backtest(
            combined, windowed_signal, stop_fn, target_fn, initial_capital=initial_capital, **backtest_kwargs
        )

        test_trades = [t for t in result.trades if t.entry_date >= test.index[0]]
        test_equity = result.equity_curve.loc[result.equity_curve.index >= test.index[0]]
        metrics = compute_metrics(test_trades, test_equity, initial_capital=initial_capital)

        windows.append(
            WalkForwardWindow(
                label=f"window_{i}",
                train_start=train.index[0],
                train_end=train.index[-1],
                test_start=test.index[0],
                test_end=test.index[-1],
                metrics=metrics,
                trade_count=len(test_trades),
            )
        )

    return windows
