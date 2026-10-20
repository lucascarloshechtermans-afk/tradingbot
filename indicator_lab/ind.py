"""Indicator functions written to match TradingView's ta.* built-ins, so results
here carry over to the Pine port (Wilder RMA for RSI/ATR/ADX, EMA seeded the
pandas-ewm way which converges to Pine's within the warm-up we discard)."""
from __future__ import annotations

import numpy as np
import pandas as pd


def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n, min_periods=n).mean()


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False, min_periods=n).mean()


def rma(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()


def rsi(c: pd.Series, n: int = 14) -> pd.Series:
    d = c.diff()
    up = rma(d.clip(lower=0), n)
    dn = rma((-d).clip(lower=0), n)
    rs = up / dn.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(100)


def true_range(df: pd.DataFrame) -> pd.Series:
    pc = df["close"].shift()
    return pd.concat([df["high"] - df["low"], (df["high"] - pc).abs(), (df["low"] - pc).abs()], axis=1).max(axis=1)


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    return rma(true_range(df), n)


def adx(df: pd.DataFrame, n: int = 14) -> tuple[pd.Series, pd.Series, pd.Series]:
    up = df["high"].diff()
    dn = -df["low"].diff()
    plus_dm = np.where((up > dn) & (up > 0), up, 0.0)
    minus_dm = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = rma(true_range(df), n)
    pdi = 100 * rma(pd.Series(plus_dm, index=df.index), n) / tr
    mdi = 100 * rma(pd.Series(minus_dm, index=df.index), n) / tr
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    return pdi, mdi, rma(dx.fillna(0), n)


def macd(c: pd.Series, fast: int = 12, slow: int = 26, sig: int = 9):
    m = ema(c, fast) - ema(c, slow)
    s = ema(m, sig)
    return m, s, m - s


def bbands(c: pd.Series, n: int = 20, k: float = 2.0):
    mid = sma(c, n)
    sd = c.rolling(n, min_periods=n).std(ddof=0)
    return mid - k * sd, mid, mid + k * sd


def stoch(df: pd.DataFrame, n: int = 14, smooth: int = 3) -> pd.Series:
    ll = df["low"].rolling(n).min()
    hh = df["high"].rolling(n).max()
    k = 100 * (df["close"] - ll) / (hh - ll).replace(0, np.nan)
    return sma(k, smooth)


def ibs(df: pd.DataFrame) -> pd.Series:
    """Internal bar strength: where the close sits in the day's range (0..1)."""
    rng = (df["high"] - df["low"]).replace(0, np.nan)
    return ((df["close"] - df["low"]) / rng).fillna(0.5)


def roc(c: pd.Series, n: int) -> pd.Series:
    return c / c.shift(n) - 1


def efficiency_ratio(c: pd.Series, n: int) -> pd.Series:
    """Kaufman: net move over n bars / sum of absolute bar moves (0 = chop, 1 = straight line)."""
    net = (c - c.shift(n)).abs()
    path = c.diff().abs().rolling(n).sum()
    return net / path.replace(0, np.nan)


def supertrend(df: pd.DataFrame, n: int = 10, mult: float = 3.0) -> pd.Series:
    """True while in an up-trend (TradingView ta.supertrend direction < 0)."""
    a = atr(df, n).to_numpy()
    hl2 = ((df["high"] + df["low"]) / 2).to_numpy()
    c = df["close"].to_numpy()
    up = hl2 - mult * a
    dn = hl2 + mult * a
    fu, fd = up.copy(), dn.copy()
    trend = np.ones(len(c), dtype=bool)
    for i in range(1, len(c)):
        if not np.isfinite(a[i]):
            continue
        fu[i] = max(up[i], fu[i - 1]) if np.isfinite(fu[i - 1]) and c[i - 1] > fu[i - 1] else up[i]
        fd[i] = min(dn[i], fd[i - 1]) if np.isfinite(fd[i - 1]) and c[i - 1] < fd[i - 1] else dn[i]
        if trend[i - 1] and c[i] < fu[i]:
            trend[i] = False
        elif not trend[i - 1] and c[i] > fd[i]:
            trend[i] = True
        else:
            trend[i] = trend[i - 1]
    return pd.Series(trend, index=df.index)


def aroon_up(df: pd.DataFrame, n: int = 25) -> pd.Series:
    return df["high"].rolling(n + 1).apply(lambda x: float(np.argmax(x)) / n * 100, raw=True)
