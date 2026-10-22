"""Signals, trade simulation with path statistics, and a max-K-positions portfolio for the swing v4 round.

`simulate()` reproduces the research engine for the v3 exits exactly (tests/test_swing4.py) and additionally
records, per trade, the risk unit R = trail_mult x ATR(signal bar) and the path in R: MFE, MAE and the first
bar on which +0.5/+1/+1.5/+2/+3 R was touched. Fills: next open; the protective stop is live from the fill bar;
a gap through a stop fills at the open; close < prior m-day low exits at the next open; no re-entry on an exit bar.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from indicator_lab import data, ind, meta
from indicator_lab.evaluate import get
from indicator_lab.metrics import equity_stats

LEVELS = (0.5, 1.0, 1.5, 2.0, 3.0)
V3 = {"n": 20, "m": 20, "trail": 4.0, "ibs_min": 0.7, "trend_len": 200, "keep": 0.75, "l2": 100.0, "stop": 4.0}
COST = 0.001


# ---------------------------------------------------------------- signals
_MODEL: dict = {}


def model(feats=None, p=V3, label_min: float = 0.0):
    """Walk-forward yearly logistic models trained on DEV candidates (as v3)."""
    feats = tuple(feats or meta.FEATS)
    key = (feats, p["n"], p["m"], p["trail"], p["ibs_min"], p["keep"], p["l2"], label_min)
    if key not in _MODEL:
        tab = meta.candidate_table(data.DEV, p["n"], p["m"], p["trail"], p["ibs_min"], p["trend_len"])
        _MODEL[key] = meta.YearlyModels(tab, feats=list(feats), keep=p["keep"], l2=p["l2"], label_min=label_min)
    return _MODEL[key]


def signals(t: str, p=V3, use_model: bool = True, feats=None) -> dict:
    """Per-bar arrays for one ticker: candidate, model probability/threshold, entry signal, exit signal, ATR."""
    df = get(t)
    f = meta.feature_frame(df)
    cand = meta.base_candidates(df, p["n"], p["ibs_min"], p["trend_len"]).to_numpy()
    m = model(feats, p)
    pr, th = m.prob(f)
    take = m.take(f) if use_model else np.ones(len(df), bool)
    lo_m = df["low"].rolling(p["m"]).min().shift(1)
    return {"df": df, "feat": f, "cand": cand, "prob": pr, "thr": th, "entry": cand & take,
            "exit_sig": (df["close"] < lo_m).to_numpy(), "atr": ind.atr(df, 14).to_numpy()}


# ---------------------------------------------------------------- trades
def simulate(df: pd.DataFrame, entry: np.ndarray, exit_sig: np.ndarray, atr: np.ndarray, p=V3, cost: float = COST):
    o, h, lo, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    n = len(c)
    ret = np.zeros(n)
    trades = []
    in_pos = pend_entry = pend_exit = False
    ep = stop = hh = risk_px = 0.0
    ei = 0

    def close(t, px, reason):
        nonlocal in_pos, pend_exit
        prev = c[t - 1]
        ret[t] = (px * (1 - cost)) / prev - 1 if t > ei else (px * (1 - cost)) / (ep * (1 + cost)) - 1
        r = (px * (1 - cost)) / (ep * (1 + cost)) - 1
        # path = bars from the fill up to the bar before the exit bar (inside the exit bar the order of high, low
        # and stop is unknown, so it never counts: conservative for MFE and for "touched +xR")
        seg_h, seg_l = h[ei:t], lo[ei:t]
        hi_path = seg_h.max() if len(seg_h) else ep
        lo_path = min(seg_l.min() if len(seg_l) else ep, px)
        touch = {}
        for k in LEVELS:
            hit = np.flatnonzero(seg_h >= ep + k * risk_px)
            touch[k] = int(hit[0]) if len(hit) else None
        rp = risk_px / ep
        trades.append({"entry_i": ei, "exit_i": t, "entry_date": df.index[ei], "exit_date": df.index[t],
                       "entry": ep, "exit": px, "ret": r, "bars": t - ei, "reason": reason, "risk": rp,
                       "R": r / rp, "R_gross": (px - ep) / risk_px, "mfe_R": (hi_path - ep) / risk_px,
                       "mae_R": (lo_path - ep) / risk_px, "touch": touch})
        in_pos = pend_exit = False

    for t in range(n):
        if in_pos:
            if pend_exit:
                close(t, o[t], "signal")
            elif o[t] <= stop:
                close(t, o[t], "stop")
            elif lo[t] <= stop:
                close(t, stop, "stop")
            else:
                ret[t] = c[t] / c[t - 1] - 1
                hh = max(hh, h[t])
                if np.isfinite(atr[t]):
                    stop = max(stop, hh - p["trail"] * atr[t])
                if exit_sig[t]:
                    pend_exit = True
            continue
        if pend_entry:
            pend_entry = False
            a = atr[t - 1]
            ep, ei, in_pos = o[t], t, True
            risk_px = p["trail"] * a
            stop = ep - p["stop"] * a
            hh = h[t]
            if lo[t] <= stop:
                close(t, stop, "stop")
                continue
            ret[t] = c[t] / (ep * (1 + cost)) - 1
            if np.isfinite(atr[t]):
                stop = max(stop, hh - p["trail"] * atr[t])
            if exit_sig[t]:
                pend_exit = True
            continue
        if entry[t] and t + 1 < n and np.isfinite(atr[t]):
            pend_entry = True
    return ret, trades


def run_universe(tickers, p=V3, use_model: bool = True, feats=None, period=None) -> dict:
    """{ticker: (daily returns Series, trades list)} with signal-bar features attached to each trade."""
    out = {}
    for t in tickers:
        s = signals(t, p, use_model, feats)
        r, tr = simulate(s["df"], s["entry"], s["exit_sig"], s["atr"], p)
        for x in tr:
            i = x["entry_i"] - 1
            x["ticker"] = t
            x["feat"] = s["feat"].iloc[i].to_dict()
            x["prob"] = float(s["prob"][i])
            x["thr"] = float(s["thr"][i])
        out[t] = (pd.Series(r, index=s["df"].index), tr)
    if period:
        a, b = period
        out = {t: (r[(r.index >= a) & (r.index <= b)], [x for x in tr if a <= x["entry_date"] <= b])
               for t, (r, tr) in out.items()}
    return out


# ---------------------------------------------------------------- statistics
def trade_table(res: dict) -> pd.DataFrame:
    rows = [x for _, tr in res.values() for x in tr]
    return pd.DataFrame(rows)


def trade_metrics(tt: pd.DataFrame) -> dict:
    if len(tt) == 0:
        return {"n": 0}
    r = tt["ret"].to_numpy()
    R = tt["R"].to_numpy()
    w, lz = r[r > 0], r[r <= 0]
    return {"n": len(r), "win": float((r > 0).mean()), "exp_pct": float(r.mean()), "exp_R": float(R.mean()),
            "pf": float(w.sum() / -lz.sum()) if lz.sum() < 0 else np.inf,
            "avg_win": float(w.mean()) if len(w) else np.nan, "avg_loss": float(lz.mean()) if len(lz) else np.nan,
            "avg_win_R": float(R[r > 0].mean()) if len(w) else np.nan,
            "avg_loss_R": float(R[r <= 0].mean()) if len(lz) else np.nan,
            "hold": float(tt["bars"].mean())}


def portfolio(res: dict, k: int = 10, seed: int = 0, order: str = "random", key=None) -> dict:
    """At most k open positions, each 1/k of equity; a signal with all slots full is skipped.
    Same-day signals are ordered randomly (seeded) unless `key(trade)` gives a priority (higher first)."""
    rng = np.random.default_rng(seed)
    rets = pd.concat({t: r for t, (r, _) in res.items()}, axis=1).fillna(0.0)
    idx = rets.index
    allt = []
    for t, (_, tr) in res.items():
        for x in tr:
            pri = -key(x) if key is not None else 0.0
            allt.append((x["entry_date"], pri, rng.random(), x["exit_date"], t))
    allt.sort()
    mask = np.zeros(rets.shape)
    cols = {t: i for i, t in enumerate(rets.columns)}
    active: list = []
    taken = skipped = 0
    crowded_days = set()
    by_day: dict = {}
    for ed, _, _, xd, t in allt:
        active = [x for x in active if x > ed]
        by_day.setdefault(ed, [0, 0])
        by_day[ed][0] += 1
        if len(active) >= k:
            skipped += 1
            by_day[ed][1] += 1
            crowded_days.add(ed)
            continue
        active.append(xd)
        taken += 1
        i0, i1 = idx.searchsorted(ed), idx.searchsorted(xd)
        mask[i0:i1 + 1, cols[t]] = 1
    port = pd.Series((rets.to_numpy() * mask).sum(axis=1) / k, index=idx)
    st = equity_stats(port)
    st.update({"exposure": float(np.minimum(mask.sum(axis=1) / k, 1).mean()), "taken": taken, "skipped": skipped,
               "signal_days": len(by_day), "crowded_days": len(crowded_days), "equity": (1 + port).cumprod()})
    return st


def portfolio_avg(res: dict, k: int = 10, seeds: int = 5, key=None) -> dict:
    runs = [portfolio(res, k, s, key=key) for s in range(seeds if key is None else 1)]
    out = {m: float(np.mean([x[m] for x in runs])) for m in ("cagr", "sharpe", "maxdd", "mar", "exposure", "taken",
                                                                "skipped", "signal_days", "crowded_days")}
    out["equity"] = runs[0]["equity"]
    return out


def compare(tt_new: pd.DataFrame, tt_base: pd.DataFrame, half_a, half_b, metric: str = "R") -> dict:
    """Acceptance checks of the protocol for a trade-level metric (mean R by default): share of years in which the
    new variant is better, and whether it is better in each half of the ticker set."""
    def by_year(tt):
        return tt.groupby(tt["entry_date"].dt.year)[metric].mean()
    a, b = by_year(tt_new), by_year(tt_base)
    yrs = a.index.intersection(b.index)
    half = {}
    for nm, h in (("a", half_a), ("b", half_b)):
        half[nm] = bool(tt_new[tt_new["ticker"].isin(h)][metric].mean() > tt_base[tt_base["ticker"].isin(h)][metric].mean())
    return {"years_better": float((a[yrs] > b[yrs]).mean()), "half_a": half["a"], "half_b": half["b"]}
