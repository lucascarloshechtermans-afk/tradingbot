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
    exit_reason: str | None = None  # "stop" | "target" | "time_exit" | "end_of_data"
    pnl: float | None = None
    pnl_pct: float | None = None
    holding_days: int | None = None
    holding_bars: int | None = None
    max_holding_bars: int | None = None  # this trade's own time-exit cap (None = no cap)


@dataclass
class BacktestResult:
    trades: list[Trade]
    equity_curve: pd.Series
    final_equity: float
    initial_capital: float


SignalFn = Callable[[pd.DataFrame], bool]
StopFn = Callable[[pd.DataFrame, float], float]
TargetFn = Callable[[pd.DataFrame, float, float], float]
HoldingDaysFn = Callable[[pd.DataFrame], "int | None"]
EntryFilterFn = Callable[[pd.DataFrame, float], bool]


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
    max_holding_days: int | None = None,
    holding_days_fn: HoldingDaysFn | None = None,
    entry_filter_fn: EntryFilterFn | None = None,
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
    5b. A stop is a market order once triggered: if the bar's OPEN already gapped
       through the stop (open <= stop for a long), the fill happens at that worse
       open price, not at the theoretical stop level — a stop resting at $100
       cannot be filled at $100 when the market opens at $95. The same applies,
       symmetrically, to a target gapping through on the open (open >= target):
       real brokers still fill a triggered market/marketable-limit exit at the
       open when it's already better than the target, so pretending the fill
       happened exactly at the target would understate gains just as pretending
       a blown-through stop filled at the stop would overstate them.
    6. `max_holding_days`, when set, force-closes a position at that bar's CLOSE
       once it has been held for that many BARS (trading days, not calendar days —
       a weekend never counts) without hitting its stop or target — this is what
       actually enforces a "~1 trading week" swing-trade horizon end to end,
       rather than just hoping the target happens to be reached in time.
    7. `holding_days_fn`, when given, is called once at entry (with the same
       `history.iloc[:i]` stop_fn/target_fn see) and may return a per-trade cap
       that overrides `max_holding_days` for that trade only -- e.g. a longer
       horizon for trend-following setups than for mean-reversion ones.
    8. `entry_filter_fn(history.iloc[:i], raw_open_of_bar_i)`, when given, can
       cancel the pending entry at the open -- models a buy-limit order placed
       before the session (e.g. "no fill if it gaps up too far"). It only sees
       the entry bar's OPEN, which is known at the moment the order would fill.
    """
    n = len(history)
    equity = initial_capital
    equity_curve_values: list[float] = []
    trades: list[Trade] = []

    in_position = False
    pending_entry = False
    trade: Trade | None = None
    entry_bar_index: int | None = None

    for i in range(n):
        date = history.index[i]
        bar = history.iloc[i]

        if pending_entry and not in_position:
            history_before_entry = history.iloc[:i]
            if entry_filter_fn is not None and not entry_filter_fn(history_before_entry, float(bar["open"])):
                # the order is a buy-limit placed before the open; when the
                # open is already above the limit it doesn't fill, no trade
                pending_entry = False
                equity_curve_values.append(equity)
                continue
            entry_price = float(bar["open"]) * (1 + slippage_pct / 100)
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

            trade_cap = holding_days_fn(history_before_entry) if holding_days_fn is not None else None
            if trade_cap is None:
                trade_cap = max_holding_days

            equity -= commission_per_trade
            trade = Trade(
                entry_date=date, entry_price=entry_price, shares=shares, stop=stop, target=target,
                max_holding_bars=trade_cap,
            )
            in_position = True
            entry_bar_index = i
            equity_curve_values.append(equity)
            continue

        if in_position and trade is not None:
            hit_stop = bar["low"] <= trade.stop
            hit_target = bar["high"] >= trade.target
            is_last_bar = i == n - 1
            bars_held = i - entry_bar_index
            hit_time_limit = trade.max_holding_bars is not None and bars_held >= trade.max_holding_bars

            if hit_stop or hit_target or hit_time_limit or is_last_bar:
                if hit_stop:
                    # A stop becomes a market order once triggered: if the bar's
                    # open already gapped through it, the fill is at that worse
                    # open, not at the untouched stop level (see docstring 5b).
                    base_price = min(float(bar["open"]), trade.stop)
                    exit_price = base_price * (1 - slippage_pct / 100)
                    reason = "stop"
                elif hit_target:
                    # Symmetric: a gap open beyond the target is filled at that
                    # (better) open rather than capped at the target price.
                    base_price = max(float(bar["open"]), trade.target)
                    exit_price = base_price * (1 - slippage_pct / 100)
                    reason = "target"
                elif hit_time_limit:
                    exit_price = float(bar["close"])
                    reason = "time_exit"
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
                trade.holding_bars = bars_held
                trades.append(trade)

                in_position = False
                trade = None
                entry_bar_index = None

            equity_curve_values.append(equity)
            continue

        history_so_far = history.iloc[: i + 1]
        if signal_fn(history_so_far):
            pending_entry = True
        equity_curve_values.append(equity)

    equity_curve = pd.Series(equity_curve_values, index=history.index[: len(equity_curve_values)])
    return BacktestResult(trades=trades, equity_curve=equity_curve, final_equity=equity, initial_capital=initial_capital)
