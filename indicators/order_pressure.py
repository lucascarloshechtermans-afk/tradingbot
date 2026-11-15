"""Order pressure toolkit + rolling period HVN profiles.

Builds on ``indicators/hvn_absorption.py`` and mirrors the TradingView script
``pine/hvn_absorption.pine``:

* **Rolling period profiles** (``period_hvns``): one volume profile per calendar
  period (e.g. week/month), its HVNs and POC, and each level's first *retest*
  after price traded away from it — computed strictly from completed periods, so
  it is safe to use in a backtest.
* **Order pressure** (``order_pressure``): buy vs. sell volume per bar (from a real
  delta when available, else split by close location) and the rolling buy-side
  share; plus *aggressive* bars — outsized volume that actually moved price.
* **Passive limit order zones** (``passive_zones``): where an absorption bar's
  aggression was soaked up (the lower wick of bullish absorption, the upper wick of
  bearish absorption). Zones stay live until a close goes through them.
* **Psychological levels** (``psych_step`` / ``psych_levels``): round numbers.
* **Multi-signal** (``multi_signal``): absorption scored by confluence with an
  HVN/POC, a round number, a passive zone retest, and trapped aggressors.

Same data caveat as hvn_absorption: from OHLCV bars "aggressive" and "passive"
are inferred from volume, wick shape and close location; pass a real ``delta``
(buy minus sell volume) for the order-flow version.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from indicators.hvn_absorption import HVN, absorption, find_hvns, volume_profile
from indicators.volatility import atr


# --------------------------------------------------------------------------- #
# Psychological levels
# --------------------------------------------------------------------------- #

def psych_step(price: float) -> float:
    """Auto round-number step: 10^(digits-1). 754 -> 10, 6000 -> 100, 1.08 -> 0.1."""
    if price <= 0 or not math.isfinite(price):
        return 1.0
    return 10.0 ** (math.floor(math.log10(price)) - 1)


def psych_levels(price: float, step: float | None = None, count: int = 3) -> list[float]:
    step = step or psych_step(price)
    base = round(price / step) * step
    return [round(base + j * step, 10) for j in range(-count, count + 1)]


def touches_psych_level(high: pd.Series, low: pd.Series, step: float | None = None) -> pd.Series:
    """True where the bar's range contains a round number."""
    steps = pd.Series(step, index=high.index) if step else high.map(psych_step)
    return np.floor(high / steps) * steps >= low


# --------------------------------------------------------------------------- #
# Order pressure
# --------------------------------------------------------------------------- #

def order_pressure(
    df: pd.DataFrame,
    delta: pd.Series | None = None,
    window: int = 20,
    aggressive_rvol: float = 2.5,
    aggressive_body_atr: float = 0.8,
    rvol_window: int = 20,
    atr_window: int = 14,
) -> pd.DataFrame:
    """Columns: buy_volume, sell_volume, buy_pressure (rolling % of volume on the
    buy side over `window` bars), aggressive (+1 buy / -1 sell / 0) for bars with
    relative volume >= `aggressive_rvol` AND a net move >= `aggressive_body_atr`
    ATR — effort that produced result, the opposite of absorption."""
    h, l, c, o, v = (df[k].astype(float) for k in ("high", "low", "close", "open", "volume"))
    if delta is not None:
        d = delta.reindex(df.index).astype(float).fillna(0.0).clip(-v, v)
        buy, sell = (v + d) / 2, (v - d) / 2
    else:
        rng = (h - l).replace(0, np.nan)
        clv = ((c - l) / rng).fillna(0.5)
        buy, sell = v * clv, v * (1 - clv)
    tot = buy.rolling(window, min_periods=1).sum() + sell.rolling(window, min_periods=1).sum()
    pressure = (buy.rolling(window, min_periods=1).sum() / tot.replace(0, np.nan) * 100).fillna(50.0)

    rvol = v / v.shift(1).rolling(rvol_window, min_periods=rvol_window).mean()
    body_atr = (c - o).abs() / atr(h, l, c, atr_window)
    big = (rvol >= aggressive_rvol) & (body_atr >= aggressive_body_atr)
    aggressive = pd.Series(0, index=df.index, dtype=int)
    aggressive[big & (c > o)] = 1
    aggressive[big & (c < o)] = -1
    return pd.DataFrame({"buy_volume": buy, "sell_volume": sell, "buy_pressure": pressure,
                         "aggressive": aggressive}, index=df.index)


