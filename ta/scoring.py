"""Transparent technical confluence score, 0-100.

One sub-score per FAMILY, never per indicator: RSI, MACD, ROC and DI all live
in 'momentum' and produce one momentum number, so three bullish oscillators
are one confirmation, not three. Weights are configurable (config 'technical:
weights:'); a family without data (e.g. no volume) is left out and the other
weights are renormalised -- the explanation says so.

The score measures how complete and aligned the TECHNICAL picture is for one
direction. It is not a probability of profit: the historical validation
measures what scores actually did afterwards (ta/evaluate.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ta import nl

DEFAULT_WEIGHTS = {"trend": 18.0, "price_action": 14.0, "sr": 12.0, "momentum": 12.0, "volume": 10.0,
                   "volatility": 6.0, "candles": 5.0, "mtf": 13.0, "rs": 10.0}
FAMILY_NL = {"trend": "trendstructuur", "price_action": "price action / setup", "sr": "steun & weerstand",
             "momentum": "momentum", "volume": "volume", "volatility": "volatiliteit", "candles": "candlesticks",
             "mtf": "multi-timeframe", "rs": "relatieve sterkte"}
TREND_LONG = {"strong_uptrend": None, "weak_uptrend": 60.0, "consolidation": 40.0, "potential_reversal_up": 50.0,
              "potential_reversal_down": 25.0, "weak_downtrend": 20.0, "strong_downtrend": 5.0}
STATUS_PA = {"confirmed": 80.0, "triggered": 65.0, "developing": 45.0, "failed": 15.0}


@dataclass
class Contribution:
    family: str
    sub: float | None          # 0..100, None = no data
    weight: float
    points: float              # contribution to the total
    why: str


@dataclass
class TechnicalScore:
    total: float
    direction: int
    contributions: list[Contribution]
    quality: float             # = total
    maturity: str              # e.g. "bevestigd; trend established"
    confirmation: str          # status of the primary setup
    conflicts: list[str] = field(default_factory=list)
    note: str = ("Score = hoe volledig en eensgezind het technische beeld is. Geen winstkans: zie de historische "
                 "validatie voor wat scores achteraf deden.")


def _flip(x: float, d: int) -> float:
    return x if d > 0 else 100 - x


def score(report, weights: dict[str, float] | None = None) -> TechnicalScore:
    w = {**DEFAULT_WEIGHTS, **(weights or {})}
    fa = report.daily
    d = report.direction
    prim = report.primary
    tr, m, v, vo = fa.trend, fa.momentum, fa.volume, fa.volatility
    subs: dict[str, tuple[float | None, str]] = {}

    base = TREND_LONG.get(tr.label, 40.0)
    if base is None:
        base = 60 + 0.4 * tr.strength
    if d < 0:
        mirror = {"strong_uptrend": "strong_downtrend", "weak_uptrend": "weak_downtrend", "potential_reversal_up": "potential_reversal_down",
                  "potential_reversal_down": "potential_reversal_up", "weak_downtrend": "weak_uptrend",
                  "strong_downtrend": "strong_uptrend", "consolidation": "consolidation"}
        base = TREND_LONG.get(mirror.get(tr.label, tr.label), 40.0)
        if base is None:
            base = 60 + 0.4 * tr.strength
    pen = 8 * len(tr.exhaustion) if (tr.direction == d) else 0
    subs["trend"] = (max(base - pen, 0), (f"{tr.label_nl}, kracht {tr.strength:.0f}/100, fase {nl(tr.stage)}" if tr.direction
                                          else f"{tr.label_nl} (geen trendkracht)")
                     + (f"; -{pen} voor overstrekking" if pen else ""))

    if prim is not None:
        pa = STATUS_PA[prim.status] + 5 * len(prim.combos)
        pats = [p.quality for p in fa.patterns if (p.direction == "bull") == (d > 0) and p.status != "failed"]
        pa += (max(pats) - 50) / 5 if pats else 0
        subs["price_action"] = (float(np.clip(pa, 0, 100)), f"{prim.name_nl} ({prim.status_nl})"
                                + (f"; combinatie: {prim.combos[0]}" if prim.combos else ""))
    else:
        subs["price_action"] = (30.0, "geen setup")

    close, atr = fa.close, fa.atr
    above = [z for z in fa.zones if z.low > close]
    below = [z for z in fa.zones if z.high < close]
    room_side, base_side = (above, below) if d > 0 else (below, above)
    if room_side:
        nz = min(room_side, key=lambda z: abs(z.mid - close))
        room = (nz.low - close if d > 0 else close - nz.high) / atr
        room_s, room_txt = 50 * float(np.clip(room / 3, 0, 1)), f"{room:.1f} ATR ruimte tot {nl(nz.strength)} {'weerstand' if d > 0 else 'steun'}"
    else:
        room_s, room_txt = 50.0, "geen zone in de weg (open lucht)"
    sup_s, sup_txt = 0.0, "geen zone vlak achter de koers"
    if base_side:
        bz = min(base_side, key=lambda z: abs(z.mid - close))
        dist = (close - bz.high if d > 0 else bz.low - close) / atr
        if dist <= 1.5:
            sup_s = 30.0 if bz.strength == "strong" else 15.0
            sup_txt = f"{nl(bz.strength)} {'steun' if d > 0 else 'weerstand'} {dist:.1f} ATR {'eronder' if d > 0 else 'erboven'}"
            if bz.role in ("flip_support", "flip_resistance"):
                sup_s += 20
                sup_txt += " (rolwissel)"
    subs["sr"] = (min(room_s + sup_s + 10, 100), f"{room_txt}; {sup_txt}")

    ms = _flip((m.score + 100) / 2, d)
    divs = [x for x in m.divergences if x.bars_ago <= 15]
    adj = sum(-15 for x in divs if x.kind == ("regular_bear" if d > 0 else "regular_bull")) + \
        sum(10 for x in divs if x.kind == ("regular_bull" if d > 0 else "regular_bear"))
    subs["momentum"] = (float(np.clip(ms + adj, 0, 100)), f"{nl(m.state)} (familiescore {m.score:+.0f}), {nl(m.acceleration)}"
                        + (f"; divergentie {adj:+d}" if adj else ""))

    if v.available:
        vs = _flip((v.score + 100) / 2, d) - (10 if v.climax and tr.direction == d else 0)
        subs["volume"] = (float(np.clip(vs, 0, 100)), f"familiescore {v.score:+.0f}, RVOL {v.rvol:.2f}"
                          + ("; climax" if v.climax else ""))
    else:
        subs["volume"] = (None, "geen volumedata -- familie weggelaten, gewichten herschaald")

    if prim is not None and prim.kind in ("early_breakout", "volatility_squeeze"):
        subs["volatility"] = (vo.score, f"compressiescore {vo.score:.0f} (van belang voor deze setup)")
    elif prim is not None and prim.kind in ("confirmed_breakout", "breakdown") and vo.expansion:
        subs["volatility"] = (75.0, "volatiliteit zet uit met de breakout mee")
    else:
        subs["volatility"] = (50.0 + (vo.score - 50) * 0.3, f"compressiescore {vo.score:.0f} (neutraal voor deze setup)")

    same = [x for x in fa.candles if x.direction == ("bull" if d > 0 else "bear")]
    opp = [x for x in fa.candles if x.direction == ("bear" if d > 0 else "bull") and x.significance == "high"]
    if same:
        best = max(same, key=lambda x: x.score)
        subs["candles"] = (best.score, f"{best.name_nl} ({nl(best.significance)}, {nl(best.confirmation)})")
    elif opp:
        subs["candles"] = (20.0, f"tegengestelde kaars: {opp[-1].name_nl}")
    else:
        subs["candles"] = (40.0, "geen relevante kaars")

    others = [r for tf, r in report.mtf.rows.items() if tf != "daily" and r.get("ok")]
    if not others:
        subs["mtf"] = (None, "alleen de daggrafiek beschikbaar -- familie weggelaten (zou de dagtrend dubbel tellen)")
    else:
        subs["mtf"] = (report.mtf.score, f"{len(report.mtf.agree)} timeframes mee ({', '.join(report.mtf.agree) or '-'}), "
                       f"{len(report.mtf.disagree)} tegen ({', '.join(report.mtf.disagree) or '-'})")

    if report.rs is not None and report.rs.results:
        subs["rs"] = (_flip((report.rs.score + 100) / 2, d), f"familiescore {report.rs.score:+.0f}")
    else:
        subs["rs"] = (None, "geen benchmarkdata")

    avail = {k: w[k] for k, (s, _) in subs.items() if s is not None and w.get(k, 0) > 0}
    tot_w = sum(avail.values()) or 1.0
    contribs = []
    total = 0.0
    for k in DEFAULT_WEIGHTS:
        s, why = subs.get(k, (None, ""))
        if s is None or k not in avail:
            contribs.append(Contribution(k, None, 0.0, 0.0, why))   # dropped: no weight
            continue
        pts = s * avail[k] / tot_w
        total += pts
        contribs.append(Contribution(k, round(s, 1), round(avail[k] / tot_w * 100, 1), round(pts, 1), why))
    conflicts = list(prim.conflicts) if prim is not None else []
    conflicts += [f"{FAMILY_NL[c.family]} spreekt tegen ({c.sub:.0f}/100): {c.why}" for c in contribs
                  if c.sub is not None and c.sub < 30 and c.family not in ("candles",)]
    maturity = (f"{prim.status_nl}; trendfase {nl(tr.stage)}" if prim is not None else f"geen setup; trendfase {nl(tr.stage)}")
    return TechnicalScore(round(total, 1), d, contribs, round(total, 1), maturity,
                          prim.status if prim is not None else "none", conflicts)
