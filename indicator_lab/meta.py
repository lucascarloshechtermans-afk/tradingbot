"""Meta-labeling: learn WHICH base breakout signals to take.

For every candidate bar of a base rule (n-day breakout above SMA200) we compute
features known at that close and the outcome of a trade opened there with the base
exits. A small L2 logistic regression is refit before each calendar year on
candidates whose trade had already CLOSED before that year (no label leakage), from
DEV tickers only. In the test year, a candidate is taken when its predicted win
probability is in the top `keep` fraction of that year's training predictions.
Linear on standardized features -> portable to Pine as hard-coded coefficients.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from indicator_lab import data, ind
from indicator_lab.engine import ExitRules
from indicator_lab.evaluate import get

FEATS = ["ibs", "rvol", "roc21", "roc63", "roc126", "atr_pct", "rsi14", "ext50", "rs63", "dist52",
         "bbw_pct", "gap", "spy_up", "spy_roc63", "range_atr", "brk_atr", "er20"]


def feature_frame(df: pd.DataFrame) -> pd.DataFrame:
    c = df["close"]
    a = ind.atr(df, 14)
    spy = get("SPY")["close"].reindex(df.index).ffill()
    lo_b, mid_b, up_b = ind.bbands(c, 20, 2.0)
    bw = (up_b - lo_b) / mid_b
    hi20 = df["high"].rolling(20).max().shift(1)
    return pd.DataFrame({
        "ibs": ind.ibs(df),
        "rvol": np.log((df["volume"] / ind.sma(df["volume"], 50)).clip(lower=0.05)),
        "roc21": ind.roc(c, 21), "roc63": ind.roc(c, 63), "roc126": ind.roc(c, 126),
        "atr_pct": a / c * 100,
        "rsi14": ind.rsi(c, 14),
        "ext50": (c - ind.sma(c, 50)) / a,
        "rs63": ind.roc(c, 63) - ind.roc(spy, 63),
        "dist52": c / df["high"].rolling(252, min_periods=200).max() - 1,
        "bbw_pct": bw.rolling(252, min_periods=100).rank(pct=True),
        "gap": (df["open"] - c.shift()) / a.shift(),
        "spy_up": (spy > ind.sma(spy, 200)).astype(float),
        "spy_roc63": ind.roc(spy, 63),
        "range_atr": (df["high"] - df["low"]) / a.shift(),
        "brk_atr": (c - hi20) / a,
        "er20": ind.efficiency_ratio(c, 20),
    })


def base_candidates(df: pd.DataFrame, n: int = 20, ibs_min: float = 0.0) -> pd.Series:
    c = df["close"]
    return (c > df["high"].rolling(n).max().shift(1)) & (c > ind.sma(c, 200)) & (ind.ibs(df) >= ibs_min)


def single_trade(o, h, lo, c, atr, exit_sig, i, rules: ExitRules, cost=0.001):
    """Outcome of a trade signalled at bar i (filled at i+1 open), same logic as engine."""
    n = len(c)
    if i + 1 >= n:
        return np.nan, n - 1
    t = i + 1
    ep = o[t]
    stop = ep - rules.stop_atr * atr[i] if rules.stop_atr else -np.inf
    hh = h[t]
    if rules.trail_atr:
        stop = max(stop, hh - rules.trail_atr * atr[t])
    pend = exit_sig[t]
    for t in range(i + 2, n):
        if pend:
            return o[t] * (1 - cost) / (ep * (1 + cost)) - 1, t
        if o[t] <= stop:
            return o[t] * (1 - cost) / (ep * (1 + cost)) - 1, t
        if lo[t] <= stop:
            return stop * (1 - cost) / (ep * (1 + cost)) - 1, t
        hh = max(hh, h[t])
        if rules.trail_atr:
            stop = max(stop, hh - rules.trail_atr * atr[t])
        pend = exit_sig[t]
    return c[-1] * (1 - cost) / (ep * (1 + cost)) - 1, n - 1


def candidate_table(tickers: list[str], n: int = 20, m: int = 20, trail: float = 4.0,
                    ibs_min: float = 0.0) -> pd.DataFrame:
    rows = []
    rules = ExitRules(trail_atr=trail)
    for t in tickers:
        df = get(t)
        f = feature_frame(df)
        cand = base_candidates(df, n, ibs_min).to_numpy()
        lo_m = df["low"].rolling(m).min().shift(1)
        exit_sig = (df["close"] < lo_m).to_numpy()
        o, h, lo, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
        a = ind.atr(df, 14).to_numpy()
        for i in np.flatnonzero(cand):
            r, xi = single_trade(o, h, lo, c, a, exit_sig, i, rules)
            rows.append({"ticker": t, "date": df.index[i], "exit_date": df.index[xi], "ret": r,
                         **f.iloc[i].to_dict()})
    return pd.DataFrame(rows).dropna()


def fit_logreg(X: np.ndarray, y: np.ndarray, l2: float = 1.0, iters: int = 50):
    """Newton-Raphson L2 logistic regression. Returns (w, b)."""
    nobs, k = X.shape
    Xb = np.hstack([X, np.ones((nobs, 1))])
    w = np.zeros(k + 1)
    reg = np.eye(k + 1) * l2
    reg[-1, -1] = 0
    for _ in range(iters):
        p = 1 / (1 + np.exp(-Xb @ w))
        g = Xb.T @ (p - y) + reg @ w
        H = (Xb * (p * (1 - p))[:, None]).T @ Xb + reg
        step = np.linalg.solve(H, g)
        w -= step
        if np.abs(step).max() < 1e-8:
            break
    return w[:-1], w[-1]


class YearlyModels:
    """Per test year: standardization, coefficients and the probability threshold."""

    def __init__(self, table: pd.DataFrame, feats=FEATS, keep: float = 0.5, l2: float = 10.0,
                 first_year: int = 2015, last_year: int = 2026, min_train: int = 200):
        self.feats = feats
        self.models = {}
        for y in range(first_year, last_year + 1):
            tr = table[table["exit_date"] < pd.Timestamp(f"{y}-01-01")]
            if len(tr) < min_train:
                continue
            X = tr[feats].to_numpy(float)
            mu, sd = X.mean(0), X.std(0) + 1e-9
            Z = (X - mu) / sd
            yv = (tr["ret"].to_numpy() > 0).astype(float)
            w, b = fit_logreg(Z, yv, l2=l2)
            p = 1 / (1 + np.exp(-(Z @ w + b)))
            thr = np.quantile(p, 1 - keep)
            self.models[y] = (mu, sd, w, b, thr)

    def take(self, feats_df: pd.DataFrame) -> np.ndarray:
        out = np.zeros(len(feats_df), dtype=bool)
        years = feats_df.index.year
        X = feats_df[self.feats].to_numpy(float)
        for y, (mu, sd, w, b, thr) in self.models.items():
            idx = years == y
            if not idx.any():
                continue
            z = (X[idx] - mu) / sd
            p = 1 / (1 + np.exp(-(np.nan_to_num(z) @ w + b)))
            out[idx] = p >= thr
        return out


_MODELS: dict = {}


def meta_breakout(df, p):
    """Base breakout, filtered by the walk-forward logistic model (trained on DEV)."""
    ib = p.get("ibs_min", 0.0)
    key = (p["n"], p["m"], p["trail"], p.get("keep", 0.5), p.get("l2", 10.0), tuple(p.get("feats", FEATS)), ib)
    if key not in _MODELS:
        tab = candidate_table(data.DEV, p["n"], p["m"], p["trail"], ib)
        _MODELS[key] = YearlyModels(tab, feats=list(key[5]), keep=key[3], l2=key[4])
    model = _MODELS[key]
    f = feature_frame(df)
    cand = base_candidates(df, p["n"], ib).to_numpy()
    entry = cand & model.take(f)
    lo_m = df["low"].rolling(p["m"]).min().shift(1)
    exit_sig = (df["close"] < lo_m).to_numpy()
    a = ind.atr(df, 14)
    return entry, exit_sig, ExitRules(trail_atr=p["trail"]), a.to_numpy(), None


def export_final(n=20, m=20, trail=4.0, ibs_min=0.7, keep=0.75, l2=100.0, year=2027) -> dict:
    """The model a live user would run today: trained on every DEV candidate whose trade
    has closed. Returns standardization, weights, bias and threshold (for the Pine port)."""
    tab = candidate_table(data.DEV, n, m, trail, ibs_min)
    ym = YearlyModels(tab, keep=keep, l2=l2, first_year=year, last_year=year)
    mu, sd, w, b, thr = ym.models[year]
    return {"feats": FEATS, "mu": mu.tolist(), "sd": sd.tolist(), "w": w.tolist(), "b": float(b),
            "thr": float(thr), "logit_thr": float(np.log(thr / (1 - thr))), "n_train": len(tab)}
