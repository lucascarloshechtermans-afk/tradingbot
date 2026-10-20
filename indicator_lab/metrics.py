from __future__ import annotations

import numpy as np
import pandas as pd

TD = 252


def equity_stats(r: pd.Series) -> dict:
    r = r.fillna(0.0)
    if len(r) < 2:
        return {"cagr": 0.0, "sharpe": 0.0, "maxdd": 0.0, "mar": 0.0}
    eq = (1 + r).cumprod()
    years = len(r) / TD
    cagr = eq.iloc[-1] ** (1 / years) - 1 if eq.iloc[-1] > 0 else -1.0
    sd = r.std()
    sharpe = r.mean() / sd * np.sqrt(TD) if sd > 0 else 0.0
    maxdd = float((eq / eq.cummax() - 1).min())
    return {"cagr": float(cagr), "sharpe": float(sharpe), "maxdd": maxdd,
            "mar": float(cagr / -maxdd) if maxdd < 0 else 0.0}


def trade_stats(trades: list[dict]) -> dict:
    if not trades:
        return {"n": 0, "win": 0.0, "pf": 0.0, "avg": 0.0, "bars": 0.0}
    r = np.array([t["ret"] for t in trades])
    gains, losses = r[r > 0].sum(), -r[r <= 0].sum()
    return {"n": len(r), "win": float((r > 0).mean()), "pf": float(gains / losses) if losses > 0 else np.inf,
            "avg": float(r.mean()), "bars": float(np.mean([t["bars"] for t in trades]))}
