"""TechnicalReport: every module combined for one ticker.

    report = analyze("NVDA", daily, hourly=hourly, benchmarks={"SPY": spy_close, ...})

`daily` must hold completed sessions only (data.sessions); weekly / monthly /
4H / 1H are derived from it with closed candles only (ta/timeframes.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ta.frame import FrameAnalysis, analyze_frame
from ta.regime import Regime
from ta.relstrength import RSAssessment, assess_rs
from ta.scoring import TechnicalScore, score
from ta.setups import STATUS_RANK, Setup, classify
from ta.timeframes import build_timeframes

TF_ORDER = ("monthly", "weekly", "daily", "4h", "1h")
TF_NL = {"monthly": "maand", "weekly": "week", "daily": "dag", "4h": "4 uur", "1h": "1 uur"}
TF_WEIGHT = {"monthly": 1.0, "weekly": 2.0, "daily": 3.0, "4h": 1.5, "1h": 0.5}


@dataclass
class MTFConfluence:
    direction: int
    rows: dict[str, dict] = field(default_factory=dict)
    agree: list[str] = field(default_factory=list)
    disagree: list[str] = field(default_factory=list)
    neutral: list[str] = field(default_factory=list)
    score: float = 50.0
    narrative: list[str] = field(default_factory=list)


@dataclass
class TechnicalReport:
    ticker: str
    as_of: pd.Timestamp
    close: float
    frames: dict[str, FrameAnalysis]
    daily: FrameAnalysis
    setups: list[Setup]
    primary: Setup | None
    direction: int
    mtf: MTFConfluence
    regime: Regime | None
    rs: RSAssessment | None
    score: TechnicalScore | None = None
    notes: list[str] = field(default_factory=list)


def _tf_direction(fa: FrameAnalysis) -> int:
    if not fa.ok or fa.trend is None:
        return 0
    d = fa.trend.direction
    if d == 0 and fa.momentum is not None:
        if fa.momentum.state == "strong_bullish":
            return 0
    return d


def confluence(frames: dict[str, FrameAnalysis], direction: int) -> MTFConfluence:
    mc = MTFConfluence(direction)
    num = den = 0.0
    for tf in TF_ORDER:
        fa = frames.get(tf)
        if fa is None:
            continue
        if not fa.ok:
            mc.rows[tf] = {"ok": False, "note": fa.note}
            continue
        d = _tf_direction(fa)
        sup = max((z for z in fa.zones if z.high < fa.close), key=lambda z: z.high, default=None)
        res = min((z for z in fa.zones if z.low > fa.close), key=lambda z: z.low, default=None)
        pat = next((p for p in fa.patterns if p.status in ("near", "breakout", "confirmed")), None)
        mc.rows[tf] = {"ok": True, "trend": fa.trend.label_nl, "direction": d, "swings": " ".join(fa.trend.swing_labels[-4:]),
                       "momentum": fa.momentum.state, "volume": (f"RVOL {fa.volume.rvol:.1f}" if fa.volume.available and
                                                                np.isfinite(fa.volume.rvol) else "n.v.t."),
                       "support": sup, "resistance": res, "pattern": pat,
                       "event": fa.trend.last_event}
        wt = TF_WEIGHT[tf]
        den += wt
        if d == direction and d != 0:
            mc.agree.append(TF_NL[tf])
            num += wt
        elif d == -direction and d != 0:
            mc.disagree.append(TF_NL[tf])
        else:
            mc.neutral.append(TF_NL[tf])
            num += 0.4 * wt
        line = f"{TF_NL[tf].capitalize()}: {fa.trend.label_nl}"
        if fa.trend.swing_labels:
            line += f" ({'/'.join(fa.trend.swing_labels[-2:])})"
        line += f", momentum {fa.momentum.state}"
        e = fa.trend.last_event
        if e is not None and len(fa.df) - 1 - e.i <= 10:
            line += f"; {'bullish' if e.direction == 'bull' else 'bearish'} {e.kind} op {e.date:%d-%m}"
        if pat is not None:
            line += f"; {pat.name} {pat.status_nl} (trigger {pat.trigger:,.2f})"
        if res is not None:
            line += f"; weerstand {res.low:,.2f}"
        if sup is not None:
            line += f"; steun {sup.high:,.2f}"
        mc.narrative.append(line + ".")
    mc.score = round(100 * num / den, 1) if den else 50.0
    return mc


def analyze(ticker: str, daily: pd.DataFrame, hourly: pd.DataFrame | None = None,
            benchmarks: dict[str, pd.Series] | None = None, regime: Regime | None = None,
            weights: dict[str, float] | None = None, light: bool = False) -> TechnicalReport:
    """light=True (historical evaluation): no patterns/candles/liquidity on the higher timeframes."""
    frames_raw = build_timeframes(daily, hourly)
    frames: dict[str, FrameAnalysis] = {}
    for tf, df in frames_raw.items():
        frames[tf] = analyze_frame(df, tf, full=tf == "daily" or (not light and tf in ("weekly", "4h")))
    d = frames["daily"]
    if not d.ok:
        return TechnicalReport(ticker, d.df.index[-1] if len(d.df) else pd.NaT, d.close if len(d.df) else np.nan, frames, d, [],
                               None, 0, MTFConfluence(0), regime, None, None, [d.note])
    setups = classify(d)
    rs = None
    if benchmarks:
        close = d.df["close"]
        bm = {k: (v.set_axis(v.index.tz_convert("America/New_York").tz_localize(None).normalize())
                  if getattr(v.index, "tz", None) is not None else v) for k, v in benchmarks.items() if v is not None}
        rs = assess_rs(close, bm, market_ranging=regime is not None and regime.label == "range_bound")
    rep = TechnicalReport(ticker, d.df.index[-1], d.close, frames, d, setups, None, d.trend.direction or 1,
                          confluence(frames, d.trend.direction or 1), regime, rs)
    # every setup is scored in its own direction; the primary is the most advanced status, then the best score
    mtf_by_dir = {1: confluence(frames, 1), -1: confluence(frames, -1)}
    for s in setups:
        s.tf_agree, s.tf_disagree = mtf_by_dir[s.direction].agree, mtf_by_dir[s.direction].disagree
        rep.primary, rep.direction, rep.mtf = s, s.direction, mtf_by_dir[s.direction]
        s.quality = score(rep, weights).total
    live = [s for s in setups if s.status != "failed"]
    rep.primary = max(live, key=lambda s: (STATUS_RANK[s.status], s.quality)) if live else None
    rep.direction = rep.primary.direction if rep.primary is not None else (d.trend.direction or 1)
    rep.mtf = mtf_by_dir[rep.direction]
    rep.score = score(rep, weights)
    if regime is not None:
        rep.notes.append(regime.breakout_context())
    return rep
