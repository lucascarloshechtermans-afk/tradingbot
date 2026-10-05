"""Full single-timeframe analysis: every module run once on one frame."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ta.candles import CandleSignal, evaluate_candles
from ta.core import Indicators, compute_indicators, volume_available
from ta.levels import Zone, find_zones
from ta.liquidity import LiquidityAssessment, assess_liquidity
from ta.momentum import MomentumAssessment, assess_momentum
from ta.patterns import ChartPattern, find_patterns
from ta.structure import StructureEvent, TrendAssessment, assess_trend, structure_events
from ta.swings import Swing, find_swings
from ta.volatility import VolatilityAssessment, assess_volatility
from ta.volume import VolumeAssessment, assess_volume

SWING_ORDER = {"monthly": 2, "weekly": 2, "daily": 3, "4h": 3, "1h": 3}
MIN_BARS = {"monthly": 24, "weekly": 52, "daily": 120, "4h": 120, "1h": 120}


@dataclass
class FrameAnalysis:
    name: str
    df: pd.DataFrame
    ok: bool
    note: str = ""
    ind: Indicators | None = None
    swings: list[Swing] = field(default_factory=list)
    events: list[StructureEvent] = field(default_factory=list)
    trend: TrendAssessment | None = None
    momentum: MomentumAssessment | None = None
    volume: VolumeAssessment | None = None
    volatility: VolatilityAssessment | None = None
    zones: list[Zone] = field(default_factory=list)
    patterns: list[ChartPattern] = field(default_factory=list)
    candles: list[CandleSignal] = field(default_factory=list)
    liquidity: LiquidityAssessment | None = None

    @property
    def close(self) -> float:
        return float(self.df["close"].iloc[-1])

    @property
    def atr(self) -> float:
        return self.ind.last("atr") if self.ind is not None else np.nan


def analyze_frame(df: pd.DataFrame, name: str, full: bool = True) -> FrameAnalysis:
    if df is None or len(df) < MIN_BARS.get(name, 120):
        return FrameAnalysis(name, df if df is not None else pd.DataFrame(), False,
                             f"te weinig afgesloten {name}-kaarsen ({0 if df is None else len(df)})")
    ind = compute_indicators(df)
    sw = find_swings(df, SWING_ORDER.get(name, 3), ind["atr"])
    ev, st = structure_events(df, sw)
    tr = assess_trend(df, ind, sw, ev, st)
    t = len(df) - 1
    fa = FrameAnalysis(name, df, True, ind=ind, swings=sw, events=ev, trend=tr)
    fa.zones = find_zones(df, ind["atr"], ev, ind["rvol"] if "rvol" in ind else None)
    above = [z for z in fa.zones if z.low > fa.close]
    near_res = bool(above and np.isfinite(fa.atr) and min(z.low for z in above) - fa.close <= fa.atr)
    fa.momentum = assess_momentum(ind, sw, t, tr.direction, near_resistance=near_res)
    fa.volume = assess_volume(df, ind, sw, t)
    fa.volatility = assess_volatility(df, ind)
    if full:
        fa.patterns = find_patterns(df, ind["atr"], fa.zones, tr.direction, volume_available(df))
        fa.candles = evaluate_candles(df, ind, fa.zones, tr.direction)
        fa.liquidity = assess_liquidity(df, ind, sw)
    return fa
