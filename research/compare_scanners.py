"""Head-to-head comparison: the uploaded "Explosive Breakout" swing scanner
(alt_scanners/explosive_breakout_scanner.py -- a cross-sectional momentum
scanner) vs this repo's screener, on the same price data, the same date
window and -- in the "fair" mode -- the same fill and cost rules.

    python -m research.compare_scanners --universe theirs --ours-pickle ours_on_theirs.pkl
    python -m research.compare_scanners --universe ours   --ours-pickle sg_merged.pkl

Their scanner is NOT re-implemented from scratch: signals use their own
compute_indicators(), _passeert_filters() and compute_stop(), and the ranking
reproduces bereken_samengesteld_momentum()/rangschik_universum_v2() in
vectorized form (checked against their function on sampled dates at
startup, so a drift between the two is caught instead of silently skewing
the comparison).

Their trades are evaluated under a ladder of rule sets, each changing ONE
assumption relative to the previous, so the report shows which assumption
their published numbers depend on:

  M1  "as published"  -- their own walk_forward_actueel(): entry at the
      signal day's CLOSE, their simuleer_exit() semantics (a stop fills AT
      the stop even when the day opens below it), a new overlapping trade
      on the same ticker every qualifying day, their cost model (0.2%
      round trip + liquidity-tiered slippage on stop-outs only).
  M1b M1 + one position per ticker at a time (no stacking the same bet).
  M1c M1b + gap-through fills (stop filled at the open when it gaps through,
      partial at the open when it gaps above the 1R level).
  M2  "same rules as our engine" -- entry at the NEXT session's OPEN
      (+0.05% slippage), stop placed from that fill, exits checked from the
      bar after entry, gap-through fills, one position per ticker, the same
      0.5%-risk / 20%-max-position sizing and $1-per-fill commission that
      backtesting/engine.py applies to our scanner.

Our scanner's trades come from research/capture_trades.py pickles, i.e. they
are already produced by backtesting/engine.py under M2's rules. Both sides
are restricted to entries inside the same window: from their first possible
signal (320 bars of history, required by their EMA300 + 252-day momentum)
to the common last date.
"""

from __future__ import annotations

import argparse
import logging
import math
import pickle
import sys
from dataclasses import dataclass

import numpy as np
import pandas as pd

import alt_scanners.explosive_breakout_scanner as eb
from config.schema import load_config
from data.cache import DiskCache
from data.universe import DEFAULT_UNIVERSE
from data.yfinance_provider import YFinanceProvider

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("compare_scanners")

MIN_HIST = 320  # their walk_forward_actueel(): 320 bars for the "multi" momentum method
HORIZONS = (63, 126, 252)
EXIT_METHOD = eb.EXIT_VARIANTEN["1. HUIDIG: 50%@1R + BE + ATR1.5 trail"]


# --------------------------------------------------------------------------- data

def _to_their_format(df: pd.DataFrame) -> pd.DataFrame:
    """Our provider's lower-case, UTC-indexed OHLCV -> their Title-case,
    naive-date-indexed frame (the format yfinance.download gives them)."""
    out = df.rename(columns={"open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"})
    out = out[["Open", "High", "Low", "Close", "Volume"]].copy()
    out.index = pd.DatetimeIndex(pd.to_datetime(out.index.date))
    out = out[~out.index.duplicated(keep="last")]
    return out.dropna()


def load_prepared(provider, tickers: list[str], period: str) -> tuple[dict[str, pd.DataFrame], pd.Series, pd.Series]:
    spy = _to_their_format(provider.get_history("SPY", period))["Close"]
    vix = _to_their_format(provider.get_history("^VIX", period))["Close"]
    prepared: dict[str, pd.DataFrame] = {}
    for t in tickers:
        try:
            df = _to_their_format(provider.get_history(t, period))
        except Exception as exc:  # noqa: BLE001 -- best effort, same as their loader
            logger.warning("skip %s: %s", t, exc)
            continue
        if len(df) < MIN_HIST:
            continue
        prepared[t] = eb.compute_indicators(df, spy_close=spy)
    return prepared, spy, vix


# --------------------------------------------------------------------------- signals

def composite_momentum(close: pd.Series) -> pd.Series:
    """Vectorized bereken_samengesteld_momentum(df, "multi") for every bar:
    mean over h of (Close[-(skip+1)] / Close[-(h+skip+1)] - 1) * 100."""
    skip = eb.MOMENTUM_SKIP
    parts = [(close.shift(skip) / close.shift(skip + h) - 1) * 100 for h in HORIZONS]
    return pd.concat(parts, axis=1).mean(axis=1, skipna=False)


