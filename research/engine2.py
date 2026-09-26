"""Research engine for round 4: panel (days x stocks) indicators, vectorized
trade simulation, same-stock/same-month baseline and cell metrics.

Rules (see research/HYPOTHESES.md): signal at the close of t, entry at the
open of t+1 (+slippage); stop k ATR below the entry, checked from the entry
bar itself (conservative: a stop touched later that same day counts);
H = bars held including the entry bar (exit at the close of bar t+H);
gap-through stops fill at the open; one open trade per ticker per hypothesis.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

SLIP = 0.0005
HOLDS = (3, 5, 10, 20)
SPLIT_DATE = pd.Timestamp("2022-01-01")


@dataclass
class Panel:
    dates: pd.DatetimeIndex
    tickers: list[str]
    o: np.ndarray
    h: np.ndarray
    l: np.ndarray  # noqa: E741
    c: np.ndarray
    v: np.ndarray
    atr: np.ndarray
    eligible: np.ndarray
    half: np.ndarray          # 1 = research, 0 = holdout
    sector: list[str | None]
    bench: dict[str, pd.DataFrame]

    def df(self, a: np.ndarray) -> pd.DataFrame:
        return pd.DataFrame(a, index=self.dates, columns=self.tickers)


def build_panel(big: dict) -> Panel:
    spy = big["bench"]["SPY"]
    dates = spy.index
    tickers = sorted(big["stocks"])
    cols = {k: pd.DataFrame({t: big["stocks"][t][k] for t in tickers}).reindex(dates) for k in ("open", "high", "low", "close", "volume")}
    o, h, l, c, v = (cols[k].to_numpy(dtype=np.float64) for k in ("open", "high", "low", "close", "volume"))
    pc = np.vstack([np.full((1, c.shape[1]), np.nan), c[:-1]])
    tr = np.nanmax(np.stack([h - l, np.abs(h - pc), np.abs(l - pc)]), axis=0)
    atr = pd.DataFrame(tr).rolling(14, min_periods=14).mean().to_numpy()
    dv = pd.DataFrame(c * v).rolling(20, min_periods=20).mean().to_numpy()
    nbars = np.cumsum(np.isfinite(c), axis=0)
    eligible = (c >= 5) & (dv >= 10e6) & (nbars >= 260) & np.isfinite(atr) & (atr > 0) & (v > 0)
    half = np.array([1 if big["half"].get(t) == "RESEARCH" else 0 for t in tickers])
    return Panel(dates, tickers, o, h, l, c, v, atr, eligible, half, [big["sectors"].get(t) for t in tickers], big["bench"])


def simulate(p: Panel, signal: np.ndarray, stop_atr: float = 2.5, holds=HOLDS, busy_hold: int = 10) -> pd.DataFrame:
    """Trades for a boolean signal matrix (T x N). Returns one row per trade
    with R for every hold in `holds`."""
    T, N = p.c.shape
    sig = signal & p.eligible
    sig[-(max(holds) + 1):] = False
    ts, js = np.nonzero(sig)
    if len(ts) == 0:
        return pd.DataFrame()
    order = np.lexsort((ts, js))
    ts, js = ts[order], js[order]
    te = ts + 1
    entry = p.o[te, js] * (1 + SLIP)
    ok = np.isfinite(entry) & (entry > 0)
    risk = stop_atr * p.atr[ts, js]
    stop = entry - risk
    out = {"t": ts, "j": js}
    exit_idx_busy = None
    for H in holds:
        k = np.arange(H)
        idx = te[:, None] + k[None, :]
        lows = p.l[idx, js[:, None]]
        opens = p.o[idx, js[:, None]]
        hit = lows <= stop[:, None]
        hit = np.where(np.isfinite(lows), hit, False)
        any_hit = hit.any(axis=1)
        first = np.argmax(hit, axis=1)
        fill_stop = np.minimum(np.where(first == 0, entry, opens[np.arange(len(ts)), first]), stop) * (1 - SLIP)
        fill_time = p.c[te + H - 1, js] * (1 - SLIP)
        px = np.where(any_hit, fill_stop, fill_time)
        r = (px - entry) / risk
        out[f"r{H}"] = r
        if H == busy_hold:
            exit_idx_busy = np.where(any_hit, te + first, te + H - 1)
    df = pd.DataFrame(out)
    df = df[ok & np.isfinite(df[f"r{busy_hold}"])]
    # one open trade per ticker: skip signals while the previous trade is open
    keep = np.zeros(len(df), dtype=bool)
    busy = exit_idx_busy[df.index.to_numpy()]
    tt, jj = df["t"].to_numpy(), df["j"].to_numpy()
    last_j, last_exit = -1, -1
    for i in range(len(df)):
        if jj[i] != last_j:
            last_j, last_exit = jj[i], -1
        if tt[i] > last_exit:
            keep[i] = True
            last_exit = busy[i]
    df = df[keep].reset_index(drop=True)
    for H in holds:
        df[f"r{H}"] = df[f"r{H}"].clip(-5, 10)  # robustness to bad prints
    return df


def baseline(p: Panel, stop_atr: float = 2.5, holds=HOLDS, step: int = 1) -> dict[int, np.ndarray]:
    """Mean R of every eligible day per (month, ticker) for each hold: the
    same-stock, same-time benchmark. Returns {H: array[month_index, N]}."""
    sig = np.zeros_like(p.eligible)
    sig[::step] = True
    T, N = p.c.shape
    months = p.dates.to_period("M")
    mcodes, muniq = pd.factorize(months)
    res = {H: np.full((len(muniq), N), np.nan) for H in holds}
    chunk = 120
    for j0 in range(0, N, chunk):
        cols = np.zeros(N, dtype=bool)
        cols[j0:j0 + chunk] = True
        s = sig & cols[None, :]
        tr = _simulate_all(p, s, stop_atr, holds)
        for H in holds:
            g = pd.DataFrame({"m": mcodes[tr["t"]], "j": tr["j"], "r": tr[f"r{H}"]}).groupby(["m", "j"])["r"].mean()
            res[H][g.index.get_level_values(0), g.index.get_level_values(1)] = g.to_numpy()
    return res


def _simulate_all(p: Panel, sig: np.ndarray, stop_atr: float, holds) -> pd.DataFrame:
    """Like simulate() but without the one-trade-per-ticker rule (baseline)."""
    sig = sig & p.eligible
    sig[-(max(holds) + 1):] = False
    ts, js = np.nonzero(sig)
    te = ts + 1
    entry = p.o[te, js] * (1 + SLIP)
    risk = stop_atr * p.atr[ts, js]
    stop = entry - risk
    out = {"t": ts, "j": js}
    for H in holds:
        idx = te[:, None] + np.arange(H)[None, :]
        lows = p.l[idx, js[:, None]]
        opens = p.o[idx, js[:, None]]
        hit = np.where(np.isfinite(lows), lows <= stop[:, None], False)
        any_hit = hit.any(axis=1)
        first = np.argmax(hit, axis=1)
        fill_stop = np.minimum(np.where(first == 0, entry, opens[np.arange(len(ts)), first]), stop) * (1 - SLIP)
        px = np.where(any_hit, fill_stop, p.c[te + H - 1, js] * (1 - SLIP))
        out[f"r{H}"] = np.clip((px - entry) / risk, -5, 10)
    df = pd.DataFrame(out)
    return df[np.isfinite(df[f"r{holds[0]}"])]


def add_context(p: Panel, trades: pd.DataFrame, base: dict[int, np.ndarray]) -> pd.DataFrame:
    if trades.empty:
        return trades
    months = pd.factorize(p.dates.to_period("M"))[0]
    trades = trades.copy()
    trades["date"] = p.dates[trades["t"].to_numpy()]
    trades["ticker"] = np.array(p.tickers)[trades["j"].to_numpy()]
    trades["research"] = p.half[trades["j"].to_numpy()] == 1
    trades["late"] = trades["date"] >= SPLIT_DATE
    trades["cell"] = np.select(
        [trades.research & ~trades.late, trades.research & trades.late, ~trades.research & ~trades.late],
        ["DEV", "VAL-T", "VAL-U"], "FINAL")
    for H, b in base.items():
        trades[f"x{H}"] = trades[f"r{H}"] - b[months[trades["t"].to_numpy()], trades["j"].to_numpy()]
    return trades


def cell_stats(tr: pd.DataFrame, H: int) -> dict:
    x = tr[f"x{H}"].dropna()
    r = tr[f"r{H}"].dropna()
    if len(x) < 30:
        return {"n": len(x)}
    daily = tr.groupby("t")[f"x{H}"].mean().dropna()
    tstat = daily.mean() / (daily.std(ddof=1) / np.sqrt(len(daily))) if len(daily) > 2 and daily.std() > 0 else np.nan
    yearly = tr.groupby(tr["date"].dt.year)[f"x{H}"].mean()
    pf = r[r > 0].sum() / -r[r < 0].sum() if (r < 0).any() else np.inf
    return {"n": len(r), "R": r.mean(), "medR": r.median(), "X": x.mean(), "t": tstat,
            "yrs+": (yearly > 0).mean(), "PF": pf, "win": (r > 0).mean()}


def simulate_rules(p: Panel, signal: np.ndarray, *, stop_atr: float = 2.5, max_hold: int = 10,
                   exit_cond: np.ndarray | None = None, target_atr: float | None = None,
                   min_hold: int = 1) -> pd.DataFrame:
    """Generic exits: stop (intrabar, gap-aware, checked first), optional profit
    target (intrabar), optional exit condition evaluated at the close
    (exit_cond[t, j] True -> sell at that close), time exit at the close of
    bar entry+max_hold-1. One open trade per ticker. Returns t, j, r, bars."""
    T, N = p.c.shape
    sig = signal & p.eligible
    sig[-(max_hold + 1):] = False
    ts, js = np.nonzero(sig)
    if len(ts) == 0:
        return pd.DataFrame(columns=["t", "j", "r", "bars"])
    order = np.lexsort((ts, js))
    ts, js = ts[order], js[order]
    te = ts + 1
    n = len(ts)
    entry = p.o[te, js] * (1 + SLIP)
    risk = stop_atr * p.atr[ts, js]
    stop = entry - risk
    idx = te[:, None] + np.arange(max_hold)[None, :]
    lows, highs, opens, closes = (a[idx, js[:, None]] for a in (p.l, p.h, p.o, p.c))
    hit_stop = np.where(np.isfinite(lows), lows <= stop[:, None], False)
    if target_atr is not None:
        tgt = entry + target_atr * p.atr[ts, js]
        hit_tgt = np.where(np.isfinite(highs), highs >= tgt[:, None], False) & ~hit_stop
    else:
        hit_tgt = np.zeros_like(hit_stop)
    if exit_cond is not None:
        ec = exit_cond[idx, js[:, None]]
        ec[:, : max(0, min_hold - 1)] = False
        hit_ec = ec & ~hit_stop & ~hit_tgt
    else:
        hit_ec = np.zeros_like(hit_stop)
    any_evt = hit_stop | hit_tgt | hit_ec
    has = any_evt.any(axis=1)
    k = np.where(has, np.argmax(any_evt, axis=1), max_hold - 1)
    rows = np.arange(n)
    px = closes[rows, k] * (1 - SLIP)  # time exit or exit condition: at the close
    s_mask = has & hit_stop[rows, k]
    first_open = np.where(k == 0, entry, opens[rows, k])
    px = np.where(s_mask, np.minimum(first_open, stop) * (1 - SLIP), px)
    t_mask = has & hit_tgt[rows, k]
    if target_atr is not None:
        px = np.where(t_mask, np.maximum(first_open, tgt) * (1 - SLIP), px)
    r = np.clip((px - entry) / risk, -5, 10)
    exit_idx = te + k
    ok = np.isfinite(r)
    keep = np.zeros(n, dtype=bool)
    last_j, last_exit = -1, -1
    for i in range(n):
        if not ok[i]:
            continue
        if js[i] != last_j:
            last_j, last_exit = js[i], -1
        if ts[i] > last_exit:
            keep[i] = True
            last_exit = exit_idx[i]
    return pd.DataFrame({"t": ts[keep], "j": js[keep], "r": r[keep], "bars": (k + 1)[keep],
                         "exit_t": exit_idx[keep]})


def day_baseline(p: Panel, stop_atr: float = 2.5, holds=HOLDS) -> dict[int, np.ndarray]:
    """Mean R of ALL eligible stocks entering on the same day (signal day t) for
    each hold: a same-day, cross-sectional benchmark that uses no information
    about the stock's own future. (The same-stock same-month baseline above
    contains the event's own move and biases dips up / breakouts down.)"""
    T, N = p.c.shape
    sums = {H: np.zeros(T) for H in holds}
    cnt = {H: np.zeros(T) for H in holds}
    chunk = 120
    for j0 in range(0, N, chunk):
        cols = np.zeros(N, dtype=bool)
        cols[j0:j0 + chunk] = True
        s = np.ones_like(p.eligible) & cols[None, :]
        tr = _simulate_all(p, s, stop_atr, holds)
        t = tr["t"].to_numpy()
        for H in holds:
            r = tr[f"r{H}"].to_numpy()
            ok = np.isfinite(r)
            np.add.at(sums[H], t[ok], r[ok])
            np.add.at(cnt[H], t[ok], 1)
    return {H: np.where(cnt[H] > 0, sums[H] / np.maximum(cnt[H], 1), np.nan) for H in holds}


def add_day_excess(trades: pd.DataFrame, dbase: dict[int, np.ndarray]) -> pd.DataFrame:
    trades = trades.copy()
    for H, b in dbase.items():
        if f"r{H}" in trades:
            trades[f"x{H}"] = trades[f"r{H}"] - b[trades["t"].to_numpy()]
    return trades