# --------------------------------------------------------------------------- #
# Passive limit order zones
# --------------------------------------------------------------------------- #

@dataclass
class PassiveZone:
    top: float
    bottom: float
    direction: int                     # +1 passive buyers (support), -1 passive sellers
    created: pd.Timestamp
    heavy: bool
    broken_at: pd.Timestamp | None = None
    retests: int = 0

    @property
    def active(self) -> bool:
        return self.broken_at is None


def passive_zones(
    df: pd.DataFrame,
    abs_df: pd.DataFrame | None = None,
    min_zone_atr: float = 0.15,
    atr_window: int = 14,
    max_zones: int = 20,
) -> tuple[list[PassiveZone], pd.DataFrame]:
    """Walk the bars once: create a zone on each absorption bar, track retests
    (price comes back after having left) and breaks (close through the far side).

    Returns (zones, events) where events has per-bar `zone_retest` (+1/-1/0) and
    `zone_broken` (+1/-1/0) — only zones created on EARLIER bars count.
    """
    abs_df = absorption(df) if abs_df is None else abs_df
    a = atr(df["high"], df["low"], df["close"], atr_window)
    zones: list[PassiveZone] = []
    armed: dict[int, bool] = {}
    retest = np.zeros(len(df), dtype=int)
    broken = np.zeros(len(df), dtype=int)

    for i, ts in enumerate(df.index):
        hi, lo, cl, op = (float(df[k].iloc[i]) for k in ("high", "low", "close", "open"))
        for z in zones:
            if not z.active:
                continue
            inside = lo <= z.top and hi >= z.bottom
            if (z.direction == 1 and cl < z.bottom) or (z.direction == -1 and cl > z.top):
                z.broken_at = ts
                broken[i] = z.direction
            elif inside and armed[id(z)]:
                z.retests += 1
                retest[i] = z.direction
            elif not inside:
                armed[id(z)] = True

        direction = int(abs_df["direction"].iloc[i])
        if direction != 0:
            min_h = float(np.nan_to_num(a.iloc[i])) * min_zone_atr
            top, bot = (min(op, cl), lo) if direction == 1 else (hi, max(op, cl))
            if top - bot < min_h:
                if direction == 1:
                    top = bot + min_h
                else:
                    bot = top - min_h
            z = PassiveZone(top, bot, direction, ts, bool(abs_df["heavy"].iloc[i]))
            zones.append(z)
            armed[id(z)] = False
            live = [zz for zz in zones if zz.active]
            if len(live) > max_zones:
                live[0].broken_at = ts  # retire the oldest live zone

    events = pd.DataFrame({"zone_retest": retest, "zone_broken": broken}, index=df.index)
    return zones, events


# --------------------------------------------------------------------------- #
# Rolling period HVN profiles
# --------------------------------------------------------------------------- #

@dataclass
class PeriodNode:
    node: HVN
    period: pd.Period
    available_from: pd.Timestamp       # first bar AFTER the period closed
    retested_at: pd.Timestamp | None = None


