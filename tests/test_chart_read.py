import numpy as np
import pandas as pd

from analysis.chart_read import find_descending_pattern, find_zones, read_chart, resample_to_4h


def _daily_from_close(close: np.ndarray, start="2025-01-01") -> pd.DataFrame:
    idx = pd.bdate_range(start, periods=len(close), tz="UTC")
    c = pd.Series(close, index=idx)
    o = c.shift(1).fillna(c.iloc[0])
    return pd.DataFrame({"open": o, "high": np.maximum(o, c) * 1.01, "low": np.minimum(o, c) * 0.99,
                         "close": c, "volume": 1e6})


def _wedge_breakout() -> pd.DataFrame:
    rng = np.random.default_rng(3)
    up = np.linspace(50, 100, 220)                               # long uptrend: 200 EMA well below
    t = np.arange(90)
    wedge = 100 - 0.35 * t + 4 * np.sin(t / 3.0) * (1 - t / 110)  # falling, oscillating, converging
    brk = wedge[-1] + np.array([2.5, 5.0, 7.0])                   # breakout closes
    return _daily_from_close(np.concatenate([up, wedge, brk]) + rng.normal(0, 0.05, 313))


def test_resample_to_4h_builds_two_session_bars_per_day():
    idx = pd.date_range("2026-09-24 09:30", periods=7, freq="h", tz="America/New_York").tz_convert("UTC")
    h = pd.DataFrame({"open": range(7), "high": range(1, 8), "low": range(7), "close": range(7), "volume": 1.0}, index=idx)
    four = resample_to_4h(h)
    assert len(four) == 2
    assert four["open"].iloc[0] == 0 and four["close"].iloc[0] == 3   # 09:30..12:30 bars
    assert four["open"].iloc[1] == 4 and four["close"].iloc[1] == 6   # 13:30..15:30 bars


def test_falling_wedge_breakout_is_detected():
    daily = _wedge_breakout()
    pat = find_descending_pattern(daily)
    assert pat is not None
    assert pat.upper.slope_per_bar < 0
    assert pat.broke_out and pat.breakout_bars_ago is not None and pat.breakout_bars_ago <= 3


def test_zones_are_price_bands_with_touches():
    t = np.arange(300)
    zones = find_zones(_daily_from_close(100 + 10 * np.sin(t / 8.0)))   # a range: tops ~110, bottoms ~90
    assert zones
    assert all(z.high > z.low and z.touches >= 2 for z in zones)
    assert any(z.low <= 111 <= z.high + 1.5 for z in zones) and any(z.low - 1.5 <= 89 <= z.high for z in zones)


def test_read_chart_reports_200_ema_reclaim_and_plan():
    close = np.concatenate([np.linspace(100, 60, 260), np.linspace(60, 66, 30), [70.0, 74.0]])
    daily = _daily_from_close(close)
    read = read_chart("TEST", daily, hourly=None)
    ema200 = read.daily_emas[200]
    assert read.close > ema200
    assert any(h.startswith("CROSSED DTF 200 EMA ABOVE") for h in read.headlines)
    assert read.plan is not None and "HOLD THE DTF 200 EMA" in read.plan
    assert read.invalidation.startswith(f"daily close back below {ema200:.2f}")
