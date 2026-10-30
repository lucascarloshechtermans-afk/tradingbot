"""Round 6: complete trading systems (research/HYPOTHESES.md, "Round 6").

Weight-based systems (momentum portfolio, sector rotation, index RSI2) use an
exact next-open execution model: weights decided at the close of t are held
from the open of t+1; the overnight gap of t+1 belongs to the previous
weights. Cost per unit of turnover; idle cash earns the 13-week T-bill.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

COST = 0.0010  # per side


def weight_returns(W: np.ndarray, O: np.ndarray, C: np.ndarray, rf: np.ndarray, cost: float = COST) -> np.ndarray:
    """Daily portfolio returns for target weights W[t] decided at the close of t."""
    T = len(W)
    W = np.nan_to_num(W)
    w_new = np.vstack([np.zeros((1, W.shape[1])), W[:-1]])      # held from the open of d
    w_prev = np.vstack([np.zeros((2, W.shape[1])), W[:-2]])     # held through the close of d-1
    prevC = np.vstack([np.full((1, C.shape[1]), np.nan), C[:-1]])
    gap = np.nan_to_num(O / prevC - 1)
    intraday = np.nan_to_num(C / O - 1)
    r = (w_prev * gap).sum(1) + (w_new * intraday).sum(1)
    r += (1 - w_new.sum(1)) * rf
    r -= np.abs(w_new - w_prev).sum(1) * cost
    r[:2] = 0
    return r[:T]


def stats(ret: pd.Series) -> dict:
    ret = ret.dropna()
    if len(ret) < 50:
        return {}
    e = (1 + ret).cumprod()
    yrs = len(ret) / 252
    yearly = (1 + ret).groupby(ret.index.year).prod() - 1
    return {"CAGR": e.iloc[-1] ** (1 / yrs) - 1, "maxDD": (1 - e / e.cummax()).max(),
            "sharpe": ret.mean() / ret.std() * np.sqrt(252) if ret.std() > 0 else np.nan,
            "worst_yr": yearly.min(), "yrs_pos": (yearly > 0).mean()}


PERIODS = {"1999-2007": ("1999-01-01", "2007-12-31"), "2008-2021": ("2008-01-01", "2021-12-31"),
           "2022-2026": ("2022-01-01", "2026-12-31")}


def fmt(name: str, ret: pd.Series, periods=PERIODS, extra: str = "") -> str:
    line = f"{name:<34}"
    for p, (a, b) in periods.items():
        s = stats(ret[(ret.index >= a) & (ret.index <= b)])
        line += (f" | {p}: {s['CAGR'] * 100:5.1f}% DD {s['maxDD'] * 100:4.1f}% Sh {s['sharpe']:.2f} worst {s['worst_yr'] * 100:5.1f}%"
                 if s else f" | {p}: {'-':>38}")
    return line + extra


def rsi(c: pd.Series, n: int = 2) -> pd.Series:
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))
