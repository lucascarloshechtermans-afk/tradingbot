import pandas as pd

from relative_strength.relative_strength import compute_relative_strength


def _series(n, daily_change, start=100.0, year="2024"):
    idx = pd.date_range(f"{year}-01-01", periods=n, freq="D")
    return pd.Series([start + i * daily_change for i in range(n)], index=idx)


def test_outperformance_detected():
    stock = _series(150, daily_change=0.5)
    benchmark = _series(150, daily_change=0.1)
    rs = compute_relative_strength(stock, benchmark)
    assert rs.outperforming_benchmark_1m is True
    assert rs.relative["1M"] > 0


def test_underperformance_detected():
    stock = _series(150, daily_change=0.05)
    benchmark = _series(150, daily_change=0.5)
    rs = compute_relative_strength(stock, benchmark)
    assert rs.outperforming_benchmark_1m is False
    assert rs.relative["1M"] < 0


def test_all_windows_present():
    stock = _series(150, daily_change=0.2)
    benchmark = _series(150, daily_change=0.1)
    rs = compute_relative_strength(stock, benchmark)
    assert set(rs.performance.keys()) == {"1W", "1M", "3M", "6M", "YTD"}
