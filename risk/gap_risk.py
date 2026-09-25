from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd

DEFAULT_GAP_WINDOW = 60
LARGE_GAP_THRESHOLD_PCT = 3.0


def compute_gap_series(open_: pd.Series, close: pd.Series) -> pd.Series:
    """Overnight gap %: (today's open - yesterday's close) / yesterday's close.
    This is the risk a multi-day hold is actually exposed to (a ~5-trading-day
    hold sits through ~4 overnight sessions where the price can jump past a stop
    with no chance to exit at the stop price) — unlike intraday range, which the
    position isn't continuously exposed to. Purely mechanical from OHLCV, no
    look-ahead: each value only needs today's open and yesterday's close.
    """
    prior_close = close.shift(1)
    return (open_ - prior_close) / prior_close * 100


@dataclass
class GapRiskProfile:
    avg_gap_pct: float | None  # signed average — a directional bias, not just magnitude
    avg_abs_gap_pct: float | None  # magnitude regardless of direction
    large_gap_frequency_pct: float | None  # % of days in the window with |gap| > threshold
    up_gap_bias: float | None  # of the large gaps, the fraction that were gap-UPS (0-1)
    reasons: list[str] = field(default_factory=list)


def analyze_gap_risk(
    history: pd.DataFrame,
    window: int = DEFAULT_GAP_WINDOW,
    large_gap_threshold_pct: float = LARGE_GAP_THRESHOLD_PCT,
) -> GapRiskProfile:
    """OHLCV-only overnight gap risk profile — safe to compute walk-forward inside
    a backtest (see strategies/context.py:build_context) with no earnings-date
    dependency. `earnings_gap_fraction` below is a separate, live-scanner-only
    enrichment: correctly attributing which HISTORICAL gaps were earnings-driven
    in a backtest would require knowing exactly when each earnings date was
    first announced (to stay causal), which isn't available — rather than risk a
    subtle look-ahead bug, that cross-reference is only done for the live scan,
    where "is there a known earnings date nearby" is trivially causal (today).
    """
    if history is None or len(history) < window + 1:
        return GapRiskProfile(None, None, None, None, ["Insufficient history to assess overnight gap risk"])

    gaps = compute_gap_series(history["open"], history["close"]).tail(window).dropna()
    if gaps.empty:
        return GapRiskProfile(None, None, None, None, ["Insufficient history to assess overnight gap risk"])

    avg_gap = float(gaps.mean())
    avg_abs_gap = float(gaps.abs().mean())
    large_mask = gaps.abs() > large_gap_threshold_pct
    large_gap_frequency = float(large_mask.mean() * 100)
    large_gaps = gaps[large_mask]
    up_gap_bias = float((large_gaps > 0).mean()) if len(large_gaps) else None

    reasons = [
        f"Avg overnight gap magnitude {avg_abs_gap:.1f}%, gaps over {large_gap_threshold_pct:g}% on "
        f"{large_gap_frequency:.0f}% of the last {len(gaps)} sessions"
    ]
    if up_gap_bias is not None:
        reasons.append(f"Of large gaps, {up_gap_bias * 100:.0f}% were gap-ups, {(1 - up_gap_bias) * 100:.0f}% gap-downs")

    return GapRiskProfile(
        avg_gap_pct=avg_gap,
        avg_abs_gap_pct=avg_abs_gap,
        large_gap_frequency_pct=large_gap_frequency,
        up_gap_bias=up_gap_bias,
        reasons=reasons,
    )


def earnings_gap_fraction(
    history: pd.DataFrame,
    earnings_dates: list[datetime],
    window: int = DEFAULT_GAP_WINDOW,
    large_gap_threshold_pct: float = LARGE_GAP_THRESHOLD_PCT,
) -> float | None:
    """Of the large overnight gaps in the trailing window, what fraction landed
    within 1 day of a known earnings date — live-scan-only enrichment, see
    `analyze_gap_risk`'s docstring for why this isn't computed in the backtest.
    """
    if history is None or len(history) < window + 1 or not earnings_dates:
        return None
    gaps = compute_gap_series(history["open"], history["close"]).tail(window).dropna()
    large_gaps = gaps[gaps.abs() > large_gap_threshold_pct]
    if large_gaps.empty:
        return None

    def _to_naive_date(ts) -> pd.Timestamp:
        ts = pd.Timestamp(ts)
        return (ts.tz_localize(None) if ts.tz is not None else ts).normalize()

    earnings_days = {_to_naive_date(d) for d in earnings_dates}
    large_gap_days = [_to_naive_date(ts) for ts in large_gaps.index]
    near_earnings = sum(1 for d in large_gap_days if any(abs((d - ed).days) <= 1 for ed in earnings_days))
    return near_earnings / len(large_gap_days)
