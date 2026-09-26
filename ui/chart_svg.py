"""Self-contained SVG chart of a ChartRead: candles, daily EMAs 9/21/50/200,
support/resistance zones, the wedge/channel trendlines, the 4H 200 EMA level
and the read's headlines -- drawn like a trader's annotated TradingView chart.
No plotting dependency: plain SVG, embeddable in the dashboard HTML."""

from __future__ import annotations

from html import escape

import pandas as pd

from analysis.chart_read import DAILY_EMAS, ChartRead
from indicators.trend import ema

EMA_COLORS = {9: "#22b8cf", 21: "#f08c00", 50: "#2f9e44", 200: "#7048e8"}
UP, DOWN = "#12b886", "#e03131"
LINE = "#364fc7"


def render_chart_svg(daily: pd.DataFrame, read: ChartRead, bars: int = 200, width: int = 980, height: int = 520) -> str:
    full = daily.dropna(subset=["open", "high", "low", "close"])
    emas = {w: ema(full["close"], w) for w in DAILY_EMAS}
    d = full.iloc[-bars:]
    offset = len(full) - len(d)
    n = len(d)
    pad_l, pad_r, pad_t, pad_b = 10, 70, 18, 26
    extra = 25  # empty bars to the right, room for projected lines
    lo = float(d["low"].min())
    hi = float(d["high"].max())
    if read.ema200_4h:
        lo, hi = min(lo, read.ema200_4h), max(hi, read.ema200_4h)
    span = hi - lo
    lo, hi = lo - span * 0.05, hi + span * 0.08
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b
    step = plot_w / (n + extra)

    def x(i: float) -> float:
        return pad_l + (i + 0.5) * step

    def y(p: float) -> float:
        return pad_t + (hi - p) / (hi - lo) * plot_h

    out = [f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" '
           f'style="width:100%;height:auto;background:var(--chart-bg,#fff);font-family:system-ui,sans-serif">']
    # zones
    below = sorted([z for z in read.zones if z.high <= read.close], key=lambda z: -z.high)[:3]
    above = sorted([z for z in read.zones if z.high > read.close], key=lambda z: z.low)[:3]
    for z in below + above:
        if z.high < lo or z.low > hi:
            continue
        is_support = z.high <= read.close
        fill = "#12b886" if is_support else "#e03131"
        out.append(f'<rect x="{pad_l}" y="{y(min(z.high, hi)):.1f}" width="{plot_w}" '
                   f'height="{max(2.0, y(max(z.low, lo)) - y(min(z.high, hi))):.1f}" fill="{fill}" fill-opacity="0.16"/>')
    # price grid labels
    for k in range(6):
        p = lo + (hi - lo) * k / 5
        out.append(f'<text x="{width - pad_r + 6}" y="{y(p) + 4:.1f}" font-size="11" fill="#868e96">{p:.2f}</text>')
    # candles
    for i, (_, row) in enumerate(d.iterrows()):
        up = row["close"] >= row["open"]
        col = UP if up else DOWN
        out.append(f'<line x1="{x(i):.1f}" x2="{x(i):.1f}" y1="{y(row["high"]):.1f}" y2="{y(row["low"]):.1f}" stroke="{col}" stroke-width="1"/>')
        top, bot = max(row["open"], row["close"]), min(row["open"], row["close"])
        out.append(f'<rect x="{x(i) - step * 0.35:.1f}" y="{y(top):.1f}" width="{step * 0.7:.1f}" '
                   f'height="{max(1.0, y(bot) - y(top)):.1f}" fill="{col}"/>')
    # EMAs
    for w, series in emas.items():
        s = series.iloc[-bars:]
        pts = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(s.values) if pd.notna(v) and lo <= v <= hi)
        if pts:
            out.append(f'<polyline points="{pts}" fill="none" stroke="{EMA_COLORS[w]}" stroke-width="{1.8 if w == 200 else 1.2}"/>')
    # trendlines of the pattern, projected to the right edge
    if read.pattern is not None:
        for line in (read.pattern.upper, read.pattern.lower):
            i0 = max(line.start_index - offset, 0)
            i1 = n - 1 + extra * 0.6
            v0 = line.value_at(i0 + offset)
            v1 = line.value_at(int(i1) + offset)
            out.append(f'<line x1="{x(i0):.1f}" y1="{y(v0):.1f}" x2="{x(i1):.1f}" y2="{y(v1):.1f}" stroke="{LINE}" stroke-width="1.6"/>')
    # 4H 200 EMA level
    if read.ema200_4h:
        yy = y(read.ema200_4h)
        out.append(f'<line x1="{x(n * 0.55):.1f}" x2="{width - pad_r}" y1="{yy:.1f}" y2="{yy:.1f}" stroke="{LINE}" stroke-width="1.4"/>')
        out.append(f'<text x="{x(n * 0.62):.1f}" y="{yy - 5:.1f}" font-size="12" fill="{LINE}">4H 200EMA {read.ema200_4h:.2f}</text>')
    # last close marker
    out.append(f'<line x1="{pad_l}" x2="{width - pad_r}" y1="{y(read.close):.1f}" y2="{y(read.close):.1f}" stroke="#495057" stroke-dasharray="2,3" stroke-width="0.8"/>')
    out.append(f'<rect x="{width - pad_r + 2}" y="{y(read.close) - 9:.1f}" width="{pad_r - 4}" height="18" fill="#495057" rx="3"/>'
               f'<text x="{width - pad_r + 6}" y="{y(read.close) + 4:.1f}" font-size="11" fill="#fff">{read.close:.2f}</text>')
    # legend top-left, dates along the bottom
    lx = pad_l + 8
    for w in DAILY_EMAS:
        out.append(f'<text x="{lx}" y="{pad_t + 12}" font-size="11" font-weight="600" fill="{EMA_COLORS[w]}">EMA {w}</text>')
        lx += 58
    for i in range(5, n, max(1, n // 6)):
        out.append(f'<text x="{x(i):.1f}" y="{height - 8}" font-size="10" fill="#868e96" text-anchor="middle">{d.index[i].strftime("%b %Y")}</text>')
    out.append(f'<text x="{width - pad_r - 4}" y="{pad_t + 12}" font-size="13" font-weight="700" fill="#212529" text-anchor="end">'
               f'{escape(read.ticker)} 1D  ·  {read.last_date.date()}</text>')
    out.append("</svg>")
    return "".join(out)


def render_chart_page(items: list[tuple[pd.DataFrame, ChartRead]]) -> str:
    """Standalone HTML page with one annotated chart + read per ticker."""
    cards = []
    for daily, read in items:
        extra = []
        if read.invalidation:
            extra.append(f"<p><b>Ongeldig als:</b> {escape(read.invalidation)}</p>")
        e = read.daily_emas
        extra.append("<p class='m'>EMA dag: " + " · ".join(f"{w}: {e[w]:.2f}" for w in DAILY_EMAS if w in e)
                     + (f" · 4H 200: {read.ema200_4h:.2f}" if read.ema200_4h else "") + "</p>")
        heads = "".join(f"<li>{escape(h)}</li>" for h in read.headlines)
        plan = f"<p class='plan'>{escape(read.plan)}</p>" if read.plan else ""
        cards.append(f"<section><h2>{escape(read.ticker)} <span class='b {read.bias}'>{read.bias.upper()}</span></h2>"
                     f"<ul class='heads'>{heads}</ul>{plan}"
                     f"{render_chart_svg(daily, read)}{''.join(extra)}</section>")
    return ("<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>Chart reads</title><style>"
            ":root{--chart-bg:#fff}body{margin:0;padding:16px;background:#f1f3f5;color:#212529;font-family:system-ui,sans-serif}"
            "section{background:#fff;border-radius:10px;padding:14px;margin:0 auto 18px;max-width:1000px;box-shadow:0 1px 3px #0001}"
            "h2{margin:0 0 8px;font-size:18px}.b{font-size:12px;padding:2px 8px;border-radius:10px;vertical-align:middle}"
            ".bullish{background:#d3f9d8;color:#2b8a3e}.neutral{background:#e9ecef;color:#495057}.bearish{background:#ffe3e3;color:#c92a2a}"
            ".m{color:#868e96;font-size:13px}"
            ".heads{margin:0 0 6px;padding-left:18px;color:#364fc7;font-weight:600;font-size:13px;text-transform:uppercase}"
            ".plan{margin:4px 0 10px;padding:8px 10px;background:#edf2ff;border-left:3px solid #364fc7;color:#364fc7;font-weight:700;font-size:13px}"
            "</style></head><body>" + "".join(cards) + "</body></html>")
