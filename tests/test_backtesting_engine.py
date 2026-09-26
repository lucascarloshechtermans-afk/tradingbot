import pandas as pd
import pytest

from backtesting.engine import run_backtest


def _flat_ohlcv(n=30, level=100.0):
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    close = pd.Series(level, index=idx)
    return pd.DataFrame(
        {"open": close, "high": close + 1, "low": close - 1, "close": close, "volume": 1_000_000.0}
    )


def test_signal_fn_never_receives_future_bars():
    """The core no-look-ahead guarantee: at the moment signal_fn is called for bar
    i, it must never see bar i+1 or later."""
    history = _flat_ohlcv(n=20)
    seen_lengths = []

    def spy_signal(h):
        seen_lengths.append(len(h))
        assert h.index[-1] <= history.index[len(h) - 1]
        return False  # never trade; we're only checking what data it's shown

    run_backtest(history, spy_signal, lambda h, e: e - 1, lambda h, e, s: e + 1)
    assert seen_lengths == list(range(1, 21))


def test_entry_executes_at_next_bar_open_not_signal_bar_close():
    idx = pd.date_range("2024-01-01", periods=5, freq="D")
    # bar 0: close 100 (signal fires here) -> entry must be at bar 1's open (105), not bar 0's close (100)
    df = pd.DataFrame(
        {
            "open": [100, 105, 106, 107, 108],
            "high": [101, 106, 107, 108, 109],
            "low": [99, 104, 105, 106, 107],
            "close": [100, 105.5, 106.5, 107.5, 200],  # final close spikes so trade exits at end via close
            "volume": [1_000_000] * 5,
        },
        index=idx,
    )

    call_count = {"n": 0}

    def signal_once(h):
        call_count["n"] += 1
        return len(h) == 1  # fire only after seeing bar 0

    def stop_fn(h, entry):
        return entry - 50  # far away, won't trigger

    def target_fn(h, entry, stop):
        return entry + 1000  # far away, won't trigger

    result = run_backtest(df, signal_once, stop_fn, target_fn, slippage_pct=0.0, commission_per_trade=0.0)
    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.entry_price == pytest.approx(105.0)  # bar 1's open, not bar 0's close (100)
    assert trade.entry_date == idx[1]


def test_stop_hit_exits_at_stop_price():
    idx = pd.date_range("2024-01-01", periods=5, freq="D")
    df = pd.DataFrame(
        {
            "open": [100, 100, 100, 90, 90],
            "high": [101, 101, 101, 91, 91],
            "low": [99, 99, 99, 85, 85],  # bar 3's low breaches the stop
            "close": [100, 100, 100, 90, 90],
            "volume": [1_000_000] * 5,
        },
        index=idx,
    )

    def signal_once(h):
        return len(h) == 1

    def stop_fn(h, entry):
        return entry - 5  # stop at 95 (entry ~100)

    def target_fn(h, entry, stop):
        return entry + 1000

    result = run_backtest(df, signal_once, stop_fn, target_fn, slippage_pct=0.0, commission_per_trade=0.0)
    assert len(result.trades) == 1
    assert result.trades[0].exit_reason == "stop"
    assert result.trades[0].pnl < 0


def test_stop_gapped_through_exits_at_worse_open_not_stop_price():
    """A stop resting at 95 cannot fill at 95 when the market opens at 90 —
    once triggered it's a market order, filled at the open it actually got."""
    idx = pd.date_range("2024-01-01", periods=4, freq="D")
    df = pd.DataFrame(
        {
            "open": [100, 100, 100, 90],  # bar 3 opens BELOW the stop (95)
            "high": [101, 101, 101, 91],
            "low": [99, 99, 99, 85],
            "close": [100, 100, 100, 90],
            "volume": [1_000_000] * 4,
        },
        index=idx,
    )

    def signal_once(h):
        return len(h) == 1

    def stop_fn(h, entry):
        return entry - 5  # stop at 95 (entry ~100)

    def target_fn(h, entry, stop):
        return entry + 1000

    result = run_backtest(df, signal_once, stop_fn, target_fn, slippage_pct=0.0, commission_per_trade=0.0)
    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.exit_reason == "stop"
    assert trade.exit_price == pytest.approx(90.0)  # the gapped-down open, not the untouched 95 stop


