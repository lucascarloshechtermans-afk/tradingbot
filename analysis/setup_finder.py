"""'Ready to boom' finder: every bullish chart pattern across the universe,
ranked by how close it is to (or how fresh it is past) its breakout and by
the context the pattern backtest found to matter.

Status per pattern:
  BREAKOUT TODAY   -- today's close cleared the trigger
  BROKE OUT Nd AGO -- cleared it 1-3 sessions ago, still above, not stretched (< 1.5 ATR)
  READY            -- still below the trigger but within min(3%, 1 ATR): a buy-stop
                      just above the trigger catches the breakout

Score (0-100) = the pattern's own backtested edge + confluence: above the daily
200 EMA, 21>50>200 stacked, volume surge / dry-up, ATR% >= 3, several
patterns at once, top-20% composite momentum, a clean (efficient) trend, tight
coil, room to the next resistance zone. Weights follow
research/pattern_backtest.py (5y, 190 tickers, 2021-2026) -- see README.

    python -m analysis.setup_finder --top 15 --html boom.html
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from analysis.chart_read import find_zones, read_chart
from analysis.patterns import PatternHit, detect_patterns
from indicators.trend import ema
from indicators.volatility import atr as atr_fn
from relative_strength.relative_strength import compute_universe_momentum_ranks, efficiency_ratio

# mean R per breakout in research/pattern_backtest.py (5y, 190 tickers, 10-day
# hold, 2-4 ATR stop, 2-4 R measured-move target). channel up bounce lost
# money (-0.02R), so it never makes the list.
PATTERN_EDGE = {
    "descending triangle": 0.34, "VCP": 0.15, "channel up strong breakout": 0.15, "descending channel": 0.12,
    "bull flag": 0.12, "cup & handle": 0.11, "ascending triangle": 0.10, "double bottom": 0.10,
    "falling wedge": 0.09, "inverse head & shoulders": 0.07, "flat base": 0.07, "horizontal range": 0.07,
    "symmetric triangle": 0.06, "bull flag (channel)": 0.12,
}
EXCLUDED = {"channel up bounce"}


@dataclass
class Setup:
    ticker: str
    status: str
    patterns: list[PatternHit]
    close: float
    trigger: float
    stop: float
    target: float
    rr: float
    score: float
    reasons: list[str] = field(default_factory=list)
    daily: pd.DataFrame | None = None

    @property
    def names(self) -> str:
        return " + ".join(sorted({p.name for p in self.patterns}))


def _levels(hit: PatternHit, close: float, atr_now: float) -> tuple[float, float, float]:
    entry = max(close, hit.trigger)
    risk = float(np.clip(entry - (hit.invalidation - 0.25 * atr_now), 2 * atr_now, 4 * atr_now))
    stop = entry - risk
    target = entry + float(np.clip((hit.target - entry) / risk, 2.0, 4.0)) * risk
    return stop, target, (target - entry) / risk


def evaluate_ticker(ticker: str, df: pd.DataFrame, momentum_rank: float | None = None) -> Setup | None:
    df = df.dropna(subset=["open", "high", "low", "close"])
    if len(df) < 260:
        return None
    c = df["close"]
    close = float(c.iloc[-1])
    atr_s = atr_fn(df["high"], df["low"], df["close"], 14)
    atr_now = float(atr_s.iloc[-1])
    if not np.isfinite(atr_now) or atr_now <= 0:
        return None
    candidates: list[tuple[str, PatternHit]] = []
    for hit in detect_patterns(df):
        if hit.name in EXCLUDED:
            continue
        if hit.broke_out_today:
            candidates.append(("BREAKOUT TODAY", hit))
        elif 0 < hit.distance_pct <= min(3.0, atr_now / close * 100):
            candidates.append(("READY", hit))
    for k in (1, 2, 3):
        for hit in detect_patterns(df.iloc[:-k]):
            if hit.name in EXCLUDED or not hit.broke_out_today:
                continue
            if close > hit.trigger and close - hit.trigger <= 1.5 * atr_now and not any(h.name == hit.name for _, h in candidates):
                candidates.append((f"BROKE OUT {k}D AGO", hit))
    if not candidates:
        return None

    order = {"BREAKOUT TODAY": 0, "BROKE OUT 1D AGO": 1, "READY": 2, "BROKE OUT 2D AGO": 3, "BROKE OUT 3D AGO": 4}
    candidates.sort(key=lambda sh: (order.get(sh[0], 9), -PATTERN_EDGE.get(sh[1].name, 0.05)))
    status, lead = candidates[0]
    hits = [h for _, h in candidates]
    stop, target, rr = _levels(lead, close, atr_now)

    e21, e50, e200 = (float(ema(c, w).iloc[-1]) for w in (21, 50, 200))
    vol = df["volume"]
    v20 = float(vol.iloc[-21:-1].mean())
    reasons = []
    score = min(40.0, max(PATTERN_EDGE.get(h.name, 0.05) for h in hits) * 160)
    reasons.append(f"{lead.name} ({lead.bars} bars), backtest edge {PATTERN_EDGE.get(lead.name, 0.05):+.2f}R")
    if len({h.name for h in hits}) >= 2:
        score += 8
        reasons.append(f"{len({h.name for h in hits})} patterns at once")
    if close > e200:
        score += 10
        reasons.append(f"above DTF 200 EMA ({e200:.2f})")
    else:
        score -= 10
    if e21 > e50 > e200:
        score += 6
        reasons.append("EMA 21 > 50 > 200 stacked")
    if v20 > 0 and vol.iloc[-1] > 1.5 * v20 and status != "READY":
        score += 6
        reasons.append(f"breakout volume {vol.iloc[-1] / v20:.1f}x average")
    if status == "READY" and v20 > 0 and vol.iloc[-5:].mean() < 0.8 * v20:
        score += 4
        reasons.append("volume drying up into the trigger")
    atr_pct = atr_now / close * 100
    if atr_pct >= 3:
        score += 5
        reasons.append(f"ATR {atr_pct:.1f}% (moves enough)")
    if momentum_rank is not None and momentum_rank >= 80:
        score += 10
        reasons.append(f"momentum rank {momentum_rank:.0f}/100")
    er = efficiency_ratio(c)
    if er is not None and er >= 0.25:
        score += 5
        reasons.append(f"clean trend (efficiency {er:.2f})")
    coil = (df["high"].iloc[-5:].max() - df["low"].iloc[-5:].min()) / atr_now
    if coil <= 2.0:
        score += 5
        reasons.append(f"tight coil (5-day range {coil:.1f} ATR)")
    zones = find_zones(df)
    above = [z for z in zones if z.low > max(close, lead.trigger)]
    if above:
        room = (min(z.low for z in above) - max(close, lead.trigger)) / (max(close, lead.trigger) - stop)
        if room >= 2:
            score += 5
            reasons.append(f"room to next resistance {min(z.low for z in above):.2f} ({room:.1f}R)")
        elif room < 1:
            score -= 8
            reasons.append(f"resistance close overhead at {min(z.low for z in above):.2f}")
    else:
        score += 5
        reasons.append("no resistance overhead (2y)")
    return Setup(ticker=ticker, status=status, patterns=hits, close=close, trigger=lead.trigger, stop=stop,
                 target=target, rr=rr, score=round(max(0.0, min(100.0, score)), 1), reasons=reasons, daily=df)


def find_setups(histories: dict[str, pd.DataFrame], min_price: float = 5.0, min_dollar_volume: float = 5e6) -> list[Setup]:
    ranks = compute_universe_momentum_ranks({t: d["close"] for t, d in histories.items()})
    out = []
    for t, df in histories.items():
        if df.empty or df["close"].iloc[-1] < min_price:
            continue
        if (df["close"] * df["volume"]).iloc[-20:].mean() < min_dollar_volume:
            continue
        s = evaluate_ticker(t, df, ranks.get(t))
        if s is not None:
            out.append(s)
    return sorted(out, key=lambda s: s.score, reverse=True)


def main(argv: list[str] | None = None) -> int:
    from config.schema import load_config
    from data.cache import DiskCache
    from data.provider import DataUnavailable
    from data.universe import DEFAULT_UNIVERSE
    from data.yfinance_provider import YFinanceProvider

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tickers", default=None, help="comma list (default: the scanner universe)")
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--html", default=None, help="annotated chart page for the top setups")
    args = ap.parse_args(argv)
    cfg = load_config(None)
    prov = YFinanceProvider(cache=DiskCache(cache_dir=cfg.data.cache_dir, ttl_hours=cfg.data.cache_ttl_hours))
    tickers = [t.strip().upper() for t in args.tickers.split(",")] if args.tickers else list(DEFAULT_UNIVERSE)
    hist = {}
    for t in tickers:
        try:
            hist[t] = prov.get_history(t, "2y")
        except DataUnavailable:
            continue
    setups = find_setups(hist)
    top = setups[: args.top]
    print(f"\n{len(setups)} pattern setups found in {len(hist)} tickers -- top {len(top)} (ready to boom first)\n")
    print(f"{'#':<3}{'TICKER':<7}{'SCORE':>6}  {'STATUS':<17}{'PATTERN(S)':<44}{'CLOSE':>9}{'TRIGGER':>9}{'STOP':>9}{'TARGET':>9}{'R:R':>5}")
    for i, s in enumerate(top, 1):
        print(f"{i:<3}{s.ticker:<7}{s.score:>6.0f}  {s.status:<17}{s.names[:43]:<44}{s.close:>9.2f}{s.trigger:>9.2f}"
              f"{s.stop:>9.2f}{s.target:>9.2f}{s.rr:>5.1f}")
    print()
    for i, s in enumerate(top, 1):
        print(f"{i}. {s.ticker}: " + "; ".join(s.reasons))
    if args.html and top:
        from ui.chart_svg import render_setup_page

        items = []
        for s in top:
            try:
                hourly = prov.get_history(s.ticker, "730d", "1h")
            except DataUnavailable:
                hourly = None
            items.append((s, read_chart(s.ticker, s.daily, hourly)))
        with open(args.html, "w") as f:
            f.write(render_setup_page(items))
        print(f"\nwrote {args.html}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
