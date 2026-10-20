"""Shared evaluation protocol so every idea is judged the same way.

- Periods: in-sample (IS) 2015-2020 is where ideas are designed/tuned; out-of-sample
  (OOS) 2021-2026 is only looked at to confirm. A rolling walk-forward (`walk_forward`)
  re-tunes on all data before each test year and only scores the year after.
- Universes: DEV tickers are used while designing; HOLDOUT tickers never are.
- Portfolio = equal-weight sleeves (1/N of capital per ticker, idle sleeve in cash),
  so CAGR is diluted by low exposure; Sharpe/MAR are the fair comparison to B&H.
"""
from __future__ import annotations

import itertools
from typing import Callable

import numpy as np
import pandas as pd

from indicator_lab import data
from indicator_lab.engine import simulate
from indicator_lab.metrics import equity_stats, trade_stats

IS = ("2015-01-01", "2020-12-31")
OOS = ("2021-01-01", "2026-12-31")
FULL = ("2015-01-01", "2026-12-31")

_DATA: dict[str, pd.DataFrame] = {}


def get(t: str) -> pd.DataFrame:
    if t not in _DATA:
        _DATA[t] = data.load(t)
        from indicator_lab import meta  # lets ticker-aware filters (earnings) find the symbol
        meta._TICKER_OF[id(_DATA[t])] = t
    return _DATA[t]


_FEAT: dict[str, pd.DataFrame] = {}


def features(t: str) -> pd.DataFrame:
    """Per-bar values a trader could rank same-day signals by (all known at the close)."""
    if t not in _FEAT:
        from indicator_lab import ind
        df = get(t)
        c = df["close"]
        a = ind.atr(df, 14)
        spy = get("SPY")["close"].reindex(df.index).ffill()
        _FEAT[t] = pd.DataFrame({
            "roc21": ind.roc(c, 21), "roc63": ind.roc(c, 63), "roc126": ind.roc(c, 126), "roc252": ind.roc(c, 252),
            "rs63": ind.roc(c, 63) - ind.roc(spy, 63),
            "atr_pct": a / c, "rsi14": ind.rsi(c, 14), "ibs": ind.ibs(df),
            "ext50": (c - ind.sma(c, 50)) / a,
            "rvol": df["volume"] / ind.sma(df["volume"], 50),
            "ret_vol": ind.roc(c, 126) / (c.pct_change().rolling(126).std() * np.sqrt(126)),
        })
    return _FEAT[t]


def run_ticker(strategy: Callable, params: dict, t: str):
    df = get(t)
    entry, exit_sig, rules, atr, size = strategy(df, params)
    r, trades = simulate(df, np.asarray(entry, bool), None if exit_sig is None else np.asarray(exit_sig, bool),
                         np.asarray(atr, float), rules, size=size)
    f = features(t)
    for x in trades:  # feature values on the SIGNAL bar (the bar before the fill)
        i = df.index.get_loc(x["entry_date"]) - 1
        x["feat"] = f.iloc[i].to_dict()
    return pd.Series(r, index=df.index), trades


def blend_ticker(parts, t: str):
    """One position per ticker, sized by the fraction of `parts` that are long
    (e.g. 3 breakout lookbacks -> 0, 1/3, 2/3 or full size). Each part keeps its own
    entries/exits; the slot is held from the first part entering until the last exits."""
    sims = [run_ticker(fn, p, t) for fn, p in parts]
    r = sum(s[0] for s in sims) / len(sims)
    idx = r.index
    held = np.zeros(len(idx), dtype=bool)
    for _, trades in sims:
        for x in trades:
            held[idx.get_loc(x["entry_date"]):idx.get_loc(x["exit_date"]) + 1] = True
    trades, i, n = [], 0, len(idx)
    while i < n:
        if held[i]:
            j = i
            while j + 1 < n and held[j + 1]:
                j += 1
            first = [x for _, ts in sims for x in ts if idx.get_loc(x["entry_date"]) == i]
            trades.append({"entry_date": idx[i], "exit_date": idx[j], "ret": float(np.prod(1 + r.iloc[i:j + 1]) - 1),
                           "bars": j - i, "reason": "blend", "feat": first[0].get("feat", {}) if first else {}})
            i = j + 1
        else:
            i += 1
    return r, trades


def run(strategy, params: dict, tickers: list[str]):
    """Full-history simulation per ticker; slicing to periods happens in `score`.
    `strategy` may be a list of (fn, params) parts: each part trades independently
    (its own exits) and they compete for the same portfolio slots, which is how a
    multi-signal indicator would be traded."""
    if isinstance(strategy, dict) and "blend" in strategy:
        return {t: blend_ticker(strategy["blend"], t) for t in tickers}
    if isinstance(strategy, (list, tuple)):
        out = {}
        for i, (fn, p) in enumerate(strategy):
            for t in tickers:
                out[f"{t}#{i}"] = run_ticker(fn, p, t)
        return out
    return {t: run_ticker(strategy, params, t) for t in tickers}


