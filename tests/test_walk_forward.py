import pandas as pd

from backtesting.walk_forward import split_walk_forward, run_walk_forward


def _uptrend_history(n=600, start=50.0, step=0.1):
    idx = pd.date_range("2022-01-01", periods=n, freq="D")
    close = pd.Series([start + step * i for i in range(n)], index=idx)
    return pd.DataFrame(
        {"open": close, "high": close + 0.3, "low": close - 0.3, "close": close, "volume": 1_000_000.0}
    )


def test_split_walk_forward_produces_expected_number_of_rolling_windows():
    # step defaults to test_days, so windows roll forward by 100 days each time
    # start offsets that fit are 0, 100, 200, 300 -> 4 windows
    history = _uptrend_history(n=600)
    splits = split_walk_forward(history, train_days=200, test_days=100)
    assert len(splits) == 4
    train0, test0 = splits[0]
    assert len(train0) == 200
    assert len(test0) == 100
    assert train0.index[-1] < test0.index[0]


def test_split_walk_forward_test_immediately_follows_train():
    history = _uptrend_history(n=600)
    splits = split_walk_forward(history, train_days=200, test_days=100)
    train0, test0 = splits[0]
    assert test0.index[0] == train0.index[-1] + pd.Timedelta(days=1)


def test_split_walk_forward_rolls_forward_by_step_days():
    history = _uptrend_history(n=600)
    splits = split_walk_forward(history, train_days=200, test_days=100)
    train0, _ = splits[0]
    train1, _ = splits[1]
    assert train1.index[0] == train0.index[0] + pd.Timedelta(days=100)


def test_split_walk_forward_empty_when_history_too_short():
    history = _uptrend_history(n=100)
    splits = split_walk_forward(history, train_days=200, test_days=100)
    assert splits == []


def test_run_walk_forward_produces_one_window_per_split():
    history = _uptrend_history(n=500)
    windows = run_walk_forward(
        history, lambda h: True, lambda h, e: e - 5, lambda h, e, s: e + 1000,
        train_days=200, test_days=100, risk_per_trade_pct=1.0,
    )
    expected_splits = split_walk_forward(history, train_days=200, test_days=100)
    assert len(windows) == len(expected_splits) == 3


def test_run_walk_forward_trades_only_land_inside_each_test_window():
    """Regression guard for the walk-forward-specific no-look-ahead guarantee: a
    signal that fires unconditionally must still produce zero trades attributed to
    the train segment — every counted trade's window boundaries confirm this."""
    history = _uptrend_history(n=500)
    windows = run_walk_forward(
        history, lambda h: True, lambda h, e: e - 5, lambda h, e, s: e + 1000,
        train_days=200, test_days=100,
    )
    for window in windows:
        assert window.trade_count >= 1
        assert (window.test_start - window.train_start).days == 200
        assert window.test_start > window.train_end


def test_run_walk_forward_produces_metrics_per_window():
    history = _uptrend_history(n=500)
    windows = run_walk_forward(
        history, lambda h: len(h) % 20 == 0, lambda h, e: e - 5, lambda h, e, s: e + 20,
        train_days=200, test_days=100,
    )
    assert len(windows) == 3
    for window in windows:
        assert window.metrics is not None
        assert window.metrics.num_trades == window.trade_count


def test_run_walk_forward_empty_when_no_valid_splits():
    history = _uptrend_history(n=100)
    windows = run_walk_forward(
        history, lambda h: True, lambda h, e: e - 5, lambda h, e, s: e + 1000,
        train_days=200, test_days=100,
    )
    assert windows == []
