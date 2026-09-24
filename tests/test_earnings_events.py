from datetime import datetime

import pandas as pd

from events.earnings import check_earnings_proximity, check_recent_split, check_upcoming_dividend


def test_no_upcoming_earnings():
    result = check_earnings_proximity([], as_of=datetime(2024, 6, 1))
    assert result.has_upcoming_earnings is False
    assert result.should_avoid is False


def test_earnings_within_buffer_flags_avoid():
    earnings = [datetime(2024, 6, 4)]
    result = check_earnings_proximity(earnings, as_of=datetime(2024, 6, 1), buffer_days=5, avoid_earnings=True)
    assert result.has_upcoming_earnings is True
    assert result.days_until_earnings == 3
    assert result.should_avoid is True
    assert "3 days" in result.message


def test_earnings_outside_buffer_does_not_avoid():
    earnings = [datetime(2024, 7, 1)]
    result = check_earnings_proximity(earnings, as_of=datetime(2024, 6, 1), buffer_days=5, avoid_earnings=True)
    assert result.has_upcoming_earnings is True
    assert result.should_avoid is False


def test_avoid_earnings_disabled_never_flags_avoid():
    earnings = [datetime(2024, 6, 2)]
    result = check_earnings_proximity(earnings, as_of=datetime(2024, 6, 1), buffer_days=5, avoid_earnings=False)
    assert result.should_avoid is False
    assert result.has_upcoming_earnings is True


def test_only_future_dates_considered():
    earnings = [datetime(2024, 5, 1), datetime(2024, 6, 10)]
    result = check_earnings_proximity(earnings, as_of=datetime(2024, 6, 1), buffer_days=5, avoid_earnings=True)
    assert result.days_until_earnings == 9


def test_check_recent_split_detects_within_window():
    splits = pd.Series([2.0], index=pd.DatetimeIndex(["2024-05-20"]))
    result = check_recent_split(splits, as_of=datetime(2024, 6, 1), lookback_days=30)
    assert result is not None
    assert "2:1" in result


def test_check_recent_split_ignores_old_split():
    splits = pd.Series([2.0], index=pd.DatetimeIndex(["2023-01-01"]))
    result = check_recent_split(splits, as_of=datetime(2024, 6, 1), lookback_days=30)
    assert result is None


def test_check_recent_split_handles_empty_series():
    assert check_recent_split(pd.Series(dtype=float), as_of=datetime(2024, 6, 1)) is None


def test_check_upcoming_dividend_detects_recent():
    dividends = pd.Series([0.5], index=pd.DatetimeIndex(["2024-05-28"]))
    result = check_upcoming_dividend(dividends, as_of=datetime(2024, 6, 1), lookback_days=10)
    assert result is not None
    assert "0.50" in result


def test_check_upcoming_dividend_handles_tz_aware_index():
    dividends = pd.Series([0.5], index=pd.DatetimeIndex(["2024-05-28"], tz="UTC"))
    result = check_upcoming_dividend(dividends, as_of=datetime(2024, 6, 1), lookback_days=10)
    assert result is not None
