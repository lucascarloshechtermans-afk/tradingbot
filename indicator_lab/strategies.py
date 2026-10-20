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


def _spy(df):
    from indicator_lab import data
    return data.load("SPY").reindex(df.index).ffill()


def breakout(df, p):
    """v1 Donchian breakout plus optional filters, each off unless its param is set:
    regime: SPY close > SMA(regime) | rs: ticker's `rs`-day return > SPY's |
    adx_min: ADX14 >= adx_min | vol_mult: breakout-day volume >= vol_mult x SMA50(volume) |
    ext_max: close no more than ext_max ATR above SMA50 (don't chase) |
    stop: initial ATR stop | max_bars: time stop."""
    b = base(df)
    c = b["c"]
    n, m = p["n"], p["m"]
    src_hi = c if p.get("close_break") else df["high"]
    hi = C(df, f"hh{n}{p.get('close_break')}", lambda: src_hi.rolling(n).max().shift(1))
    lo = C(df, f"ll{m}", lambda: df["low"].rolling(m).min().shift(1))
    tl = p.get("trend_len", 200)
    tma = C(df, f"sma{tl}", lambda: ind.sma(c, tl))
    cond = (c > hi) & (c > tma)
    if p.get("slope"):  # trend MA higher than `slope` bars ago
        cond &= tma > tma.shift(p["slope"])
    if p.get("abs_mom"):  # positive absolute momentum over abs_mom bars
        cond &= ind.roc(c, p["abs_mom"]) > 0
    if p.get("gap_max"):  # skip breakouts that gapped up more than gap_max ATR
        cond &= (df["open"] - c.shift()) / b["atr"].shift() <= p["gap_max"]
    if p.get("squeeze"):  # BB width now below its `squeeze`-pctile of the last year, within 10 bars
        lo_b, mid_b, up_b = ind.bbands(c, 20, 2.0)
        bw = (up_b - lo_b) / mid_b
        pct = bw.rolling(252).rank(pct=True)
        cond &= (pct <= p["squeeze"]).rolling(10).max().astype(bool)
    if p.get("regime"):
        spy = _spy(df)["close"]
        cond &= spy > ind.sma(spy, p["regime"])
    if p.get("rs"):
        k = p["rs"]
        spy = _spy(df)["close"]
        cond &= ind.roc(c, k) > ind.roc(spy, k)
    if p.get("adx_min"):
        a = C(df, "adx14", lambda: ind.adx(df, 14)[2])
        cond &= a >= p["adx_min"]
    if p.get("vol_mult"):
        v = df["volume"]
        cond &= v >= p["vol_mult"] * ind.sma(v, 50)
    if p.get("ext_max"):
        cond &= (c - b["sma50"]) / b["atr"] <= p["ext_max"]
    if p.get("ibs_min") is not None:
        cond &= ind.ibs(df) >= p["ibs_min"]
    if p.get("wk_ema"):  # last completed weekly close above its weekly EMA
        wk = c.resample("W-FRI").last().dropna()
        ok = (wk > ind.ema(wk, p["wk_ema"])).reindex(c.index, method="ffill").fillna(False)
        cond &= ok.astype(bool)
    if p.get("wk_macd"):  # weekly MACD histogram > 0
        wk = c.resample("W-FRI").last().dropna()
        ok = (ind.macd(wk)[2] > 0).reindex(c.index, method="ffill").fillna(False)
        cond &= ok.astype(bool)
    if p.get("atr_pct_min"):
        cond &= b["atr"] / c * 100 >= p["atr_pct_min"]
    if p.get("er_min"):
        er_n = p.get("er_n", 50)
        cond &= C(df, f"er{er_n}", lambda: ind.efficiency_ratio(c, er_n)) >= p["er_min"]
    if p.get("vdry"):  # volume dried up into the breakout: 10-bar avg vol < vdry x 50-bar avg (prior bars)
        v = df["volume"]
        cond &= (ind.sma(v, 10) / ind.sma(v, 50)).shift(1) <= p["vdry"]
    if p.get("range_min"):  # breakout bar's range >= range_min x ATR (prior)
        cond &= (df["high"] - df["low"]) >= p["range_min"] * b["atr"].shift(1)
    if p.get("nr"):  # the bar before the breakout had the narrowest range of the last `nr` bars
        rng = df["high"] - df["low"]
        cond &= (rng.shift(1) <= rng.shift(1).rolling(p["nr"]).min())
    if p.get("near_high"):  # close within near_high % of its 252-day high
        h252 = df["high"].rolling(252, min_periods=200).max()
        cond &= c >= h252 * (1 - p["near_high"] / 100)
    if p.get("fresh"):  # first breakout after a base: no n-day breakout in the prior `fresh` bars
        prior = (c > hi).shift(1, fill_value=False).rolling(p["fresh"], min_periods=1).max().astype(bool)
        cond &= ~prior
    if p.get("cont"):  # continuation: there WAS a breakout in the prior `cont` bars
        prior = (c > hi).shift(1, fill_value=False).rolling(p["cont"], min_periods=1).max().astype(bool)
        cond &= prior
    if p.get("months"):  # only enter in these calendar months
        cond &= pd.Series(c.index.month.isin(p["months"]), index=c.index)
    entry = cond.to_numpy()
    if p.get("exit_close_low"):  # exit on close below the lowest CLOSE of m bars
        lo = C(df, f"llc{m}", lambda: c.rolling(m).min().shift(1))
    if p.get("exit_sma"):
        lo = C(df, f"sma{m}", lambda: ind.sma(c, m))
    ex = c < lo
    if p.get("exit_ema"):
        ex |= c < C(df, f"ema{p['exit_ema']}", lambda: ind.ema(c, p["exit_ema"]))
    exit_sig = ex.to_numpy()
    rules = ExitRules(stop_atr=p.get("stop"), trail_atr=p.get("trail"), max_bars=p.get("max_bars"),
                      be_atr=p.get("be"), close_stop=bool(p.get("close_stop")),
                      tight_after=p.get("tight_after"), tight_trail=p.get("tight_trail"))
    size = None
    if p.get("vol_target"):
        # risk-parity-ish: full size when ATR% <= vol_target, scaled down above it
        size = np.clip(p["vol_target"] / (b["atr"] / c * 100), 0, 1).to_numpy()
    return entry, exit_sig, rules, b["atr"].to_numpy(), size


