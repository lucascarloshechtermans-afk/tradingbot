import pandas as pd

from sector.rotation import rank_sectors, sector_rank_series, sector_strength_for


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


def test_sector_rank_series_matches_point_in_time_rank_sectors_at_last_date():
    """The walk-forward table's rank/trend at the LAST date must agree with
    running the original point-in-time `rank_sectors` on the same full
    history — same formula, just computed for every date instead of one."""
    spy = _df(120, daily_change=0.1)
    sector_histories = {
        "XLK": _df(120, daily_change=0.5),
        "XLU": _df(120, daily_change=-0.2),
        "XLF": _df(120, daily_change=0.1),
    }
    rank_df, trend_df = sector_rank_series(sector_histories, spy)
    ranked = rank_sectors(sector_histories, spy)
    last_date = spy["close"].index[-1]
    for s in ranked:
        assert rank_df.loc[last_date, s.etf] == s.rank
        assert trend_df.loc[last_date, s.etf] == s.trend


def test_sector_rank_series_is_walk_forward_safe():
    """A date's rank must be unaffected by data that comes AFTER it -- cutting
    the input history short after some date must leave every earlier date's
    rank/trend identical, the same guarantee `regime_series`/`rs_rank_table`
    already have."""
    spy = _df(120, daily_change=0.1)
    sector_histories = {
        "XLK": _df(120, daily_change=0.5),
        "XLU": _df(120, daily_change=-0.2),
        "XLF": _df(120, daily_change=0.1),
    }
    full_rank_df, full_trend_df = sector_rank_series(sector_histories, spy)

    cutoff = 80
    spy_trunc = spy.iloc[:cutoff]
    sector_histories_trunc = {etf: df.iloc[:cutoff] for etf, df in sector_histories.items()}
    trunc_rank_df, trunc_trend_df = sector_rank_series(sector_histories_trunc, spy_trunc)

    check_date = spy["close"].index[cutoff - 1]
    for etf in sector_histories:
        assert trunc_rank_df.loc[check_date, etf] == full_rank_df.loc[check_date, etf]
        assert trunc_trend_df.loc[check_date, etf] == full_trend_df.loc[check_date, etf]
