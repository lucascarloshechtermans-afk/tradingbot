"""Market structure: BOS / CHoCH events and trend classification.

Events are produced by a causal walk over the bars: at bar t only swings with
known_at <= t are referenced. A close above the latest unbroken swing high is a
bullish break -- a BOS when the structure state was already up, a CHoCH when it
was down (the first break against the prevailing structure). Mirror for lows.

Trend labels combine moving averages WITH price structure; moving averages
alone never decide the label.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ta.core import Indicators
from ta.swings import Swing, known_swings

TREND_LABELS = {
    "strong_uptrend": "sterke uptrend", "weak_uptrend": "zwakke uptrend",
    "strong_downtrend": "sterke downtrend", "weak_downtrend": "zwakke downtrend",
    "consolidation": "consolidatie", "potential_reversal_up": "mogelijke ommekeer omhoog",
    "potential_reversal_down": "mogelijke ommekeer omlaag",
}


@dataclass
class StructureEvent:
    kind: str          # "BOS" | "CHoCH"
    direction: str     # "bull" | "bear"
    i: int             # bar of the breaking close
    date: pd.Timestamp
    level: float       # the swing level that was broken
    swing_i: int       # bar of that swing


def structure_events(df: pd.DataFrame, swings: list[Swing]) -> tuple[list[StructureEvent], list[str]]:
    """(events, state per bar) -- state is 'up', 'down' or '' before the first break."""
    close = df["close"].to_numpy()
    by_known: dict[int, list[Swing]] = {}
    for s in swings:
        by_known.setdefault(s.known_at, []).append(s)
    ref_h: Swing | None = None
    ref_l: Swing | None = None
    state = ""
    events: list[StructureEvent] = []
    states: list[str] = []
    for t in range(len(df)):
        for s in by_known.get(t, []):
            if s.kind == "H":
                ref_h = s
            else:
                ref_l = s
        if ref_h is not None and close[t] > ref_h.price:
            kind = "CHoCH" if state == "down" else "BOS"
            events.append(StructureEvent(kind, "bull", t, df.index[t], ref_h.price, ref_h.i))
            state, ref_h = "up", None
        elif ref_l is not None and close[t] < ref_l.price:
            kind = "CHoCH" if state == "up" else "BOS"
            events.append(StructureEvent(kind, "bear", t, df.index[t], ref_l.price, ref_l.i))
            state, ref_l = "down", None
        states.append(state)
    return events, states


@dataclass
class TrendAssessment:
    label: str                     # key of TREND_LABELS
    direction: int                 # +1 up, -1 down, 0 sideways
    strength: float                # 0-100 (how clean / strong the trend is)
    stage: str                     # early | established | mature | n/a
    bars_in_state: int
    state: str                     # structure state 'up' | 'down' | ''
    alignment: int                 # -4..+4 MA stack (close>EMA21>SMA50>SMA100>SMA200)
    swing_labels: list[str]
    last_event: StructureEvent | None
    recent_events: list[StructureEvent]
    dist_atr: dict[str, float]
    slopes: dict[str, float]
    adx: float
    exhaustion: list[str] = field(default_factory=list)
    continuation: bool = False
    reasons: list[str] = field(default_factory=list)

    @property
    def label_nl(self) -> str:
        return TREND_LABELS.get(self.label, self.label)


def ma_alignment(ind: Indicators, close: float) -> int:
    chain = [close, ind.last("ema21"), ind.last("sma50"), ind.last("sma100"), ind.last("sma200")]
    score = 0
    for a, b in zip(chain, chain[1:]):
        if np.isfinite(a) and np.isfinite(b):
            score += 1 if a > b else -1
    return score


def assess_trend(df: pd.DataFrame, ind: Indicators, swings: list[Swing], events: list[StructureEvent],
                 states: list[str]) -> TrendAssessment:
    t = len(df) - 1
    c = float(df["close"].iloc[-1])
    atr = ind.last("atr")
    known = known_swings(swings, t)
    highs = [s for s in known if s.kind == "H"][-2:]
    lows = [s for s in known if s.kind == "L"][-2:]
    labels = [s.label for s in sorted(highs + lows, key=lambda s: s.i) if s.label]
    swing_bull = bool(highs and lows and highs[-1].label == "HH" and lows[-1].label in ("HL", "EL"))
    swing_bear = bool(highs and lows and highs[-1].label in ("LH", "EH") and lows[-1].label == "LL")
    state = states[-1] if states else ""
    bars_in_state = 0
    for s in reversed(states):
        if s != state:
            break
        bars_in_state += 1
    align = ma_alignment(ind, c)
    slopes = {k: ind.last(k) for k in ("sma50_slope", "sma200_slope", "ema21_slope")}
    dist = {k: (c - ind.last(k)) / atr if atr and np.isfinite(atr) and np.isfinite(ind.last(k)) else np.nan
            for k in ("ema21", "sma50", "sma200")}
    adx, pdi, mdi = ind.last("adx"), ind.last("plus_di"), ind.last("minus_di")
    window = df.iloc[-30:]
    box_atr = (window["high"].max() - window["low"].min()) / atr if atr and np.isfinite(atr) else np.nan
    last_event = events[-1] if events else None
    recent = [e for e in events if e.i >= t - 60]
    reasons: list[str] = []

    sma50_up = slopes["sma50_slope"] > 0 if np.isfinite(slopes["sma50_slope"]) else False
    sma50_dn = slopes["sma50_slope"] < 0 if np.isfinite(slopes["sma50_slope"]) else False
    adx_ok = np.isfinite(adx) and adx >= 20
    recent_choch = last_event is not None and last_event.kind == "CHoCH" and t - last_event.i <= 20

    if recent_choch and last_event.direction == "bull" and align <= 1:
        label = "potential_reversal_up"
        reasons.append(f"Bullish CHoCH op {last_event.date:%d-%m} (slot boven swing high {last_event.level:,.2f}) "
                       f"na een downtrend, maar de gemiddelden staan nog niet in een uptrend-volgorde ({align:+d}/4).")
    elif recent_choch and last_event.direction == "bear" and align >= -1:
        label = "potential_reversal_down"
        reasons.append(f"Bearish CHoCH op {last_event.date:%d-%m} (slot onder swing low {last_event.level:,.2f}) "
                       f"na een uptrend; de gemiddelden staan nog niet in downtrend-volgorde ({align:+d}/4).")
    elif state == "up" and not swing_bear and align >= 3 and sma50_up and adx_ok and pdi > mdi:
        label = "strong_uptrend"
    elif state == "down" and not swing_bull and align <= -3 and sma50_dn and adx_ok and mdi > pdi:
        label = "strong_downtrend"
    elif (np.isfinite(box_atr) and box_atr <= 6 and not adx_ok) or (not swing_bull and not swing_bear and abs(align) <= 1):
        label = "consolidation"
        bias = ("in een opwaartse structuur" if state == "up" and align >= 2 else
                "in een neerwaartse structuur" if state == "down" and align <= -2 else "zonder duidelijke richting")
        reasons.append(f"Zijwaarts {bias}: de laatste 30 dagen beslaan {box_atr:.1f} ATR, ADX {adx:.0f}, MA-volgorde {align:+d}/4.")
    elif state == "up" or (swing_bull and align >= 1):
        label = "weak_uptrend"
    elif state == "down" or (swing_bear and align <= -1):
        label = "weak_downtrend"
    else:
        label = "consolidation"
        reasons.append("Geen duidelijke structuur.")

    direction = 1 if label in ("strong_uptrend", "weak_uptrend", "potential_reversal_up") else (
        -1 if label in ("strong_downtrend", "weak_downtrend", "potential_reversal_down") else 0)
    if label in ("strong_uptrend", "weak_uptrend", "strong_downtrend", "weak_downtrend"):
        word = "hogere toppen en hogere bodems" if swing_bull else ("lagere toppen en lagere bodems" if swing_bear else "gemengde swings")
        reasons.append(f"Structuur {state or '-'} sinds {bars_in_state} bars ({word}); MA-volgorde {align:+d}/4; "
                       f"SMA50-helling {slopes['sma50_slope']:+.1f}%/10d; ADX {adx:.0f} (+DI {pdi:.0f} / -DI {mdi:.0f}).")

    # strength: structure, MA stack, slope, ADX -- each a different aspect of the same trend
    raw = 0.0
    raw += 30 * (1 if (state == "up" and direction > 0) or (state == "down" and direction < 0) else 0)
    raw += 25 * min(abs(align), 4) / 4 * (1 if np.sign(align) == direction and direction != 0 else 0)
    raw += 15 * (1 if (swing_bull and direction > 0) or (swing_bear and direction < 0) else 0)
    raw += 15 * (1 if (sma50_up and direction > 0) or (sma50_dn and direction < 0) else 0)
    raw += 15 * (min(max((adx - 15) / 20, 0), 1) if np.isfinite(adx) else 0)
    strength = float(round(raw if direction != 0 else min(raw, 30), 1))

    n_bos = sum(1 for e in events if e.kind == "BOS" and e.i >= t - bars_in_state + 1 and e.direction == ("bull" if state == "up" else "bear"))
    if state == "" or direction == 0:
        stage = "n/a"
    elif n_bos <= 1 and bars_in_state < 40:
        stage = "early"
    elif n_bos >= 4 or bars_in_state > 150:
        stage = "mature"
    else:
        stage = "established"

    exhaustion = []
    if direction > 0 and np.isfinite(dist["ema21"]) and dist["ema21"] > 3:
        exhaustion.append(f"ver boven de EMA21 ({dist['ema21']:.1f} ATR) -- overstrekt")
    if direction < 0 and np.isfinite(dist["ema21"]) and dist["ema21"] < -3:
        exhaustion.append(f"ver onder de EMA21 ({dist['ema21']:.1f} ATR) -- overstrekt naar beneden")
    adx_series = ind["adx"]
    if len(adx_series) > 6 and np.isfinite(adx) and adx > 40 and adx < float(adx_series.iloc[-6]):
        exhaustion.append(f"ADX {adx:.0f} boven 40 en dalend -- trend verliest kracht")
    ups = (df["close"].diff() > 0).to_numpy()[-10:]
    run = 0
    for u in ups[::-1]:
        if (u and direction > 0) or (not u and direction < 0):
            run += 1
        else:
            break
    if run >= 7:
        exhaustion.append(f"{run} slotkoersen op rij in trendrichting")
    continuation = bool(last_event is not None and last_event.kind == "BOS" and t - last_event.i <= 10
                        and ((last_event.direction == "bull" and direction > 0) or (last_event.direction == "bear" and direction < 0)))
    return TrendAssessment(label=label, direction=direction, strength=strength, stage=stage, bars_in_state=bars_in_state,
                           state=state, alignment=align, swing_labels=labels[-4:], last_event=last_event,
                           recent_events=recent, dist_atr=dist, slopes=slopes, adx=adx, exhaustion=exhaustion,
                           continuation=continuation, reasons=reasons)