SLOTS = 5
SEEDS = 5
# Optional rule for choosing among same-day signals when slots are scarce:
# (feature name, True = highest first). None = random order.
RANK: tuple[str, bool] | None = None


def slot_portfolio(rets: pd.DataFrame, trades: dict[str, list[dict]], k: int | None = None, seed: int = 0) -> pd.Series:
    """How a swing trader actually uses a buy signal on a watchlist: at most `k` open
    positions, each sized 1/k of equity; a signal arriving with all slots full is
    skipped. Simultaneous signals are taken in a fixed random order (seeded) so no
    ticker is systematically favoured."""
    k = k or SLOTS
    rng = np.random.default_rng(seed)

    def key(x):
        if RANK is None:
            return rng.random()
        v = x.get("feat", {}).get(RANK[0], np.nan)
        v = -np.inf if not np.isfinite(v) else v
        return (-v if RANK[1] else v) + rng.random() * 1e-12

    allt = [(x["entry_date"], key(x), x["exit_date"], t) for t, ts in trades.items() for x in ts]
    allt.sort()
    mask = np.zeros(rets.shape)
    cols = {t: i for i, t in enumerate(rets.columns)}
    idx = rets.index
    active: list[pd.Timestamp] = []
    for ed, _, xd, t in allt:
        active = [x for x in active if x > ed]
        if len(active) >= k:
            continue
        active.append(xd)
        i0, i1 = idx.searchsorted(ed), idx.searchsorted(xd)
        mask[i0:i1 + 1, cols[t]] = 1
    return pd.Series((rets.to_numpy() * mask).sum(axis=1) / k, index=idx)


def score(results: dict, period: tuple[str, str], k: int | None = None) -> dict:
    a, b = pd.Timestamp(period[0]), pd.Timestamp(period[1])
    rets, trades, per, tmap = [], [], {}, {}
    for t, (r, tr) in results.items():
        rs = r[(r.index >= a) & (r.index <= b)]
        ts = [x for x in tr if a <= x["entry_date"] <= b]
        rets.append(rs.rename(t))
        trades += ts
        tmap[t] = ts
        per[t] = {**equity_stats(rs), **trade_stats(ts), "expo": float((rs != 0).mean())}
    rdf = pd.concat(rets, axis=1).fillna(0)
    port = rdf.mean(axis=1)
    out = {**equity_stats(port), **trade_stats(trades)}
    # Which of several same-day signals gets the last free slot is luck; average the
    # stats over a few seeded orderings so one lucky draw can't crown a version.
    seeds = [equity_stats(slot_portfolio(rdf, tmap, k, seed=s)) for s in range(SEEDS)]
    out["slot"] = {m: float(np.mean([x[m] for x in seeds])) for m in seeds[0]}
    out["slot_port"] = slot_portfolio(rdf, tmap, k, seed=0)
    out["med_sharpe"] = float(np.median([p["sharpe"] for p in per.values()]))
    if any("#" in t for t in results):  # combined parts: equal-weight sleeves per ticker
        port = rdf.T.groupby(lambda t: t.split("#")[0]).sum().T.mean(axis=1)
        out.update(equity_stats(port))
    out["pos_frac"] = float(np.mean([p["avg"] > 0 for p in per.values() if p["n"] > 0] or [0]))
    out["expo"] = float(np.mean([p["expo"] for p in per.values()]))
    out["per"] = per
    out["port"] = port
    return out


def buy_hold(tickers: list[str], period: tuple[str, str]) -> dict:
    a, b = pd.Timestamp(period[0]), pd.Timestamp(period[1])
    rets, per = [], {}
    for t in tickers:
        c = get(t)["close"]
        r = c.pct_change()
        r = r[(r.index >= a) & (r.index <= b)]
        rets.append(r)
        per[t] = equity_stats(r)
    port = pd.concat(rets, axis=1).fillna(0).mean(axis=1)
    out = equity_stats(port)
    out["med_sharpe"] = float(np.median([p["sharpe"] for p in per.values()]))
    out["per"] = per
    return out


def fmt(s: dict) -> str:
    if "slot" in s:
        k = s["slot"]
        base = (f"[{SLOTS}-slot] Sharpe {k['sharpe']:.2f} CAGR {k['cagr']*100:5.1f}% DD {k['maxdd']*100:6.1f}% "
                f"MAR {k['mar']:.2f} || sleeves Sharpe {s['sharpe']:.2f}")
    else:
        base = f"Sharpe {s['sharpe']:.2f} | CAGR {s['cagr']*100:5.1f}% | MaxDD {s['maxdd']*100:6.1f}% | MAR {s['mar']:.2f}"
    if "n" in s:
        base += (f" | trades {s['n']:4d} | win {s['win']*100:4.1f}% | PF {s['pf']:.2f} | avg {s['avg']*100:+.2f}%"
                 f" | bars {s['bars']:.1f} | expo {s['expo']*100:4.1f}% | medSh {s['med_sharpe']:.2f}"
                 f" | +tick {s['pos_frac']*100:3.0f}%")
    else:
        base += f" | medSh {s['med_sharpe']:.2f}"
    return base


