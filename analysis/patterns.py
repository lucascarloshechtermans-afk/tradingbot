"""Bullish chart-pattern library: every pattern returns the same shape --
a TRIGGER (a close above it = breakout), an INVALIDATION level (stop
reference), a measured-move TARGET and the lines to draw it.

All detectors look only at the frame they are given. `detect_patterns(df)`
builds each pattern from every bar EXCEPT the last one and then judges the
last close against the trigger, so the same call answers both "is it
breaking out today?" (walk-forward safe for backtests) and "how far is it
from triggering?" (the live 'ready to boom' list).

Patterns: falling wedge / descending channel / descending triangle (via
analysis.chart_read), ascending triangle, double bottom, inverse head &
shoulders, cup & handle, bull flag, flat base / range, VCP.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from indicators.trend import confirmed_swing_highs, confirmed_swing_lows, ema
from indicators.volatility import atr as atr_fn


@dataclass
class PatternHit:
    name: str
    trigger: float
    invalidation: float
    target: float
    start: pd.Timestamp
    bars: int
    close: float
    broke_out_today: bool
    lines: list[tuple[pd.Timestamp, float, pd.Timestamp, float]] = field(default_factory=list)

    @property
    def distance_pct(self) -> float:
        """How far below the trigger the last close is (negative = above)."""
        return (self.trigger - self.close) / self.close * 100


def _swings(df: pd.DataFrame, order: int = 3) -> tuple[list[int], list[int]]:
    hi = [i for i, m in enumerate(confirmed_swing_highs(df["high"], order).values) if m]
    lo = [i for i, m in enumerate(confirmed_swing_lows(df["low"], order).values) if m]
    return hi, lo


# --------------------------------------------------------------------------- detectors
# each takes `base` (all bars except the one being judged) and returns a hit
# dict {name, trigger, invalidation, target, start_i, lines} or None


def _flat_base(base: pd.DataFrame, atr_now: float, sh: list[int], sl: list[int]):
    n = len(base)
    h, lo = base["high"].to_numpy(), base["low"].to_numpy()
    best = None
    for length in (15, 25, 40, 60):
        if n < length + 30:
            continue
        seg_h, seg_l = h[n - length:], lo[n - length:]
        top, bot = seg_h.max(), seg_l.min()
        if (top - bot) / top > min(0.15, 7 * atr_now / top):
            continue
        tops = [i for i in sh if i >= n - length and h[i] >= top * 0.985]
        if len(tops) < 2:
            continue
        best = {"name": "flat base", "trigger": top, "invalidation": bot, "target": top + (top - bot),
                "start_i": n - length,
                "lines": [(n - length, top, n - 1, top), (n - length, bot, n - 1, bot)]}
    return best


def _ascending_triangle(base: pd.DataFrame, atr_now: float, sh: list[int], sl: list[int]):
    n = len(base)
    h, lo = base["high"].to_numpy(), base["low"].to_numpy()
    for length in (30, 60, 100):
        if n < length + 10:
            continue
        highs = [i for i in sh if i >= n - length]
        lows = [i for i in sl if i >= n - length]
        if len(highs) < 2 or len(lows) < 2:
            continue
        top = max(h[i] for i in highs)
        flat = [i for i in highs if h[i] >= top * 0.985]
        if len(flat) < 2 or flat[-1] - flat[0] < 10:
            continue
        lx = np.array(lows[-4:], dtype=float)
        ly = np.array([lo[i] for i in lows[-4:]])
        slope = np.polyfit(lx, ly, 1)[0]
        if slope <= 0 or ly[-1] < ly[0] * 1.03 or ly[-1] > top * 0.97:
            continue
        height = top - ly[0]
        return {"name": "ascending triangle", "trigger": top, "invalidation": ly[-1], "target": top + height,
                "start_i": min(flat[0], lows[-len(ly)]),
                "lines": [(flat[0], top, n - 1, top), (int(lx[0]), ly[0], n - 1, ly[0] + slope * (n - 1 - lx[0]))]}
    return None


def _double_bottom(base: pd.DataFrame, atr_now: float, sh: list[int], sl: list[int]):
    n = len(base)
    h, lo = base["high"].to_numpy(), base["low"].to_numpy()
    recent = [i for i in sl if i >= n - 40]
    for b2 in reversed(recent):
        for b1 in reversed([i for i in sl if 10 <= b2 - i <= 90]):
            l1, l2 = lo[b1], lo[b2]
            if abs(l2 - l1) / l1 > 0.035:
                continue
            neck_i = b1 + int(np.argmax(h[b1:b2 + 1]))
            neck = h[neck_i]
            if neck < max(l1, l2) * 1.08:
                continue
            prior = h[max(0, b1 - 60):b1]
            if len(prior) == 0 or prior.max() < l1 * 1.15:
                continue
            if h[b2 + 1:].max(initial=0) > neck * 1.001:
                continue  # already broke out earlier -- not this setup any more
            return {"name": "double bottom", "trigger": neck, "invalidation": min(l1, l2),
                    "target": neck + (neck - min(l1, l2)), "start_i": b1,
                    "lines": [(b1, neck, n - 1, neck), (b1, l1, b2, l2)]}
    return None


def _inverse_hs(base: pd.DataFrame, atr_now: float, sh: list[int], sl: list[int]):
    n = len(base)
    h, lo = base["high"].to_numpy(), base["low"].to_numpy()
    lows = [i for i in sl if i >= n - 130]
    for k in range(len(lows) - 1, 1, -1):
        rs, hd, ls = lows[k], lows[k - 1], lows[k - 2]
        if rs < n - 35 or hd - ls < 5 or rs - hd < 5:
            continue
        if not (lo[hd] < min(lo[ls], lo[rs]) * 0.97):
            continue
        if abs(lo[ls] - lo[rs]) / max(lo[ls], lo[rs]) > 0.07:
            continue
        p1 = ls + int(np.argmax(h[ls:hd + 1]))
        p2 = hd + int(np.argmax(h[hd:rs + 1]))
        slope = (h[p2] - h[p1]) / max(p2 - p1, 1)
        neck_now = h[p2] + slope * (n - p2)
        if h[rs:].max(initial=0) > neck_now * 1.001 + max(0.0, slope) * 0:
            # highs after the right shoulder already cleared the neckline
            if (base["close"].to_numpy()[rs:] > h[p2] + slope * (np.arange(rs, n) - p2)).any():
                continue
        depth = (h[p1] + slope * (hd - p1)) - lo[hd]
        return {"name": "inverse head & shoulders", "trigger": neck_now, "invalidation": lo[rs],
                "target": neck_now + depth, "start_i": ls,
                "lines": [(p1, h[p1], n - 1, neck_now)]}
    return None


def _cup_handle(base: pd.DataFrame, atr_now: float, sh: list[int], sl: list[int]):
    n = len(base)
    if n < 80:
        return None
    h, lo = base["high"].to_numpy(), base["low"].to_numpy()
    for left in reversed([i for i in sh if n - 220 <= i <= n - 40]):
        lip = h[left]
        if h[left + 1:].max(initial=0) > lip * 1.02:
            continue
        bottom_i = left + int(np.argmin(lo[left:n]))
        depth = (lip - lo[bottom_i]) / lip
        if not (0.12 <= depth <= 0.50) or bottom_i - left < 10:
            continue
        right_zone = h[bottom_i:]
        rp = bottom_i + int(np.argmax(right_zone))
        if h[rp] < lip * 0.93 or n - 1 - rp < 3 or n - 1 - rp > 30 or rp - left < 30:
            continue
        handle_low = lo[rp:].min()
        if (h[rp] - handle_low) / h[rp] > 0.15 or handle_low < lo[bottom_i] + (lip - lo[bottom_i]) / 2:
            continue
        trigger = h[rp]
        return {"name": "cup & handle", "trigger": trigger, "invalidation": handle_low,
                "target": trigger + (lip - lo[bottom_i]), "start_i": left,
                "lines": [(left, lip, rp, h[rp]), (rp, trigger, n - 1, trigger)]}
    return None


def _bull_flag(base: pd.DataFrame, atr_now: float, sh: list[int], sl: list[int]):
    n = len(base)
    if n < 40:
        return None
    h, lo, c = base["high"].to_numpy(), base["low"].to_numpy(), base["close"].to_numpy()
    for flag_len in range(3, 16):
        peak = n - 1 - flag_len
        if h[peak] < h[peak - 15:peak + 1].max() or h[peak + 1:].max(initial=0) > h[peak]:
            continue
        pole_start = peak - 15 + int(np.argmin(lo[peak - 15:peak + 1]))
        pole = h[peak] - lo[pole_start]
        if pole / lo[pole_start] < 0.15 or pole < 4 * atr_now:
            continue
        flag_low = lo[peak + 1:].min()
        if h[peak] - flag_low > 0.5 * pole or h[peak] - flag_low < 0.8 * atr_now:
            continue
        # the flag's own highs drift down: trigger = the flag's upper line now
        fh = h[peak:]
        slope = min(0.0, np.polyfit(np.arange(len(fh)), fh, 1)[0])
        trigger = max(h[peak] + slope * flag_len, c[-1])
        trigger = max(trigger, fh[1:].max(initial=trigger))
        return {"name": "bull flag", "trigger": float(trigger), "invalidation": flag_low,
                "target": float(trigger + pole), "start_i": pole_start,
                "lines": [(pole_start, lo[pole_start], peak, h[peak]), (peak, h[peak], n - 1, h[peak] + slope * flag_len)]}
    return None


def _vcp(base: pd.DataFrame, atr_now: float, sh: list[int], sl: list[int]):
    n = len(base)
    if n < 210:
        return None
    h, lo, c = base["high"].to_numpy(), base["low"].to_numpy(), base["close"].to_numpy()
    e50, e200 = ema(base["close"], 50).to_numpy(), ema(base["close"], 200).to_numpy()
    if not (c[-1] > e50[-1] > e200[-1]):
        return None
    highs = [i for i in sh if i >= n - 90]
    depths, pivots = [], []
    for a, b in zip(highs, highs[1:] + [n]):
        seg = lo[a:b]
        if len(seg) < 2:
            continue
        depths.append((h[a] - seg.min()) / h[a])
        pivots.append(a)
    if len(depths) < 3:
        return None
    d3 = depths[-3:]
    if not (d3[0] > d3[1] > d3[2] and d3[1] <= 0.8 * d3[0] and d3[2] <= 0.8 * d3[1] and d3[2] <= 0.10):
        return None
    pivot = pivots[-1]
    if h[pivot + 1:].max(initial=0) > h[pivot]:
        return None
    return {"name": "VCP", "trigger": h[pivot], "invalidation": lo[pivot:].min(),
            "target": h[pivot] * (1 + d3[0]), "start_i": pivots[-3],
            "lines": [(pivots[-3], h[pivots[-3]], pivot, h[pivot]), (pivot, h[pivot], n - 1, h[pivot])]}


def _descending(base: pd.DataFrame, atr_now: float, sh: list[int], sl: list[int]):
    from analysis.chart_read import find_descending_pattern

    pat = find_descending_pattern(base)
    if pat is None:
        return None
    n = len(base)
    up, low_line = pat.upper, pat.lower
    trigger = up.value_at(n)  # the line's value on the bar being judged
    recent_low = base["low"].to_numpy()[-15:].min()
    height = up.value_at(up.start_index) - low_line.value_at(up.start_index)
    # a descending line already far below price means the breakout is old
    if base["close"].to_numpy()[-1] > up.value_at(n - 1) * 1.001:
        return None
    return {"name": pat.name, "trigger": float(trigger), "invalidation": float(recent_low),
            "target": float(trigger + height), "start_i": up.start_index,
            "lines": [(up.start_index, up.start_price, n, trigger),
                      (low_line.start_index, low_line.start_price, n, low_line.value_at(n))]}


def _fit_line(idx: list[int], vals: np.ndarray) -> tuple[float, float]:
    slope, icpt = np.polyfit(np.array(idx, dtype=float), vals, 1)
    return float(slope), float(icpt)


def _channel_up(base: pd.DataFrame, atr_now: float, sh: list[int], sl: list[int]):
    """Rising parallel channel. Two tradeable setups come out of one channel:
    a bounce off the lower line (buy the dip inside the trend) and, for a
    steep 'strong' channel, a breakout above the upper line (acceleration)."""
    n = len(base)
    h, lo, c = base["high"].to_numpy(), base["low"].to_numpy(), base["close"].to_numpy()
    out = []
    for length in (40, 70, 110):
        if n < length + 10:
            continue
        highs = [i for i in sh if i >= n - length]
        lows = [i for i in sl if i >= n - length]
        if len(highs) < 3 or len(lows) < 3:
            continue
        su, iu = _fit_line(highs, h[highs])
        sd, id_ = _fit_line(lows, lo[lows])
        if su <= 0 or sd <= 0 or not (0.6 <= su / sd <= 1.6):
            continue
        up_now, dn_now = su * n + iu, sd * n + id_
        width = up_now - dn_now
        if width <= 1.5 * atr_now or width > 10 * atr_now:
            continue
        # most of the time price stayed inside the channel
        xs = np.arange(n - length, n)
        inside = ((c[xs] <= su * xs + iu + 0.5 * atr_now) & (c[xs] >= sd * xs + id_ - 0.5 * atr_now)).mean()
        if inside < 0.85:
            continue
        touches_up = sum(abs(h[i] - (su * i + iu)) <= 0.5 * atr_now for i in highs)
        touches_dn = sum(abs(lo[i] - (sd * i + id_)) <= 0.5 * atr_now for i in lows)
        if touches_up < 2 or touches_dn < 2:
            continue
        per_bar_pct = sd / c[-1] * 100
        strong = per_bar_pct >= 0.25   # >= ~0.25%/day (~ +60%/quarter) is a steep channel
        start = n - length
        lines = [(start, su * start + iu, n, up_now), (start, sd * start + id_, n, dn_now)]
        # bounce: yesterday's low tagged the lower line; trigger = its high
        if lo[-1] <= dn_now - sd + 0.5 * atr_now and c[-1] >= dn_now - sd - 0.25 * atr_now:
            out.append({"name": "channel up bounce", "trigger": h[-1], "invalidation": dn_now - 0.75 * atr_now,
                        "target": up_now, "start_i": start, "lines": lines})
        if strong:
            out.append({"name": "channel up strong breakout", "trigger": up_now, "invalidation": dn_now,
                        "target": up_now + width, "start_i": start, "lines": lines})
        break
    return out or None


def _symmetric_triangle(base: pd.DataFrame, atr_now: float, sh: list[int], sl: list[int]):
    n = len(base)
    h, lo = base["high"].to_numpy(), base["low"].to_numpy()
    for length in (30, 60, 100):
        if n < length + 10:
            continue
        highs = [i for i in sh if i >= n - length]
        lows = [i for i in sl if i >= n - length]
        if len(highs) < 2 or len(lows) < 2:
            continue
        su, iu = _fit_line(highs[-3:], h[highs[-3:]])
        sd, id_ = _fit_line(lows[-3:], lo[lows[-3:]])
        if not (su < 0 < sd):
            continue
        up_now, dn_now = su * n + iu, sd * n + id_
        if up_now - dn_now < 0.3 * atr_now:
            continue
        start = min(highs[-3:][0], lows[-3:][0])
        height = (su * start + iu) - (sd * start + id_)
        if height < 3 * atr_now:
            continue
        return {"name": "symmetric triangle", "trigger": up_now, "invalidation": dn_now,
                "target": up_now + height, "start_i": start,
                "lines": [(start, su * start + iu, n, up_now), (start, sd * start + id_, n, dn_now)]}
    return None


def _horizontal_range(base: pd.DataFrame, atr_now: float, sh: list[int], sl: list[int]):
    """A longer sideways range (horizontal channel): >= 2 tops and >= 2
    bottoms at similar prices over 40-150 bars; breakout above the top."""
    n = len(base)
    h, lo = base["high"].to_numpy(), base["low"].to_numpy()
    for length in (150, 100, 60, 40):
        if n < length + 10:
            continue
        top, bot = h[n - length:].max(), lo[n - length:].min()
        if (top - bot) / top > 0.35 or top - bot < 4 * atr_now:
            continue
        tops = [i for i in sh if i >= n - length and h[i] >= top - 0.6 * atr_now]
        bots = [i for i in sl if i >= n - length and lo[i] <= bot + 0.6 * atr_now]
        if len(tops) < 2 or len(bots) < 2:
            continue
        return {"name": "horizontal range", "trigger": top, "invalidation": max(bot, top - 3 * atr_now),
                "target": top + (top - bot), "start_i": n - length,
                "lines": [(n - length, top, n - 1, top), (n - length, bot, n - 1, bot)]}
    return None


DETECTORS = (_descending, _ascending_triangle, _double_bottom, _inverse_hs, _cup_handle, _bull_flag, _flat_base, _vcp,
             _channel_up, _symmetric_triangle, _horizontal_range)


def detect_patterns(df: pd.DataFrame, only: tuple[str, ...] | None = None) -> list[PatternHit]:
    """Patterns formed on every bar but the last; the last close is judged
    against each trigger (broke_out_today = it closed above it today)."""
    df = df.dropna(subset=["open", "high", "low", "close"])
    if len(df) < 60:
        return []
    base = df.iloc[:-1]
    atr_now = float(atr_fn(base["high"], base["low"], base["close"], 14).iloc[-1])
    if not np.isfinite(atr_now) or atr_now <= 0:
        return []
    sh, sl = _swings(base, 3)
    last_close = float(df["close"].iloc[-1])
    prev_close = float(base["close"].iloc[-1])
    idx = df.index
    hits = []
    for det in DETECTORS:
        try:
            res = det(base, atr_now, sh, sl)
        except (ValueError, IndexError, np.linalg.LinAlgError):
            res = None
        for r in (res if isinstance(res, list) else [res]):
            if r is None or not np.isfinite(r["trigger"]) or r["invalidation"] >= r["trigger"]:
                continue
            if only is not None and r["name"] not in only:
                continue
            hits.append(_to_hit(r, idx, len(base), last_close, prev_close))
    return hits


def _to_hit(r: dict, idx: pd.Index, n_base: int, last_close: float, prev_close: float) -> PatternHit:
    lines = [(idx[min(int(a), len(idx) - 1)], float(pa), idx[min(int(b), len(idx) - 1)], float(pb))
             for a, pa, b, pb in r["lines"]]
    return PatternHit(
        name=r["name"], trigger=float(r["trigger"]), invalidation=float(r["invalidation"]),
        target=float(r["target"]), start=idx[int(r["start_i"])], bars=n_base - int(r["start_i"]),
        close=last_close, broke_out_today=last_close > r["trigger"] and prev_close <= r["trigger"], lines=lines,
    )
