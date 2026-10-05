"""Interactive technical chart for a ta.engine.TechnicalReport.

One SVG per pane sharing the same x-scale: price (candles, moving averages,
Bollinger Bands, zones, pattern lines, setup levels, swing labels, BOS/CHoCH
markers), volume + RVOL, RSI, MACD, ADX, ATR. Every overlay is a <g data-layer>
and every pane an element with data-pane; the checkbox bar toggles them with a
few lines of JS. Markers carry a <title> with the rule and the candle date that
produced them, so every annotation is traceable to the bars behind it.
"""

from __future__ import annotations

from html import escape

import numpy as np
import pandas as pd

UP, DOWN = "#2b8a3e", "#c92a2a"
MA_STYLE = {  # key: (color, default on)
    "ema9": ("#22b8cf", False), "ema21": ("#f08c00", True), "ema34": ("#e64980", False), "ema50": ("#2f9e44", False),
    "ema200": ("#7048e8", False), "sma10": ("#74c0fc", False), "sma20": ("#ffa94d", False), "sma50": ("#37b24d", True),
    "sma100": ("#9775fa", False), "sma200": ("#5f3dc4", True),
}
LAYERS = [("zones", "Zones", True), ("patterns", "Patronen", True), ("levels", "Setup-niveaus", True),
          ("swings", "Swings HH/HL", True), ("structure", "BOS/CHoCH", True), ("bb", "Bollinger", False)] + \
    [(k, k.upper(), on) for k, (_, on) in MA_STYLE.items()]
PANES = [("volume", "Volume/RVOL", True), ("rsi", "RSI", True), ("macd", "MACD", False), ("adx", "ADX", False),
         ("atr", "ATR", False)]
PANE_ON = {k: on for k, _, on in PANES}
_uid = [0]


def _fmt(v: float) -> str:
    return f"{v:,.2f}"


