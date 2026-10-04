"""Technical setup classification on the daily frame, with multi-timeframe
agreement. A setup is a COMPLETE situation (structure + level + trigger),
not a count of indicators.

Status ladder, decided on closes only:
  developing  the situation exists, its trigger has not been hit
  triggered   the trigger close happened (one close, no follow-through yet)
  confirmed   follow-through: a second close beyond the level, a volume
              thrust (RVOL >= 1.5 with the close in the upper third of the
              bar), a confirmed higher low, or a confirming candle
  failed      price closed back through the level / invalidation
A setup is never labelled 'confirmed' before one of those conditions holds.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ta import nl

from ta.frame import FrameAnalysis
from ta.levels import containing, nearest
from ta.swings import known_swings
from ta.volume import breakout_volume_ratio

SETUP_NL = {
    "early_breakout": "vroege breakout", "confirmed_breakout": "bevestigde breakout", "breakout_retest": "breakout-retest",
    "bullish_pullback": "bullish pullback", "bearish_pullback": "bearish pullback", "trend_continuation": "trendvoortzetting",
    "momentum_reversal": "momentum-ommekeer", "mean_reversion": "mean reversion", "support_bounce": "steunbounce",
    "resistance_rejection": "weerstandsafwijzing", "volatility_squeeze": "volatiliteits-squeeze",
    "failed_breakout": "mislukte breakout", "failed_breakdown": "mislukte breakdown",
    "potential_trend_reversal": "mogelijke trendommekeer", "breakdown": "breakdown",
}
STATUS_NL = {"developing": "in ontwikkeling", "triggered": "getriggerd (nog niet bevestigd)", "confirmed": "bevestigd",
             "failed": "mislukt"}
STATUS_RANK = {"confirmed": 3, "triggered": 2, "developing": 1, "failed": 0}


@dataclass
class Setup:
    kind: str
    direction: int                   # +1 long, -1 short
    status: str
    levels: dict[str, float] = field(default_factory=dict)
    evidence: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    trigger: str = ""
    trigger_price: float | None = None
    invalidation: str = ""
    invalidation_price: float | None = None
    tf_agree: list[str] = field(default_factory=list)
    tf_disagree: list[str] = field(default_factory=list)
    combos: list[str] = field(default_factory=list)
    families: set[str] = field(default_factory=set)
    quality: float = 0.0

    @property
    def name_nl(self) -> str:
        return SETUP_NL.get(self.kind, self.kind)

    @property
    def status_nl(self) -> str:
        return STATUS_NL.get(self.status, self.status)


def _recent_cross(c: np.ndarray, level: float, up: bool, within: int) -> int | None:
    n = len(c)
    for j in range(n - 1, max(n - 1 - within, 0), -1):
        if (up and c[j] > level >= c[j - 1]) or (not up and c[j] < level <= c[j - 1]):
            return j
    return None


def _post_break_status(fa: FrameAnalysis, j: int, level: float, up: bool) -> str:
    c = fa.df["close"].to_numpy()
    sgn = 1 if up else -1
    post = c[j:]
    if (sgn * (post - level) < 0).any():
        return "failed"
    # confirmation needs a bar AFTER the trigger bar (a second close beyond the level);
    # a volume thrust on the trigger bar is evidence, not confirmation
    return "confirmed" if len(post) >= 2 else "triggered"


def _volume_thrust(fa: FrameAnalysis, j: int, up: bool) -> bool:
    c, h, lo = (fa.df[k].to_numpy() for k in ("close", "high", "low"))
    rv = breakout_volume_ratio(fa.df, j)
    third = (c[j] - lo[j]) >= (2 / 3) * (h[j] - lo[j]) if up else (h[j] - c[j]) >= (2 / 3) * (h[j] - lo[j])
    return bool(np.isfinite(rv) and rv >= 1.5 and third)


def classify(fa: FrameAnalysis) -> list[Setup]:
    if not fa.ok:
        return []
    df, ind, tr, m, v, vo = fa.df, fa.ind, fa.trend, fa.momentum, fa.volume, fa.volatility
    c, h, lo = df["close"].to_numpy(), df["high"].to_numpy(), df["low"].to_numpy()
    n = len(df)
    t = n - 1
    close, atr = c[-1], fa.atr
    if not np.isfinite(atr) or atr <= 0:
        return []
    ema21, sma50 = ind.last("ema21"), ind.last("sma50")
    rsi14 = ind.last("rsi14")
    res, sup = nearest(fa.zones, close, "above"), nearest(fa.zones, close, "below")
    known = known_swings(fa.swings, t)
    last_low = next((s for s in reversed(known) if s.kind == "L"), None)
    last_high = next((s for s in reversed(known) if s.kind == "H"), None)
    bull_pats = [p for p in fa.patterns if p.direction == "bull"]
    bear_pats = [p for p in fa.patterns if p.direction == "bear"]
    events = fa.liquidity.events if fa.liquidity else []
    compression = bool(vo.squeeze_on or vo.contraction or vo.nr7 or vo.inside_bars >= 1
                       or (np.isfinite(vo.range10_atr) and vo.range10_atr <= 4))
    out: list[Setup] = []

    def add(s: Setup) -> None:
        out.append(s)

    swing_low_px = last_low.price if last_low else close - 2 * atr

    # 1 early breakout / 2 confirmed breakout -- from zones and bullish patterns
    if tr.direction >= 0:
        cand = []
        if res is not None and res.low - close <= atr:
            cand.append((f"{res.strength} weerstand {res.low:,.2f}-{res.high:,.2f}", res.high, res.score))
        for p in bull_pats:
            if p.status == "near":
                cand.append((f"{p.name} (trigger {p.trigger:,.2f})", p.trigger, p.quality))
        if cand and compression:
            what, trig, _ = max(cand, key=lambda x: x[2])
            ev = [f"Koers vlak onder {what}", "Compressie: " + ", ".join(
                x for x, ok in (("squeeze", vo.squeeze_on), ("volatiliteit krimpt", vo.contraction), ("NR7", vo.nr7),
                                (f"{vo.inside_bars} inside bar(s)", vo.inside_bars >= 1),
                                (f"10-daagse range {vo.range10_atr:.1f} ATR", np.isfinite(vo.range10_atr) and vo.range10_atr <= 4)) if ok)]
            lows_below = [x.price for x in reversed(known) if x.kind == "L" and x.price < close]
            inv = sup.low if sup is not None and close - sup.low < 3 * atr else (
                lows_below[0] if lows_below else float(lo[-10:].min()))
            add(Setup("early_breakout", 1, "developing", {"trigger": trig, "invalidatie": inv}, ev,
                      trigger=f"slot boven {trig:,.2f}", trigger_price=trig, invalidation=f"slot onder {inv:,.2f}",
                      invalidation_price=inv, families={"price_action", "sr", "volatility"}))
    broke = []
    for z in fa.zones:
        if z.high < close or containing([z], close):
            j = _recent_cross(c, z.high, True, 5)
            if j is not None:
                broke.append((f"{nl(z.strength)} weerstand {z.low:,.2f}-{z.high:,.2f}", z.high, j, z.low))
    for p in bull_pats:
        if p.status in ("breakout", "confirmed") and p.breakout_date is not None:
            j = df.index.get_loc(p.breakout_date)
            if t - j <= 5:
                broke.append((f"{p.name}", p.trigger, j, p.invalidation))
    if broke:
        # the breakout that started the move: earliest cross in the window (later crosses of nearby
        # pattern lines are the same move seen by another detector)
        what, lvl, j, inv = min(broke, key=lambda x: (x[2], -x[1]))
        st = _post_break_status(fa, j, lvl, True)
        rv = breakout_volume_ratio(df, j)
        ev = [f"Slot boven {what} ({lvl:,.2f}) op {df.index[j]:%d-%m}"]
        conf = []
        if np.isfinite(rv):
            (ev if rv >= 1.3 else conf).append(f"breakout-volume {rv:.1f}x het gemiddelde" + ("" if rv >= 1.3 else " -- zwak, verdacht"))
        if m.state in ("bullish", "strong_bullish"):
            ev.append(f"momentum bevestigt ({nl(m.state)}, RSI14 {rsi14:.0f})")
        else:
            conf.append(f"momentum bevestigt niet ({nl(m.state)})")
        if st == "failed":
            # the long failed: a SHORT with its own levels (first close back under, top of the attempt)
            k = j + int(np.flatnonzero(c[j:] < lvl)[0])
            top = float(h[j:k + 1].max())
            if close <= top:
                fst = "confirmed" if k < t and close < lvl else "triggered"
                add(Setup("failed_breakout", -1, fst, {"niveau": lvl, "top": top},
                          [f"Brak boven {what} ({lvl:,.2f}) op {df.index[j]:%d-%m} en sloot er op {df.index[k]:%d-%m} weer onder"]
                          + [x for x in conf if "volume" in x],
                          [x for x in ev[1:] if "momentum" in x],
                          trigger=f"slot terug onder {lvl:,.2f} (gebeurd op {df.index[k]:%d-%m}); bevestigd bij een volgend slot eronder",
                          trigger_price=lvl, invalidation=f"slot boven de top van de poging ({top:,.2f})",
                          invalidation_price=top, families={"price_action", "sr"}))
        else:
            if st == "triggered" and _volume_thrust(fa, j, True):
                ev.append("volume-uitbraak op de triggerdag (RVOL >= 1.5, slot in het bovenste derde) -- bevestiging volgt bij het volgende slot")
            add(Setup("confirmed_breakout", 1, st, {"breakout": lvl, "invalidatie": inv},
                      ev, conf, trigger=f"slot boven {lvl:,.2f}; bevestigd bij een tweede slot erboven", trigger_price=lvl,
                      invalidation=(f"slot terug onder {lvl:,.2f} = mislukte breakout; structureel ongeldig onder {inv:,.2f}"
                                    if np.isfinite(inv) and inv < lvl else f"slot terug onder {lvl:,.2f}"),
                      invalidation_price=inv if np.isfinite(inv) and inv < lvl else lvl,
                      families={"price_action", "sr", "volume", "momentum"}))

    # 3 breakout retest
    for p in bull_pats:
        if p.name == "break & retest" and p.status != "failed":
            st = {"confirmed": "confirmed", "breakout": "triggered"}.get(p.status, "developing")
            ev = [f"Breakout boven de zone, daarna hertest van de bovenkant ({p.lines[0][1]:,.2f}) zonder slot eronder"]
            if last_low is not None and last_low.label in ("HL", "EL") and last_low.i > df.index.get_loc(p.start):
                ev.append(f"hogere bodem op {last_low.date:%d-%m} ({last_low.price:,.2f})")
            add(Setup("breakout_retest", 1, st, {"retest-niveau": p.lines[0][1], "trigger": p.trigger, "invalidatie": p.invalidation},
                      ev, trigger=f"slot boven {p.trigger:,.2f} (hoogste van de retest-kaars)", trigger_price=p.trigger,
                      invalidation=f"slot onder {p.invalidation:,.2f}", invalidation_price=p.invalidation,
                      families={"price_action", "sr"}))
            break

    # 4/5 pullbacks in trend
    def touched(level: float) -> bool:
        return np.isfinite(level) and (np.abs(lo[-3:] - level) <= 0.5 * atr).any() if level < close + atr else False

    if tr.label in ("strong_uptrend", "weak_uptrend") and last_high is not None and last_high.price - close >= 1.5 * atr:
        where = [nm for nm, lv in (("EMA21", ema21), ("SMA50", sma50)) if touched(lv)]
        if sup is not None and (lo[-3:] <= sup.high + 0.3 * atr).any():
            where.append(f"steunzone {sup.low:,.2f}-{sup.high:,.2f}")
        if where and (not np.isfinite(sma50) or close >= sma50 - 0.5 * atr) and (not np.isfinite(rsi14) or 30 <= rsi14 <= 60):
            ev = [f"Pullback van {(last_high.price - close) / atr:.1f} ATR in een {tr.label_nl} naar " + " / ".join(where)]
            conf = []
            if v.available and v.pullback_contraction is not None:
                (ev if v.pullback_contraction else conf).append(
                    "volume droogt op in de pullback" if v.pullback_contraction else "volume krimpt niet in de pullback")
            # the turn: the latest bar (within 5) that closed above the previous bar's high
            turns = [k for k in range(max(t - 4, last_high.i + 1, 1), t + 1) if c[k] > h[k - 1]]
            hl = last_low is not None and last_low.label in ("HL", "EL") and last_low.i > last_high.i
            if turns and close > h[turns[-1] - 1]:
                k = turns[-1]
                trig = float(h[k - 1])
                st = "triggered" if k == t else "confirmed"     # confirmed = a later close still above the trigger
            else:
                trig, st = float(h[-1]), "developing"
            if hl:
                ev.append(f"hogere bodem bevestigd op {last_low.date:%d-%m}")
            inv = min(lo[-5:].min(), sup.low if sup is not None else lo[-5:].min())
            add(Setup("bullish_pullback", 1, st, {"trigger": trig, "invalidatie": inv, "EMA21": ema21}, ev, conf,
                      trigger=f"slot boven de top van de vorige kaars ({trig:,.2f})", trigger_price=trig,
                      invalidation=f"slot onder {inv:,.2f}", invalidation_price=inv, families={"trend", "sr", "volume"}))
    if tr.label in ("strong_downtrend", "weak_downtrend") and last_low is not None and close - last_low.price >= 1.5 * atr:
        where = [nm for nm, lv in (("EMA21", ema21), ("SMA50", sma50)) if np.isfinite(lv) and (np.abs(h[-3:] - lv) <= 0.5 * atr).any()]
        if res is not None and (h[-3:] >= res.low - 0.3 * atr).any():
            where.append(f"weerstandszone {res.low:,.2f}-{res.high:,.2f}")
        if where:
            turn = c[-1] < lo[-2]
            add(Setup("bearish_pullback", -1, "triggered" if turn else "developing",
                      {"trigger": float(lo[-1]), "invalidatie": float(h[-5:].max())},
                      [f"Opleving van {(close - last_low.price) / atr:.1f} ATR in een {tr.label_nl} naar " + " / ".join(where)],
                      trigger=f"slot onder {lo[-1]:,.2f}", trigger_price=float(lo[-1]),
                      invalidation=f"slot boven {h[-5:].max():,.2f}", invalidation_price=float(h[-5:].max()),
                      families={"trend", "sr"}))

    # 6 trend continuation
    if tr.label == "strong_uptrend" and tr.continuation and m.state in ("bullish", "strong_bullish") and \
            np.isfinite(tr.dist_atr["ema21"]) and tr.dist_atr["ema21"] <= 2.5:
        e = tr.last_event
        held = bool((c[e.i:] > e.level).all())          # every close since the BOS stayed above the level
        tc_st = ("confirmed" if held and e.i < t else "triggered" if close > e.level and (held or c[-2] <= e.level)
                 else "developing" if close <= e.level else "triggered")
        add(Setup("trend_continuation", 1, tc_st,
                  {"BOS-niveau": e.level, "EMA21": ema21, "invalidatie": swing_low_px},
                  [f"Bullish BOS op {e.date:%d-%m} (slot boven {e.level:,.2f}) in een sterke uptrend",
                   f"momentum {nl(m.state)}, koers {tr.dist_atr['ema21']:.1f} ATR boven de EMA21 (niet overstrekt)"],
                  [x for x in tr.exhaustion] + (["koers terug onder het BOS-niveau"] if close <= e.level else []),
                  trigger=f"BOS boven {e.level:,.2f} ({'vandaag' if e.i == t else 'gebeurd'}); bevestigd bij een volgend slot erboven",
                  trigger_price=e.level,
                  invalidation=f"slot onder de laatste swing low {swing_low_px:,.2f}", invalidation_price=swing_low_px,
                  families={"trend", "momentum"}))

    # 7 momentum reversal
    for dv in m.divergences:
        if dv.kind == "regular_bull" and dv.bars_ago <= 15 and np.isfinite(ema21) and close < ema21 + atr:
            ch = tr.last_event if (tr.last_event and tr.last_event.kind == "CHoCH" and tr.last_event.direction == "bull"
                                   and 0 < t - tr.last_event.i <= 10) else None
            st = ("failed" if close < dv.b.price else
                  "confirmed" if ch is not None and close > ema21 else ("triggered" if close > ema21 else "developing"))
            add(Setup("momentum_reversal", 1, st, {"swing low": dv.b.price, "EMA21": ema21}, [dv.describe()],
                      trigger=f"slot boven de EMA21 ({ema21:,.2f}), daarna een bullish CHoCH", trigger_price=ema21,
                      invalidation=f"slot onder {dv.b.price:,.2f}", invalidation_price=dv.b.price, families={"momentum"}))
            break
        if dv.kind == "regular_bear" and dv.bars_ago <= 15 and np.isfinite(ema21) and close > ema21 - atr:
            ch = tr.last_event if (tr.last_event and tr.last_event.kind == "CHoCH" and tr.last_event.direction == "bear"
                                   and 0 < t - tr.last_event.i <= 10) else None
            st = ("failed" if close > dv.b.price else
                  "confirmed" if ch is not None and close < ema21 else ("triggered" if close < ema21 else "developing"))
            add(Setup("momentum_reversal", -1, st, {"swing high": dv.b.price, "EMA21": ema21}, [dv.describe()],
                      trigger=f"slot onder de EMA21 ({ema21:,.2f})", trigger_price=ema21,
                      invalidation=f"slot boven {dv.b.price:,.2f}", invalidation_price=dv.b.price, families={"momentum"}))
            break

    # 8 mean reversion
    if tr.label != "strong_downtrend" and np.isfinite(ema21):
        stretch = (close - ema21) / atr
        bbl = ind.last("bb_lower")
        if stretch <= -2.5 or (np.isfinite(rsi14) and rsi14 <= 30) or (np.isfinite(bbl) and close < bbl):
            back = np.isfinite(bbl) and c[-2] < float(ind["bb_lower"].iloc[-2]) and close > bbl
            add(Setup("mean_reversion", 1, "triggered" if back else "developing", {"EMA21": ema21, "onderste BB": bbl},
                      [f"Uitgerekt onder het gemiddelde: {stretch:.1f} ATR onder de EMA21, RSI14 {rsi14:.0f}"],
                      ["tegenbeweging: werkt alleen als de grotere trend niet omlaag is"] if tr.direction < 0 else [],
                      trigger=f"slot terug boven de onderste Bollinger-band ({bbl:,.2f})", trigger_price=bbl,
                      invalidation=f"slot onder {lo[-5:].min():,.2f}", invalidation_price=float(lo[-5:].min()),
                      families={"momentum", "volatility"}))

    # 9 support bounce / 10 resistance rejection
    for z in fa.zones:
        if z.role in ("support", "flip_support", "at") and (lo[-3:] <= z.high + 0.3 * atr).any() and close > z.high:
            cs = [x for x in fa.candles if x.direction == "bull" and any("zone" in cx for cx in x.context)]
            st = "confirmed" if cs and cs[-1].confirmation == "confirmed" else ("triggered" if cs else "developing")
            ev = [f"Koers raakte {z.describe()} en sloot erboven"] + [f"{x.name_nl} ({x.significance}): {', '.join(x.context[:2])}" for x in cs[-1:]]
            add(Setup("support_bounce", 1, st, {"zone laag": z.low, "zone hoog": z.high}, ev,
                      [] if cs else ["nog geen bullish bevestigingskaars op de zone"],
                      trigger=f"slot boven {h[-1]:,.2f}", trigger_price=float(h[-1]),
                      invalidation=f"slot onder de zone ({z.low:,.2f})", invalidation_price=z.low, families={"sr", "candles"}))
            break
    for z in fa.zones:
        if z.role in ("resistance", "flip_resistance", "at") and (h[-3:] >= z.low - 0.3 * atr).any() and close < z.low:
            cs = [x for x in fa.candles if x.direction == "bear" and any("zone" in cx for cx in x.context)]
            st = "confirmed" if cs and cs[-1].confirmation == "confirmed" else ("triggered" if cs else "developing")
            add(Setup("resistance_rejection", -1, st, {"zone laag": z.low, "zone hoog": z.high},
                      [f"Koers raakte {z.describe()} en sloot eronder"] + [f"{x.name_nl} ({x.significance})" for x in cs[-1:]],
                      trigger=f"slot onder {lo[-1]:,.2f}", trigger_price=float(lo[-1]),
                      invalidation=f"slot boven de zone ({z.high:,.2f})", invalidation_price=z.high, families={"sr", "candles"}))
            break

    # 11 volatility squeeze
    if vo.squeeze_on and vo.squeeze_bars >= 5:
        d = 1 if tr.direction >= 0 else -1
        add(Setup("volatility_squeeze", d, "developing", {"Keltner boven": ind.last("kc_upper"), "Keltner onder": ind.last("kc_lower")},
                  [f"Bollinger binnen Keltner sinds {vo.squeeze_bars} bars -- volatiliteit samengedrukt, richting nog onbekend"],
                  trigger=f"slot {'boven' if d > 0 else 'onder'} de Keltner-band ({ind.last('kc_upper' if d > 0 else 'kc_lower'):,.2f})",
                  trigger_price=ind.last("kc_upper" if d > 0 else "kc_lower"),
                  invalidation="squeeze lost op in de andere richting", families={"volatility"}))
    elif vo.squeeze_fired:
        d = 1 if vo.squeeze_fired == "up" else -1
        add(Setup("volatility_squeeze", d, "triggered", {"Keltner midden": ind.last("kc_mid")},
                  [f"Squeeze net losgelaten naar {'boven' if d > 0 else 'beneden'}"],
                  trigger="tweede slot in dezelfde richting", invalidation=f"slot terug voorbij het Keltner-midden ({ind.last('kc_mid'):,.2f})",
                  invalidation_price=ind.last("kc_mid"), families={"volatility"}))

    # 12 failed breakout / 13 failed breakdown (from liquidity events, last 5 bars)
    for e in reversed(events):
        if t - e.i > 5:
            continue
        if e.kind in ("failed_breakout", "sweep_high") and not any(s.kind == "failed_breakout" for s in out):
            top = float(h[e.i:t].max()) if e.i < t else float(h[e.i])   # the sweep's top, not today's bar
            st = "failed" if close > top else ("confirmed" if c[-1] < lo[e.i] and e.i < t else "triggered")
            add(Setup("failed_breakout", -1, st, {"niveau": e.level, "top": top}, [e.note],
                      trigger=f"slot onder de low van {e.date:%d-%m} ({lo[e.i]:,.2f})", trigger_price=float(lo[e.i]),
                      invalidation=f"slot boven {top:,.2f}", invalidation_price=top,
                      families={"price_action", "sr"}))
        if e.kind in ("failed_breakdown", "sweep_low") and not any(s.kind == "failed_breakdown" for s in out):
            bottom = float(lo[e.i:t].min()) if e.i < t else float(lo[e.i])
            st = "failed" if close < bottom else ("confirmed" if c[-1] > h[e.i] and e.i < t else "triggered")
            ev = [e.note] + (["in een opwaartse structuur"] if tr.state == "up" else [])
            add(Setup("failed_breakdown", 1, st, {"niveau": e.level, "bodem": bottom}, ev,
                      trigger=f"slot boven de high van {e.date:%d-%m} ({h[e.i]:,.2f})", trigger_price=float(h[e.i]),
                      invalidation=f"slot onder {bottom:,.2f}", invalidation_price=bottom,
                      families={"price_action", "sr"}))

    # 14 potential trend reversal
    if tr.label in ("potential_reversal_up", "potential_reversal_down"):
        d = 1 if tr.label.endswith("up") else -1
        e = tr.last_event
        sma_prev = float(ind["sma50"].iloc[-2]) if n > 1 else np.nan
        cond = (close > sma50 and ind.last("sma50_slope") >= 0) if d > 0 else (close < sma50 and ind.last("sma50_slope") <= 0)
        sl_prev = float(ind["sma50_slope"].iloc[-2]) if n > 1 else np.nan
        prev = (c[-2] > sma_prev and sl_prev >= 0) if d > 0 else (c[-2] < sma_prev and sl_prev <= 0)
        broken = (close < e.level) if d > 0 else (close > e.level)
        pr_st = "failed" if broken else ("confirmed" if cond and prev else ("triggered" if cond else "developing"))
        add(Setup("potential_trend_reversal", d, pr_st,
                  {"CHoCH-niveau": e.level, "SMA50": sma50}, tr.reasons[:1],
                  [f"MA-volgorde nog {tr.alignment:+d}/4"] if tr.alignment * d < 2 else [],
                  trigger=f"slot {'boven' if d > 0 else 'onder'} de SMA50 met een {'stijgende' if d > 0 else 'dalende'} SMA50",
                  trigger_price=sma50, invalidation=f"slot {'onder' if d > 0 else 'boven'} {e.level:,.2f}",
                  invalidation_price=e.level, families={"trend"}))

    # bearish chart-pattern breakdowns
    for p in bear_pats:
        if p.status in ("breakout", "confirmed") and p.breakout_date is not None and t - df.index.get_loc(p.breakout_date) <= 5:
            add(Setup("breakdown", -1, "confirmed" if p.status == "confirmed" else "triggered",
                      {"breakdown": p.trigger, "invalidatie": p.invalidation},
                      [f"{p.name}: slot onder {p.trigger:,.2f} op {p.breakout_date:%d-%m}", p.volume],
                      trigger=f"slot onder {p.trigger:,.2f}", trigger_price=p.trigger,
                      invalidation=f"slot boven {p.invalidation:,.2f}", invalidation_price=p.invalidation,
                      families={"price_action"}))
            break

    _combos(fa, out)
    for s in out:
        if s.status in ("triggered", "confirmed") and tr.exhaustion and tr.direction == s.direction:
            s.conflicts += [f"trend overstrekt: {x}" for x in tr.exhaustion]
        against = "regular_bear" if s.direction > 0 else "regular_bull"
        if any(d.kind == against and d.bars_ago <= 15 for d in m.divergences):
            s.conflicts.append(f"recente {'bearish' if s.direction > 0 else 'bullish'} divergentie")
        if s.direction > 0 and res is not None and s.kind not in ("early_breakout", "confirmed_breakout") and res.low - close <= 0.75 * atr:
            s.conflicts.append(f"weerstand vlak erboven ({res.low:,.2f}, {(res.low - close) / atr:.1f} ATR)")
        if s.direction < 0 and sup is not None and s.kind != "breakdown" and close - sup.high <= 0.75 * atr:
            s.conflicts.append(f"steun vlak eronder ({sup.high:,.2f}, {(close - sup.high) / atr:.1f} ATR)")
        for e in events:
            still = (close < e.level) if s.direction > 0 else (close > e.level)
            if still and len(fa.df) - 1 - e.i <= 3 and ((s.direction > 0 and e.kind in ("sweep_high", "failed_breakout")) or
                                                        (s.direction < 0 and e.kind in ("sweep_low", "failed_breakdown"))):
                s.conflicts.append(e.note)
                break
        if v.available and v.climax and tr.direction == s.direction != 0:
            s.conflicts.append("climax-volume: vaak einde van een beweging")
    return out


def _combos(fa: FrameAnalysis, setups: list[Setup]) -> None:
    """Named multi-factor confluences: a COMPLETE setup, counted once."""
    tr, m, v, vo = fa.trend, fa.momentum, fa.volume, fa.volatility
    rsi = fa.ind["rsi14"]
    rsi_up = len(rsi) > 4 and np.isfinite(rsi.iloc[-1]) and rsi.iloc[-1] > rsi.iloc[-4]
    known = known_swings(fa.swings, len(fa.df) - 1)
    hl = any(s.kind == "L" and s.label in ("HL", "EL") for s in known[-3:])
    for s in setups:
        if s.kind == "confirmed_breakout":
            if any(p.name == "bull flag" and p.status in ("breakout", "confirmed") for p in fa.patterns) and \
                    tr.label == "strong_uptrend":
                s.combos.append("Bull flag + sterke uptrend + breakout" + (" + volume-expansie" if v.available and v.rvol >= 1.3 else ""))
            if (vo.squeeze_on or vo.squeeze_fired == "up" or vo.contraction) and v.available and v.rvol >= 1.5:
                s.combos.append("Volatiliteits-squeeze + weerstand-breakout + volume-expansie")
            if any(p.name == "double bottom" and p.status in ("breakout", "confirmed") for p in fa.patterns) and \
                    m.state in ("bullish", "strong_bullish"):
                s.combos.append("Double bottom + neckline-breakout + momentumbevestiging")
        if s.kind == "breakout_retest" and hl and rsi_up:
            s.combos.append("Break & retest + hogere bodem + stijgende RSI")
        if s.kind == "failed_breakdown" and tr.state == "up":
            s.combos.append("Liquidity sweep onder steun + reclaim + bullish structuur")
        if s.kind == "bullish_pullback" and any("EMA21" in e for e in s.evidence) and \
                any(x.direction == "bull" and x.significance != "low" for x in fa.candles):
            s.combos.append("Pullback naar EMA21 + bullish kaars (+ weektrend: zie multi-timeframe)")
