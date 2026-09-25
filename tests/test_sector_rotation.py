import pandas as pd

from sector.rotation import rank_sectors, sector_strength_for


def _df(n, daily_change):
    idx = pd.date_range("2023-01-01", periods=n, freq="D")
    close = pd.Series([100 + i * daily_change for i in range(n)], index=idx)
    return pd.DataFrame({"close": close})


def test_rank_sectors_orders_by_relative_strength():
    spy = _df(100, daily_change=0.1)
    sector_histories = {
        "XLK": _df(100, daily_change=0.5),  # strong outperformer
        "XLU": _df(100, daily_change=-0.2),  # underperformer
        "XLF": _df(100, daily_change=0.1),   # roughly in line with SPY
    }
    ranked = rank_sectors(sector_histories, spy)
    assert ranked[0].etf == "XLK"
    assert ranked[-1].etf == "XLU"
    assert ranked[0].rank == 1


def test_sector_strength_for_maps_sector_name_to_etf():
    spy = _df(100, daily_change=0.1)
    sector_histories = {"XLK": _df(100, daily_change=0.5), "XLV": _df(100, daily_change=0.2)}
    ranked = rank_sectors(sector_histories, spy)
    result = sector_strength_for("Technology", ranked)
    assert result is not None
    assert result.etf == "XLK"


def test_sector_strength_for_returns_none_for_unmapped_sector():
    ranked = []
    assert sector_strength_for("Unknown Sector", ranked) is None


def test_sector_strength_for_returns_none_for_none_sector():
    assert sector_strength_for(None, []) is None


def test_rank_sectors_includes_5d_performance_and_volatility():
    spy = _df(100, daily_change=0.1)
    sector_histories = {"XLK": _df(100, daily_change=0.5)}
    ranked = rank_sectors(sector_histories, spy)
    assert ranked[0].performance_5d > 0  # steadily rising fixture
    assert ranked[0].volatility_pct >= 0
