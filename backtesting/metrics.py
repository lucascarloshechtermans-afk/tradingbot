from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from backtesting.engine import Trade

TRADING_DAYS_PER_YEAR = 252


@dataclass
class BacktestMetrics:
    total_return_pct: float
    cagr_pct: float
    win_rate_pct: float
    avg_win_pct: float
    avg_loss_pct: float
    profit_factor: float
    expectancy: float
    max_drawdown_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    num_trades: int
    avg_holding_days: float
    largest_win_pct: float
    largest_loss_pct: float
    max_consecutive_wins: int
    max_consecutive_losses: int


def _max_drawdown_pct(equity_curve: pd.Series) -> float:
    running_max = equity_curve.cummax()
    drawdown = (equity_curve - running_max) / running_max
    return float(drawdown.min() * 100) if len(drawdown) else 0.0


def _consecutive_streaks(trades: list[Trade]) -> tuple[int, int]:
    max_wins = max_losses = cur_wins = cur_losses = 0
    for t in trades:
        if t.pnl is None:
            continue
        if t.pnl > 0:
            cur_wins += 1
            cur_losses = 0
        elif t.pnl < 0:
            cur_losses += 1
            cur_wins = 0
        else:
            cur_wins = cur_losses = 0
        max_wins = max(max_wins, cur_wins)
        max_losses = max(max_losses, cur_losses)
    return max_wins, max_losses


def compute_metrics(trades: list[Trade], equity_curve: pd.Series, initial_capital: float) -> BacktestMetrics:
    closed = [t for t in trades if t.pnl is not None]

    if equity_curve.empty:
        final_equity = initial_capital
    else:
        final_equity = float(equity_curve.iloc[-1])

    total_return_pct = (final_equity / initial_capital - 1) * 100 if initial_capital else 0.0

    num_days = len(equity_curve)
    years = num_days / TRADING_DAYS_PER_YEAR if num_days > 0 else 0
    if years > 0 and final_equity > 0 and initial_capital > 0:
        cagr_pct = ((final_equity / initial_capital) ** (1 / years) - 1) * 100
    else:
        cagr_pct = 0.0

    wins = [t for t in closed if t.pnl > 0]
    losses = [t for t in closed if t.pnl < 0]
    win_rate_pct = (len(wins) / len(closed) * 100) if closed else 0.0
    avg_win_pct = float(np.mean([t.pnl_pct for t in wins])) if wins else 0.0
    avg_loss_pct = float(np.mean([t.pnl_pct for t in losses])) if losses else 0.0

    gross_profit = sum(t.pnl for t in wins)
    gross_loss = abs(sum(t.pnl for t in losses))
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (float("inf") if gross_profit > 0 else 0.0)

    win_prob = len(wins) / len(closed) if closed else 0.0
    loss_prob = len(losses) / len(closed) if closed else 0.0
    expectancy = (win_prob * avg_win_pct) + (loss_prob * avg_loss_pct)

    max_drawdown_pct = _max_drawdown_pct(equity_curve)

    daily_returns = equity_curve.pct_change().dropna()
    if len(daily_returns) > 1 and daily_returns.std() > 0:
        sharpe_ratio = float(daily_returns.mean() / daily_returns.std() * np.sqrt(TRADING_DAYS_PER_YEAR))
    else:
        sharpe_ratio = 0.0

    downside_returns = daily_returns[daily_returns < 0]
    if len(downside_returns) > 1 and downside_returns.std() > 0:
        sortino_ratio = float(daily_returns.mean() / downside_returns.std() * np.sqrt(TRADING_DAYS_PER_YEAR))
    else:
        sortino_ratio = 0.0

    avg_holding_days = float(np.mean([t.holding_days for t in closed])) if closed else 0.0
    largest_win_pct = max((t.pnl_pct for t in wins), default=0.0)
    largest_loss_pct = min((t.pnl_pct for t in losses), default=0.0)
    max_consecutive_wins, max_consecutive_losses = _consecutive_streaks(closed)

    return BacktestMetrics(
        total_return_pct=round(total_return_pct, 2),
        cagr_pct=round(cagr_pct, 2),
        win_rate_pct=round(win_rate_pct, 2),
        avg_win_pct=round(avg_win_pct, 2),
        avg_loss_pct=round(avg_loss_pct, 2),
        profit_factor=round(profit_factor, 2) if profit_factor != float("inf") else profit_factor,
        expectancy=round(expectancy, 2),
        max_drawdown_pct=round(max_drawdown_pct, 2),
        sharpe_ratio=round(sharpe_ratio, 2),
        sortino_ratio=round(sortino_ratio, 2),
        num_trades=len(closed),
        avg_holding_days=round(avg_holding_days, 1),
        largest_win_pct=round(largest_win_pct, 2),
        largest_loss_pct=round(largest_loss_pct, 2),
        max_consecutive_wins=max_consecutive_wins,
        max_consecutive_losses=max_consecutive_losses,
    )


def buy_and_hold_return_pct(history: pd.DataFrame) -> float:
    if history.empty:
        return 0.0
    start = float(history["close"].iloc[0])
    end = float(history["close"].iloc[-1])
    if start <= 0:
        return 0.0
    return (end / start - 1) * 100