def test_target_gapped_through_exits_at_better_open_not_target_price():
    """Symmetric case: the market opens ABOVE the target -- a real exit order
    fills at that better open, not capped at the target price."""
    idx = pd.date_range("2024-01-01", periods=4, freq="D")
    df = pd.DataFrame(
        {
            "open": [100, 100, 100, 120],  # bar 3 opens ABOVE the target (110)
            "high": [101, 101, 101, 121],
            "low": [99, 99, 99, 119],
            "close": [100, 100, 100, 120],
            "volume": [1_000_000] * 4,
        },
        index=idx,
    )

    def signal_once(h):
        return len(h) == 1

    def stop_fn(h, entry):
        return entry - 50

    def target_fn(h, entry, stop):
        return entry + 10  # target at 110

    result = run_backtest(df, signal_once, stop_fn, target_fn, slippage_pct=0.0, commission_per_trade=0.0)
    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.exit_reason == "target"
    assert trade.exit_price == pytest.approx(120.0)  # the gapped-up open, not the capped 110 target


def test_target_hit_exits_at_target_price():
    idx = pd.date_range("2024-01-01", periods=5, freq="D")
    df = pd.DataFrame(
        {
            "open": [100, 100, 100, 110, 110],
            "high": [101, 101, 101, 120, 120],  # bar 3's high breaches the target
            "low": [99, 99, 99, 109, 109],
            "close": [100, 100, 100, 115, 115],
            "volume": [1_000_000] * 5,
        },
        index=idx,
    )

    def signal_once(h):
        return len(h) == 1

    def stop_fn(h, entry):
        return entry - 50

    def target_fn(h, entry, stop):
        return entry + 10  # target ~110

    result = run_backtest(df, signal_once, stop_fn, target_fn, slippage_pct=0.0, commission_per_trade=0.0)
    assert len(result.trades) == 1
    assert result.trades[0].exit_reason == "target"
    assert result.trades[0].pnl > 0


def test_both_stop_and_target_hit_same_bar_assumes_stop_first():
    idx = pd.date_range("2024-01-01", periods=4, freq="D")
    df = pd.DataFrame(
        {
            "open": [100, 100, 100, 100],
            "high": [101, 101, 101, 130],  # would hit target
            "low": [99, 99, 99, 70],  # would ALSO hit stop
            "close": [100, 100, 100, 100],
            "volume": [1_000_000] * 4,
        },
        index=idx,
    )

    def signal_once(h):
        return len(h) == 1

    def stop_fn(h, entry):
        return entry - 10  # 90

    def target_fn(h, entry, stop):
        return entry + 10  # 110

    result = run_backtest(df, signal_once, stop_fn, target_fn, slippage_pct=0.0, commission_per_trade=0.0)
    assert result.trades[0].exit_reason == "stop"


def test_no_signal_never_trades():
    history = _flat_ohlcv()
    result = run_backtest(history, lambda h: False, lambda h, e: e - 1, lambda h, e, s: e + 1)
    assert result.trades == []
    assert result.final_equity == result.initial_capital


def test_open_position_closed_at_end_of_data():
    history = _flat_ohlcv(n=10)

    def signal_once(h):
        return len(h) == 1

    result = run_backtest(
        history, signal_once, lambda h, e: e - 20, lambda h, e, s: e + 20,
        slippage_pct=0.0, commission_per_trade=0.0,
    )
    assert len(result.trades) == 1
    assert result.trades[0].exit_reason == "end_of_data"


def test_commission_and_slippage_reduce_pnl():
    idx = pd.date_range("2024-01-01", periods=4, freq="D")
    df = pd.DataFrame(
        {
            "open": [100, 100, 100, 100],
            "high": [101, 101, 101, 120],
            "low": [99, 99, 99, 109],
            "close": [100, 100, 100, 115],
            "volume": [1_000_000] * 4,
        },
        index=idx,
    )

    def signal_once(h):
        return len(h) == 1

    def stop_fn(h, entry):
        return entry - 50

    def target_fn(h, entry, stop):
        return entry + 10

    no_cost = run_backtest(df, signal_once, stop_fn, target_fn, slippage_pct=0.0, commission_per_trade=0.0)
    with_cost = run_backtest(df, signal_once, stop_fn, target_fn, slippage_pct=1.0, commission_per_trade=5.0)
    assert with_cost.trades[0].pnl < no_cost.trades[0].pnl


