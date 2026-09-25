import pandas as pd

from config.schema import UniverseConfig
from data.provider import TickerInfo
from data.universe import apply_universe_filters, average_dollar_volume


def _history(price: float, volume: float, days: int = 25):
    idx = pd.date_range("2024-01-01", periods=days, freq="D", tz="UTC")
    return pd.DataFrame(
        {
            "open": [price] * days,
            "high": [price] * days,
            "low": [price] * days,
            "close": [price] * days,
            "adj_close": [price] * days,
            "volume": [volume] * days,
        },
        index=idx,
    )


def test_average_dollar_volume_basic():
    hist = _history(price=10.0, volume=1_000_000)
    assert average_dollar_volume(hist) == 10_000_000.0


def test_average_dollar_volume_none_when_insufficient_history():
    hist = _history(price=10.0, volume=1_000_000, days=5)
    assert average_dollar_volume(hist, window=20) is None


def test_filters_reject_low_price():
    cfg = UniverseConfig.from_dict({"preset": "BALANCED"})
    candidates = {
        "PENNY": (
            TickerInfo(ticker="PENNY", market_cap=5_000_000_000),
            _history(price=2.0, volume=10_000_000),
        )
    }
    result = apply_universe_filters(candidates, cfg)
    assert "PENNY" in result.excluded
    assert result.included == []


def test_filters_reject_low_liquidity():
    cfg = UniverseConfig.from_dict({"preset": "BALANCED"})
    candidates = {
        "ILLIQUID": (
            TickerInfo(ticker="ILLIQUID", market_cap=5_000_000_000),
            _history(price=50.0, volume=1_000),
        )
    }
    result = apply_universe_filters(candidates, cfg)
    assert "ILLIQUID" in result.excluded
    assert "volume" in result.excluded["ILLIQUID"]


def test_filters_reject_missing_market_cap_rather_than_assume():
    cfg = UniverseConfig.from_dict({"preset": "BALANCED"})
    candidates = {
        "NOCAP": (
            TickerInfo(ticker="NOCAP", market_cap=None),
            _history(price=50.0, volume=1_000_000),
        )
    }
    result = apply_universe_filters(candidates, cfg)
    assert "NOCAP" in result.excluded
    assert "market cap" in result.excluded["NOCAP"]


def test_filters_accept_qualifying_stock():
    cfg = UniverseConfig.from_dict({"preset": "BALANCED"})
    candidates = {
        "GOOD": (
            TickerInfo(ticker="GOOD", market_cap=50_000_000_000, sector="Technology"),
            _history(price=100.0, volume=1_000_000),
        )
    }
    result = apply_universe_filters(candidates, cfg)
    assert result.included == ["GOOD"]


def test_sector_filter_excludes_non_matching_sector():
    cfg = UniverseConfig.from_dict({"preset": "BALANCED", "sectors": ["Healthcare"]})
    candidates = {
        "TECHCO": (
            TickerInfo(ticker="TECHCO", market_cap=50_000_000_000, sector="Technology"),
            _history(price=100.0, volume=1_000_000),
        )
    }
    result = apply_universe_filters(candidates, cfg)
    assert "TECHCO" in result.excluded


def _flat_history(price: float, volume: float, days: int = 25):
    """Zero daily range -> ATR% ~0, for testing the min_atr_pct filter."""
    idx = pd.date_range("2024-01-01", periods=days, freq="D", tz="UTC")
    return pd.DataFrame(
        {
            "open": [price] * days,
            "high": [price] * days,
            "low": [price] * days,
            "close": [price] * days,
            "adj_close": [price] * days,
            "volume": [volume] * days,
        },
        index=idx,
    )


def test_filters_reject_low_atr_pct_when_min_atr_pct_set():
    cfg = UniverseConfig.from_dict({"preset": "BALANCED", "min_atr_pct": 5.0})
    candidates = {
        "SLOWMOVER": (
            TickerInfo(ticker="SLOWMOVER", market_cap=500_000_000_000),
            _flat_history(price=200.0, volume=10_000_000),
        )
    }
    result = apply_universe_filters(candidates, cfg)
    assert "SLOWMOVER" in result.excluded
    assert "ATR%" in result.excluded["SLOWMOVER"]


def test_min_atr_pct_zero_disables_the_filter():
    cfg = UniverseConfig.from_dict({"preset": "BALANCED"})
    assert cfg.min_atr_pct == 0.0
    candidates = {
        "SLOWMOVER": (
            TickerInfo(ticker="SLOWMOVER", market_cap=500_000_000_000),
            _flat_history(price=200.0, volume=10_000_000),
        )
    }
    result = apply_universe_filters(candidates, cfg)
    assert result.included == ["SLOWMOVER"]


def test_aggressive_preset_allows_lower_price_and_cap():
    cfg = UniverseConfig.from_dict({"preset": "AGGRESSIVE"})
    candidates = {
        "SMALLCAP": (
            TickerInfo(ticker="SMALLCAP", market_cap=500_000_000),
            _history(price=6.0, volume=500_000),
        )
    }
    result = apply_universe_filters(candidates, cfg)
    assert result.included == ["SMALLCAP"]
