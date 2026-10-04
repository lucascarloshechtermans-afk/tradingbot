"""Chart patterns with boundaries, confirmation, invalidation, age, status,
volume confirmation and trend context.

Rules are measurable, not visual:
  * bullish shapes: analysis.patterns (ascending triangle, double bottom,
    inverse H&S, cup & handle, bull flag, flat base, VCP, falling wedge /
    descending channel / triangle, channel up, symmetric triangle, range)
  * bearish shapes: the SAME detectors run on the price-mirrored chart
    (p' = K / p, a monotone flip that turns tops into bottoms): a double top is
    a double bottom of the mirror, head & shoulders an inverse H&S, a bear flag
    a bull flag, a descending triangle an ascending triangle
  * pennant: a symmetric triangle of <= 20 bars after a pole of >= 3 ATR in
    <= 15 bars
  * rounded bottom: quadratic fit of 60/100/150 closes, curvature > 0, low in
    the middle 40%, R^2 >= 0.75, depth >= 12%, price back within 10% of the rim
  * break & retest: a close through a zone, a later touch of it from the
    other side within 0.5 ATR, and no close back through it

Status is decided on later closes (detection is re-run on the frame cut 0, 5
and 10 bars back): forming -> near trigger -> breakout (first close beyond the
trigger) -> confirmed (2+ closes beyond, none back inside) / failed (back
inside within 5 bars, or beyond the invalidation).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from analysis.patterns import detect_patterns
from ta.volume import breakout_volume_ratio

MIRROR_NAMES = {
    "double bottom": "double top", "inverse head & shoulders": "head & shoulders", "bull flag": "bear flag",
    "ascending triangle": "descending triangle", "falling wedge": "rising wedge", "descending channel": "ascending channel",
    "descending triangle": "ascending triangle (breakdown)", "cup & handle": "inverted cup & handle",
    "channel up strong breakout": "channel down breakdown", "symmetric triangle": "symmetric triangle",
    "horizontal range": "horizontal range", "flat base": "flat top",
}
CONTINUATION = {"bull flag", "bear flag", "flat base", "flat top", "ascending triangle", "descending triangle", "VCP",
                "cup & handle", "channel up bounce", "channel up strong breakout", "pennant", "symmetric triangle",
                "horizontal range", "break & retest"}
STATUS_NL = {"forming": "in vorming", "near": "vlak bij trigger", "breakout": "breakout (nog niet bevestigd)",
             "confirmed": "bevestigd", "failed": "mislukt"}


@dataclass
class ChartPattern:
    name: str
    direction: str                 # bull | bear
    trigger: float                 # close beyond it = breakout
    invalidation: float
    target: float
    start: pd.Timestamp
    end: pd.Timestamp              # last bar used to define it
    age: int                       # bars from start to the last bar
    status: str                    # forming | near | breakout | confirmed | failed
    breakout_date: pd.Timestamp | None = None
    volume: str = "n/a"
    trend_context: str = ""
    rule: str = ""
    lines: list[tuple[pd.Timestamp, float, pd.Timestamp, float]] = field(default_factory=list)
    quality: float = 0.0           # 0..100

    @property
    def status_nl(self) -> str:
        return STATUS_NL.get(self.status, self.status)


def _mirror(df: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    k = float(df["close"].iloc[-1]) ** 2
    m = pd.DataFrame({"open": k / df["open"], "high": k / df["low"], "low": k / df["high"], "close": k / df["close"],
                      "volume": df["volume"]}, index=df.index)
    return m, k


def _hits(df: pd.DataFrame, direction: str) -> list[dict]:
    if direction == "bull":
        src, k = df, None
    else:
        src, k = _mirror(df)
    out = []
    for h in detect_patterns(src):
        name = h.name if direction == "bull" else MIRROR_NAMES.get(h.name)
        if name is None:
            continue
        tr, inv, tg = h.trigger, h.invalidation, h.target
        lines = h.lines
        if k is not None:
            tr, inv, tg = k / tr, k / inv, k / tg
            lines = [(a, k / pa, b, k / pb) for a, pa, b, pb in lines]
        out.append({"name": name, "trigger": tr, "invalidation": inv, "target": tg, "start": h.start, "bars": h.bars,
                    "lines": lines})
    return out


def _pennant(df: pd.DataFrame, atr: float, hit: dict, direction: str) -> bool:
    if hit["name"] != "symmetric triangle" or hit["bars"] > 20:
        return False
    i0 = df.index.get_loc(hit["start"])
    pole = df["close"].iloc[max(0, i0 - 15):i0 + 1]
    if len(pole) < 5 or not np.isfinite(atr):
        return False
    move = (pole.iloc[-1] - pole.min()) if direction == "bull" else (pole.max() - pole.iloc[-1])
    return bool(move >= 3 * atr)


def rounded_bottom(df: pd.DataFrame) -> dict | None:
    c = df["close"].to_numpy()
    for w in (150, 100, 60):
        if len(c) < w + 1:
            continue
        y = c[-w - 1:-1]
        x = np.linspace(0, 1, w)
        a, b, d = np.polyfit(x, y, 2)
        fit = a * x ** 2 + b * x + d
        ss = ((y - y.mean()) ** 2).sum()
        r2 = 1 - ((y - fit) ** 2).sum() / ss if ss > 0 else 0
        vx = -b / (2 * a) if a != 0 else -1
        rim = df["high"].iloc[-w - 1:-w - 1 + max(3, w // 7)].max()
        low = y.min()
        if a > 0 and 0.3 <= vx <= 0.7 and r2 >= 0.75 and (rim - low) / rim >= 0.12 and 0.9 * rim <= c[-1] <= 1.08 * rim:
            start = df.index[-w - 1]
            return {"name": "rounded bottom", "trigger": float(rim), "invalidation": float(df["low"].iloc[-w // 3:].min()),
                    "target": float(rim + (rim - low)), "start": start, "bars": w,
                    "lines": [(start, float(rim), df.index[-1], float(rim))], "r2": r2}
    return None


def break_and_retest(df: pd.DataFrame, zones: list, atr: float, max_age: int = 30) -> list[dict]:
    out = []
    c, h, lo = df["close"].to_numpy(), df["high"].to_numpy(), df["low"].to_numpy()
    n = len(df)
    if not np.isfinite(atr):
        return out
    for z in zones:
        for j in range(n - 1, max(n - max_age, 1), -1):
            up = c[j] > z.high and c[j - 1] <= z.high
            dn = c[j] < z.low and c[j - 1] >= z.low
            if not (up or dn):
                continue
            after = slice(j + 1, n)
            if up and (c[after] >= z.low).all() and len(c[after]) and (lo[after] <= z.high + 0.5 * atr).any():
                r = j + 1 + int(np.argmax(lo[after] <= z.high + 0.5 * atr))
                out.append({"name": "break & retest", "dir": "bull", "trigger": float(h[r]), "invalidation": float(z.low),
                            "target": float(c[j] + (c[j] - z.low) * 2), "start": df.index[j], "bars": n - 1 - j,
                            "lines": [(df.index[j], z.high, df.index[-1], z.high), (df.index[j], z.low, df.index[-1], z.low)],
                            "retest_i": r})
            if dn and (c[after] <= z.high).all() and len(c[after]) and (h[after] >= z.low - 0.5 * atr).any():
                r = j + 1 + int(np.argmax(h[after] >= z.low - 0.5 * atr))
                out.append({"name": "break & retest", "dir": "bear", "trigger": float(lo[r]), "invalidation": float(z.high),
                            "target": float(c[j] - (z.high - c[j]) * 2), "start": df.index[j], "bars": n - 1 - j,
                            "lines": [(df.index[j], z.high, df.index[-1], z.high), (df.index[j], z.low, df.index[-1], z.low)],
                            "retest_i": r})
            break
    return out


def _status(df: pd.DataFrame, cut: int, trig: float, inv: float, direction: str, atr: float) -> tuple[str, int | None]:
    c = df["close"].to_numpy()
    sgn = 1 if direction == "bull" else -1
    after = c[cut + 1:]
    beyond = sgn * (after - trig) > 0
    if beyond.any():
        b = cut + 1 + int(np.argmax(beyond))
        post = c[b:]
        if (sgn * (post - inv) < 0).any() or (len(post) > 1 and (sgn * (post[1:6] - trig) < 0).any()):
            return "failed", b
        return ("confirmed" if len(post) >= 3 else "breakout"), b
    if (sgn * (after - inv) < 0).any():
        return "failed", None
    last = c[-1]
    dist = sgn * (trig - last)
    return ("near" if np.isfinite(atr) and dist <= 1.0 * atr else "forming"), None


def find_patterns(df: pd.DataFrame, atr: pd.Series, zones: list, trend_direction: int, volume_ok: bool,
                  cuts: tuple[int, ...] = (0, 5, 10)) -> list[ChartPattern]:
    n = len(df)
    a_now = float(atr.iloc[-1])
    found: dict[tuple[str, str], ChartPattern] = {}
    for back in cuts:
        if n - back < 80:
            continue
        sub = df.iloc[:n - back] if back else df
        cut = n - back - 1
        hits = []
        for direction in ("bull", "bear"):
            for hd in _hits(sub, direction):
                hd["dir"] = direction
                if _pennant(sub, a_now, hd, direction):
                    hd["name"] = "pennant"
                hits.append(hd)
        rb = rounded_bottom(sub)
        if rb:
            rb["dir"] = "bull"
            hits.append(rb)
        for hd in hits:
            key = (hd["name"], hd["dir"])
            if key in found:
                continue
            # detect_patterns judges the last bar of `sub` against the trigger: the shape is
            # built on sub[:-1], so the status walk starts at the bar before `cut`
            status, b = _status(df, cut - 1, hd["trigger"], hd["invalidation"], hd["dir"], a_now)
            if back and status in ("forming", "near"):
                continue  # still forming: the cut-0 detection (if any) describes it better
            found[key] = _make(df, hd, status, b, trend_direction, volume_ok)
    for hd in break_and_retest(df, zones, a_now):
        key = (hd["name"], hd["dir"])
        if key in found:
            continue
        r = hd["retest_i"]
        status, b = _status(df, r, hd["trigger"], hd["invalidation"], hd["dir"], a_now)
        found[key] = _make(df, hd, status, b, trend_direction, volume_ok)
    last = float(df["close"].iloc[-1])
    keep = []
    for p in found.values():
        dist = abs(p.trigger - last)
        if p.status in ("forming", "near") and (dist > 4 * a_now or dist / last > 0.10):
            continue  # trigger too far away to be a setup now
        if p.status in ("failed", "confirmed", "breakout") and p.breakout_date is not None and \
                len(df) - 1 - df.index.get_loc(p.breakout_date) > 15:
            continue  # old news
        if p.status == "failed" and p.breakout_date is None:
            continue  # broke the invalidation without ever triggering
        keep.append(p)
    return sorted(keep, key=lambda p: (p.status != "confirmed", p.status != "breakout", -p.quality))


def _make(df, hd, status, b, trend_direction, volume_ok) -> ChartPattern:
    d = hd["dir"]
    start = hd["start"]
    age = len(df) - 1 - df.index.get_loc(start)
    vol = "n/a"
    if volume_ok and b is not None:
        r = breakout_volume_ratio(df, b)
        if np.isfinite(r):
            vol = (f"bevestigd: breakout-volume {r:.1f}x het gemiddelde van de 20 dagen ervoor" if r >= 1.3
                   else f"verdacht: breakout op maar {r:.1f}x het gemiddelde volume")
    elif volume_ok:
        i0 = df.index.get_loc(start)
        base = df["volume"].iloc[i0:].astype(float)
        if len(base) >= 9:
            third = len(base) // 3
            ratio = base.iloc[-third:].mean() / max(base.iloc[:third].mean(), 1e-9)
            vol = (f"volume krimpt in de basis ({ratio:.2f}x)" if ratio < 0.85 else f"volume krimpt niet in de basis ({ratio:.2f}x)")
    cont = hd["name"] in CONTINUATION
    want = 1 if d == "bull" else -1
    if trend_direction == want:
        ctx = "voortzettingspatroon met de trend mee" if cont else "keerpatroon, maar de trend wijst al deze kant op"
    elif trend_direction == -want:
        ctx = "tegen de trend in" + (" (keerpatroon na een beweging de andere kant op)" if not cont else " -- minder betrouwbaar")
    else:
        ctx = "trend zijwaarts"
    q = 40.0
    q += 20 if trend_direction == want and cont else (10 if trend_direction == -want and not cont else 0)
    q += 15 if vol.startswith("bevestigd") or vol.startswith("volume krimpt in") else (-10 if vol.startswith("verdacht") else 0)
    q += {"confirmed": 20, "breakout": 10, "near": 5, "forming": 0, "failed": -30}[status]
    q += 5 if 15 <= age <= 120 else 0
    rule = {
        "pennant": "symmetrische driehoek <= 20 bars na een vlaggenstok >= 3 ATR",
        "rounded bottom": "kwadratische fit, R2 >= 0.75, laagste punt in het midden, diepte >= 12%",
        "break & retest": "slot door een zone, later van de andere kant geraakt binnen 0,5 ATR, niet terug doorgesloten",
    }.get(hd["name"], "analysis.patterns-regel" + (" op de gespiegelde grafiek" if d == "bear" else ""))
    return ChartPattern(name=hd["name"], direction=d, trigger=float(hd["trigger"]), invalidation=float(hd["invalidation"]),
                        target=float(hd["target"]), start=start, end=df.index[-1], age=int(age), status=status,
                        breakout_date=df.index[b] if b is not None else None, volume=vol, trend_context=ctx, rule=rule,
                        lines=list(hd.get("lines", [])), quality=float(np.clip(q, 0, 100)))
