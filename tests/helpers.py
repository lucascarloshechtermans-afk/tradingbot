from __future__ import annotations

import numpy as np
import pandas as pd

from strategies.context import build_context


def _to_ohlcv(close: pd.Series, volume: float | pd.Series = 1_000_000.0, spread: float = 0.3) -> pd.DataFrame:
    open_ = close.shift(1).fillna(close.iloc[0])
    high = pd.concat([open_, close], axis=1).max(axis=1) + spread
    low = pd.concat([open_, close], axis=1).min(axis=1) - spread
    vol = volume if isinstance(volume, pd.Series) else pd.Series(volume, index=close.index)
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": vol})


def zigzag_uptrend_history(
    n: int = 260, start: float = 50.0, step: float = 0.35, amplitude: float = 2.5, period: int = 10,
) -> pd.DataFrame:
    """A rising series with regular oscillation superimposed: real swing highs/lows
    (needed for market-structure/level detection) while the underlying trend stays
    clearly bullish once smoothed by a moving average."""
    idx = pd.date_range("2023-01-01", periods=n, freq="D")
    t = np.arange(n)
    close = pd.Series(start + step * t + amplitude * np.sin(2 * np.pi * t / period), index=idx)
    return _to_ohlcv(close)


def flat_history(n: int = 260, level: float = 50.0) -> pd.DataFrame:
    idx = pd.date_range("2023-01-01", periods=n, freq="D")
    return _to_ohlcv(pd.Series(level, index=idx), spread=0.2)


def breakout_history(rise_days: int = 220, step: float = 0.1, start: float = 50.0, spike: float = 8.0) -> pd.DataFrame:
    idx = pd.date_range("2023-01-01", periods=rise_days + 1, freq="D")
    close = pd.Series([start + step * i for i in range(rise_days)] + [start + step * (rise_days - 1) + spike], index=idx)
    volume = pd.Series([1_000_000.0] * rise_days + [3_000_000.0], index=idx)
    return _to_ohlcv(close, volume=volume)


def pullback_history(rise_days: int = 220, step: float = 0.4, start: float = 50.0, decline_days: int = 10, decline_pct: float = 3.0) -> pd.DataFrame:
    rising = start + step * np.arange(rise_days)
    peak = rising[-1]
    decline = peak * (1 - np.linspace(0, decline_pct / 100, decline_days))
    idx = pd.date_range("2023-01-01", periods=rise_days + decline_days, freq="D")
    close = pd.Series(np.concatenate([rising, decline]), index=idx)
    return _to_ohlcv(close)


def mean_reversion_history(rise_days: int = 220, step: float = 0.4, start: float = 50.0, decline_days: int = 5, decline_pct: float = 10.0) -> pd.DataFrame:
    return pullback_history(rise_days, step, start, decline_days, decline_pct)


def support_bounce_history() -> pd.DataFrame:
    rise_days, step, start = 220, 0.4, 50.0
    rising = start + step * np.arange(rise_days)
    tail_closes = [130.0, 132, 134, 136, 135, 133, 130.2, 132, 133.5, 132.5, 130.5]
    all_close = np.concatenate([rising, tail_closes])
    idx = pd.date_range("2023-01-01", periods=len(all_close), freq="D")
    close = pd.Series(all_close, index=idx)
    open_ = close.shift(1).fillna(close.iloc[0])
    low = close - 0.5
    high = pd.concat([open_, close], axis=1).max(axis=1) + 0.5
    touch_positions = {rise_days: 130.0, rise_days + 6: 130.2, rise_days + 10: 130.1}
    for pos, val in touch_positions.items():
        low.iloc[pos] = val
    volume = pd.Series(1_000_000.0, index=idx)
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": volume})


def momentum_continuation_history(flat_days: int = 200, accel_days: int = 20, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    flat = 50 + np.linspace(0, 2, flat_days) + rng.normal(0, 0.05, flat_days)
    t = np.arange(1, accel_days + 1)
    accel = flat[-1] + 0.05 * t**1.6 + rng.normal(0, 0.05, accel_days)
    idx = pd.date_range("2023-01-01", periods=flat_days + accel_days, freq="D")
    close = pd.Series(np.concatenate([flat, accel]), index=idx)
    return _to_ohlcv(close, spread=0.2)


def volatility_contraction_history(rise_days: int = 150, flat_days: int = 120, step: float = 0.4, start: float = 50.0, seed: int = 8, flat_noise: float = 0.08) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rising = start + step * np.arange(rise_days) + rng.normal(0, 0.3, rise_days)
    flat = rising[-1] + rng.normal(0, flat_noise, flat_days)
    idx = pd.date_range("2023-01-01", periods=rise_days + flat_days, freq="D")
    close = pd.Series(np.concatenate([rising, flat]), index=idx)
    return _to_ohlcv(close, spread=0.1)


def downtrend_oversold_history(decline_days: int = 220, step: float = 0.4, start: float = 200.0, sharp_days: int = 5, sharp_pct: float = 10.0) -> pd.DataFrame:
    """A long downtrend (price well below its own SMA200) ending in a further sharp
    drop — oversold, but NOT a mean-reversion candidate since the longer-term trend
    is down, not up."""
    declining = start - step * np.arange(decline_days)
    trough = declining[-1]
    sharp_drop = trough * (1 - np.linspace(0, sharp_pct / 100, sharp_days))
    idx = pd.date_range("2023-01-01", periods=decline_days + sharp_days, freq="D")
    close = pd.Series(np.concatenate([declining, sharp_drop]), index=idx)
    return _to_ohlcv(close)


def context_from(history: pd.DataFrame, ticker: str = "TEST"):
    return build_context(ticker, history)
