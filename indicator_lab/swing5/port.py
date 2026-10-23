"""The complete system as it would be traded (swing v5 round): breakout positions (max k slots of 1/k), idle capital
in SPY while SPY closed above its SMA200 the day before (E48 rule; switching costs charged), otherwise in T-bills
(^IRX). Plus benchmarks (SPY buy & hold, 60/40 SPY / T-bills) and the alpha / beta decomposition vs SPY."""
from __future__ import annotations

import numpy as np
import pandas as pd

from indicator_lab.evaluate import get
from indicator_lab.metrics import equity_stats

COST = 0.001


def market(idx: pd.DatetimeIndex) -> pd.DataFrame:
    spy = get("SPY")["close"]
    on = (spy > spy.rolling(200).mean()).shift(1).fillna(False)
    irx = get("^IRX")["close"].ffill().shift(1)            # yesterday's 13-week bill yield, % per year
    out = pd.DataFrame({"spy": spy.pct_change(), "on": on.astype(float), "rf": irx / 100 / 252}).reindex(idx)
    return out.fillna({"spy": 0.0, "on": 0.0}).ffill().fillna(0.0)


def portfolio(res: dict, k: int = 10, seed: int = 0, key=None, park: bool = True, group=None, cap: int | None = None) -> dict:
    """`res`: {ticker: (daily returns of that ticker's positions, trades)} from swing4.lab.run."""
    rng = np.random.default_rng(seed)
    rets = pd.concat({t: r for t, (r, _) in res.items()}, axis=1).fillna(0.0)
    idx = rets.index
    R = rets.to_numpy()
    cols = {t: i for i, t in enumerate(rets.columns)}
    allt = []
    for t, (_, tr) in res.items():
        for x in tr:
            pri = -key(x) if key is not None else 0.0
            allt.append((x["entry_date"], pri if np.isfinite(pri) else 0.0, rng.random(), t, x))
    allt.sort(key=lambda z: (z[0], z[1], z[2]))
    w = np.zeros(R.shape)
    active: list = []
    taken = []
    groups: list = []          # (exit_date, group) of the open positions, for the per-group cap
    for ed, _, _, t, x in allt:
        active = [z for z in active if z > ed]
        groups = [z for z in groups if z[0] > ed]
        if len(active) >= k:
            continue
        if cap is not None:
            g = group(x)
            if g is not None and sum(1 for _, gg in groups if gg == g) >= cap:
                continue
            groups.append((x["exit_date"], g))
        active.append(x["exit_date"])
        taken.append(x)
        i0, i1 = idx.searchsorted(ed), idx.searchsorted(x["exit_date"])
        w[i0:i1 + 1, cols[t]] = 1.0 / k
    m = market(idx)
    invested = np.minimum(w.sum(axis=1), 1.0)
    idle = 1.0 - invested
    parked = idle * m["on"].to_numpy() if park else np.zeros(len(idx))
    cash = idle - parked
    switch = np.abs(np.diff(parked, prepend=0.0)) * COST
    c_tr = (R * w).sum(axis=1)
    c_pk = parked * m["spy"].to_numpy() - switch
    c_ca = cash * m["rf"].to_numpy()
    port = pd.Series(c_tr + c_pk + c_ca, index=idx)
    return {"port": port, "taken": taken, "invested": invested, "parked": parked,
            "contrib": pd.DataFrame({"breakouts": c_tr, "spy_parking": c_pk, "cash": c_ca}, index=idx), "mkt": m}


def stats(port: pd.Series, m: pd.DataFrame) -> dict:
    """Return stats plus regression on SPY: alpha (annual), beta, information ratio vs SPY."""
    s = equity_stats(port)
    ex = port - m["rf"]
    mx = m["spy"] - m["rf"]
    beta = float(np.cov(ex, mx)[0, 1] / np.var(mx, ddof=1))
    alpha_d = float(ex.mean() - beta * mx.mean())
    act = port - m["spy"]
    s.update({"sharpe_rf": float(ex.mean() / ex.std() * np.sqrt(252)), "beta": beta, "alpha": alpha_d * 252,
              "alpha_t": alpha_d / (np.std(ex - beta * mx, ddof=1) / np.sqrt(len(ex))),
              "ir": float(act.mean() / act.std() * np.sqrt(252)), "te": float(act.std() * np.sqrt(252))})
    return s


def benchmarks(idx: pd.DatetimeIndex) -> dict:
    m = market(idx)
    return {"SPY buy & hold": m["spy"], "60/40 SPY / T-bills": 0.6 * m["spy"] + 0.4 * m["rf"],
            "T-bills": m["rf"]}, m


def system(res: dict, k: int = 10, seeds: int = 20, key=None, park: bool = True, group=None, cap=None) -> dict:
    """Mean over `seeds` random orders of same-day signals: stats, contributions (annualised) and exposures."""
    runs = [portfolio(res, k, s, key, park, group, cap) for s in range(seeds)]
    m = runs[0]["mkt"]
    st = [stats(r["port"], m) for r in runs]
    out = {key_: float(np.mean([x[key_] for x in st])) for key_ in st[0]}
    out["mar_range"] = (float(np.min([x["mar"] for x in st])), float(np.max([x["mar"] for x in st])))
    out["contrib_ann"] = pd.concat([r["contrib"].mean() * 252 for r in runs], axis=1).mean(axis=1).to_dict()
    out["invested"] = float(np.mean([r["invested"].mean() for r in runs]))
    out["parked"] = float(np.mean([r["parked"].mean() for r in runs]))
    out["port0"] = runs[0]["port"]
    out["ports"] = [r["port"] for r in runs]
    out["taken"] = [r["taken"] for r in runs]
    out["mkt"] = m
    return out
