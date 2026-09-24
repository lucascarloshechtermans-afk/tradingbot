import pandas as pd
import pytest

from data.provider import DataUnavailable
from data.yfinance_provider import YFinanceProvider


def _fake_history_df():
    idx = pd.date_range("2024-01-01", periods=5, freq="D")  # tz-naive, like yfinance sometimes returns
    return pd.DataFrame(
        {
            "Open": [10, 11, 12, 13, 14],
            "High": [10.5, 11.5, 12.5, 13.5, 14.5],
            "Low": [9.5, 10.5, 11.5, 12.5, 13.5],
            "Close": [10.2, 11.2, 12.2, 13.2, 14.2],
            "Adj Close": [10.2, 11.2, 12.2, 13.2, 14.2],
            "Volume": [1000, 1100, 1200, 1300, 1400],
        },
        index=idx,
    )


class FakeTicker:
    def __init__(self, ticker, history_df=None, info=None, earnings_df=None, fail_times=0):
        self.ticker = ticker
        self._history_df = history_df if history_df is not None else _fake_history_df()
        self._info = info or {}
        self._earnings_df = earnings_df
        self._fail_times = fail_times
        self._calls = 0

    def history(self, period, interval, auto_adjust=False):
        self._calls += 1
        if self._calls <= self._fail_times:
            raise ConnectionError("simulated network failure")
        return self._history_df

    def get_info(self):
        return self._info

    def get_earnings_dates(self, limit=12):
        return self._earnings_df

    @property
    def dividends(self):
        return pd.Series([0.5, 0.5], index=pd.date_range("2024-01-01", periods=2, freq="90D"))

    @property
    def splits(self):
        return pd.Series(dtype=float)


def test_get_history_normalizes_columns_and_timezone(monkeypatch):
    monkeypatch.setattr(
        "yfinance.Ticker", lambda t: FakeTicker(t)
    )
    provider = YFinanceProvider(cache=None, max_retries=1)
    df = provider.get_history("FAKE", period="6mo", interval="1d")
    assert list(df.columns) == ["open", "high", "low", "close", "adj_close", "volume"]
    assert df.index.tz is not None
    assert str(df.index.tz) == "UTC"
    assert len(df) == 5


def test_get_history_retries_then_succeeds(monkeypatch):
    # yf.Ticker(...) is called fresh on every retry attempt (matching real yfinance
    # usage), so the fake must persist call-count state across construction calls.
    persistent_ticker = FakeTicker("FAKE", fail_times=2)
    monkeypatch.setattr("yfinance.Ticker", lambda t: persistent_ticker)
    provider = YFinanceProvider(cache=None, max_retries=3, retry_backoff_seconds=0.01)
    df = provider.get_history("FAKE", period="6mo", interval="1d")
    assert len(df) == 5


def test_get_history_raises_after_exhausting_retries(monkeypatch):
    monkeypatch.setattr(
        "yfinance.Ticker", lambda t: FakeTicker(t, fail_times=99)
    )
    provider = YFinanceProvider(cache=None, max_retries=2, retry_backoff_seconds=0.01)
    with pytest.raises(DataUnavailable):
        provider.get_history("FAKE", period="6mo", interval="1d")


def test_get_history_uses_cache(monkeypatch, tmp_path):
    from data.cache import DiskCache

    calls = {"n": 0}

    def make_ticker(t):
        calls["n"] += 1
        return FakeTicker(t)

    monkeypatch.setattr("yfinance.Ticker", make_ticker)
    cache = DiskCache(cache_dir=str(tmp_path), ttl_hours=1)
    provider = YFinanceProvider(cache=cache, max_retries=1)

    provider.get_history("FAKE", period="6mo", interval="1d")
    provider.get_history("FAKE", period="6mo", interval="1d")
    assert calls["n"] == 1


def test_get_info_reports_missing_fields_explicitly(monkeypatch):
    monkeypatch.setattr(
        "yfinance.Ticker",
        lambda t: FakeTicker(t, info={"sector": "Technology"}),
    )
    provider = YFinanceProvider(cache=None, max_retries=1)
    info = provider.get_info("FAKE")
    assert info.sector == "Technology"
    assert info.market_cap is None
    assert "market_cap" in info.missing_fields
    assert "industry" in info.missing_fields


def test_get_earnings_dates_returns_empty_on_failure(monkeypatch):
    def raiser(t):
        raise ConnectionError("down")

    monkeypatch.setattr("yfinance.Ticker", raiser)
    provider = YFinanceProvider(cache=None, max_retries=1)
    assert provider.get_earnings_dates("FAKE") == []
