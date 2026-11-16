"""HVN Profile + Absorption indicator.

Two related order-flow-style tools built from plain OHLCV bars (optionally
enriched with a per-bar volume delta when the data source has one):

**HVN Profile** — a volume-by-price profile over one or more lookback windows
("multi-period"), smoothed with a Gaussian kernel so adjacent busy price bins
cluster into one node instead of a comb of tiny peaks ("smoothed clustering").
High Volume Nodes are the local peaks of that smoothed profile that stand out
from the rest of it. Each node carries a price zone, a strength relative to the
POC (Point of Control, the single busiest price), and the number of times price
has traded back into it. Nodes found by several lookbacks at the same price are
merged into one, stronger, confluence level.

**Absorption** — a bar where a lot of volume went through but price barely
moved: high effort, little result. Aggressive orders hit the book and were
soaked up by passive limit orders on the other side.

  * bullish absorption: sellers were the aggressors (negative delta, or — without
    delta — price was pushed into the lower part of the bar) but the bar closed
    in its upper half: the selling was absorbed by buyers.
  * bearish absorption: the mirror image.

"Heavy" absorption is the same pattern on a much larger volume multiple, and
absorption *at an HVN* (price inside a node's zone) is the highest-quality
variant, since the node is where the passive liquidity is expected to sit.

Data caveat: true absorption is read from a footprint (bid/ask volume per price
inside the bar). Daily OHLCV can only approximate it with the effort-vs-result
and wick shape of the whole bar. Pass a ``delta`` series (buy volume minus sell
volume per bar, e.g. from tick or 1-minute data) to get the order-flow version.
Same caveat as the anchored VWAP in ``indicators/vwap.py``: the volume-by-price
profile spreads each bar's volume evenly over its high-low range, because the
true intrabar distribution isn't in the data.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from indicators.volatility import atr
from indicators.volume import relative_volume


# --------------------------------------------------------------------------- #
# Volume profile
# --------------------------------------------------------------------------- #

@dataclass
class VolumeProfile:
    bin_edges: np.ndarray       # len = bins + 1
    volume: np.ndarray          # raw volume per bin, len = bins
    smoothed: np.ndarray        # Gaussian-smoothed volume per bin
    poc: float                  # price of the busiest smoothed bin
    value_area_low: float
    value_area_high: float
    buy: np.ndarray | None = None  # raw buy-side volume per bin, when buy_volume was given

    @property
    def bin_centers(self) -> np.ndarray:
        return (self.bin_edges[:-1] + self.bin_edges[1:]) / 2

    @property
    def bin_size(self) -> float:
        return float(self.bin_edges[1] - self.bin_edges[0])


def _gaussian_smooth(values: np.ndarray, sigma: float) -> np.ndarray:
    if sigma <= 0:
        return values.astype(float).copy()
    radius = max(1, int(round(3 * sigma)))
    x = np.arange(-radius, radius + 1)
    kernel = np.exp(-0.5 * (x / sigma) ** 2)
    kernel /= kernel.sum()
    padded = np.pad(values.astype(float), radius, mode="constant")
    return np.convolve(padded, kernel, mode="valid")


def _value_area(volume: np.ndarray, poc_idx: int, pct: float) -> tuple[int, int]:
    """Standard value-area expansion: start at the POC and keep adding whichever
    neighbouring bin is busier until `pct` of total volume is enclosed."""
    total = volume.sum()
    lo = hi = poc_idx
    enclosed = volume[poc_idx]
    while enclosed < total * pct and (lo > 0 or hi < len(volume) - 1):
        below = volume[lo - 1] if lo > 0 else -1.0
        above = volume[hi + 1] if hi < len(volume) - 1 else -1.0
        if above >= below:
            hi += 1
            enclosed += volume[hi]
        else:
            lo -= 1
            enclosed += volume[lo]
    return lo, hi


def volume_profile(
    high: pd.Series,
    low: pd.Series,
    volume: pd.Series,
    bins: int = 60,
    smoothing: float = 1.5,
    value_area_pct: float = 0.70,
    buy_volume: pd.Series | None = None,
) -> VolumeProfile:
    """Volume-by-price over the given bars.

    Pass `buy_volume` (per bar, e.g. (volume + delta) / 2) to also get the
    buy-side volume per bin, from which each HVN's buyer/seller dominance follows.

    Each bar's volume is spread over the bins its [low, high] range overlaps, in
    proportion to the overlap. A zero-range bar puts all its volume in one bin.
    """
    h = high.to_numpy(dtype=float)
    lo_ = low.to_numpy(dtype=float)
    v = volume.to_numpy(dtype=float)
    ok = ~(np.isnan(h) | np.isnan(lo_) | np.isnan(v))
    h, lo_, v = h[ok], lo_[ok], v[ok]
    if len(h) == 0:
        raise ValueError("volume_profile needs at least one complete bar")

    p_min, p_max = float(lo_.min()), float(h.max())
    if p_max <= p_min:
        p_max = p_min + max(abs(p_min) * 1e-6, 1e-9)
    edges = np.linspace(p_min, p_max, bins + 1)

    # overlap of every bar with every bin: (n_bars, bins)
    overlap = np.clip(
        np.minimum(h[:, None], edges[None, 1:]) - np.maximum(lo_[:, None], edges[None, :-1]), 0, None
    )
    rng = h - lo_
    per_bar = np.zeros_like(overlap)
    has_range = rng > 0
    per_bar[has_range] = overlap[has_range] / rng[has_range, None]
    # zero-range bars: whole volume to the bin containing the price
    flat_idx = np.where(~has_range)[0]
    if len(flat_idx):
        bin_of = np.clip(np.searchsorted(edges, h[flat_idx], side="right") - 1, 0, bins - 1)
        per_bar[flat_idx, bin_of] = 1.0
    raw = (per_bar * v[:, None]).sum(axis=0)
    buy_raw = None
    if buy_volume is not None:
        b = np.nan_to_num(buy_volume.to_numpy(dtype=float)[ok])
        buy_raw = (per_bar * b[:, None]).sum(axis=0)

    smooth = _gaussian_smooth(raw, smoothing)
    centers = (edges[:-1] + edges[1:]) / 2
    poc_idx = int(np.argmax(smooth))
    va_lo, va_hi = _value_area(smooth, poc_idx, value_area_pct)
    return VolumeProfile(
        bin_edges=edges,
        volume=raw,
        smoothed=smooth,
        poc=float(centers[poc_idx]),
        value_area_low=float(edges[va_lo]),
        value_area_high=float(edges[va_hi + 1]),
        buy=buy_raw,
    )


# --------------------------------------------------------------------------- #
# High Volume Nodes
# --------------------------------------------------------------------------- #

@dataclass
class HVN:
    price: float                 # peak of the node
    zone_low: float
    zone_high: float
    volume: float                # smoothed volume at the peak
    strength: float              # 0-100, peak volume relative to the POC
    is_poc: bool
    lookbacks: list[int] = field(default_factory=list)  # which profile windows found it
    touches: int = 0             # bars that traded back into the zone after it formed
    zone_volume: float = 0.0     # raw volume traded inside the zone
    buy_pct: float | None = None  # % of zone volume on the buy side (None without buy data)

    @property
    def dominant_side(self) -> str | None:
        """'buy' / 'sell' — which side traded more at this node."""
        if self.buy_pct is None:
            return None
        return "buy" if self.buy_pct >= 50 else "sell"

    @property
    def label(self) -> str:
        """Chart label: zone volume (k) | dominant side share, e.g. '51 | 54%'."""
        vol = f"{self.zone_volume / 1000:.0f}"
        if self.buy_pct is None:
            return vol
        return f"{vol} | {max(self.buy_pct, 100 - self.buy_pct):.0f}%"

    def contains(self, price: float) -> bool:
        return self.zone_low <= price <= self.zone_high

    def overlaps(self, bar_low: float, bar_high: float) -> bool:
        return bar_low <= self.zone_high and bar_high >= self.zone_low


def find_hvns(
    profile: VolumeProfile,
    threshold: float = 0.70,
    zone_ratio: float = 0.80,
    min_separation_bins: int = 3,
    max_nodes: int = 6,
) -> list[HVN]:
    """Local peaks of the smoothed profile that are high-volume nodes.

    threshold: a peak must be at least this percentile (0-1) of all smoothed bins.
    zone_ratio: the node's zone extends outward from the peak while volume stays
        at or above `zone_ratio` x peak volume.
    min_separation_bins: peaks closer than this are merged (the bigger one wins).
    """
    s = profile.smoothed
    n = len(s)
    if n < 3 or s.max() <= 0:
        return []
    cutoff = np.quantile(s, threshold)
    left = np.r_[-np.inf, s[:-1]]
    right = np.r_[s[1:], -np.inf]
    peak_idx = np.where((s >= left) & (s > right) & (s >= cutoff))[0]

    chosen: list[int] = []
    for i in sorted(peak_idx, key=lambda k: s[k], reverse=True):
        if all(abs(i - j) >= min_separation_bins for j in chosen):
            chosen.append(int(i))

    edges = profile.bin_edges
    poc_vol = s.max()
    nodes: list[HVN] = []
    for i in chosen[:max_nodes]:
        lo = hi = i
        while lo > 0 and s[lo - 1] >= s[i] * zone_ratio and s[lo - 1] <= s[lo]:
            lo -= 1
        while hi < n - 1 and s[hi + 1] >= s[i] * zone_ratio and s[hi + 1] <= s[hi]:
            hi += 1
        nodes.append(HVN(
            price=float((edges[i] + edges[i + 1]) / 2),
            zone_low=float(edges[lo]),
            zone_high=float(edges[hi + 1]),
            volume=float(s[i]),
            strength=float(s[i] / poc_vol * 100),
            is_poc=bool(s[i] == poc_vol),
            zone_volume=float(profile.volume[lo:hi + 1].sum()),
            buy_pct=(float(profile.buy[lo:hi + 1].sum() / profile.volume[lo:hi + 1].sum() * 100)
                     if profile.buy is not None and profile.volume[lo:hi + 1].sum() > 0 else None),
        ))
    nodes.sort(key=lambda nd: nd.price)
    return nodes


def count_touches(nodes: list[HVN], high: pd.Series, low: pd.Series) -> list[HVN]:
    """Fill in `touches`: how many of the given bars traded into each node's zone
    (pass the bars *after* the profile window to count retests)."""
    hv, lv = high.to_numpy(float), low.to_numpy(float)
    for nd in nodes:
        nd.touches = int(np.sum((lv <= nd.zone_high) & (hv >= nd.zone_low)))
    return nodes


def hvn_profile(
    df: pd.DataFrame,
    lookbacks: tuple[int, ...] = (50, 100, 200),
    bins: int = 60,
    smoothing: float = 1.5,
    threshold: float = 0.70,
    zone_ratio: float = 0.80,
    merge_tolerance_pct: float = 0.75,
    max_nodes: int = 8,
) -> list[HVN]:
    """Multi-period HVN levels for the latest bar of `df` (needs high/low/volume).

    A profile is built for each lookback window ending at the last bar; nodes from
    different windows within `merge_tolerance_pct` of each other merge into one
    level whose `lookbacks` lists every window that found it — the more windows,
    the more significant the level. Strength of a merged node is the max of its
    members. Touches count bars inside the longest window that revisited the zone.
    """
    merged: list[HVN] = []
    for lb in sorted(set(lookbacks)):
        window = df.tail(lb)
        if len(window) < 10:
            continue
        prof = volume_profile(window["high"], window["low"], window["volume"], bins, smoothing)
        for nd in find_hvns(prof, threshold, zone_ratio):
            nd.lookbacks = [lb]
            match = next(
                (m for m in merged if abs(m.price - nd.price) / m.price * 100 <= merge_tolerance_pct), None
            )
            if match is None:
                merged.append(nd)
                continue
            match.lookbacks.append(lb)
            match.zone_low = min(match.zone_low, nd.zone_low)
            match.zone_high = max(match.zone_high, nd.zone_high)
            match.is_poc = match.is_poc or nd.is_poc
            if nd.strength > match.strength:
                match.price, match.volume, match.strength = nd.price, nd.volume, nd.strength

    longest = df.tail(max(lookbacks))
    count_touches(merged, longest["high"], longest["low"])
    merged.sort(key=lambda nd: (len(nd.lookbacks), nd.strength), reverse=True)
    return sorted(merged[:max_nodes], key=lambda nd: nd.price)


def hvn_touch(nodes: list[HVN], bar_high: float, bar_low: float) -> list[HVN]:
    """Nodes the given bar trades into — the "HVN touch" alert condition."""
    return [nd for nd in nodes if nd.overlaps(bar_low, bar_high)]


# --------------------------------------------------------------------------- #
# Absorption
# --------------------------------------------------------------------------- #

def absorption(
    df: pd.DataFrame,
    delta: pd.Series | None = None,
    rvol_window: int = 20,
    atr_window: int = 14,
    min_rvol: float = 1.5,
    heavy_rvol: float = 2.5,
    max_body_atr: float = 0.5,
    min_delta_ratio: float = 0.10,
) -> pd.DataFrame:
    """Per-bar absorption signals.

    A bar is absorption when ALL hold:
      * effort: relative volume >= `min_rvol`
      * little result: net move |close - open| <= `max_body_atr` x ATR. The bar's
        range may be wide — a long rejection wick on heavy volume is absorption
        too — what matters is that all that volume produced little net progress.
      * a direction can be read:
          with delta  — |delta| / volume >= `min_delta_ratio` and price closed
                        *against* the aggressor (sell delta, close in upper half
                        -> bullish; buy delta, close in lower half -> bearish)
          without     — close location in the upper/lower 40% of the bar, i.e.
                        the wick shows which side got pushed back

    Columns returned:
      rvol, body_atr (net move in ATRs), range_atr, clv (close location, 0=low 1=high),
      effort_result (rvol / body_atr: higher = more volume per unit of net movement),
      absorption (bool), direction (+1 bullish, -1 bearish, 0 none), heavy (bool).
    """
    o, h, l, c, v = (df[k].astype(float) for k in ("open", "high", "low", "close", "volume"))
    rng = (h - l)
    rvol = relative_volume(v, rvol_window)
    a = atr(h, l, c, atr_window)
    range_atr = rng / a.replace(0, np.nan)
    body_atr = (c - o).abs() / a.replace(0, np.nan)
    clv = ((c - l) / rng.replace(0, np.nan)).fillna(0.5)
    effort_result = rvol / body_atr.clip(lower=0.1)

    effort = rvol >= min_rvol
    small_result = body_atr <= max_body_atr

    if delta is not None:
        d = delta.reindex(df.index).astype(float)
        delta_ratio = (d / v.replace(0, np.nan)).fillna(0.0)
        bull = (delta_ratio <= -min_delta_ratio) & (clv >= 0.5)
        bear = (delta_ratio >= min_delta_ratio) & (clv <= 0.5)
    else:
        bull = clv >= 0.6
        bear = clv <= 0.4

    base = effort & small_result
    direction = pd.Series(0, index=df.index, dtype=int)
    direction[base & bull] = 1
    direction[base & bear] = -1
    is_abs = direction != 0

    return pd.DataFrame({
        "rvol": rvol,
        "body_atr": body_atr,
        "range_atr": range_atr,
        "clv": clv,
        "effort_result": effort_result,
        "absorption": is_abs,
        "direction": direction,
        "heavy": is_abs & (rvol >= heavy_rvol),
    }, index=df.index)


def absorption_at_hvn(
    df: pd.DataFrame,
    nodes: list[HVN] | None = None,
    delta: pd.Series | None = None,
    **absorption_kwargs,
) -> pd.DataFrame:
    """`absorption()` plus an `at_hvn` column (bar traded into an HVN zone) and
    `hvn_price` (the node it hit). Nodes default to `hvn_profile(df)`.

    Note: with the default, nodes are computed from the whole of `df`, so for a
    backtest compute them per bar from history only to avoid lookahead.
    """
    out = absorption(df, delta=delta, **absorption_kwargs)
    nodes = hvn_profile(df) if nodes is None else nodes
    hit_price = pd.Series(np.nan, index=df.index)
    for nd in sorted(nodes, key=lambda x: x.strength):  # strongest node wins on overlap
        inside = (df["low"] <= nd.zone_high) & (df["high"] >= nd.zone_low)
        hit_price[inside] = nd.price
    out["at_hvn"] = hit_price.notna()
    out["hvn_price"] = hit_price
    return out


def level_absorption(
    df: pd.DataFrame,
    nodes: list[HVN],
    delta: pd.Series | None = None,
    rvol_window: int = 20,
    min_rvol: float = 2.0,
    heavy_rvol: float = 3.0,
    min_wick: float = 0.5,
    min_delta_ratio: float = 0.10,
) -> pd.DataFrame:
    """Absorption AT an HVN: price pushes into a node on heavy volume and is thrown
    back out of it within the same bar.

    bearish (-1): opened below the node, traded up into it (high >= zone_low), closed
        back below it, with an upper wick >= `min_wick` of the range — the buyers
        who drove price into the node were absorbed by passive sellers there.
    bullish (+1): the mirror image — price drops into a node from above and is
        rejected back up out of it, with a lower wick >= `min_wick` of the range.

    With `delta`, the push must also be aggressive: delta/volume >= `min_delta_ratio`
    toward the node (buying into it for bearish, selling into it for bullish).

    `nodes` must come from data BEFORE the bars being tested (no lookahead).
    Columns: direction, heavy, level (node price), absorbed_volume (aggressor
    volume: buy side for bearish, sell side for bullish; whole bar without delta), rvol.
    """
    o, h, low_, c, v = (df[k].astype(float) for k in ("open", "high", "low", "close", "volume"))
    rvol = relative_volume(v, rvol_window)
    rng = (h - low_).replace(0, np.nan)
    upper = ((h - np.maximum(o, c)) / rng).fillna(0.0)
    lower = ((np.minimum(o, c) - low_) / rng).fillna(0.0)
    if delta is not None:
        d = delta.reindex(df.index).astype(float).fillna(0.0)
        ratio = d / v.replace(0, np.nan)
        buy_push, sell_push = ratio >= min_delta_ratio, ratio <= -min_delta_ratio
        buy_vol, sell_vol = (v + d) / 2, (v - d) / 2
    else:
        buy_push = sell_push = pd.Series(True, index=df.index)
        buy_vol = sell_vol = v

    direction = pd.Series(0, index=df.index, dtype=int)
    level = pd.Series(np.nan, index=df.index)
    heavy_enough = rvol >= min_rvol
    for nd in sorted(nodes, key=lambda x: x.strength):  # strongest node wins
        bear = (o < nd.zone_low) & (h >= nd.zone_low) & (c < nd.zone_low) & (upper >= min_wick) & buy_push
        bull = (o > nd.zone_high) & (low_ <= nd.zone_high) & (c > nd.zone_high) & (lower >= min_wick) & sell_push
        bear, bull = bear & heavy_enough, bull & heavy_enough
        direction[bear] = -1
        direction[bull] = 1
        level[bear | bull] = nd.price
    absorbed = pd.Series(np.where(direction == -1, buy_vol, np.where(direction == 1, sell_vol, 0.0)), index=df.index)
    return pd.DataFrame({
        "direction": direction,
        "heavy": (direction != 0) & (rvol >= heavy_rvol),
        "level": level,
        "absorbed_volume": absorbed,
        "rvol": rvol,
    }, index=df.index)
