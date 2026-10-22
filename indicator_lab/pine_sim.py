"""Bar-by-bar Python simulation of the v3 Pine INDICATOR (its BUY/SELL state machine and its
"chart statistics" table row), with switches for every step of the reliability round, so each
change can be measured before/after on the same tickers.

cfg keys (all default to the ORIGINAL pre-round behaviour):
  features   "current" | "step1" | "fixed"   feature definitions (step 1, + step 7 SPY on SPY bars)
  model      "final"   | "oos"     final fit on every bar, or the walk-forward fit of each bar's year (step 2)
  na_block   bool                  quality = na and no BUY when any feature is na (step 4)
  half_book  bool                  book the half-profit exit 50/50 (step 5; only matters with tp_mult > 0)
  tp_mult    float                 half-profit target in ATR (0 = off)

stats(): "mae" is the worst and "dd_avg" the average per-trade max drawdown (peak since the fill to a later low,
a bar's high assumed before its low), "bars" the average holding period: the Pine table row "OOS per trade".
"""
from __future__ import annotations

import os

import numpy as np
import pandas as pd

from indicator_lab import pine_parity as PP
from indicator_lab import pine_ta as T
from indicator_lab.evaluate import get

PINE_DIR = os.path.join(os.path.dirname(__file__), "pine")
DEFAULT = {"features": "current", "model": "final", "na_block": False, "half_book": False, "tp_mult": 0.0,
           "n": 20, "m": 20, "trail": 4.0, "ibs_min": 0.7, "trend_len": 200, "cost_pct": 0.1,
           "stats_from": "2015-01-01"}
# the Pine files at the end of the reliability round (steps 1-7)
FINAL = {"features": "fixed", "model": "oos", "na_block": True, "half_book": True}


def load_models():
    from indicator_lab.export_pine import _load
    return _load()


def quality(df: pd.DataFrame, ticker: str, cfg: dict) -> tuple[np.ndarray, np.ndarray]:
    """Per-bar (quality probability, threshold probability) as the Pine script computes them."""
    final, yearly = load_models()
    f = PP.pine_features(df, us=ticker not in PP.NON_US, version=cfg["features"])
    feats = final["feats"]
    X = f[feats].to_numpy(float)
    has_na = np.isnan(X).any(axis=1)

    def sc(fit):
        z = (X - np.asarray(fit["mu"])) / np.asarray(fit["sd"])
        z = np.where(np.isnan(z), 0.0, z)  # original Pine: f_z() = nz(...) -> 0
        return fit["b"] + z @ np.asarray(fit["w"])

    if cfg["model"] == "final":
        s = sc(final)
        thr = np.full(len(df), final["thr"])
    else:
        s = np.full(len(df), np.nan)
        thr = np.full(len(df), np.nan)
        years = df.index.year
        live = df.index > pd.Timestamp(yearly["train_end"])
        for fit in yearly["fits"]:
            sel = (years == fit["year"]) & ~live
            if sel.any():
                s[sel] = sc(fit)[sel]
                thr[sel] = fit["thr"]
        s[live] = sc(final)[live]
        thr[live] = final["thr"]
    q = 1 / (1 + np.exp(-s))
    if cfg["na_block"]:
        q = np.where(has_na, np.nan, q)
    return q, thr


def run(df: pd.DataFrame, ticker: str, cfg: dict | None = None) -> dict:
    cfg = {**DEFAULT, **(cfg or {})}
    o, h, lo, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    a = T.atr(h, lo, c, 14) if cfg["features"] == "current" else T.atr_py(h, lo, c, 14)
    tma = T.sma(c, cfg["trend_len"])
    hi_n = T.shift(T.highest(h, cfg["n"]))
    lo_m = T.shift(pd.Series(lo).rolling(cfg["m"], min_periods=cfg["m"]).min().to_numpy())
    rng = h - lo
    ibs = np.where(rng > 0, (c - lo) / np.where(rng > 0, rng, 1), 0.5)
    q, thr = quality(df, ticker, cfg)
    with np.errstate(invalid="ignore"):
        ok = q >= thr
    k = cfg["cost_pct"] / 100
    tpm = cfg["tp_mult"]
    stats_from = pd.Timestamp(cfg["stats_from"])

    def book(px):
        return px * (1 - k) / (entry_px * (1 + k)) - 1

    state, hh, stop, entry_px, tp, half_off, half_ret = 0, np.nan, np.nan, np.nan, np.nan, False, np.nan
    counted, ebar, peak, mae = False, 0, np.nan, 0.0
    trades = []
    buy = np.zeros(len(c), bool)
    sell = np.zeros(len(c), bool)

    def close_trade(t, px):
        r = book(px)
        if cfg["half_book"] and half_off:
            r = 0.5 * half_ret + 0.5 * r
        if counted:
            trades.append({"entry_date": df.index[ebar], "exit_date": df.index[t], "ret": r, "bars": t - ebar,
                           "mae": min(mae, px / peak - 1)})

    for t in range(len(c)):
        exited = False
        if state == 3:
            close_trade(t, o[t])
            state, stop, exited = 0, np.nan, True
        if state == 1:
            entry_px, ebar, counted = o[t], t, df.index[t] >= stats_from
            state, hh = 2, h[t]
            peak, mae = o[t], min(0.0, lo[t] / o[t] - 1)  # Pine: a bar's high is assumed before its low
            istop = o[t] - cfg["trail"] * a[t - 1]
            stop = max(istop, hh - cfg["trail"] * a[t])
            tp = o[t] + tpm * a[t - 1] if tpm > 0 else np.nan
            half_off = False
            if lo[t] <= istop:
                close_trade(t, istop)
                sell[t], state, stop = True, 0, np.nan
            else:
                if tpm > 0 and h[t] >= tp:
                    half_off, half_ret = True, book(tp)
                peak = max(o[t], c[t])
                if c[t] < lo_m[t]:
                    sell[t], state = True, 3
        elif state == 2:
            if lo[t] <= stop:
                close_trade(t, min(o[t], stop))
                sell[t], state, stop = True, 0, np.nan
            else:
                if tpm > 0 and not half_off and h[t] >= tp:
                    half_off, half_ret = True, book(max(o[t], tp))  # gap above target fills at the open
                peak = max(peak, h[t])
                mae = min(mae, lo[t] / peak - 1)
                hh = max(hh, h[t])
                stop = max(stop, hh - cfg["trail"] * a[t])
                if c[t] < lo_m[t]:
                    sell[t], state = True, 3
        cand = c[t] > hi_n[t] and c[t] > tma[t] and ibs[t] >= cfg["ibs_min"]
        if state == 0 and not sell[t] and not exited and cand and bool(ok[t]):
            buy[t], state = True, 1
    return {"buy": buy, "sell": sell, "trades": trades}