def build_signals(prepared: dict[str, pd.DataFrame], vix: pd.Series) -> pd.DataFrame:
    """Every (date, ticker) their walk_forward_actueel() would trade."""
    all_days = sorted(set().union(*[set(d.index) for d in prepared.values()]))
    mom_cols = {}
    for t, df in prepared.items():
        m = composite_momentum(df["Close"])
        eligible = pd.Series(np.arange(1, len(df) + 1) >= MIN_HIST, index=df.index)
        mom_cols[t] = m.where(eligible)
    mom = pd.DataFrame(mom_cols).reindex(all_days)
    counts = mom.notna().sum(axis=1)
    pct = (mom.rank(axis=1, pct=True) * 100).round(1)
    pct[counts < 10] = np.nan

    vix_asof = vix.reindex(all_days, method="ffill")
    # their loop: range(min_hist, len(alle_dagen) - MAX_HOLD_DAYS)
    tradable_days = set(all_days[MIN_HIST: len(all_days) - eb.MAX_HOLD_DAYS])
    threshold = 100 - eb.TOP_N_PERCENTIEL

    rows = []
    for day in all_days:
        if day not in tradable_days:
            continue
        v = vix_asof.get(day)
        if eb.GEBRUIK_VIX_FILTER and (pd.isna(v) or not (eb.VIX_MINIMUM <= v <= eb.VIX_MAXIMUM)):
            continue
        day_pct = pct.loc[day].dropna()
        for t, p in day_pct[day_pct >= threshold].items():
            row = prepared[t].loc[day]
            if eb._passeert_filters(row):
                rows.append({"date": day, "ticker": t, "pct": p})
    return pd.DataFrame(rows)


def check_momentum_matches_theirs(prepared: dict[str, pd.DataFrame], n_samples: int = 40, seed: int = 0) -> None:
    rng = np.random.default_rng(seed)
    tickers = list(prepared)
    for _ in range(n_samples):
        t = tickers[rng.integers(len(tickers))]
        df = prepared[t]
        i = int(rng.integers(MIN_HIST, len(df)))
        theirs = eb.bereken_samengesteld_momentum(df.iloc[: i + 1], eb.MOMENTUM_METHODE)
        ours = composite_momentum(df["Close"]).iloc[i]
        if not np.isclose(theirs, ours, rtol=1e-9, atol=1e-9):
            raise AssertionError(f"momentum mismatch {t} @ {df.index[i]}: theirs={theirs} vectorized={ours}")


# --------------------------------------------------------------------------- simulation

@dataclass(frozen=True)
class Rules:
    name: str
    entry: str               # "close" (signal-day close) | "open" (next session open)
    gap_aware: bool          # stop/partial fill at the open when it gaps through the level
    one_position: bool       # no new trade on a ticker while one is still open
    costs: str               # "theirs" (% model) | "ours" (engine: slippage, sizing, $/fill)


RULESETS = [
    Rules("M1  as published", "close", False, False, "theirs"),
    Rules("M1b + 1 position/ticker", "close", False, True, "theirs"),
    Rules("M1c + gap-through fills", "close", True, True, "theirs"),
    Rules("M2  same rules as ours", "open", True, True, "ours"),
]