def breakout_pullback(df, p):
    """Buy the first dip AFTER a v2-style breakout instead of the breakout itself:
    a strong-close n-day breakout happened within the last `within` bars, and today
    RSI(2) < `rsi_lo` while the close is still above the breakout's trend MA.
    Exits as v2 (m-day low, ATR chandelier)."""
    b = base(df)
    c = b["c"]
    n, m = p["n"], p["m"]
    hi = C(df, f"hh{n}None", lambda: df["high"].rolling(n).max().shift(1))
    lo = C(df, f"ll{m}", lambda: df["low"].rolling(m).min().shift(1))
    brk = (c > hi) & (c > b["sma200"]) & (ind.ibs(df) >= p.get("ibs_min", 0.0))
    recent = brk.rolling(p.get("within", 10), min_periods=1).max().astype(bool) & ~brk
    r2 = C(df, "rsi2", lambda: ind.rsi(c, 2))
    dip = r2 < p.get("rsi_lo", 20)
    entry = (recent & dip & (c > b["sma200"])).to_numpy()
    exit_sig = (c < lo).to_numpy()
    rules = ExitRules(stop_atr=p.get("stop"), trail_atr=p.get("trail"))
    return entry, exit_sig, rules, b["atr"].to_numpy(), None


def family(df, p):
    """Classic entry families, all with v2's exits (m-day low + ATR trail) so only the
    entry differs. Optional IBS strong-close and SMA200 filters as in v2."""
    b = base(df)
    c = b["c"]
    k = p["kind"]
    if k == "supertrend":
        st = C(df, f"st{p.get('st_n', 10)}{p.get('st_mult', 3.0)}",
               lambda: ind.supertrend(df, p.get("st_n", 10), p.get("st_mult", 3.0)))
        sig = st & ~st.shift(1, fill_value=False)
    elif k == "keltner":
        mid = ind.ema(c, 20)
        sig = c > mid + p.get("kc_mult", 2.0) * b["atr"]
    elif k == "macd":
        m_, s_, h_ = ind.macd(c)
        sig = (m_ > s_) & (m_.shift() <= s_.shift()) & (m_ > 0)
    elif k == "ichimoku":
        tenkan = (df["high"].rolling(9).max() + df["low"].rolling(9).min()) / 2
        kijun = (df["high"].rolling(26).max() + df["low"].rolling(26).min()) / 2
        span_a = ((tenkan + kijun) / 2).shift(26)
        span_b = ((df["high"].rolling(52).max() + df["low"].rolling(52).min()) / 2).shift(26)
        above = (c > span_a) & (c > span_b) & (tenkan > kijun)
        sig = above & ~above.shift(1, fill_value=False)
    elif k == "aroon":
        au = C(df, "aroonup25", lambda: ind.aroon_up(df, 25))
        sig = (au >= 100) & (au.shift() < 100)
    elif k == "bb":
        lo_b, mid_b, up_b = ind.bbands(c, 20, 2.0)
        sig = c > up_b
    elif k == "roc":
        r = ind.roc(c, p.get("roc_n", 20))
        sig = (r > p.get("roc_min", 0.10)) & (r.shift() <= p.get("roc_min", 0.10))
    else:
        raise ValueError(k)
    cond = sig & (c > b["sma200"])
    if p.get("ibs_min") is not None:
        cond &= ind.ibs(df) >= p["ibs_min"]
    lo = C(df, f"ll{p['m']}", lambda: df["low"].rolling(p["m"]).min().shift(1))
    rules = ExitRules(trail_atr=p.get("trail"))
    return cond.to_numpy(), (c < lo).to_numpy(), rules, b["atr"].to_numpy(), None


# (strategy, params, numeric params to perturb in the robustness check)
V2 = (breakout, {"n": 20, "m": 20, "trail": 4.0, "ibs_min": 0.7}, ["n", "m", "trail", "ibs_min"])

from indicator_lab.meta import meta_breakout  # noqa: E402  (meta does not import this module)

BEST = (meta_breakout, {"n": 20, "m": 20, "trail": 4.0, "ibs_min": 0.7, "keep": 0.75, "l2": 100.0},
        ["n", "m", "trail", "ibs_min", "keep"])