def report(name: str, strategy: Callable, params: dict, verbose: bool = True) -> dict:
    """Score on DEV/HOLDOUT x IS/OOS. Returns the 4 score dicts."""
    out = {}
    for uname, uni in (("DEV", data.DEV), ("HOLD", data.HOLDOUT)):
        res = run(strategy, params, uni)
        for pname, per in (("IS", IS), ("OOS", OOS)):
            out[f"{uname}_{pname}"] = score(res, per)
    if verbose:
        print(f"== {name} {params}")
        for k, v in out.items():
            print(f"  {k:9s} {fmt(v)}")
        cs = composite(out)
        print(f"  COMPOSITE slot-Sharpe mean {cs['mean']:.2f} | min {cs['min']:.2f} | OOS {cs['oos']:.2f}"
              f" | MAR {cs['mar']:.2f} | sleeves {cs['sleeve']:.2f} | min trades/cell {cs['min_n']}")
    return out


CELLS = ("DEV_IS", "DEV_OOS", "HOLD_IS", "HOLD_OOS")


def composite(out: dict) -> dict:
    """Decision numbers: 5-slot Sharpe averaged over the 4 cells, the worst cell, and
    the OOS-only average. Plus min trades per cell (must be >= 30)."""
    sh = [out[c]["slot"]["sharpe"] for c in CELLS]
    return {"mean": float(np.mean(sh)), "min": float(np.min(sh)),
            "oos": float(np.mean([out["DEV_OOS"]["slot"]["sharpe"], out["HOLD_OOS"]["slot"]["sharpe"]])),
            "mar": float(np.mean([out[c]["slot"]["mar"] for c in CELLS])),
            "sleeve": float(np.mean([out[c]["sharpe"] for c in CELLS])),
            "min_n": int(min(out[c]["n"] for c in CELLS))}


def bh_report(verbose: bool = True) -> dict:
    out = {}
    for uname, uni in (("DEV", data.DEV), ("HOLD", data.HOLDOUT)):
        for pname, per in (("IS", IS), ("OOS", OOS)):
            out[f"{uname}_{pname}"] = buy_hold(uni, per)
    if verbose:
        print("== Buy & Hold")
        for k, v in out.items():
            print(f"  {k:9s} {fmt(v)}")
    return out


def grid(space: dict) -> list[dict]:
    keys = list(space)
    return [dict(zip(keys, vals)) for vals in itertools.product(*space.values())]


def walk_forward(strategy: Callable, space: dict, tickers: list[str], first_test_year: int = 2018,
                 last_test_year: int = 2026, train_start: str = "2015-01-01", min_trades: int = 30,
                 objective: str = "sharpe"):
    """Anchored walk-forward: before each test year, pick the params with the best
    portfolio `objective` on [train_start, year-1], then record only the next year."""
    combos = grid(space)
    sims = [run(strategy, p, tickers) for p in combos]
    pieces, chosen = [], []
    for y in range(first_test_year, last_test_year + 1):
        tr = (train_start, f"{y-1}-12-31")
        best, best_v = 0, -np.inf
        for i, res in enumerate(sims):
            s = score(res, tr)
            v = s[objective] if s["n"] >= min_trades else -np.inf
            if v > best_v:
                best, best_v = i, v
        te = score(sims[best], (f"{y}-01-01", f"{y}-12-31"))
        pieces.append(te["port"])
        chosen.append((y, combos[best]))
    port = pd.concat(pieces)
    return equity_stats(port), chosen, port


def neighbors(params: dict, keys: list[str], pct: float = 0.2) -> list[dict]:
    """One-at-a-time +-pct perturbations of the numeric params in `keys`."""
    out = []
    for k in keys:
        v = params[k]
        for m in (1 - pct, 1 + pct):
            nv = type(v)(round(v * m)) if isinstance(v, int) else round(v * m, 4)
            if nv != v:
                out.append({**params, k: nv})
    return out


def robustness(strategy: Callable, params: dict, keys: list[str], tickers: list[str] | None = None,
               period=FULL, pct: float = 0.2) -> pd.DataFrame:
    tickers = tickers or data.DEV
    rows = []
    for p in [params] + neighbors(params, keys, pct):
        s = score(run(strategy, p, tickers), period)
        diff = {k: p[k] for k in keys if p[k] != params[k]}
        rows.append({"change": str(diff) if diff else "BASE", "sharpe": s["sharpe"], "cagr": s["cagr"],
                     "maxdd": s["maxdd"], "n": s["n"], "pf": s["pf"]})
    return pd.DataFrame(rows)
