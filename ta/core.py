"""Frame normalisation and the shared indicator bundle.

Every series in the bundle is causal (rolling / exponential windows over past
rows only), so `compute_indicators(df.iloc[:t+1])` equals
`compute_indicators(df).iloc[:t+1]` -- tested in tests/test_ta_core.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from indicators.momentum import macd as _macd
from indicators.momentum import roc as _roc
from indicators.momentum import rsi as _rsi
from indicators.trend import ema as _ema
from indicators.trend import sma as _sma
from indicators.trend_strength import adx as _adx
from indicators.volatility import atr as _atr
from indicators.volatility import bollinger_bands as _bb
from indicators.volatility import historical_volatility as _hv
from indicators.volume import accumulation_distribution as _ad
from indicators.volume import on_balance_volume as _obv

SMA_WINDOWS = (10, 20, 50, 100, 200)
EMA_WINDOWS = (9, 21, 34, 50, 200)
RSI_WINDOWS = (7, 14, 21)
OHLC = ["open", "high", "low", "close"]


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    """Lower-case OHLCV columns, sorted unique index, rows with complete OHLC.
    A missing volume column becomes NaN (volume metrics then report 'unavailable')."""
    if df is None or len(df) == 0:
        return pd.DataFrame(columns=OHLC + ["volume"])
    out = df.rename(columns=str.lower).copy()
    if "volume" not in out:
        out["volume"] = np.nan
    out = out[OHLC + ["volume"]]
    out = out[~out.index.duplicated(keep="last")].sort_index()
    return out.dropna(subset=OHLC)


def volume_available(df: pd.DataFrame, lookback: int = 60) -> bool:
    v = df["volume"].iloc[-lookback:]
    return bool(v.notna().sum() >= min(len(v), 20) and (v.fillna(0) > 0).mean() > 0.8)


def stochastic(high: pd.Series, low: pd.Series, close: pd.Series, k: int = 14, d: int = 3, smooth: int = 3):
    lo, hi = low.rolling(k, min_periods=k).min(), high.rolling(k, min_periods=k).max()
    raw = 100 * (close - lo) / (hi - lo).replace(0, np.nan)
    pct_k = raw.rolling(smooth, min_periods=smooth).mean()
    return pct_k, pct_k.rolling(d, min_periods=d).mean()


def stoch_rsi(close: pd.Series, rsi_window: int = 14, stoch_window: int = 14, k: int = 3, d: int = 3):
    r = _rsi(close, rsi_window)
    lo, hi = r.rolling(stoch_window, min_periods=stoch_window).min(), r.rolling(stoch_window, min_periods=stoch_window).max()
    raw = 100 * (r - lo) / (hi - lo).replace(0, np.nan)
    pct_k = raw.rolling(k, min_periods=k).mean()
    return pct_k, pct_k.rolling(d, min_periods=d).mean()


def keltner(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 20, atr_window: int = 10, mult: float = 1.5):
    mid = _ema(close, window)
    a = _atr(high, low, close, atr_window)
    return mid + mult * a, mid, mid - mult * a


def chaikin_money_flow(high, low, close, volume, window: int = 20) -> pd.Series:
    rng = (high - low).replace(0, np.nan)
    mfm = ((close - low) - (high - close)) / rng
    return (mfm * volume).rolling(window, min_periods=window).sum() / volume.rolling(window, min_periods=window).sum().replace(0, np.nan)


@dataclass
class Indicators:
    """All indicator series for one frame, indexed like the frame."""
    s: dict[str, pd.Series] = field(default_factory=dict)

    def __getitem__(self, key: str) -> pd.Series:
        return self.s[key]

    def __contains__(self, key: str) -> bool:
        return key in self.s

    def last(self, key: str, default: float = np.nan) -> float:
        v = self.s.get(key)
        if v is None or len(v) == 0:
            return default
        x = v.iloc[-1]
        return float(x) if pd.notna(x) else default


def compute_indicators(df: pd.DataFrame) -> Indicators:
    o, h, l, c, v = (df[k] for k in ("open", "high", "low", "close", "volume"))  # noqa: E741
    s: dict[str, pd.Series] = {}
    for w in SMA_WINDOWS:
        s[f"sma{w}"] = _sma(c, w)
    for w in EMA_WINDOWS:
        s[f"ema{w}"] = _ema(c, w)
    for w in RSI_WINDOWS:
        s[f"rsi{w}"] = _rsi(c, w)
    s["macd"], s["macd_signal"], s["macd_hist"] = _macd(c)
    for w in (5, 10, 20, 60):
        s[f"roc{w}"] = _roc(c, w)
    s["stoch_k"], s["stoch_d"] = stochastic(h, l, c)
    s["stochrsi_k"], s["stochrsi_d"] = stoch_rsi(c)
    s["adx"], s["plus_di"], s["minus_di"] = _adx(h, l, c)
    s["atr"] = _atr(h, l, c, 14)
    s["atr_pct"] = s["atr"] / c * 100
    s["atr10"], s["atr50"] = _atr(h, l, c, 10), _atr(h, l, c, 50)
    s["bb_upper"], s["bb_mid"], s["bb_lower"] = _bb(c)
    s["bb_width"] = (s["bb_upper"] - s["bb_lower"]) / s["bb_mid"]
    s["bb_width_pct"] = s["bb_width"].rolling(120, min_periods=40).rank(pct=True)
    s["kc_upper"], s["kc_mid"], s["kc_lower"] = keltner(h, l, c)
    s["squeeze_on"] = (s["bb_upper"] < s["kc_upper"]) & (s["bb_lower"] > s["kc_lower"])
    s["hv20"] = _hv(c, 20)
    s["hv20_pct"] = s["hv20"].rolling(252, min_periods=60).rank(pct=True)
    if volume_available(df):
        vol = v.astype(float)
        s["vol_sma20"] = vol.rolling(20, min_periods=20).mean()
        s["rvol"] = vol / vol.rolling(20, min_periods=20).mean().shift(1)
        s["obv"] = _obv(c, vol)
        s["ad"] = _ad(h, l, c, vol)
        s["cmf"] = chaikin_money_flow(h, l, c, vol)
    for w in (20, 50):
        for key in (f"sma{w}",):
            s[f"{key}_slope"] = (s[key] / s[key].shift(10) - 1) * 100
    s["sma200_slope"] = (s["sma200"] / s["sma200"].shift(20) - 1) * 100
    s["ema21_slope"] = (s["ema21"] / s["ema21"].shift(5) - 1) * 100
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    s["range"] = h - l
    s["tr"] = tr
    return Indicators(s)


def last_completed(df: pd.DataFrame) -> pd.DataFrame:
    """Daily frames: drop today's live bar (data.sessions) -- signals use closes only."""
    from data.sessions import drop_incomplete_daily

    return drop_incomplete_daily(df)