def simulate(prepared: dict[str, pd.DataFrame], signals: pd.DataFrame, rules: Rules, cfg) -> pd.DataFrame:
    slip = cfg.backtesting.slippage_pct / 100 if rules.costs == "ours" else 0.0
    commission = cfg.backtesting.commission_per_trade
    capital = cfg.backtesting.initial_capital
    risk_amount = capital * cfg.risk.risk_per_trade_pct / 100
    max_pos_value = capital * cfg.risk.max_position_pct / 100
    hold = eb.MAX_HOLD_DAYS
    m = EXIT_METHOD

    out = []
    for t, sig in signals.sort_values("date").groupby("ticker"):
        df = prepared[t]
        idx = df.index
        o, h, lo, c, atr = (df[k].to_numpy() for k in ("Open", "High", "Low", "Close", "ATR"))
        last_exit = -1
        for day, rank_pct in zip(sig["date"], sig["pct"]):
            i = idx.get_loc(day)
            if rules.one_position and i <= last_exit:
                continue
            row = df.iloc[i]
            if rules.entry == "close":
                entry_bar, entry = i, float(c[i])
            else:
                if i + 1 >= len(df):
                    continue
                entry_bar, entry = i + 1, float(o[i + 1]) * (1 + slip)
            stop0 = float(eb.compute_stop(row, entry))
            risk_ps = entry - stop0
            if risk_ps <= 0:
                continue
            first, last = entry_bar + 1, min(entry_bar + hold, len(df) - 1)
            if first > last:
                continue

            shares = math.floor(risk_amount / risk_ps)
            if shares * entry > max_pos_value:
                shares = math.floor(max_pos_value / entry)
            if rules.costs == "ours" and shares <= 0:
                continue

            stop, frac_open, partial_taken = stop0, 1.0, False
            fills: list[tuple[float, float]] = []   # (fraction of position, raw fill price)
            outcome, j = None, first
            level = entry + m["partial_r"] * risk_ps
            for j in range(first, last + 1):
                if lo[j] <= stop:
                    px = min(o[j], stop) if rules.gap_aware else stop
                    fills.append((frac_open, px))
                    outcome = "stop_after_partial" if partial_taken else "stop"
                    break
                if not partial_taken and h[j] >= level:
                    px = max(o[j], level) if rules.gap_aware else level
                    fr = m["partial_fractie"]
                    fills.append((fr, px))
                    frac_open -= fr
                    partial_taken = True
                    stop = max(stop, entry)
                if not np.isnan(atr[j]):
                    stop = max(stop, c[j] - m["trail_atr"] * atr[j])
            if outcome is None:
                fills.append((frac_open, float(c[last])))
                outcome = "time_after_partial" if partial_taken else "time"
                j = last

            if rules.costs == "theirs":
                pct = sum(fr * (px - entry) / entry * 100 for fr, px in fills)
                if "stop" in outcome:
                    pct -= eb.get_dynamic_slippage((row.get("VOL_SMA20", 0) or 0) * entry) * 100
                pct -= eb.COMMISSION_PCT * 2 * 100
                r = pct / (risk_ps / entry * 100)
                pnl = np.nan
            else:
                # integer shares like the engine; a 1-share position can't be split
                sold, proceeds, n_fills = 0, 0.0, 0
                for k, (fr, px) in enumerate(fills):
                    is_last_fill = k == len(fills) - 1
                    qty = shares - sold if is_last_fill else math.floor(shares * fr)
                    if qty <= 0:
                        continue
                    time_fill = is_last_fill and outcome.startswith("time")
                    fill_px = px if time_fill else px * (1 - slip)   # engine: no slippage on time exits
                    proceeds += qty * fill_px
                    sold += qty
                    n_fills += 1
                pnl = proceeds - shares * entry - commission * (1 + n_fills)
                pct = pnl / (shares * entry) * 100
                r = pnl / (shares * risk_ps)
            last_exit = j
            out.append({"ticker": t, "signal_date": day, "entry_date": idx[entry_bar], "exit_date": idx[j],
                        "pct": pct, "r": r, "pnl": pnl, "outcome": outcome, "priority": rank_pct,
                        "stop_pct": risk_ps / entry * 100,
                        "gap_through": bool(rules.gap_aware and "stop" in outcome and o[j] < stop)})
    return pd.DataFrame(out)


# --------------------------------------------------------------------------- our scanner

def ours_from_pickle(path: str) -> pd.DataFrame:
    with open(path, "rb") as f:
        payload = pickle.load(f)
    rows = []
    for tr, strat, score in zip(payload["trades"], payload["strategies"], payload["scores"]):
        risk = tr.shares * (tr.entry_price - tr.stop)
        rows.append({
            "ticker": getattr(tr, "ticker", None), "strategy": strat, "priority": score,
            "entry_date": pd.Timestamp(tr.entry_date.date()), "exit_date": pd.Timestamp(tr.exit_date.date()),
            "pct": tr.pnl_pct, "r": tr.pnl / risk if risk > 0 else np.nan, "pnl": tr.pnl,
            "outcome": tr.exit_reason, "stop_pct": (tr.entry_price - tr.stop) / tr.entry_price * 100,
        })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- one account

