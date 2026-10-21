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


_BREADTH: dict = {}


def market_breadth() -> pd.DataFrame:
    """Share of TRAIN_EXTRA tickers (never scored) above their SMA50 / SMA200, plus VIX."""
    if "b" not in _BREADTH:
        cl = pd.concat({t: get(t)["close"] for t in data.TRAIN_EXTRA}, axis=1)
        above50 = (cl > cl.rolling(50).mean()).where(cl.rolling(50).mean().notna()).mean(axis=1)
        above200 = (cl > cl.rolling(200).mean()).where(cl.rolling(200).mean().notna()).mean(axis=1)
        vix = get("^VIX")["close"]
        _BREADTH["b"] = pd.DataFrame({"breadth50": above50, "breadth200": above200,
                                      "vix": vix.reindex(cl.index).ffill(),
                                      "vix_rel": (vix / vix.rolling(50).mean()).reindex(cl.index).ffill()})
    return _BREADTH["b"]


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
        "winter": pd.Series(df.index.month.isin([11, 12, 1, 2, 3, 4]).astype(float), index=df.index),
        "spy_vol20": spy.pct_change().rolling(20).std() * np.sqrt(252),
        "vol_ratio": c.pct_change().rolling(20).std() / c.pct_change().rolling(120).std(),
        "rsi2": ind.rsi(c, 2),
        "roc5": ind.roc(c, 5),
        "ext200": (c - ind.sma(c, 200)) / a,
    }).join(market_breadth().reindex(df.index).ffill()).pipe(_poly)


POLY_BASE = ["rvol", "spy_roc63", "er20", "bbw_pct", "rs63", "roc126"]


def _poly(f: pd.DataFrame) -> pd.DataFrame:
    """Squares and pairwise products of the sign-stable features (E55), for a non-linear model."""
    out = {}
    for i, a in enumerate(POLY_BASE):
        out[f"{a}^2"] = f[a] ** 2
        for b in POLY_BASE[i + 1:]:
            out[f"{a}*{b}"] = f[a] * f[b]
    return f.join(pd.DataFrame(out, index=f.index))


POLY_FEATS = POLY_BASE + [f"{a}^2" for a in POLY_BASE] + [f"{a}*{b}" for i, a in enumerate(POLY_BASE)
                                                          for b in POLY_BASE[i + 1:]]


def base_candidates(df: pd.DataFrame, n: int = 20, ibs_min: float = 0.0, trend_len: int | None = 200) -> pd.Series:
    c = df["close"]
    cond = (c > df["high"].rolling(n).max().shift(1)) & (ind.ibs(df) >= ibs_min)
    if trend_len:
        cond &= c > ind.sma(c, trend_len)
    return cond


