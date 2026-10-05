"""Relative strength as a purely technical price-performance comparison
(stock vs SPY, QQQ and its sector ETF). No fundamentals."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

WINDOWS = (5, 20, 60, 120)


@dataclass
class RSResult:
    benchmark: str
    rel: dict[int, float]          # stock return minus benchmark return, percentage points
    rs_slope20: float              # % change of the RS line over 20 bars
    rs_new_high: bool              # RS line at a 63-bar high
    rs_breakout: bool              # RS line crossed above its prior 63-bar high in the last 5 bars
    leads_price: bool              # RS line at a new high while price is not


@dataclass
class RSAssessment:
    results: list[RSResult] = field(default_factory=list)
    consistent: bool = False
    improving: bool = False
    weakening: bool = False
    outperforming_in_quiet_market: bool = False
    score: float = 0.0             # -100..+100
    notes: list[str] = field(default_factory=list)


def compare(close: pd.Series, bench: pd.Series, name: str) -> RSResult | None:
    b = bench.reindex(close.index).ffill()
    if b.notna().sum() < 130:
        return None
    rel = {w: float((close.iloc[-1] / close.iloc[-1 - w] - b.iloc[-1] / b.iloc[-1 - w]) * 100) for w in WINDOWS
           if len(close) > w}
    rs = close / b
    slope = float((rs.iloc[-1] / rs.iloc[-21] - 1) * 100) if len(rs) > 21 else np.nan
    prior_max = rs.shift(1).rolling(63).max()
    new_high = bool(rs.iloc[-1] >= prior_max.iloc[-1]) if np.isfinite(prior_max.iloc[-1]) else False
    brk = bool(((rs > prior_max) & (rs.shift(1) <= prior_max.shift(1))).iloc[-5:].any())
    price_high = bool(close.iloc[-1] >= close.shift(1).rolling(63).max().iloc[-1])
    return RSResult(name, rel, slope, new_high, brk, new_high and not price_high)


def assess_rs(close: pd.Series, benchmarks: dict[str, pd.Series], market_ranging: bool = False) -> RSAssessment:
    ra = RSAssessment()
    for name, b in benchmarks.items():
        if b is not None:
            r = compare(close, b, name)
            if r is not None:
                ra.results.append(r)
    if not ra.results:
        ra.notes.append("Relatieve sterkte niet beschikbaar (geen benchmarkdata)")
        return ra
    spy = next((r for r in ra.results if r.benchmark == "SPY"), ra.results[0])
    pos = sum(1 for w in WINDOWS if spy.rel.get(w, np.nan) > 0)
    ra.consistent = pos >= 3
    r20, r60, r120 = (spy.rel.get(w, np.nan) for w in (20, 60, 120))
    ra.improving = bool(np.isfinite(r20) and r20 > 0 and spy.rs_slope20 > 0 and (not np.isfinite(r60) or r20 > r60 * 20 / 60))
    ra.weakening = bool(np.isfinite(r20) and r20 < 0 and np.isfinite(r120) and r120 > 0)
    ra.outperforming_in_quiet_market = bool(market_ranging and np.isfinite(r20) and r20 > 0 and spy.rs_slope20 > 0)
    parts = [np.clip(spy.rel.get(w, 0) / s, -1, 1) for w, s in ((20, 8), (60, 15), (120, 25))]
    sec = next((r for r in ra.results if r.benchmark not in ("SPY", "QQQ")), None)
    if sec is not None:
        parts.append(np.clip(sec.rel.get(60, 0) / 15, -1, 1))
    ra.score = float(round(np.mean(parts) * 100, 1))
    for r in ra.results:
        txt = ", ".join(f"{w}d {r.rel[w]:+.1f}pp" for w in WINDOWS if w in r.rel)
        flags = []
        if r.rs_breakout:
            flags.append("RS-lijn breekt uit (63-daags hoog)")
        elif r.rs_new_high:
            flags.append("RS-lijn op 63-daags hoog")
        if r.leads_price:
            flags.append("RS-lijn loopt voor op de koers")
        ra.notes.append(f"vs {r.benchmark}: {txt}" + (f" -- {'; '.join(flags)}" if flags else ""))
    if ra.consistent:
        ra.notes.append("Consistent sterker dan SPY (>= 3 van 4 periodes)")
    if ra.improving:
        ra.notes.append("Relatieve sterkte verbetert (recent sneller dan de markt)")
    if ra.weakening:
        ra.notes.append("Relatieve sterkte verzwakt (laatste 20 dagen achter op SPY, op 120 dagen nog voor)")
    if ra.outperforming_in_quiet_market:
        ra.notes.append("Sterker dan de markt terwijl de markt zijwaarts beweegt")
    ra.notes.append("Industrie-benchmark: niet beschikbaar in de gratis data (alleen sector-ETF)")
    return ra
