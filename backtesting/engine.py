from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable

import pandas as pd


@dataclass
class Trade:
    entry_date: pd.Timestamp
    entry_price: float
    shares: int
    stop: float
    target: float
    exit_date: pd.Timestamp | None = None
    exit_price: float | None = None
    exit_reason: str | None = None  # "stop" | "target" | "end_of_data"
    pnl: float | None = None
    pnl_pct: float | None = None
    holding_days: int | None = None


@dataclass
class BacktestResult:
    trades: list[Trade]
    equity_curve: pd.Series
    final_equity: float
    initial_capital: float


SignalFn = Callable[[pd.DataFrame], bool]
StopFn = Callable[[pd.DataFrame, float], float]
TargetFn = Callable[[pd.DataFrame, float, float], float]


def run_backtest(
    history: pd.DataFrame,
    signal_fn: SignalFn,
    stop_fn: StopFn,
    target_fn: TargetFn,
    initial_capital: float = 10_000.0,
    risk_per_trade_pct: float = 1.0,
    commission_per_trade: float = 1.0,
    slippage_pct: float = 0.05,
    max_position_pct: float = 20.0,
) -> BacktestResult:
    """Event-driven, single-position backtester with no look-ahead bias.

    Sequence enforced on every bar to avoid look-ahead:
    1. `signal_fn` is only ever given `history.iloc[:i+1]` — data through the bar
       that has already closed, never anything later.
    2. A True signal on bar i only opens a position at bar i+1's OPEN (the next
       bar), priced with slippage — never at bar i's own close, which would assume
       a fill at a price not actually achievable when the decision was made.
    3. Stop/target levels are computed from `history.iloc[:i]` (data known BEFORE
       the entry bar opened), passed alongside the entry price itself.
    4. Once in a position, a bar's own low/high (starting from the bar AFTER entry,
       never the entry bar itself) determines a stop/target hit — this is legitimate
       because by the time that bar is fully known, so is whether its low/high
       breached a level set the day before.
    5. If both stop and target are breached within the same bar, the STOP is
       assumed to have been hit first (the conservative assumption — we cannot
       know intrabar order from daily OHLC data).
    """
    n = len(history)
    equity = initial_capital
    equity_curve_values: list[float] = []
    trades: list[Trade] = []

    in_position = False
    pending_entry = False
    trade: Trade | None = None

    for i in range(n):
        date = history.index[i]
        bar = history.iloc[i]

        if pending_entry and not in_position:
            entry_price = float(bar["open"]) * (1 + slippage_pct / 100)
            history_before_entry = history.iloc[:i]
            stop = stop_fn(history_before_entry, entry_price)
            target = target_fn(history_before_entry, entry_price, stop)

            stop_distance = abs(entry_price - stop)
            pending_entry = False
            if stop_distance <= 0:
                equity_curve_values.append(equity)
                continue

            risk_amount = equity * (risk_per_trade_pct / 100)
            shares = math.floor(risk_amount / stop_distance)
            position_value = shares * entry_price
            max_position_value = equity * (max_position_pct / 100)
            if position_value > max_position_value:
                shares = math.floor(max_position_value / entry_price)

            if shares <= 0:
                equity_curve_values.append(equity)
                continue

            equity -= commission_per_trade
            trade = Trade(entry_date=date, entry_price=entry_price, shares=shares, stop=stop, target=target)
            in_position = True
            equity_curve_values.append(equity)
            continue

        if in_position and trade is not None:
            hit_stop = bar["low"] <= trade.stop
            hit_target = bar["high"] >= trade.target
            is_last_bar = i == n - 1

            if hit_stop or hit_target or is_last_bar:
                if hit_stop:
                    exit_price = trade.stop * (1 - slippage_pct / 100)
                    reason = "stop"
                elif hit_target:
                    exit_price = trade.target * (1 - slippage_pct / 100)
                    reason = "target"
                else:
                    exit_price = float(bar["close"])
                    reason = "end_of_data"

                proceeds = exit_price * trade.shares - commission_per_trade
                cost_basis = trade.entry_price * trade.shares
                pnl = proceeds - cost_basis
                equity += pnl

                trade.exit_date = date
                trade.exit_price = exit_price
                trade.exit_reason = reason
                trade.pnl = pnl
                trade.pnl_pct = (pnl / cost_basis * 100) if cost_basis else 0.0
                trade.holding_days = (date - trade.entry_date).days
                trades.append(trade)

                in_position = False
                trade = None

            equity_curve_values.append(equity)
            continue

        history_so_far = history.iloc[: i + 1]
        if signal_fn(history_so_far):
            pending_entry = True
        equity_curve_values.append(equity)

    equity_curve = pd.Series(equity_curve_values, index=history.index[: len(equity_curve_values)])
    return BacktestResult(trades=trades, equity_curve=equity_curve, final_equity=equity, initial_capital=initial_capital)