def single_trade(o, h, lo, c, atr, exit_sig, i, rules: ExitRules, cost=0.001):
    """Outcome of a trade signalled at bar i (filled at i+1 open), same logic as engine.
    A trade still open on the last bar returns its mark-to-market with exit index n - 1;
    callers that need a real outcome must check `is_open` via `trade_outcome`."""
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
                    ibs_min: float = 0.0, trend_len: int | None = 200) -> pd.DataFrame:
    rows = []
    rules = ExitRules(trail_atr=trail)
    for t in tickers:
        df = get(t)
        f = feature_frame(df)
        cand = base_candidates(df, n, ibs_min, trend_len).to_numpy()
        lo_m = df["low"].rolling(m).min().shift(1)
        exit_sig = (df["close"] < lo_m).to_numpy()
        o, h, lo, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
        a = ind.atr(df, 14).to_numpy()
        for i in np.flatnonzero(cand):
            r, xi = single_trade(o, h, lo, c, a, exit_sig, i, rules)
            if xi == len(c) - 1:
                continue  # still open on the last bar: no real outcome yet, never a training label
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
                 first_year: int = 2015, last_year: int = 2026, min_train: int = 200, label_min: float = 0.0):
        self.feats = feats
        self.models = {}
        for y in range(first_year, last_year + 1):
            tr = table[table["exit_date"] < pd.Timestamp(f"{y}-01-01")]
            if len(tr) < min_train:
                continue
            X = tr[feats].to_numpy(float)
            mu, sd = X.mean(0), X.std(0) + 1e-9
            Z = (X - mu) / sd
            yv = (tr["ret"].to_numpy() > label_min).astype(float)
            w, b = fit_logreg(Z, yv, l2=l2)
            p = 1 / (1 + np.exp(-(Z @ w + b)))
            thr = np.quantile(p, 1 - keep) if keep < 1 else float(yv.mean())  # keep>=1: base-rate threshold
            self.models[y] = (mu, sd, w, b, thr)

    def prob(self, feats_df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        """(probability, threshold) per bar; NaN where no model exists for that year."""
        pr = np.full(len(feats_df), np.nan)
        th = np.full(len(feats_df), np.nan)
        years = feats_df.index.year
        X = feats_df[self.feats].to_numpy(float)
        for y, (mu, sd, w, b, thr) in self.models.items():
            idx = years == y
            if not idx.any():
                continue
            z = (X[idx] - mu) / sd
            pr[idx] = 1 / (1 + np.exp(-(np.nan_to_num(z) @ w + b)))
            th[idx] = thr
        return pr, th

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
_TICKER_OF: dict = {}
PROB: dict = {}          # id(df) -> (df, model probability series), for ranking same-day signals
XS_UNIVERSE: list = []   # tickers whose cross-section defines momentum ranks (xs_mom filter)
_XS: dict = {}


def xs_rank(lookback: int) -> pd.DataFrame:
    """Percentile rank (0..1) of each ticker's `lookback`-day return within XS_UNIVERSE, per date.
    Only tickers with data that day take part; uses closes up to that day (no look-ahead)."""
    key = (tuple(XS_UNIVERSE), lookback)
    if key not in _XS:
        cl = pd.concat({t: get(t)["close"] for t in XS_UNIVERSE}, axis=1)
        _XS[key] = (cl / cl.shift(lookback) - 1).rank(axis=1, pct=True)
    return _XS[key]


def _near_earnings(df: pd.DataFrame, k: int) -> np.ndarray:
    """True on bars whose next earnings reaction day is 1..k sessions ahead. Uses actual report
    dates; in practice these are announced weeks ahead (Pine: earnings.future_time)."""
    import os

    from indicator_lab import earnings as ER
    t = _TICKER_OF.get(id(df))
    out = np.zeros(len(df), dtype=bool)
    if t is None or t in ER.ETFS or not os.path.exists(os.path.join(data.CACHE_DIR, f"earn_{t}.json")):
        return out
    rd = df.index.get_indexer(ER.reaction_days(t, df.index))
    for r in rd[rd >= 0]:
        out[max(0, r - k):r] = True
    return out


def meta_breakout(df, p):
    """Base breakout, filtered by the walk-forward logistic model (trained on DEV)."""
    ib = p.get("ibs_min", 0.0)
    tl = p.get("trend_len", 200)
    train = p.get("train", "dev")
    key = (p["n"], p["m"], p["trail"], p.get("keep", 0.5), p.get("l2", 10.0), tuple(p.get("feats", FEATS)), ib, tl,
           train, p.get("label_min", 0.0))
    if key not in _MODELS:
        tickers = data.DEV + (data.TRAIN_EXTRA if train == "dev+extra" else [])
        if train == "extra":
            tickers = data.TRAIN_EXTRA
        if train == "big":
            tickers = sorted(set(data.DEV + data.TRAIN_EXTRA + data.VOLATILE))
        tab = candidate_table(tickers, p["n"], p["m"], p["trail"], ib, tl)
        _MODELS[key] = YearlyModels(tab, feats=list(key[5]), keep=key[3], l2=key[4],
                                    label_min=p.get("label_min", 0.0))
    model = _MODELS[key]
    f = feature_frame(df)
    cand = base_candidates(df, p["n"], ib, tl).to_numpy()
    if p.get("univ_atr"):  # only "lively" names: trailing 1-year mean ATR% above a floor
        a14 = ind.atr(df, 14)
        cand = cand & ((a14 / df["close"] * 100).rolling(252, min_periods=200).mean() >= p["univ_atr"]).to_numpy()
    if p.get("xs_mom"):  # cross-sectional momentum: ticker in the top (1 - xs_mom) of the universe
        t = _TICKER_OF.get(id(df))
        rk = xs_rank(p.get("xs_n", 126))
        if t in rk.columns:
            cand = cand & (rk[t].reindex(df.index) >= p["xs_mom"]).fillna(False).to_numpy()
    if p.get("earn_skip"):  # no new entry when the next earnings reaction day is <= earn_skip bars away
        cand = cand & ~_near_earnings(df, p["earn_skip"])
    size = None
    if p.get("low_size") is not None:  # take every candidate; below-threshold ones at reduced size
        pr, th = model.prob(f)
        entry = cand & np.isfinite(pr)
        size = np.where(pr >= th, 1.0, p["low_size"])
    else:
        entry = cand & model.take(f)
    pr_all, _ = model.prob(f)
    PROB[id(df)] = (df, pd.Series(pr_all, index=df.index))
    if p.get("vol_target"):  # equal-risk sizing: full size up to vol_target ATR%, scaled down above
        a14 = ind.atr(df, 14)
        vs = np.clip(p["vol_target"] / (a14 / df["close"] * 100), 0, 1).to_numpy()
        size = vs if size is None else size * vs
    lo_m = df["low"].rolling(p["m"]).min().shift(1)
    exit_sig = (df["close"] < lo_m).to_numpy()
    a = ind.atr(df, p.get("atr_n", 14))
    rules = ExitRules(trail_atr=p["trail"], tgt_atr=p.get("tgt"), stop_atr=p.get("stop"), fail_bars=p.get("fail_bars"),
                      entry_close=bool(p.get("entry_close")), max_gap_atr=p.get("max_gap"),
                      trail_from_close=bool(p.get("trail_close")))
    return entry, exit_sig, rules, a.to_numpy(), size


def export_final(n=20, m=20, trail=4.0, ibs_min=0.7, keep=0.75, l2=100.0, year=2027) -> dict:
    """The model a live user would run today: trained on every DEV candidate whose trade
    has closed. Returns standardization, weights, bias and threshold (for the Pine port)."""
    tab = candidate_table(data.DEV, n, m, trail, ibs_min)
    ym = YearlyModels(tab, keep=keep, l2=l2, first_year=year, last_year=year)
    mu, sd, w, b, thr = ym.models[year]
    return {"feats": FEATS, "mu": mu.tolist(), "sd": sd.tolist(), "w": w.tolist(), "b": float(b),
            "thr": float(thr), "logit_thr": float(np.log(thr / (1 - thr))), "n_train": len(tab)}


# ---------------------------------------------------------------------------------
# Mean-reversion variant: RSI(2) dip in an uptrend, exit when close > SMA(x).

MR_FEATS = FEATS + ["rsi2", "roc5", "ext200"]


def mr_parts(df, lo=10.0, exit_ma=5, trend_len=200):
    c = df["close"]
    cand = (ind.rsi(c, 2) < lo) & (c > ind.sma(c, trend_len))
    exit_sig = c > ind.sma(c, exit_ma)
    return cand.to_numpy(), exit_sig.to_numpy()


def mr_table(tickers, lo, exit_ma, stop):
    rows = []
    rules = ExitRules(stop_atr=stop)
    for t in tickers:
        df = get(t)
        f = feature_frame(df)
        cand, exit_sig = mr_parts(df, lo, exit_ma)
        o, h, low, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
        a = ind.atr(df, 14).to_numpy()
        for i in np.flatnonzero(cand):
            r, xi = single_trade(o, h, low, c, a, exit_sig, i, rules)
            rows.append({"ticker": t, "date": df.index[i], "exit_date": df.index[xi], "ret": r, **f.iloc[i].to_dict()})
    return pd.DataFrame(rows).dropna()


def meta_mr(df, p):
    lo, xm, stop = p.get("lo", 10.0), p.get("exit_ma", 5), p.get("stop")
    train = p.get("train", "dev")
    key = ("mr", lo, xm, stop, p.get("keep", 0.5), p.get("l2", 100.0), train)
    if key not in _MODELS:
        tickers = data.DEV + (data.TRAIN_EXTRA if train == "dev+extra" else [])
        _MODELS[key] = YearlyModels(mr_table(tickers, lo, xm, stop), feats=MR_FEATS, keep=key[4], l2=key[5])
    f = feature_frame(df)
    cand, exit_sig = mr_parts(df, lo, xm)
    entry = cand & _MODELS[key].take(f) if p.get("keep", 0.5) < 1 else cand
    return entry, exit_sig, ExitRules(stop_atr=stop), ind.atr(df, 14).to_numpy(), None


def pyramid_add(df, p):
    """Add-on unit for v3 (pyramiding): while a v3 trade is open and already `add_atr` ATR in profit,
    a NEW qualifying v3 breakout signal adds one more unit (once per trade). The add-on has v3's exits
    and is also closed when the base trade ends. Evaluated as a second part next to the base."""
    from indicator_lab.engine import simulate
    entry, exit_sig, rules, a, size = meta_breakout(df, p)
    _, trades = simulate(df, entry, exit_sig, a, rules)
    idx = df.index
    c = df["close"].to_numpy()
    add = np.zeros(len(idx), dtype=bool)
    force_exit = np.zeros(len(idx), dtype=bool)
    for x in trades:
        i0, i1 = idx.get_loc(x["entry_date"]), idx.get_loc(x["exit_date"])
        if p.get("add_mode") == "time":  # control: add after a fixed number of bars, no condition
            t = i0 + p.get("add_bars", 10)
            if t < i1 - 1:
                add[t] = True
        elif p.get("add_mode") == "profit":  # control: add once in profit by add_atr, no new breakout needed
            for t in range(i0 + 1, i1 - 1):
                if c[t] >= x["entry"] + p.get("add_atr", 2.0) * a[t]:
                    add[t] = True
                    break
        else:
            for t in range(i0 + 1, i1 - 1):
                if entry[t] and c[t] >= x["entry"] + p.get("add_atr", 2.0) * a[t]:
                    add[t] = True
                    break
        force_exit[max(i1 - 1, 0)] = True  # base trade ends at bar i1 -> add-on leaves at the same open
    return add, exit_sig | force_exit, rules, a, None
