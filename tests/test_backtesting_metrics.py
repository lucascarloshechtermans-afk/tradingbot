import pandas as pd
import pytest

from backtesting.engine import Trade
from backtesting.metrics import buy_and_hold_return_pct, compute_metrics


def _trade(pnl, pnl_pct, holding_days=5):
    return Trade(
        entry_date=pd.Timestamp("2024-01-01"),
        entry_price=100.0,
        shares=10,
        stop=95.0,
        target=110.0,
        exit_date=pd.Timestamp("2024-01-01") + pd.Timedelta(days=holding_days),
        exit_price=100.0 + pnl / 10,
        exit_reason="target" if pnl > 0 else "stop",
        pnl=pnl,
        pnl_pct=pnl_pct,
        holding_days=holding_days,
    )


def _rising_equity_curve(n=100, start=10_000, daily_return=0.001):
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    values = [start * (1 + daily_return) ** i for i in range(n)]
    return pd.Series(values, index=idx)


def test_win_rate_and_profit_factor():
    trades = [_trade(100, 5.0), _trade(-50, -2.5), _trade(200, 8.0), _trade(-30, -1.5)]
    equity = _rising_equity_curve()
    metrics = compute_metrics(trades, equity, initial_capital=10_000)
    assert metrics.num_trades == 4
    assert metrics.win_rate_pct == 50.0
    assert metrics.profit_factor == pytest.approx((100 + 200) / (50 + 30), rel=0.01)


def test_expectancy_positive_for_profitable_system():
    trades = [_trade(100, 5.0), _trade(100, 5.0), _trade(-50, -2.5)]
    equity = _rising_equity_curve()
    metrics = compute_metrics(trades, equity, initial_capital=10_000)
    assert metrics.expectancy > 0


def test_max_drawdown_detected():
    idx = pd.date_range("2024-01-01", periods=5, freq="D")
    equity = pd.Series([10_000, 11_000, 9_000, 9_500, 10_500], index=idx)
    metrics = compute_metrics([], equity, initial_capital=10_000)
    # peak 11000 -> trough 9000 = -18.18%
    assert metrics.max_drawdown_pct == pytest.approx(-18.18, abs=0.1)


def test_no_trades_gives_zeroed_metrics():
    equity = pd.Series([10_000] * 10, index=pd.date_range("2024-01-01", periods=10, freq="D"))
    metrics = compute_metrics([], equity, initial_capital=10_000)
    assert metrics.num_trades == 0
    assert metrics.win_rate_pct == 0.0
    assert metrics.profit_factor == 0.0


def test_consecutive_streaks():
    trades = [_trade(10, 1), _trade(10, 1), _trade(-5, -1), _trade(10, 1), _trade(-5, -1), _trade(-5, -1), _trade(-5, -1)]
    equity = _rising_equity_curve()
    metrics = compute_metrics(trades, equity, initial_capital=10_000)
    assert metrics.max_consecutive_wins == 2
    assert metrics.max_consecutive_losses == 3


def test_total_return_matches_equity_curve():
    equity = pd.Series([10_000, 12_000], index=pd.date_range("2024-01-01", periods=2, freq="D"))
    metrics = compute_metrics([], equity, initial_capital=10_000)
    assert metrics.total_return_pct == 20.0


def test_buy_and_hold_return():
    idx = pd.date_range("2024-01-01", periods=3, freq="D")
    df = pd.DataFrame({"close": [100, 110, 120]}, index=idx)
    assert buy_and_hold_return_pct(df) == pytest.approx(20.0)


def test_buy_and_hold_empty_history():
    assert buy_and_hold_return_pct(pd.DataFrame()) == 0.0


def test_sharpe_ratio_zero_for_flat_equity():
    equity = pd.Series([10_000] * 20, index=pd.date_range("2024-01-01", periods=20, freq="D"))
    metrics = compute_metrics([], equity, initial_capital=10_000)
    assert metrics.sharpe_ratio == 0.0


def test_sharpe_ratio_positive_for_steadily_rising_equity():
    equity = _rising_equity_curve()
    metrics = compute_metrics([], equity, initial_capital=10_000)
    assert metrics.sharpe_ratio > 0
