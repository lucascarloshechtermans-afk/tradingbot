from scoring.multi_timeframe import multi_timeframe_confluence, resample_weekly
from tests.helpers import breakout_history, context_from, flat_history


def test_resample_weekly_reduces_row_count():
    daily = breakout_history()
    weekly = resample_weekly(daily)
    assert len(weekly) < len(daily)
    assert list(weekly.columns) == ["open", "high", "low", "close", "volume"]


def test_resample_weekly_ohlc_correct_for_single_week():
    import pandas as pd

    idx = pd.date_range("2024-01-01", periods=5, freq="D")  # Mon-Fri, one ISO week
    df = pd.DataFrame(
        {
            "open": [10, 11, 12, 13, 14],
            "high": [10.5, 11.5, 12.5, 13.5, 14.5],
            "low": [9.5, 10.5, 11.5, 12.5, 13.5],
            "close": [10.2, 11.2, 12.2, 13.2, 14.2],
            "volume": [100, 100, 100, 100, 100],
        },
        index=idx,
    )
    weekly = resample_weekly(df)
    assert weekly["open"].iloc[0] == 10
    assert weekly["high"].iloc[0] == 14.5
    assert weekly["low"].iloc[0] == 9.5
    assert weekly["close"].iloc[0] == 14.2
    assert weekly["volume"].iloc[0] == 500


def test_confluence_higher_for_aligned_bullish_trends():
    daily_ctx = context_from(breakout_history())
    weekly_hist = resample_weekly(breakout_history())
    weekly_ctx = context_from(weekly_hist)

    flat_ctx = context_from(flat_history())
    flat_weekly = context_from(resample_weekly(flat_history()))

    aligned_score, aligned_reasons = multi_timeframe_confluence(daily_ctx, weekly_ctx)
    neutral_score, _ = multi_timeframe_confluence(flat_ctx, flat_weekly)

    assert aligned_score > neutral_score
    assert len(aligned_reasons) > 0


def test_confluence_notes_missing_intraday():
    daily_ctx = context_from(breakout_history())
    weekly_ctx = context_from(resample_weekly(breakout_history()))
    _, reasons = multi_timeframe_confluence(daily_ctx, weekly_ctx, intraday_ctx=None)
    assert any("4H" in r or "not available" in r for r in reasons)


def test_confluence_score_bounded():
    daily_ctx = context_from(breakout_history())
    weekly_ctx = context_from(resample_weekly(breakout_history()))
    score, _ = multi_timeframe_confluence(daily_ctx, weekly_ctx, intraday_ctx=daily_ctx)
    assert 0 <= score <= 100
