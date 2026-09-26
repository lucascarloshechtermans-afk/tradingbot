"""One-account portfolio simulation over trade lists from engine2.simulate_rules.

Each day: open positions are marked to market at the close; exits at their
exit bar; new candidates (signal at t, entry at the open of t+1) are taken in
priority order while (a) fewer than max_positions are open, (b) total
position value stays <= 100% of equity, (c) total open risk <= max_heat.
Position size: risk_pct of equity / stop distance, capped at max_pos_pct of
equity (times an optional per-trade risk_mult column; 0 = skip). Costs are already inside the trade R (slippage both sides); a fixed
commission per fill can be added.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from research.engine2 import SLIP, Panel


def run_portfolio(p: Panel, trades: pd.DataFrame, *, stop_atr: float, risk_pct: float = 1.0,
                  max_positions: int = 10, max_pos_pct: float = 20.0, max_heat: float = 10.0,
                  start_equity: float = 100_000.0, priority: str | None = None, commission: float = 1.0,
                  date_mask: np.ndarray | None = None) -> dict:
    tr = trades.copy()
    if date_mask is not None:
        tr = tr[date_mask[tr["t"].to_numpy()]]
    tr["te"] = tr["t"] + 1
    tr["entry"] = p.o[tr["te"], tr["j"]] * (1 + SLIP)
    tr["dist"] = stop_atr * p.atr[tr["t"], tr["j"]]
    tr = tr[np.isfinite(tr.entry) & np.isfinite(tr.dist) & (tr.dist > 0)]
    tr["prio"] = tr[priority] if priority else 0.0
    if "risk_mult" not in tr:
        tr["risk_mult"] = 1.0
    tr = tr[tr["risk_mult"] > 0]
    by_day = {t: g.sort_values("prio", ascending=False) for t, g in tr.groupby("te")}
    T = len(p.dates)
    first = int(tr["te"].min()) if len(tr) else 0
    last = int(tr["exit_t"].max()) if len(tr) else 0
    equity = start_equity
    open_pos: list[dict] = []
    curve = []
    n_taken = 0
    taken_r = []
    for d in range(first, last + 1):
        # entries at today's open
        if d in by_day:
            for row in by_day[d].itertuples():
                if len(open_pos) >= max_positions:
                    break
                if any(ps["j"] == row.j for ps in open_pos):
                    continue
                risk_usd = equity * risk_pct / 100 * row.risk_mult
                shares = risk_usd / row.dist
                value = shares * row.entry
                if value > equity * max_pos_pct / 100:
                    shares = equity * max_pos_pct / 100 / row.entry
                    value = shares * row.entry
                    risk_usd = shares * row.dist
                if sum(ps["value"] for ps in open_pos) + value > equity:
                    continue
                if sum(ps["risk_usd"] for ps in open_pos) + risk_usd > equity * max_heat / 100:
                    continue
                equity -= commission
                open_pos.append({"j": row.j, "exit_t": row.exit_t, "r": row.r, "risk_usd": risk_usd,
                                 "value": value, "shares": shares, "entry": row.entry})
                n_taken += 1
        # exits during/at the close of their exit bar (including same-day exits)
        still = []
        for ps in open_pos:
            if ps["exit_t"] <= d:
                equity += ps["r"] * ps["risk_usd"] - commission
                taken_r.append(ps["r"])
            else:
                still.append(ps)
        open_pos = still
        # mark to market at the close
        mtm = 0.0
        for ps in open_pos:
            c = p.c[d, ps["j"]]
            if np.isfinite(c):
                mtm += ps["shares"] * (c - ps["entry"])
        curve.append((p.dates[d], equity + mtm, len(open_pos)))
    eq = pd.DataFrame(curve, columns=["date", "equity", "open"]).set_index("date")
    if eq.empty:
        return {"trades": 0}
    e = eq["equity"]
    years = (e.index[-1] - e.index[0]).days / 365.25
    dd = 1 - e / e.cummax()
    rets = e.pct_change().dropna()
    yearly = e.resample("YE").last().pct_change()
    yearly.iloc[0] = e.resample("YE").last().iloc[0] / start_equity - 1
    return {"trades": n_taken, "CAGR": (e.iloc[-1] / start_equity) ** (1 / years) - 1 if years > 0 else np.nan,
            "maxDD": dd.max(), "sharpe": rets.mean() / rets.std() * np.sqrt(252) if rets.std() > 0 else np.nan,
            "avg_open": eq["open"].mean(), "meanR": float(np.mean(taken_r)) if taken_r else np.nan,
            "years_pos": (yearly > 0).mean(), "worst_year": yearly.min(), "curve": e, "yearly": yearly}


def mc_portfolio(p: Panel, trades: pd.DataFrame, *, runs: int = 30, seed: int = 0, **kw) -> pd.DataFrame:
    """Selection-luck Monte Carlo: the same candidate list with random daily
    priority. Returns one row per run (CAGR, maxDD, sharpe, trades, meanR)."""
    rng = np.random.default_rng(seed)
    rows = []
    for _ in range(runs):
        tr = trades.assign(_rnd=rng.random(len(trades)))
        res = run_portfolio(p, tr, priority="_rnd", **kw)
        rows.append({k: res[k] for k in ("CAGR", "maxDD", "sharpe", "trades", "meanR", "worst_year")})
    return pd.DataFrame(rows)