def test_max_holding_days_forces_exit_after_n_bars():
    idx = pd.date_range("2024-01-01", periods=10, freq="D")
    # price never touches stop or target -> only the time limit can close this trade
    df = pd.DataFrame(
        {
            "open": [100] * 10,
            "high": [101] * 10,
            "low": [99] * 10,
            "close": [100] * 10,
            "volume": [1_000_000] * 10,
        },
        index=idx,
    )

    def signal_once(h):
        return len(h) == 1

    def stop_fn(h, entry):
        return entry - 50

    def target_fn(h, entry, stop):
        return entry + 50

    result = run_backtest(
        df, signal_once, stop_fn, target_fn, slippage_pct=0.0, commission_per_trade=0.0, max_holding_days=5,
    )
    assert len(result.trades) == 1
    trade = result.trades[0]
    assert trade.exit_reason == "time_exit"
    assert trade.holding_bars == 5


def test_holding_days_fn_overrides_max_holding_days_per_trade():
    idx = pd.date_range("2024-01-01", periods=12, freq="D")
    df = pd.DataFrame(
        {"open": [100] * 12, "high": [101] * 12, "low": [99] * 12, "close": [100] * 12, "volume": [1_000_000] * 12},
        index=idx,
    )

    def signal_once(h):
        return len(h) == 1

    result = run_backtest(
        df, signal_once, lambda h, e: e - 50, lambda h, e, s: e + 50,
        slippage_pct=0.0, commission_per_trade=0.0, max_holding_days=5,
        holding_days_fn=lambda h: 7,
    )
    trade = result.trades[0]
    assert trade.exit_reason == "time_exit"
    assert trade.holding_bars == 7


def test_holding_days_fn_returning_none_falls_back_to_max_holding_days():
    idx = pd.date_range("2024-01-01", periods=12, freq="D")
    df = pd.DataFrame(
        {"open": [100] * 12, "high": [101] * 12, "low": [99] * 12, "close": [100] * 12, "volume": [1_000_000] * 12},
        index=idx,
    )

    def signal_once(h):
        return len(h) == 1

    result = run_backtest(
        df, signal_once, lambda h, e: e - 50, lambda h, e, s: e + 50,
        slippage_pct=0.0, commission_per_trade=0.0, max_holding_days=5,
        holding_days_fn=lambda h: None,
    )
    assert result.trades[0].holding_bars == 5


def test_max_holding_days_none_disables_time_exit():
    idx = pd.date_range("2024-01-01", periods=10, freq="D")
    df = pd.DataFrame(
        {"open": [100] * 10, "high": [101] * 10, "low": [99] * 10, "close": [100] * 10, "volume": [1_000_000] * 10},
        index=idx,
    )

    def signal_once(h):
        return len(h) == 1

    result = run_backtest(
        df, signal_once, lambda h, e: e - 50, lambda h, e, s: e + 50,
        slippage_pct=0.0, commission_per_trade=0.0, max_holding_days=None,
    )
    assert result.trades[0].exit_reason == "end_of_data"


def test_stop_hit_takes_priority_over_time_exit_on_same_bar():
    # entry executes at bar index 1; the time limit (max_holding_days=5) would fire
    # at bar index 6 (bars_held = 6 - 1 = 5) -- put the stop breach on that same bar
    idx = pd.date_range("2024-01-01", periods=8, freq="D")
    lows = [99, 99, 99, 99, 99, 99, 80, 99]
    df = pd.DataFrame(
        {
            "open": [100] * 8,
            "high": [101] * 8,
            "low": lows,
            "close": [100] * 8,
            "volume": [1_000_000] * 8,
        },
        index=idx,
    )

    def signal_once(h):
        return len(h) == 1

    result = run_backtest(
        df, signal_once, lambda h, e: e - 10, lambda h, e, s: e + 1000,
        slippage_pct=0.0, commission_per_trade=0.0, max_holding_days=5,
    )
    assert result.trades[0].exit_reason == "stop"
    assert result.trades[0].holding_bars == 5


def test_position_never_exceeds_max_position_pct():
    history = _flat_ohlcv(n=10)

    def signal_once(h):
        return len(h) == 1

    def stop_fn(h, entry):
        return entry - 0.5  # tiny stop distance -> would size a huge position without the cap

    def target_fn(h, entry, stop):
        return entry + 1000

    result = run_backtest(
        history, signal_once, stop_fn, target_fn, initial_capital=10_000, risk_per_trade_pct=50.0, max_position_pct=20.0,
    )
    trade = result.trades[0] if result.trades else None
    if trade:
        assert trade.shares * trade.entry_price <= 10_000 * 0.20 + 1e-6
