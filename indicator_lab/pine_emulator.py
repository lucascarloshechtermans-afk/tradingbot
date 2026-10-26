"""Bar-by-bar Python emulation of indicator_lab/pine/swing_v3_quality_model.pine.

Purpose: prove that the Pine script produces the same BUY/SELL signals as the research
engine (`engine.simulate` + `meta`), so what the user sees in TradingView is what was
backtested. Mirrors Pine semantics where they differ from pandas:
- ta.percentrank(x, n): % of the previous n values that are <= the current value
  (pandas rank(pct=True) instead includes the current bar in the window).
- ta.stdev is the population stdev; ta.atr / ta.rsi use Wilder's RMA.
- `var` state persists across bars; everything else is recomputed per bar.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

from indicator_lab import ind
from indicator_lab.evaluate import get

MODEL = os.path.join(os.path.dirname(__file__), "pine", "v3_model.json")


def pine_percentrank(x: pd.Series, n: int) -> pd.Series:
    v = x.to_numpy(float)
    out = np.full(len(v), np.nan)
    for i in range(n, len(v)):
        prev = v[i - n:i]
        if np.isfinite(v[i]) and np.isfinite(prev).all():
            out[i] = 100.0 * (prev <= v[i]).sum() / n
    return pd.Series(out, index=x.index)


def pine_features(df: pd.DataFrame, spy: pd.Series) -> pd.DataFrame:
    c, h, lo, o, v = df["close"], df["high"], df["low"], df["open"], df["volume"]
    a = ind.atr(df, 14)
    sd = c.rolling(20).std(ddof=0)
    bbw = 4 * sd / ind.sma(c, 20)
    f = pd.DataFrame(index=df.index)
    f["ibs"] = ind.ibs(df)
    f["rvol"] = np.log(np.maximum(v / ind.sma(v, 50), 0.05))
    f["roc21"], f["roc63"], f["roc126"] = c / c.shift(21) - 1, c / c.shift(63) - 1, c / c.shift(126) - 1
    f["atr_pct"] = a / c * 100
    f["rsi14"] = ind.rsi(c, 14)
    f["ext50"] = (c - ind.sma(c, 50)) / a
    f["spy_roc63"] = spy / spy.shift(63) - 1
    f["rs63"] = f["roc63"] - f["spy_roc63"]
    f["dist52"] = c / h.rolling(252).max() - 1
    f["bbw_pct"] = pine_percentrank(bbw, 252) / 100
    f["gap"] = (o - c.shift()) / a.shift()
    f["spy_up"] = (spy > ind.sma(spy, 200)).astype(float)
    f["range_atr"] = (h - lo) / a.shift()
    f["brk_atr"] = (c - h.rolling(20).max().shift(1)) / a
    f["er20"] = (c - c.shift(20)).abs() / c.diff().abs().rolling(20).sum()
    return f


def load_model() -> dict:
    with open(MODEL) as fh:
        return json.load(fh)


def pine_score(f: pd.DataFrame, model: dict | None = None) -> pd.Series:
    model = model or load_model()
    s = pd.Series(model["b"], index=f.index)
    for name, mu, sd, w in zip(model["feats"], model["mu"], model["sd"], model["w"]):
        s = s + w * ((f[name] - mu) / sd).fillna(0.0)
    return s


def run(df: pd.DataFrame, spy: pd.Series, n=20, m=20, trail=4.0, trend_len=200, ibs_min=0.7,
        use_model=True, model: dict | None = None, cost_pct=0.1, with_trades=False, init_stop=True):
    """Returns (buy, sell) boolean arrays exactly as the Pine script marks them; with
    with_trades=True also the per-trade returns the Pine "chart statistics" row books."""
    model = model or load_model()
    c, h, lo = df["close"].to_numpy(), df["high"].to_numpy(), df["low"].to_numpy()
    a = ind.atr(df, 14).to_numpy()
    tma = ind.sma(df["close"], trend_len).to_numpy()
    hi_n = df["high"].rolling(n).max().shift(1).to_numpy()
    lo_m = df["low"].rolling(m).min().shift(1).to_numpy()
    ibs = ind.ibs(df).to_numpy()
    score = pine_score(pine_features(df, spy), model).to_numpy()
    ok = (score >= model["logit_thr"]) if use_model else np.ones(len(c), bool)
    o = df["open"].to_numpy()
    k = cost_pct / 100
    state, hh, stop, entry_px = 0, np.nan, np.nan, np.nan
    rets: list[float] = []
    buy = np.zeros(len(c), bool)
    sell = np.zeros(len(c), bool)
    for t in range(len(c)):
        exited = False
        if state == 3:
            rets.append(o[t] * (1 - k) / (entry_px * (1 + k)) - 1)
            state, stop, exited = 0, np.nan, True
        if state == 1:
            entry_px = o[t]
            state, hh = 2, h[t]
            istop = o[t] - trail * a[t - 1] if init_stop else -np.inf
            stop = max(istop, hh - trail * a[t])
            if lo[t] <= istop:
                rets.append(istop * (1 - k) / (entry_px * (1 + k)) - 1)
                sell[t], state, stop = True, 0, np.nan
            elif c[t] < lo_m[t]:
                sell[t], state = True, 3
        elif state == 2:
            if lo[t] <= stop:
                rets.append(min(o[t], stop) * (1 - k) / (entry_px * (1 + k)) - 1)
                sell[t], state, stop = True, 0, np.nan
            else:
                hh = max(hh, h[t])
                stop = max(stop, hh - trail * a[t])
                if c[t] < lo_m[t]:
                    sell[t], state = True, 3
        # Pine comparisons with na are false, so warm-up bars never signal
        if (state == 0 and not sell[t] and not exited and c[t] > hi_n[t] and c[t] > tma[t]
                and ibs[t] >= ibs_min and ok[t]):
            buy[t], state = True, 1
    if with_trades:
        return buy, sell, rets
    return buy, sell


def final_model_strategy(df, p):
    """Engine-side twin: the research engine with the SAME constant (final) model the Pine
    file embeds, so engine and emulator can be compared signal for signal."""
    from indicator_lab.engine import ExitRules
    from indicator_lab.meta import base_candidates, feature_frame
    model = load_model()
    f = feature_frame(df)
    score = pine_score(f, model).to_numpy()
    cand = base_candidates(df, p.get("n", 20), p.get("ibs_min", 0.7)).to_numpy()
    entry = cand & (score >= model["logit_thr"])
    exit_sig = (df["close"] < df["low"].rolling(p.get("m", 20)).min().shift(1)).to_numpy()
    rules = ExitRules(trail_atr=p.get("trail", 4.0), stop_atr=p.get("stop", 4.0))
    return entry, exit_sig, rules, ind.atr(df, 14).to_numpy(), None


def spy_close(index) -> pd.Series:
    return get("SPY")["close"].reindex(index).ffill()