def period_hvns(
    df: pd.DataFrame,
    freq: str = "W",
    bins: int = 50,
    smoothing: float = 1.5,
    threshold: float = 0.70,
    zone_ratio: float = 0.80,
    max_nodes: int = 4,
) -> tuple[list[PeriodNode], pd.DataFrame]:
    """One profile per calendar period (`freq`: "D", "W", "M", "Q", "Y"), built
    only once the period has closed. Returns (nodes, per-bar frame) where the
    frame holds, for each bar, using completed periods only:
      prev_poc   — POC of the most recent completed period
      at_hvn     — bar trades into an unretested node or a node of the last period
      hvn_retest — first touch of a node after price had moved away from it
    """
    idx = pd.DatetimeIndex(df.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    periods = idx.to_period(freq)
    uniq = periods.unique()

    nodes: list[PeriodNode] = []
    for p in uniq[:-1]:  # the last period is still developing
        mask = periods == p
        window = df[mask]
        if len(window) < 2:
            continue
        nxt = np.argmax(periods > p)
        prof = volume_profile(window["high"], window["low"], window["volume"], bins, smoothing)
        for nd in find_hvns(prof, threshold, zone_ratio, max_nodes=max_nodes):
            nodes.append(PeriodNode(nd, p, df.index[nxt]))

    prev_poc = pd.Series(np.nan, index=df.index)
    at_hvn = np.zeros(len(df), dtype=bool)
    retest = np.zeros(len(df), dtype=bool)
    armed = {id(pn): False for pn in nodes}
    last_period = None
    for i, ts in enumerate(df.index):
        hi, lo = float(df["high"].iloc[i]), float(df["low"].iloc[i])
        live = [pn for pn in nodes if pn.available_from <= ts]
        if live:
            last_period = max(pn.period for pn in live)
            pocs = [pn.node.price for pn in live if pn.period == last_period and pn.node.is_poc]
            prev_poc.iloc[i] = pocs[0] if pocs else np.nan
        for pn in live:
            inside = pn.node.overlaps(lo, hi)
            if inside and (pn.retested_at is None or pn.period == last_period):
                at_hvn[i] = True
            if pn.retested_at is None:
                if inside and armed[id(pn)]:
                    pn.retested_at = ts
                    retest[i] = True
                elif not inside:
                    armed[id(pn)] = True

    frame = pd.DataFrame({"prev_poc": prev_poc, "at_hvn": at_hvn, "hvn_retest": retest}, index=df.index)
    return nodes, frame


# --------------------------------------------------------------------------- #
# Multi-signal
# --------------------------------------------------------------------------- #

def multi_signal(
    df: pd.DataFrame,
    delta: pd.Series | None = None,
    freq: str = "W",
    psych: float | None = None,
    min_confluence: int = 2,
    **absorption_kwargs,
) -> pd.DataFrame:
    """Absorption bars scored by confluence (lookahead-free):
    +1 absorption, +1 inside an HVN/POC of a completed period, +1 bar contains a
    round number, +1 retest of a same-direction passive zone, +1 trapped
    aggressors (delta pushed against the close). `signal` is +1/-1 when the
    score reaches `min_confluence`, 0 otherwise."""
    ab = absorption(df, delta=delta, **absorption_kwargs)
    _, zone_ev = passive_zones(df, ab)
    _, per = period_hvns(df, freq=freq)
    at_psy = touches_psych_level(df["high"], df["low"], psych)

    d = ab["direction"]
    is_abs = d != 0
    trapped = pd.Series(False, index=df.index)
    if delta is not None:
        dd = delta.reindex(df.index).astype(float)
        trapped = ((d == 1) & (dd < 0)) | ((d == -1) & (dd > 0))

    score = (
        is_abs.astype(int)
        + (is_abs & per["at_hvn"]).astype(int)
        + (is_abs & at_psy).astype(int)
        + (is_abs & (zone_ev["zone_retest"] == d)).astype(int)
        + (is_abs & trapped).astype(int)
    )
    out = ab.copy()
    out["at_hvn"] = per["at_hvn"]
    out["hvn_retest"] = per["hvn_retest"]
    out["prev_poc"] = per["prev_poc"]
    out["at_psych"] = at_psy
    out["zone_retest"] = zone_ev["zone_retest"]
    out["zone_broken"] = zone_ev["zone_broken"]
    out["confluence"] = score
    out["signal"] = np.where(score >= min_confluence, d, 0)
    return out
