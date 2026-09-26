"""Discretionary-style chart read: what a swing trader writes on a chart.

The scanner's strategies/score use EMAs, levels and a weekly context
internally, but never SAY it the way a trader reads a chart. This module does,
for one ticker at a time, in the order a trader looks:

1. Daily EMAs 9/21/50/200 ("DTF") and a fresh reclaim/loss of the 200 EMA.
2. The 4-hour 200 EMA ("4H 200EMA") -- a second timeframe with its own level,
   built from 1h bars resampled to the 09:30 / 13:30 New York 4h sessions
   (how TradingView draws US-stock 4h candles).
3. Support/resistance ZONES (a price band, not a single line) from clustered
   swing highs AND lows -- an old top that later acted as a floor belongs to
   the same zone -- and whether price just broke out above one.
4. Trendline patterns since the last major peak: falling wedge, descending
   channel, descending triangle -- and a breakout above the upper line.
5. A conditional plan in chart language: "if it can hold X and break Y @Z",
   the next resistance zone above, and what invalidates it.

Everything is computed from data through the last bar only (no look-ahead),
so the same read can be replayed on history for backtesting.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from indicators.trend import confirmed_swing_highs, confirmed_swing_lows, ema
from indicators.volatility import atr as atr_fn

DAILY_EMAS = (9, 21, 50, 200)
FRESH_BARS = 10          # a cross/breakout within this many bars counts as "just happened"


@dataclass
class Zone:
    low: float
    high: float
    touches: int
    last_touch: pd.Timestamp

    @property
    def mid(self) -> float:
        return (self.low + self.high) / 2

    def label(self) -> str:
        return f"{self.low:.2f}-{self.high:.2f}"


@dataclass
class Trendline:
    start: pd.Timestamp
    start_price: float
    slope_per_bar: float  # price change per daily bar
    start_index: int

    def value_at(self, index: int) -> float:
        return self.start_price + self.slope_per_bar * (index - self.start_index)


@dataclass
class Pattern:
    name: str               # "falling wedge" | "descending channel" | "descending triangle"
    upper: Trendline
    lower: Trendline
    broke_out: bool
    breakout_bars_ago: int | None
    upper_now: float


@dataclass
class ChartRead:
    ticker: str
    last_date: pd.Timestamp
    close: float
    daily_emas: dict[int, float]
    ema200_4h: float | None
    zones: list[Zone]
    support_zone: Zone | None
    resistance_zone: Zone | None
    pattern: Pattern | None
    headlines: list[str] = field(default_factory=list)   # the chart annotations
    plan: str | None = None
    invalidation: str | None = None
    bias: str = "neutral"   # bullish | neutral | bearish
    bullish_points: int = 0


# --------------------------------------------------------------------------- 4h

def resample_to_4h(hourly: pd.DataFrame) -> pd.DataFrame:
    """1h OHLCV (any tz) -> US-session 4h bars: 09:30-13:30 and 13:30-16:00 NY."""
    if hourly.empty:
        return hourly
    ny = hourly.copy()
    ny.index = ny.index.tz_convert("America/New_York") if ny.index.tz is not None else ny.index.tz_localize("America/New_York")
    ny = ny.between_time("09:30", "15:59")
    minutes = ny.index.hour * 60 + ny.index.minute
    half = np.where(minutes < 13 * 60 + 30, 0, 1)
    key = pd.Index(ny.index.normalize() + pd.to_timedelta(np.where(half == 0, 9 * 60 + 30, 13 * 60 + 30), unit="m"))
    grouped = ny.groupby(key)
    out = pd.DataFrame({
        "open": grouped["open"].first(), "high": grouped["high"].max(), "low": grouped["low"].min(),
        "close": grouped["close"].last(), "volume": grouped["volume"].sum(),
    })
    return out.dropna(subset=["close"])


# --------------------------------------------------------------------------- zones

def find_zones(daily: pd.DataFrame, lookback: int = 500, order: int = 5, max_zones: int = 10) -> list[Zone]:
    """Support/resistance zones from swing highs and lows together (role
    reversal: an old top that later held as a floor is one zone). Points
    within ~0.6 ATR of each other merge; the zone spans the merged points,
    padded to at least 0.5 ATR wide. Needs >= 2 touches."""
    d = daily.iloc[-lookback:]
    atr_now = float(atr_fn(d["high"], d["low"], d["close"], 14).iloc[-1])
    if not np.isfinite(atr_now) or atr_now <= 0:
        return []
    hi_mask = confirmed_swing_highs(d["high"], order)
    lo_mask = confirmed_swing_lows(d["low"], order)
    pts = sorted(
        [(float(p), ts) for p, ts in zip(d["high"][hi_mask].values, d["high"][hi_mask].index)]
        + [(float(p), ts) for p, ts in zip(d["low"][lo_mask].values, d["low"][lo_mask].index)]
    )
    # tolerance scales with price (a $60 swing in 2024 and a $600 one today
    # need proportionally the same band), and a zone can't grow wider than
    # ~1.5 ATR-equivalents by chaining neighbours together
    atr_pct = atr_now / float(d["close"].iloc[-1])
    clusters: list[list[tuple[float, pd.Timestamp]]] = []
    for p, ts in pts:
        if clusters and p - clusters[-1][-1][0] <= 0.6 * atr_pct * p and p - clusters[-1][0][0] <= 1.5 * atr_pct * p:
            clusters[-1].append((p, ts))
        else:
            clusters.append([(p, ts)])
    zones = []
    for c in clusters:
        if len(c) < 2:
            continue
        lo, hi = min(p for p, _ in c), max(p for p, _ in c)
        mid = (hi + lo) / 2
        if hi - lo < 0.5 * atr_pct * mid:
            lo, hi = mid - 0.25 * atr_pct * mid, mid + 0.25 * atr_pct * mid
        zones.append(Zone(low=lo, high=hi, touches=len(c), last_touch=max(ts for _, ts in c)))
    # keep the zones that matter for a swing trade: the ones nearest price
    last = float(d["close"].iloc[-1])
    zones.sort(key=lambda z: abs(z.mid - last))
    return sorted(zones[:max_zones], key=lambda z: z.low)


# --------------------------------------------------------------------------- trendlines

def _upper_line(high: pd.Series, close: pd.Series, anchor: int, swing_idx: list[int], atr_now: float) -> Trendline | None:
    """The resistance line a trader would draw: through two swing highs (the
    first at/after the major peak), falling, with no CLOSE above it between its
    first touch and the latest breakout, touching as many swing highs as
    possible (within 0.5 ATR). Ties go to the later first touch."""
    n = len(high)
    cands = sorted(set([anchor] + [i for i in swing_idx if i >= anchor]))
    best, best_key = None, None
    for a_pos, i in enumerate(cands):
        for j in cands[a_pos + 1:]:
            if j - i < 10:
                continue
            slope = (high.iloc[j] - high.iloc[i]) / (j - i)
            if slope >= 0:
                continue
            line = high.iloc[i] + slope * (np.arange(n) - i)
            above = close.values[i:] > line[i:] * 1.002
            last_below = n - 1
            while last_below > i and above[last_below - i]:
                last_below -= 1
            if above[: last_below - i + 1].any():
                continue
            touches = sum(1 for k in swing_idx if k >= i and abs(high.iloc[k] - line[k]) <= 0.5 * atr_now)
            key = (touches, i)
            if best_key is None or key > best_key:
                best_key, best = key, Trendline(start=high.index[i], start_price=float(high.iloc[i]),
                                                slope_per_bar=float(slope), start_index=i)
    if best is None or best_key[0] < 3:
        return None
    return best


def _lower_line(low: pd.Series, anchor: int, swing_idx: list[int], end: int) -> Trendline | None:
    """Support line under the swing lows after the peak: least-squares slope,
    shifted down so no swing low closes below it (all lows on/above)."""
    pts = [j for j in swing_idx if anchor < j <= end]
    if len(pts) < 2:
        return None
    x = np.array(pts, dtype=float)
    y = np.array([low.iloc[j] for j in pts], dtype=float)
    slope, intercept = np.polyfit(x, y, 1)
    shift = min(y - (slope * x + intercept))
    first = pts[0]
    return Trendline(start=low.index[first], start_price=float(slope * first + intercept + shift),
                     slope_per_bar=float(slope), start_index=first)


def find_descending_pattern(daily: pd.DataFrame, window: int = 160, order: int = 4) -> Pattern | None:
    d = daily.iloc[-window:]
    n = len(d)
    if n < 60:
        return None
    high, low, close = d["high"], d["low"], d["close"]
    # anchor: the highest high of the window, not in the last 20 bars
    anchor = int(np.argmax(high.iloc[: n - 20].values))
    hi_idx = [i for i, m in enumerate(confirmed_swing_highs(high, order).values) if m]
    lo_idx = [i for i, m in enumerate(confirmed_swing_lows(low, order).values) if m]
    atr_now = float(atr_fn(high, low, close, 14).iloc[-1])
    upper = _upper_line(high, close, anchor, hi_idx, atr_now)
    if upper is None:
        return None
    # breakout: the most recent close above the upper line, after >= 10 bars below it
    above = np.array([close.iloc[i] > upper.value_at(i) for i in range(n)])
    breakout_ago = None
    for i in range(n - 1, anchor, -1):
        if above[i] and not above[max(anchor + 1, i - 10):i].any():
            breakout_ago = n - 1 - i
            break
    # the lower line is drawn from lows BEFORE the breakout
    end = n - 1 - breakout_ago if breakout_ago is not None else n - 1
    lower = _lower_line(low, upper.start_index, lo_idx, end)
    if lower is None:
        return None
    u, l_ = upper.slope_per_bar, lower.slope_per_bar
    rel = abs(u) / max(abs(close.iloc[-1]), 1e-9) * 100  # upper slope in % of price per bar
    if l_ >= -0.02 * abs(u) and abs(l_) < 0.25 * abs(u):
        name = "descending triangle"
    elif l_ < 0 and u < l_ * 1.15:
        name = "falling wedge"
    elif l_ < 0 and 0.7 <= u / l_ <= 1.3:
        name = "descending channel"
    elif l_ < 0:
        name = "falling wedge" if u < l_ else "descending channel"
    else:
        return None
    if rel < 0.02:  # practically flat: not a descending pattern
        return None
    if n - 1 - upper.start_index < 25:
        return None
    # a pullback that never came near the 200 EMA, inside a strong uptrend,
    # is a bull flag rather than a reversal wedge
    ema200 = ema(close, 200)
    if pd.notna(ema200.iloc[-1]) and low.iloc[upper.start_index:].min() > ema200.iloc[-1] * 1.10:
        name = "bull flag"
    upper_now = upper.value_at(n - 1)
    fresh = breakout_ago is not None and breakout_ago <= FRESH_BARS and close.iloc[-1] > upper_now
    return Pattern(name=name, upper=_reindex(upper, d, daily), lower=_reindex(lower, d, daily),
                   broke_out=fresh, breakout_bars_ago=breakout_ago, upper_now=float(upper_now))


def _reindex(line: Trendline, window_df: pd.DataFrame, full_df: pd.DataFrame) -> Trendline:
    offset = len(full_df) - len(window_df)
    return Trendline(start=line.start, start_price=line.start_price, slope_per_bar=line.slope_per_bar,
                     start_index=line.start_index + offset)


# --------------------------------------------------------------------------- the read

def _crossed_above(close: pd.Series, level: pd.Series, bars: int = FRESH_BARS) -> int | None:
    above = (close > level).values
    if not above[-1]:
        return None
    for k in range(1, min(bars, len(above) - 1) + 1):
        if not above[-1 - k]:
            return k - 1
    return None


def read_chart(ticker: str, daily: pd.DataFrame, hourly: pd.DataFrame | None = None) -> ChartRead:
    daily = daily.dropna(subset=["open", "high", "low", "close"])
    close = daily["close"]
    c = float(close.iloc[-1])
    emas = {w: ema(close, w) for w in DAILY_EMAS}
    ema_now = {w: float(s.iloc[-1]) for w, s in emas.items() if pd.notna(s.iloc[-1])}

    ema200_4h = None
    if hourly is not None and len(hourly) > 0:
        h4 = resample_to_4h(hourly)
        if len(h4) >= 200:
            ema200_4h = float(ema(h4["close"], 200).iloc[-1])

    zones = find_zones(daily)
    below = [z for z in zones if z.high <= c * 1.005]
    above_z = [z for z in zones if z.low > c]
    support = max(below, key=lambda z: z.high) if below else None
    resistance = min(above_z, key=lambda z: z.low) if above_z else None
    pattern = find_descending_pattern(daily)

    heads: list[str] = []
    pts = 0
    if pattern is not None and pattern.broke_out:
        heads.append(f"BROKE OUT OF {pattern.name.upper()} ({pattern.breakout_bars_ago} bars ago, upper line now {pattern.upper_now:.2f})")
        pts += 1
    elif pattern is not None and c > pattern.upper_now:
        ago = f" {pattern.breakout_bars_ago} bars ago" if pattern.breakout_bars_ago is not None else ""
        heads.append(f"ABOVE {pattern.name.upper()} (broke out{ago}, no longer fresh)")
    elif pattern is not None:
        heads.append(f"INSIDE {pattern.name.upper()} -- breakout needs a close above {pattern.upper_now:.2f}")

    if 200 in ema_now:
        k = _crossed_above(close, emas[200])
        if k is not None:
            heads.append(f"CROSSED DTF 200 EMA ABOVE ({ema_now[200]:.2f}{', today' if k == 0 else f', {k} bars ago'})")
            pts += 1
        elif c > ema_now[200]:
            heads.append(f"ABOVE DTF 200 EMA ({ema_now[200]:.2f})")
            pts += 1
        else:
            heads.append(f"BELOW DTF 200 EMA ({ema_now[200]:.2f}) -- not reclaimed yet")
    stack = [w for w in DAILY_EMAS if w in ema_now]
    if len(stack) == 4:
        if all(ema_now[a] > ema_now[b] for a, b in zip(stack, stack[1:])) and c > ema_now[9]:
            heads.append("DAILY EMAS STACKED BULLISH (9 > 21 > 50 > 200)")
            pts += 1
        elif c > max(ema_now[w] for w in (9, 21, 50)):
            heads.append(f"RECLAIMED 9/21/50 EMA ({ema_now[9]:.2f} / {ema_now[21]:.2f} / {ema_now[50]:.2f})")
            pts += 1

    # zone breakout: closed above a zone's top within the last few bars, after closing inside/below it
    for z in sorted(zones, key=lambda z: -z.high):
        if c > z.high:
            recent = close.iloc[-(FRESH_BARS + 1):-1]
            if (recent <= z.high).any():
                heads.append(f"BROKE OUT OF ZONE {z.label()} ({z.touches} touches) -- now support")
                pts += 1
            break

    if ema200_4h is not None:
        if c > ema200_4h:
            heads.append(f"ABOVE 4H 200 EMA ({ema200_4h:.2f})")
            pts += 1
        else:
            heads.append(f"4H 200 EMA OVERHEAD @{ema200_4h:.2f}")

    # the conditional plan, in chart language. What must HOLD: a freshly
    # reclaimed daily 200 EMA, else a zone just broken out of, else the
    # nearest 21/50/200 EMA below price, else the support zone.
    hold = None
    broken_zone = next((z for z in sorted(zones, key=lambda z: -z.high)
                        if c > z.high and (close.iloc[-(FRESH_BARS + 1):-1] <= z.high).any()), None)
    if 200 in ema_now and c > ema_now[200] and _crossed_above(close, emas[200]) is not None:
        hold = ("THE DTF 200 EMA", ema_now[200])
    elif broken_zone is not None:
        hold = (f"THE BROKEN ZONE {broken_zone.label()}", broken_zone.low)
    else:
        below_emas = [(w, ema_now[w]) for w in (21, 50, 200) if w in ema_now and ema_now[w] < c]
        if below_emas:
            w, v = max(below_emas, key=lambda t: t[1])
            hold = (f"THE DTF {w} EMA", v)
        elif support is not None:
            hold = (f"SUPPORT ZONE {support.label()}", support.low)
    trigger = None
    if ema200_4h is not None and ema200_4h > c:
        trigger = ("4H 200 EMA", ema200_4h)
    elif resistance is not None:
        trigger = (f"RESISTANCE ZONE {resistance.label()}", resistance.high)
    plan = None
    if hold and trigger:
        nxt = next((z for z in zones if z.low > trigger[1]), None)
        plan = (f"IF IT CAN HOLD {hold[0]} ({hold[1]:.2f}) AND BREAK THROUGH {trigger[0]} @{trigger[1]:.2f}"
                + (f" -> NEXT RESISTANCE {nxt.label()}" if nxt else ""))
    elif hold:
        plan = f"HOLD {hold[0]} ({hold[1]:.2f}); no resistance overhead in 2y (blue sky) -- trail under the DTF 9/21 EMA"
    invalidation = None
    if hold:
        invalidation = f"daily close back below {hold[1]:.2f}" + (
            f" / back inside the {pattern.name} (< {pattern.upper_now:.2f})" if pattern is not None and pattern.broke_out else "")

    bias = "bullish" if pts >= 3 else ("bearish" if 200 in ema_now and c < ema_now[200] and pts <= 1 else "neutral")
    return ChartRead(ticker=ticker, last_date=daily.index[-1], close=c, daily_emas=ema_now, ema200_4h=ema200_4h,
                     zones=zones, support_zone=support, resistance_zone=resistance, pattern=pattern,
                     headlines=heads, plan=plan, invalidation=invalidation, bias=bias, bullish_points=pts)


def format_read(r: ChartRead) -> str:
    lines = [f"{r.ticker}  {r.last_date.date()}  close {r.close:.2f}  bias: {r.bias.upper()} ({r.bullish_points} bullish points)"]
    lines += [f"  {h}" for h in r.headlines]
    if r.plan:
        lines.append(f"  PLAN: {r.plan}")
    if r.invalidation:
        lines.append(f"  INVALID: {r.invalidation}")
    e = r.daily_emas
    lines.append("  EMAs D: " + "  ".join(f"{w}={e[w]:.2f}" for w in DAILY_EMAS if w in e)
                 + (f"   4H 200={r.ema200_4h:.2f}" if r.ema200_4h else ""))
    lines.append("  zones: " + ", ".join(f"{z.label()}({z.touches})" for z in r.zones))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """python -m analysis.chart_read SYNA AMD [--html charts.html]"""
    import argparse

    from config.schema import load_config
    from data.cache import DiskCache
    from data.provider import DataUnavailable
    from data.yfinance_provider import YFinanceProvider

    ap = argparse.ArgumentParser(description="Trader-style chart read (EMAs D/4H, zones, wedges, plan)")
    ap.add_argument("tickers", nargs="+")
    ap.add_argument("--html", default=None, help="also write an annotated chart page here")
    args = ap.parse_args(argv)
    cfg = load_config(None)
    provider = YFinanceProvider(cache=DiskCache(cache_dir=cfg.data.cache_dir, ttl_hours=cfg.data.cache_ttl_hours))
    items = []
    for t in args.tickers:
        t = t.upper()
        try:
            daily = provider.get_history(t, "2y")
        except DataUnavailable as exc:
            print(f"{t}: no data ({exc})")
            continue
        try:
            hourly = provider.get_history(t, "730d", "1h")
        except DataUnavailable:
            hourly = None
        read = read_chart(t, daily, hourly)
        print(format_read(read) + "\n")
        items.append((daily, read))
    if args.html and items:
        from ui.chart_svg import render_chart_page

        with open(args.html, "w") as f:
            f.write(render_chart_page(items))
        print(f"wrote {args.html}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
