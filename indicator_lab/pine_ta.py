"""Exact re-implementations of the TradingView `ta.*` built-ins the v3 Pine script uses,
bar by bar, so Pine-side feature values can be reproduced in Python.

Pine semantics (documented TradingView source):
- ta.sma(x, n): mean of the last n values; na while fewer than n or any of them na.
- ta.rma(x, n): alpha = 1/n; seeds with ta.sma(x, n) on the first bar it is defined, then
  rma = alpha * x + (1 - alpha) * rma[1].   (pandas ewm(adjust=False) seeds with the first x instead.)
- ta.atr(n) = ta.rma(true range, n), true range on the first bar = high - low.
- ta.rsi(x, n) = 100 - 100 / (1 + rma(up, n) / rma(down, n)).
- ta.stdev(x, n) with biased=true (default): population stdev (ddof=0).
- ta.percentrank(x, n): % of the PREVIOUS n values that are <= the current value.
- ta.highest(x, n): max of the last n values incl. the current bar; na while fewer than n bars.
- math.sum(x, n): sum of the last n values; na while fewer than n or any na.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _arr(x) -> np.ndarray:
    return np.asarray(x, dtype=float)


def sma(x, n: int) -> np.ndarray:
    x = _arr(x)
    out = np.full(len(x), np.nan)
    for i in range(n - 1, len(x)):
        w = x[i - n + 1:i + 1]
        if np.isfinite(w).all():
            out[i] = w.mean()
    return out


def rma(x, n: int) -> np.ndarray:
    x = _arr(x)
    s = sma(x, n)
    out = np.full(len(x), np.nan)
    a = 1.0 / n
    for i in range(len(x)):
        if i > 0 and np.isfinite(out[i - 1]):
            out[i] = a * x[i] + (1 - a) * out[i - 1] if np.isfinite(x[i]) else np.nan
        else:
            out[i] = s[i]
    return out


def true_range(h, lo, c) -> np.ndarray:
    h, lo, c = _arr(h), _arr(lo), _arr(c)
    pc = np.r_[np.nan, c[:-1]]
    tr = np.maximum.reduce([h - lo, np.abs(h - pc), np.abs(lo - pc)])
    tr[0] = h[0] - lo[0]
    return tr


def atr(h, lo, c, n: int = 14) -> np.ndarray:
    return rma(true_range(h, lo, c), n)


def rsi(c, n: int = 14) -> np.ndarray:
    c = _arr(c)
    ch = np.r_[np.nan, np.diff(c)]
    up = np.where(np.isfinite(ch), np.maximum(ch, 0), np.nan)
    dn = np.where(np.isfinite(ch), np.maximum(-ch, 0), np.nan)
    ru, rd = rma(up, n), rma(dn, n)
    with np.errstate(divide="ignore", invalid="ignore"):
        rs = ru / rd
        out = 100 - 100 / (1 + rs)
    out[(rd == 0) & np.isfinite(ru)] = 100.0  # rs = +inf -> 100
    return out


def stdev(x, n: int) -> np.ndarray:
    x = _arr(x)
    out = np.full(len(x), np.nan)
    for i in range(n - 1, len(x)):
        w = x[i - n + 1:i + 1]
        if np.isfinite(w).all():
            out[i] = w.std(ddof=0)
    return out


def percentrank(x, n: int) -> np.ndarray:
    x = _arr(x)
    out = np.full(len(x), np.nan)
    for i in range(n, len(x)):
        prev = x[i - n:i]
        if np.isfinite(x[i]) and np.isfinite(prev).all():
            out[i] = 100.0 * (prev <= x[i]).sum() / n
    return out


def highest(x, n: int) -> np.ndarray:
    x = _arr(x)
    return pd.Series(x).rolling(n, min_periods=n).max().to_numpy()


def msum(x, n: int) -> np.ndarray:
    x = _arr(x)
    return pd.Series(x).rolling(n, min_periods=n).sum().to_numpy()


def shift(x, k: int = 1) -> np.ndarray:
    x = _arr(x)
    return np.r_[np.full(k, np.nan), x[:-k]] if k > 0 else x


# ---- pandas-compatible variants, implemented the way the FIXED Pine script does it (bar by bar) ----

def rma_py(x, n: int) -> np.ndarray:
    """Pine port of pandas ewm(alpha=1/n, adjust=False, min_periods=n).mean():
    seed with the first non-na value, then a*x + (1-a)*prev; na until n non-na values were seen."""
    x = _arr(x)
    out = np.full(len(x), np.nan)
    s, cnt, a = np.nan, 0, 1.0 / n
    for i in range(len(x)):
        if np.isfinite(x[i]):
            s = x[i] if not np.isfinite(s) else a * x[i] + (1 - a) * s
            cnt += 1
        out[i] = s if cnt >= n else np.nan
    return out


def atr_py(h, lo, c, n: int = 14) -> np.ndarray:
    return rma_py(true_range(h, lo, c), n)


def rsi_py(c, n: int = 14) -> np.ndarray:
    """ind.rsi: up/down RMA (pandas-style), rs = up/down (down == 0 -> rsi 100)."""
    c = _arr(c)
    ch = np.r_[np.nan, np.diff(c)]
    up = np.where(np.isfinite(ch), np.maximum(ch, 0), np.nan)
    dn = np.where(np.isfinite(ch), np.maximum(-ch, 0), np.nan)
    ru, rd = rma_py(up, n), rma_py(dn, n)
    with np.errstate(divide="ignore", invalid="ignore"):
        out = 100 - 100 / (1 + ru / rd)
    out[(rd == 0) & np.isfinite(ru)] = 100.0
    out[~np.isfinite(ru)] = np.nan
    # pandas: rs NaN (down == 0) -> fillna(100); before warm-up (ru NaN) also fillna(100)
    return out


def rank_pct_incl(x, n: int, min_count: int) -> np.ndarray:
    """Pine port of pandas rolling(n, min_periods).rank(pct=True) (average ties, current bar included)."""
    x = _arr(x)
    out = np.full(len(x), np.nan)
    for i in range(len(x)):
        if not np.isfinite(x[i]):
            continue
        w = x[max(0, i - n + 1):i + 1]
        w = w[np.isfinite(w)]
        if len(w) < min_count:
            continue
        less = (w < x[i]).sum()
        eq = (w == x[i]).sum()
        out[i] = (less + (eq + 1) / 2) / len(w)
    return out


def highest_min(x, n: int, min_count: int) -> np.ndarray:
    x = _arr(x)
    return pd.Series(x).rolling(n, min_periods=min_count).max().to_numpy()