def portfolio_sim(trades: pd.DataFrame, cfg, start_equity: float | None = None) -> dict:
    """Both scanners' trade lists replayed through ONE shared account, the way
    a person would actually trade them: a trade is only taken if the account
    still has cash (sum of position values <= 100%) and heat (sum of open
    risk <= max_portfolio_risk_pct) for it; same-day candidates are taken in
    priority order (our score / their momentum percentile). Sizing follows
    the engine: risk_per_trade_pct of equity, capped at max_position_pct, so
    the fraction of equity a trade gains or loses is R * risk * min(1, cap).
    A slot frees up the session after the exit (exits happen at/after the
    open, entries at the open)."""
    if trades.empty:
        return {"taken": 0}
    risk = cfg.risk.risk_per_trade_pct / 100
    cap = cfg.risk.max_position_pct / 100
    heat_max = cfg.risk.max_portfolio_risk_pct / 100
    equity = start_equity or cfg.backtesting.initial_capital
    t = trades.dropna(subset=["r"]).sort_values(["entry_date", "priority"], ascending=[True, False])
    open_pos: list[tuple[pd.Timestamp, float, float, float]] = []   # (exit_date, pos_frac, risk_frac, $pnl)
    peak, max_dd, taken, taken_r, concurrent = equity, 0.0, 0, [], []
    for day, cands in t.groupby("entry_date", sort=True):
        for p in [p for p in open_pos if p[0] < day]:
            equity += p[3]
            peak = max(peak, equity)
            max_dd = max(max_dd, 1 - equity / peak)
        open_pos = [p for p in open_pos if p[0] >= day]
        for _, tr in cands.iterrows():
            pos_frac = min(cap, risk / (tr["stop_pct"] / 100))
            risk_frac = pos_frac * tr["stop_pct"] / 100
            if sum(p[1] for p in open_pos) + pos_frac > 1.0 + 1e-9:
                continue
            if sum(p[2] for p in open_pos) + risk_frac > heat_max + 1e-9:
                continue
            open_pos.append((tr["exit_date"], pos_frac, risk_frac, tr["r"] * risk_frac * equity))
            taken += 1
            taken_r.append(tr["r"])
        concurrent.append(len(open_pos))
    for p in open_pos:
        equity += p[3]
        peak = max(peak, equity)
        max_dd = max(max_dd, 1 - equity / peak)
    start0 = cfg.backtesting.initial_capital if start_equity is None else start_equity
    years = (t["exit_date"].max() - t["entry_date"].min()).days / 365.25
    return {"taken": taken, "offered": len(t), "mean_r": float(np.mean(taken_r)), "final": equity,
            "cagr": (equity / start0) ** (1 / years) - 1 if years > 0 else np.nan,
            "max_dd": max_dd, "avg_open": float(np.mean(concurrent))}


# --------------------------------------------------------------------------- reporting

def summarize(df: pd.DataFrame, years: float) -> dict:
    if df.empty:
        return {"n": 0}
    r = df["r"].dropna()
    gains, losses = r[r > 0].sum(), -r[r < 0].sum()
    out = {
        "n": len(df), "per_yr": len(df) / years,
        "win": (df["pct"] > 0).mean() * 100,
        "mean_pct": df["pct"].mean(), "med_pct": df["pct"].median(),
        "mean_r": r.mean(), "pf_r": gains / losses if losses > 0 else np.inf,
        "total_r": r.sum(), "worst_pct": df["pct"].min(),
        "avg_stop_pct": df["stop_pct"].mean(),
    }
    pnl = df["pnl"].dropna()
    if len(pnl):
        g, l_ = pnl[pnl > 0].sum(), -pnl[pnl < 0].sum()
        out["pf_usd"] = g / l_ if l_ > 0 else np.inf
        out["net_usd"] = pnl.sum()
    return out


def _fmt(label: str, s: dict) -> str:
    if s.get("n", 0) == 0:
        return f"{label:<30} (no trades)"
    usd = f"{s['pf_usd']:>6.2f} {s['net_usd']:>9.0f}" if "pf_usd" in s else f"{'-':>6} {'-':>9}"
    return (f"{label:<30}{s['n']:>6}{s['per_yr']:>7.0f}{s['win']:>7.1f}{s['mean_pct']:>8.2f}{s['med_pct']:>8.2f}"
            f"{s['mean_r']:>8.3f}{s['pf_r']:>7.2f}{s['total_r']:>8.0f} {usd}{s['avg_stop_pct']:>7.1f}{s['worst_pct']:>8.1f}")