def stats(trades: list[dict]) -> dict:
    if not trades:
        return {"n": 0, "win": np.nan, "pf": np.nan, "avg": np.nan, "worst": np.nan, "mae": np.nan, "dd_avg": np.nan,
                "bars": np.nan}
    r = np.array([x["ret"] for x in trades])
    gl = -r[r < 0].sum()
    return {"n": len(r), "win": float((r > 0).mean()), "pf": float(r[r > 0].sum() / gl) if gl > 0 else np.inf,
            "avg": float(r.mean()), "worst": float(r.min()), "mae": float(min(x["mae"] for x in trades)),
            "dd_avg": float(np.mean([x["mae"] for x in trades])),
            "bars": float(np.mean([x["bars"] for x in trades]))}


def table(tickers, cfg: dict | None = None) -> pd.DataFrame:
    rows = []
    for t in tickers:
        s = stats(run(get(t), t, cfg)["trades"])
        rows.append({"ticker": t, **s})
    return pd.DataFrame(rows).set_index("ticker")


def run_strategy(df: pd.DataFrame, ticker: str, cfg: dict | None = None, from_time: str = "2015-01-01") -> list[dict]:
    """Emulates `swing_v3_strategy.pine` under TradingView's broker rules, written as an order book (independent
    of `run`, which follows the indicator's state machine), so the two can be compared:
    - the script runs at each bar's close; orders it places execute from the next bar (process_orders_on_close=false)
    - market orders fill at the next open; a stop order fills at the open if the open is already through it,
      otherwise at the stop price when the low reaches it
    - the entry's exit order uses `loss` = trailMult x ATR(signal bar) ticks below the fill, so it is live on the fill bar
    - commission: percent of traded value on both sides (TradingView's formula, not the engine's)."""
    cfg = {**DEFAULT, **(cfg or {})}
    o, h, lo, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    a = T.atr_py(h, lo, c, 14)
    tma = T.sma(c, cfg["trend_len"])
    hi_n = T.shift(T.highest(h, cfg["n"]))
    lo_m = T.shift(pd.Series(lo).rolling(cfg["m"], min_periods=cfg["m"]).min().to_numpy())
    rng = h - lo
    ibs = np.where(rng > 0, (c - lo) / np.where(rng > 0, rng, 1), 0.5)
    q, thr = quality(df, ticker, cfg)
    with np.errstate(invalid="ignore"):
        ok = q >= thr
    k = cfg["cost_pct"] / 100
    t0 = pd.Timestamp(from_time)
    pos_px = np.nan                         # open position's fill price (nan = flat)
    entry_order, close_order = False, False  # market orders waiting for the next open
    loss_dist, stop_order = np.nan, np.nan  # exit order: `loss` distance (until replaced) / stop price
    hh = trail = sig_atr = np.nan
    ebar = 0
    trades = []

    def fill_exit(t, px):
        trades.append({"entry_date": df.index[ebar], "exit_date": df.index[t], "bars": t - ebar,
                       "ret": (px - pos_px) / pos_px - k * (1 + px / pos_px)})

    for t in range(len(c)):
        closed = False
        # ---- broker: orders placed at the previous close ----
        if entry_order:
            pos_px, ebar, entry_order = o[t], t, False
            stop_order = pos_px - loss_dist   # `loss` becomes a stop price once the fill is known
        if not np.isnan(pos_px):
            if close_order or o[t] <= stop_order:  # market close, or a gap through the stop: both fill at the open
                fill_exit(t, o[t])
                closed = True
            elif lo[t] <= stop_order:
                fill_exit(t, stop_order)
                closed = True
            if closed:
                pos_px, close_order, stop_order = np.nan, False, np.nan
        # ---- script at the close ----
        if not np.isnan(pos_px):
            hh = h[t] if np.isnan(hh) else max(hh, h[t])
            trail = max(pos_px - cfg["trail"] * sig_atr if np.isnan(trail) else trail, hh - cfg["trail"] * a[t])
            stop_order = trail
            if c[t] < lo_m[t]:
                close_order = True
        else:
            hh = trail = np.nan
            cand = c[t] > hi_n[t] and c[t] > tma[t] and ibs[t] >= cfg["ibs_min"]
            if not closed and df.index[t] >= t0 and cand and bool(ok[t]):
                sig_atr = a[t]
                entry_order, loss_dist = True, cfg["trail"] * a[t]
    return trades