def render(report, bars: int = 160, width: int = 980) -> str:
    fa = report.daily
    if not fa.ok:
        return ""
    _uid[0] += 1
    cid = f"tac{_uid[0]}"
    df, ind = fa.df, fa.ind
    n_all = len(df)
    d = df.iloc[-bars:]
    off = n_all - len(d)
    n = len(d)
    pad_l, pad_r = 8, 72
    extra = 12
    plot_w = width - pad_l - pad_r
    step = plot_w / (n + extra)

    def x(i: float) -> float:
        return pad_l + (i - off + 0.5) * step

    def in_view(i: int) -> bool:
        return i >= off

    # ---------- price pane
    H, top, bot = 420, 14, 22
    lo, hi = float(d["low"].min()), float(d["high"].max())
    span = hi - lo
    lo, hi = lo - 0.06 * span, hi + 0.08 * span

    def y(p: float) -> float:
        return top + (hi - p) / (hi - lo) * (H - top - bot)

    g = {k: [] for k, _, _ in LAYERS}
    base = [f'<rect x="0" y="0" width="{width}" height="{H}" fill="#fff"/>']
    for k in range(5):
        p = lo + (hi - lo) * k / 4
        base.append(f'<line x1="{pad_l}" x2="{width - pad_r}" y1="{y(p):.1f}" y2="{y(p):.1f}" stroke="#eee"/>'
                    f'<text x="{width - pad_r + 4}" y="{y(p) + 4:.1f}" font-size="10" fill="#868e96">{_fmt(p)}</text>')
    last_c = float(df["close"].iloc[-1])
    near_z = sorted([z for z in fa.zones if z.high < last_c], key=lambda z: -z.high)[:3] + \
        sorted([z for z in fa.zones if z.high >= last_c], key=lambda z: z.low)[:3]
    for z in near_z:
        if z.high < lo or z.low > hi:
            continue
        col = "#2f9e44" if z.role in ("support", "flip_support") else ("#e03131" if z.role in ("resistance", "flip_resistance") else "#868e96")
        op = 0.22 if z.strength == "strong" else 0.10
        tip = (f"{z.describe()}; bronnen: {', '.join(z.sources)}; scoredelen: "
               + ", ".join(f"{k} {v:g}" for k, v in z.score_parts.items() if v))
        g["zones"].append(f'<rect x="{pad_l}" width="{plot_w}" y="{y(z.high):.1f}" height="{max(y(z.low) - y(z.high), 1.5):.1f}" '
                          f'fill="{col}" fill-opacity="{op}"><title>{escape(tip)}</title></rect>')
    bu, bl = ind["bb_upper"].to_numpy(), ind["bb_lower"].to_numpy()
    pts_u = " ".join(f"{x(i):.1f},{y(bu[i]):.1f}" for i in range(off, n_all) if np.isfinite(bu[i]))
    pts_l = " ".join(f"{x(i):.1f},{y(bl[i]):.1f}" for i in range(off, n_all) if np.isfinite(bl[i]))
    g["bb"].append(f'<polyline points="{pts_u}" fill="none" stroke="#adb5bd" stroke-dasharray="3,3"/>'
                   f'<polyline points="{pts_l}" fill="none" stroke="#adb5bd" stroke-dasharray="3,3"/>')
    for key, (col, _) in MA_STYLE.items():
        s = ind[key].to_numpy()
        pts = " ".join(f"{x(i):.1f},{y(s[i]):.1f}" for i in range(off, n_all) if np.isfinite(s[i]) and lo <= s[i] <= hi)
        if pts:
            g[key].append(f'<polyline points="{pts}" fill="none" stroke="{col}" stroke-width="1.6"><title>{key.upper()}</title></polyline>')
    candles = []
    o, h, l_, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    w = max(step * 0.6, 1)
    for i in range(off, n_all):
        col = UP if c[i] >= o[i] else DOWN
        candles.append(f'<line x1="{x(i):.1f}" x2="{x(i):.1f}" y1="{y(h[i]):.1f}" y2="{y(l_[i]):.1f}" stroke="{col}"/>'
                       f'<rect x="{x(i) - w / 2:.1f}" width="{w:.1f}" y="{y(max(o[i], c[i])):.1f}" '
                       f'height="{max(abs(y(o[i]) - y(c[i])), 1):.1f}" fill="{col}"><title>{df.index[i]:%d-%m-%Y} O {_fmt(o[i])} '
                       f'H {_fmt(h[i])} L {_fmt(l_[i])} C {_fmt(c[i])}</title></rect>')
    for s in [s for s in fa.swings if in_view(s.i) and s.label][-14:]:
        if not in_view(s.i) or not s.label:
            continue
        yy = y(s.price) - 6 if s.kind == "H" else y(s.price) + 13
        g["swings"].append(f'<text x="{x(s.i):.1f}" y="{yy:.1f}" font-size="9" text-anchor="middle" fill="#495057">{s.label}'
                           f'<title>swing {"high" if s.kind == "H" else "low"} {s.date:%d-%m-%Y} {_fmt(s.price)}, bevestigd '
                           f'op {df.index[s.known_at]:%d-%m-%Y} ({s.known_at - s.i} bars later)</title></text>')
    for e in [e for e in fa.events if in_view(e.i)][-8:]:
        if e.i - e.swing_i > 400:
            continue
        col = UP if e.direction == "bull" else DOWN
        x0 = x(max(e.swing_i, off))
        g["structure"].append(
            f'<line x1="{x0:.1f}" x2="{x(e.i):.1f}" y1="{y(e.level):.1f}" y2="{y(e.level):.1f}" stroke="{col}" stroke-dasharray="2,2"/>'
            f'<text x="{x(e.i):.1f}" y="{y(e.level) - 3:.1f}" font-size="9" fill="{col}" text-anchor="end">{e.kind}'
            f'<title>{e.kind} {"bullish" if e.direction == "bull" else "bearish"}: slot {df.index[e.i]:%d-%m-%Y} '
            f'{"boven" if e.direction == "bull" else "onder"} de swing van {df.index[e.swing_i]:%d-%m-%Y} ({_fmt(e.level)})</title></text>')
    idx_pos = {ts: k for k, ts in enumerate(df.index)}
    for k, p in enumerate(fa.patterns[:3]):
        col = ["#e8590c", "#9c36b5", "#1971c2", "#2b8a3e"][k % 4]
        tip = (f"{p.name} ({'bullish' if p.direction == 'bull' else 'bearish'}), {p.status_nl}; start {p.start:%d-%m-%Y}, "
               f"{p.age} bars; trigger {_fmt(p.trigger)}, invalidatie {_fmt(p.invalidation)}; volume: {p.volume}; regel: {p.rule}")
        for (ta, pa, tb, pb) in p.lines:
            ia, ib = idx_pos.get(pd.Timestamp(ta)), idx_pos.get(pd.Timestamp(tb))
            if ia is None or ib is None or ib < off:
                continue
            g["patterns"].append(f'<line x1="{x(max(ia, off)):.1f}" x2="{x(ib):.1f}" y1="{y(pa if ia >= off else pa + (pb - pa) * (off - ia) / max(ib - ia, 1)):.1f}" '
                                 f'y2="{y(pb):.1f}" stroke="{col}" stroke-width="2"><title>{escape(tip)}</title></line>')
        g["patterns"].append(f'<text x="{pad_l + 4}" y="{top + 10 + 12 * k}" font-size="10.5" font-weight="600" fill="{col}">'
                             f'{escape(p.name)} ({escape(p.status_nl)})<title>{escape(tip)}</title></text>')
    prim = report.primary
    if prim is not None:
        for label, px, col in (("TRIGGER", prim.trigger_price, "#1971c2"), ("INVALIDATIE", prim.invalidation_price, "#c92a2a")):
            if px is not None and np.isfinite(px) and lo <= px <= hi:
                g["levels"].append(f'<line x1="{pad_l}" x2="{width - pad_r}" y1="{y(px):.1f}" y2="{y(px):.1f}" stroke="{col}" '
                                   f'stroke-width="1.4" stroke-dasharray="6,3"/><text x="{width - pad_r - 4}" y="{y(px) - 3:.1f}" '
                                   f'font-size="10" text-anchor="end" fill="{col}">{label} {_fmt(px)}</text>')
    last = c[-1]
    base.append(f'<line x1="{pad_l}" x2="{width - pad_r}" y1="{y(last):.1f}" y2="{y(last):.1f}" stroke="#495057" stroke-dasharray="1,3"/>'
                f'<rect x="{width - pad_r + 1}" y="{y(last) - 8:.1f}" width="{pad_r - 2}" height="16" fill="#343a40"/>'
                f'<text x="{width - pad_r + 4}" y="{y(last) + 4:.1f}" font-size="10" fill="#fff">{_fmt(last)}</text>')
    for k in range(0, n, max(n // 6, 1)):
        base.append(f'<text x="{x(off + k):.1f}" y="{H - 6}" font-size="10" fill="#868e96" text-anchor="middle">{d.index[k]:%d-%m-%y}</text>')
    layers_svg = "".join(f'<g data-layer="{k}"{"" if on else " style=display:none"}>{"".join(g[k])}</g>' for k, _, on in LAYERS)
    price = (f'<svg viewBox="0 0 {width} {H}" style="width:100%;height:auto;display:block" xmlns="http://www.w3.org/2000/svg">'
             + "".join(base) + layers_svg + "".join(candles) + "</svg>")

    # ---------- indicator panes
    def pane(key: str, series: list[tuple[np.ndarray, str, str]], lo_: float, hi_: float, refs=(), bars_=None, label="") -> str:
        PH = 90
        def yy(v):
            return 6 + (hi_ - v) / (hi_ - lo_) * (PH - 14) if hi_ > lo_ else PH / 2
        parts = [f'<rect x="0" y="0" width="{width}" height="{PH}" fill="#fff"/>',
                 f'<text x="{pad_l + 2}" y="14" font-size="10" fill="#495057">{escape(label)}</text>']
        for r in refs:
            parts.append(f'<line x1="{pad_l}" x2="{width - pad_r}" y1="{yy(r):.1f}" y2="{yy(r):.1f}" stroke="#dee2e6"/>'
                         f'<text x="{width - pad_r + 4}" y="{yy(r) + 4:.1f}" font-size="9" fill="#868e96">{r:g}</text>')
        if bars_ is not None:
            vals, cols = bars_
            for i in range(off, n_all):
                v = vals[i]
                if np.isfinite(v):
                    parts.append(f'<rect x="{x(i) - w / 2:.1f}" width="{w:.1f}" y="{min(yy(v), yy(0)):.1f}" '
                                 f'height="{abs(yy(v) - yy(0)):.1f}" fill="{cols[i]}" fill-opacity="0.6"/>')
        for vals, col, name in series:
            pts = " ".join(f"{x(i):.1f},{yy(vals[i]):.1f}" for i in range(off, n_all) if np.isfinite(vals[i]))
            parts.append(f'<polyline points="{pts}" fill="none" stroke="{col}" stroke-width="1.4"><title>{name}</title></polyline>')
        disp = "block" if PANE_ON[key] else "none"
        return (f'<svg data-pane="{key}" viewBox="0 0 {width} {PH}" style="width:100%;height:auto;display:{disp}" '
                f'xmlns="http://www.w3.org/2000/svg">' + "".join(parts) + "</svg>")

    view = slice(off, n_all)
    panes = {}
    if "rvol" in ind:
        v = df["volume"].to_numpy(dtype=float)
        cols = [UP if c[i] >= o[i] else DOWN for i in range(n_all)]
        rv = ind["rvol"].to_numpy()
        vmax = np.nanmax(v[view]) or 1
        scaled_rv = rv * np.nanmean(v[view]) if np.isfinite(np.nanmean(v[view])) else rv
        panes["volume"] = pane("volume", [(scaled_rv, "#1971c2", "RVOL x gemiddeld volume")], 0, vmax * 1.05,
                               bars_=(v, cols), label=f"Volume (balken) en RVOL-lijn; RVOL nu {ind.last('rvol'):.2f}")
    else:
        panes["volume"] = ('<div data-pane="volume" style="font-size:12px;color:#868e96;padding:4px 8px">'
                           'Volume niet beschikbaar voor dit instrument</div>')
    panes["rsi"] = pane("rsi", [(ind["rsi14"].to_numpy(), "#7048e8", "RSI14"), (ind["rsi7"].to_numpy(), "#ced4da", "RSI7")],
                        0, 100, refs=(30, 50, 70), label=f"RSI14 {ind.last('rsi14'):.0f} (grijs: RSI7)")
    mh = ind["macd_hist"].to_numpy()
    mm = max(np.nanmax(np.abs(ind["macd"].to_numpy()[view])), 1e-9)
    panes["macd"] = pane("macd", [(ind["macd"].to_numpy(), "#1971c2", "MACD"), (ind["macd_signal"].to_numpy(), "#f08c00", "signaal")],
                         -mm * 1.1, mm * 1.1, refs=(0,), bars_=(mh, [UP if (np.isfinite(t) and t >= 0) else DOWN for t in mh]),
                         label="MACD 12/26/9 (balken: histogram)")
    panes["adx"] = pane("adx", [(ind["adx"].to_numpy(), "#343a40", "ADX"), (ind["plus_di"].to_numpy(), UP, "+DI"),
                                (ind["minus_di"].to_numpy(), DOWN, "-DI")], 0, 60, refs=(20, 40),
                        label=f"ADX {ind.last('adx'):.0f} (+DI groen, -DI rood)")
    at = ind["atr"].to_numpy()
    panes["atr"] = pane("atr", [(at, "#495057", "ATR14")], 0, np.nanmax(at[view]) * 1.1, label=f"ATR14 {ind.last('atr'):,.2f} "
                        f"({ind.last('atr_pct'):.1f}%)")
    pane_html = "".join(panes[k] for k, _, _ in PANES)
    boxes = "".join(f'<label><input type="checkbox" data-t="layer" value="{k}"{" checked" if on else ""}> {escape(lbl)}</label>'
                    for k, lbl, on in LAYERS)
    boxes += "".join(f'<label><input type="checkbox" data-t="pane" value="{k}"{" checked" if on else ""}> {escape(lbl)}</label>'
                     for k, lbl, on in PANES)
    js = ("<script>(function(){var r=document.getElementById('%s');r.querySelectorAll('input').forEach(function(b){"
          "b.addEventListener('change',function(){var s=b.dataset.t==='layer'?'[data-layer=\"'+b.value+'\"]':'[data-pane=\"'+b.value+'\"]';"
          "r.querySelectorAll(s).forEach(function(e){e.style.display=b.checked?(b.dataset.t==='pane'?'block':''):'none';});});});})();</script>" % cid)
    return (f'<div class="tachart" id="{cid}"><div class="tatoggles">{boxes}</div>{price}{pane_html}</div>{js}')


CHART_CSS = (".tachart{background:#fff;border-radius:6px;padding:4px;margin-top:8px}"
             ".tatoggles{display:flex;flex-wrap:wrap;gap:4px 12px;font-size:11.5px;color:#343a40;padding:4px 6px}"
             ".tatoggles label{cursor:pointer;white-space:nowrap}")