HEADER = (f"{'':<30}{'n':>6}{'/yr':>7}{'win%':>7}{'mean%':>8}{'med%':>8}{'meanR':>8}{'PF_R':>7}{'sumR':>8}"
          f" {'PF_$':>6} {'net_$':>9}{'stop%':>7}{'worst%':>8}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--universe", choices=["theirs", "ours"], required=True)
    ap.add_argument("--ours-pickle", required=True, help="capture_trades.py output for OUR scanner on the same universe")
    ap.add_argument("--period", default="5y")
    ap.add_argument("--config", default=None)
    ap.add_argument("--trades-out", default=None, help="optional pickle with every simulated trade table")
    args = ap.parse_args(argv)

    cfg = load_config(args.config)
    cache = DiskCache(cache_dir=cfg.data.cache_dir, ttl_hours=cfg.data.cache_ttl_hours)
    provider = YFinanceProvider(cache=cache, max_retries=cfg.data.max_retries,
                                retry_backoff_seconds=cfg.data.retry_backoff_seconds)
    tickers = list(eb.WATCHLIST) if args.universe == "theirs" else list(DEFAULT_UNIVERSE)

    prepared, _spy, vix = load_prepared(provider, tickers, args.period)
    logger.info("%d/%d tickers with >= %d bars", len(prepared), len(tickers), MIN_HIST)
    check_momentum_matches_theirs(prepared)
    signals = build_signals(prepared, vix)
    logger.info("%d raw signals (%d distinct days)", len(signals), signals["date"].nunique() if len(signals) else 0)

    ours = ours_from_pickle(args.ours_pickle)
    all_days = sorted(set().union(*[set(d.index) for d in prepared.values()]))
    start = all_days[MIN_HIST]
    end = min(all_days[-1], ours["entry_date"].max())
    years = (end - start).days / 365.25
    mid = start + (end - start) / 2
    ours = ours[(ours["entry_date"] >= start) & (ours["entry_date"] <= end)]

    tables = {}
    for rules in RULESETS:
        t = simulate(prepared, signals, rules, cfg)
        if not t.empty:
            t = t[(t["entry_date"] >= start) & (t["entry_date"] <= end)]
        tables[rules.name] = t
    tables["OURS (engine)"] = ours

    print(f"\nUniverse: {args.universe} ({len(prepared)} tickers usable), window {start.date()} .. {end.date()} "
          f"({years:.1f} yr), split at {mid.date()}")
    for title, sub in (("ALL", None), ("FIRST HALF", "h1"), ("SECOND HALF", "h2")):
        print(f"\n== {title} ==\n{HEADER}")
        for name, t in tables.items():
            if sub == "h1":
                t = t[t["entry_date"] < mid]
            elif sub == "h2":
                t = t[t["entry_date"] >= mid]
            print(_fmt(name, summarize(t, years / (2 if sub else 1))))

    print("\n== PER YEAR: mean R (n) ==")
    yrs = sorted({d.year for t in tables.values() for d in t["entry_date"]})
    print(f"{'':<30}" + "".join(f"{y:>14}" for y in yrs))
    for name, t in tables.items():
        cells = []
        for y in yrs:
            s = t[t["entry_date"].dt.year == y]
            cells.append(f"{s['r'].mean():>+7.3f} ({len(s):>4})" if len(s) else f"{'-':>14}")
        print(f"{name:<30}" + "".join(cells))

    print(f"\n== ONE ${cfg.backtesting.initial_capital:,.0f} ACCOUNT (max {cfg.risk.max_position_pct:.0f}%/position, "
          f"{cfg.risk.max_portfolio_risk_pct:.0f}% heat, {cfg.risk.risk_per_trade_pct}% risk/trade) ==")
    print(f"{'':<30}{'offered':>8}{'taken':>7}{'meanR':>8}{'final_$':>10}{'CAGR%':>8}{'maxDD%':>8}{'avg_open':>9}")
    for name in ("M2  same rules as ours", "OURS (engine)"):
        p = portfolio_sim(tables[name], cfg)
        if p.get("taken"):
            print(f"{name:<30}{p['offered']:>8}{p['taken']:>7}{p['mean_r']:>8.3f}{p['final']:>10.0f}"
                  f"{p['cagr'] * 100:>8.1f}{p['max_dd'] * 100:>8.1f}{p['avg_open']:>9.1f}")

    m2 = tables["M2  same rules as ours"]
    if not m2.empty:
        stops = m2[m2["outcome"].str.startswith("stop")]
        print(f"\nM2 their scanner: {len(stops)} stop-outs, {stops['gap_through'].sum()} gapped through the stop "
              f"({stops['gap_through'].mean() * 100:.1f}%)")
        print("M2 outcome mix:", m2["outcome"].value_counts().to_dict())
    if args.trades_out:
        with open(args.trades_out, "wb") as f:
            pickle.dump({"tables": tables, "signals": signals, "start": start, "end": end}, f)
    return 0


if __name__ == "__main__":
    sys.exit(main())
