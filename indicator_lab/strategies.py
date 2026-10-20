"""Candidate buy/sell indicators. Each takes (df, params) and returns
(entry, exit_signal_or_None, ExitRules, atr, size_or_None), all bar-aligned:
entry[t]/exit[t] are decided at bar t's close and filled at t+1's open."""
from __future__ import annotations

import numpy as np
import pandas as pd

from indicator_lab import ind
from indicator_lab.engine import ExitRules

_cache: dict = {}


def C(df: pd.DataFrame, key: str, fn):
    k = (id(df), key)
    if k not in _cache:
        _cache[k] = fn()
    return _cache[k]


def base(df):
    c = df["close"]
    return {
        "c": c,
        "atr": C(df, "atr14", lambda: ind.atr(df, 14)),
        "sma50": C(df, "sma50", lambda: ind.sma(c, 50)),
        "sma200": C(df, "sma200", lambda: ind.sma(c, 200)),
        "ema21": C(df, "ema21", lambda: ind.ema(c, 21)),
    }


def v0_repo_pullback(df, p):
    """Baseline: the scanner's 'Bullish Pullback' setup as a stand-alone indicator, with
    the scanner's own exits (2 ATR stop, 3R target capped to ATR*sqrt(5)*1.5, 5-bar hold)."""
    b = base(df)
    c = b["c"]
    r = C(df, "rsi14", lambda: ind.rsi(c, 14))
    uptrend = (c > b["sma50"]) & (b["sma50"] > b["sma200"])
    near = (c - b["ema21"]).abs() / b["ema21"] * 100 <= p.get("tol", 1.5)
    cooled = (r >= 35) & (r <= 58)
    entry = (uptrend & near & cooled).to_numpy()
    tgt = min(3 * 2.0, np.sqrt(5) * 1.5)
    rules = ExitRules(stop_atr=2.0, tgt_atr=tgt, max_bars=5)
    return entry, None, rules, b["atr"].to_numpy(), None


def rsi2_pullback(df, p):
    """Connors-style short-term mean reversion inside a long-term uptrend:
    buy when RSI(n) < lo and close > SMA(trend); sell when close > SMA(exit_ma) or
    RSI(n) > hi. Optional ATR stop / time stop."""
    b = base(df)
    c = b["c"]
    n = p.get("rsi_n", 2)
    r = C(df, f"rsi{n}", lambda: ind.rsi(c, n))
    tma = C(df, f"sma{p.get('trend', 200)}", lambda: ind.sma(c, p.get("trend", 200)))
    xma = C(df, f"sma{p.get('exit_ma', 5)}", lambda: ind.sma(c, p.get("exit_ma", 5)))
    entry = ((r < p.get("lo", 10)) & (c > tma)).to_numpy()
    exit_sig = ((c > xma) | (r > p.get("hi", 90))).to_numpy()
    rules = ExitRules(stop_atr=p.get("stop"), max_bars=p.get("max_bars"))
    return entry, exit_sig, rules, b["atr"].to_numpy(), None


def ema_trend(df, p):
    """Trend following: long while fast EMA > slow EMA (and close > SMA200 filter);
    exit on cross down or chandelier trail."""
    b = base(df)
    c = b["c"]
    f = C(df, f"ema{p['fast']}", lambda: ind.ema(c, p["fast"]))
    s = C(df, f"ema{p['slow']}", lambda: ind.ema(c, p["slow"]))
    up = f > s
    if p.get("filt", True):
        up = up & (c > b["sma200"])
    entry = (up & ~up.shift(1, fill_value=False)).to_numpy()
    exit_sig = (f < s).to_numpy()
    rules = ExitRules(stop_atr=p.get("stop"), trail_atr=p.get("trail"))
    return entry, exit_sig, rules, b["atr"].to_numpy(), None


def donchian_breakout(df, p):
    """Buy a close above the prior N-day high in an uptrend; exit on close below the
    prior M-day low or ATR trail."""
    b = base(df)
    c = b["c"]
    hi = df["high"].rolling(p["n"]).max().shift(1)
    lo = df["low"].rolling(p["m"]).min().shift(1)
    entry = ((c > hi) & (c > b["sma200"])).to_numpy()
    exit_sig = (c < lo).to_numpy()
    rules = ExitRules(stop_atr=p.get("stop"), trail_atr=p.get("trail"))
    return entry, exit_sig, rules, b["atr"].to_numpy(), None


# (strategy, params, numeric params to perturb in the robustness check)
BEST = (donchian_breakout, {"n": 20, "m": 20, "trail": 4.0}, ["n", "m", "trail"])
