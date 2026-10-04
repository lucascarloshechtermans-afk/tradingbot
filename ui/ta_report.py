"""HTML for ta.engine.TechnicalReport: a clickable card per ticker (setups,
score breakdown, multi-timeframe table, structure, zones, momentum, volume,
volatility, candles, liquidity, patterns, relative strength, interactive chart)
and the 'Technische analyse' tab that lists them."""

from __future__ import annotations

from html import escape

import numpy as np

from ta import nl
from ta.engine import TF_NL
from ta.scoring import FAMILY_NL
from ui.ta_chart import CHART_CSS, render

DIR_NL = {1: "long", -1: "short", 0: "-"}
STATUS_CLS = {"confirmed": "gA", "triggered": "gB", "developing": "gW", "failed": "gC", "none": "gC"}


def _f(v, d: int = 2) -> str:
    return "-" if v is None or (isinstance(v, float) and not np.isfinite(v)) else f"{v:,.{d}f}"


def _li(items) -> str:
    return "".join(f"<li>{escape(str(x))}</li>" for x in items) or "<li>-</li>"


def _sec(title: str, body: str, open_: bool = False) -> str:
    return f"<details class='tasec'{' open' if open_ else ''}><summary>{escape(title)}</summary><div>{body}</div></details>"


def setups_table(rep) -> str:
    rows = ""
    for s in sorted(rep.setups, key=lambda s: -s.quality):
        star = " ★" if s is rep.primary else ""
        rows += (f"<tr><td><b>{escape(s.name_nl)}</b>{star}</td><td>{DIR_NL[s.direction]}</td>"
                 f"<td><span class='gb {STATUS_CLS.get(s.status, 'gC')}'>{escape(s.status_nl)}</span></td>"
                 f"<td>{s.quality:.0f}</td><td>{escape(s.trigger)}</td><td>{escape(s.invalidation)}</td>"
                 f"<td>{escape(', '.join(s.tf_agree) or '-')}</td><td>{escape(', '.join(s.tf_disagree) or '-')}</td></tr>"
                 f"<tr class='sub'><td colspan='8'><b>Bewijs:</b> {escape('; '.join(s.evidence))}"
                 + (f"<br><b>Combinatie:</b> {escape('; '.join(s.combos))}" if s.combos else "")
                 + (f"<br><b>Tegenbewijs:</b> {escape('; '.join(s.conflicts))}" if s.conflicts else "")
                 + "<br><b>Niveaus:</b> " + escape(", ".join(f"{k} {_f(v)}" for k, v in s.levels.items()
                                                       if v is not None and np.isfinite(v))) + "</td></tr>")
    if not rows:
        return "<p>Geen setup: geen van de 14 setup-regels is nu van toepassing.</p>"
    return ("<table class='tat'><thead><tr><th>Setup</th><th>Richting</th><th>Status</th><th>Score</th><th>Trigger</th>"
            "<th>Invalidatie</th><th>TF mee</th><th>TF tegen</th></tr></thead><tbody>" + rows + "</tbody></table>")


def score_table(rep) -> str:
    sc = rep.score
    rows = "".join(
        f"<tr><td>{escape(FAMILY_NL[c.family])}</td><td>{'-' if c.sub is None else f'{c.sub:.0f}'}</td>"
        f"<td>{c.weight:.0f}%</td><td>{c.points:.1f}</td><td>{escape(c.why)}</td></tr>" for c in sc.contributions)
    return (f"<p><b>Totaal {sc.total:.0f}/100</b> voor {DIR_NL[sc.direction]} &middot; rijpheid: {escape(sc.maturity)} &middot; "
            f"bevestiging: {escape(nl(sc.confirmation))}</p>"
            "<table class='tat'><thead><tr><th>Familie</th><th>Deelscore</th><th>Gewicht</th><th>Punten</th><th>Waarom</th></tr></thead>"
            f"<tbody>{rows}</tbody></table>"
            + (f"<p><b>Tegenstrijdige signalen (apart, niet verrekend):</b></p><ul>{_li(sc.conflicts)}</ul>" if sc.conflicts else "")
            + f"<p class='sm'>{escape(sc.note)} Elke familie telt één keer: RSI, MACD, ROC en DI vormen samen één momentumscore.</p>")


def mtf_table(rep) -> str:
    rows = ""
    for tf, r in rep.mtf.rows.items():
        if not r.get("ok"):
            rows += f"<tr><td>{TF_NL[tf]}</td><td colspan='6' class='sm'>{escape(r['note'])}</td></tr>"
            continue
        sup, res, pat, ev = r["support"], r["resistance"], r["pattern"], r["event"]
        rows += (f"<tr><td>{TF_NL[tf]}</td><td>{escape(r['trend'])}</td><td>{escape(r['swings'] or '-')}</td>"
                 f"<td>{escape(r['momentum'])}</td><td>{escape(r['volume'])}</td>"
                 f"<td>{_f(sup.high) if sup else '-'} / {_f(res.low) if res else '-'}</td>"
                 f"<td>{escape(f'{pat.name} ({pat.status_nl})') if pat else '-'}"
                 f"{escape(f'; {ev.kind} {ev.date:%d-%m}') if ev is not None else ''}</td></tr>")
    return ("<table class='tat'><thead><tr><th>TF</th><th>Trend</th><th>Swings</th><th>Momentum</th><th>Volume</th>"
            "<th>Steun / weerstand</th><th>Patroon; laatste structuurbreuk</th></tr></thead><tbody>" + rows + "</tbody></table>"
            f"<ul>{_li(rep.mtf.narrative)}</ul><p class='sm'>Alleen afgesloten kaarsen; week/maand zonder de lopende periode; "
            "4 uur/1 uur niet verder dan het laatste dagslot.</p>")


def detail_sections(rep) -> str:
    fa = rep.daily
    tr, m, v, vo = fa.trend, fa.momentum, fa.volume, fa.volatility
    ind = fa.ind
    out = []
    ev = "".join(f"<li>{e.kind} {'bullish' if e.direction == 'bull' else 'bearish'} op {e.date:%d-%m-%Y}: slot "
                 f"{'boven' if e.direction == 'bull' else 'onder'} {_f(e.level)}</li>" for e in tr.recent_events[-5:])
    mas = ", ".join(f"{k.upper()} {_f(ind.last(k))}" for k in ("ema9", "ema21", "ema34", "ema50", "sma10", "sma20", "sma50", "sma100", "sma200", "ema200"))
    out.append(_sec(f"Trend & structuur: {tr.label_nl}",
                    f"<ul>{_li(tr.reasons)}</ul><p>Swings: {escape(' '.join(tr.swing_labels) or '-')} &middot; fase: {nl(tr.stage)} "
                    f"({tr.bars_in_state} bars) &middot; MA-volgorde {tr.alignment:+d}/4 &middot; afstand EMA21 "
                    f"{_f(tr.dist_atr['ema21'], 1)} ATR, SMA50 {_f(tr.dist_atr['sma50'], 1)} ATR, SMA200 {_f(tr.dist_atr['sma200'], 1)} ATR</p>"
                    f"<p class='sm'>{escape(mas)}</p><p><b>Structuurbreuken (BOS/CHoCH):</b></p><ul>{ev or '<li>-</li>'}</ul>"
                    + (f"<p><b>Uitputting:</b></p><ul>{_li(tr.exhaustion)}</ul>" if tr.exhaustion else "")))
    zr = "".join(f"<tr><td>{escape(z.role)}</td><td>{nl(z.strength)}</td><td>{_f(z.low)}-{_f(z.high)}</td><td>{z.score:.0f}</td>"
                 f"<td>{z.reactions} ({z.support_reactions} steun / {z.resistance_reactions} weerstand)</td>"
                 f"<td>{escape(', '.join(z.sources))}</td><td class='sm'>{escape(', '.join(f'{k} {v:g}' for k, v in z.score_parts.items() if v))}</td></tr>"
                 for z in sorted(fa.zones, key=lambda z: -z.mid))
    out.append(_sec("Steun & weerstand (gescoorde zones)",
                    "<table class='tat'><thead><tr><th>Rol</th><th>Kracht</th><th>Zone</th><th>Score</th><th>Reacties</th>"
                    f"<th>Bronnen</th><th>Scoredelen</th></tr></thead><tbody>{zr}</tbody></table>"))
    out.append(_sec(f"Momentum: {nl(m.state)}",
                    f"<p>RSI7 {_f(m.rsi[7], 0)} &middot; RSI14 {_f(m.rsi[14], 0)} &middot; RSI21 {_f(m.rsi[21], 0)} &middot; "
                    f"MACD-hist {_f(m.macd_hist)} ({nl(m.acceleration)}) &middot; ROC 5/10/20/60 "
                    + " / ".join(_f(m.roc[w], 1) for w in (5, 10, 20, 60)) + f"% &middot; Stoch {_f(m.stoch, 0)} &middot; "
                    f"StochRSI {_f(m.stochrsi, 0)} &middot; ADX {_f(m.adx, 0)} (+DI {_f(ind.last('plus_di'), 0)} / "
                    f"-DI {_f(ind.last('minus_di'), 0)})</p><ul>{_li(m.notes)}</ul>"))
    out.append(_sec("Volume", f"<ul>{_li(v.notes)}</ul>"))
    out.append(_sec("Volatiliteit & compressie", f"<ul>{_li(vo.notes)}</ul>"))
    cs = "".join(f"<li><b>{escape(c.name_nl)}</b> {c.date:%d-%m} -- {nl(c.significance)} ({c.score:.0f}), {nl(c.confirmation)}: "
                 f"{escape(', '.join(c.context))}</li>" for c in fa.candles)
    out.append(_sec("Candlesticks (laatste 3 kaarsen, met context)", f"<ul>{cs or '<li>Geen patroon.</li>'}</ul>"))
    pr = "".join(f"<tr><td>{escape(p.name)}</td><td>{'bull' if p.direction == 'bull' else 'bear'}</td><td>{escape(p.status_nl)}</td>"
                 f"<td>{_f(p.trigger)}</td><td>{_f(p.invalidation)}</td><td>{_f(p.target)}</td><td>{p.age}</td>"
                 f"<td>{escape(p.volume)}</td><td>{escape(p.trend_context)}</td><td class='sm'>{escape(p.rule)}</td></tr>"
                 for p in fa.patterns)
    out.append(_sec("Chartpatronen", ("<table class='tat'><thead><tr><th>Patroon</th><th>Richting</th><th>Status</th><th>Trigger</th>"
                                       "<th>Invalidatie</th><th>Doel</th><th>Leeftijd</th><th>Volume</th><th>Trendcontext</th>"
                                       f"<th>Regel</th></tr></thead><tbody>{pr}</tbody></table>") if pr else "<p>Geen relevant patroon.</p>"))
    out.append(_sec("Liquiditeit & marktstructuur", f"<ul>{_li(fa.liquidity.notes if fa.liquidity else [])}</ul>"
                    "<p class='sm'>Afgeleid uit zichtbare koersstructuur; zegt niets over waar orders echt staan.</p>"))
    if rep.rs is not None:
        out.append(_sec("Relatieve sterkte (koersvergelijking)", f"<ul>{_li(rep.rs.notes)}</ul>"))
    if rep.regime is not None:
        out.append(_sec(f"Marktregime: {rep.regime.label_nl}", f"<ul>{_li(rep.regime.notes + rep.notes)}</ul>"))
    return "".join(out)


def report_card(rep, open_: bool = False) -> str:
    if not rep.daily.ok:
        return f"<div class='ov'><b>{escape(rep.ticker)}</b>: {escape(rep.notes[0] if rep.notes else 'geen data')}</div>"
    p = rep.primary
    badge = (f"<span class='gb {STATUS_CLS.get(p.status, 'gC')}'>{escape(p.name_nl)} &middot; {escape(p.status_nl)}</span>"
             if p else "<span class='gb gC'>geen setup</span>")
    summary = (f"{badge} <b>{escape(rep.ticker)}</b> <span class='sm'>slot {_f(rep.close)} ({rep.as_of:%d-%m}) &middot; "
               f"score {rep.score.total:.0f} &middot; {escape(rep.daily.trend.label_nl)} &middot; MTF {rep.mtf.score:.0f} "
               f"({escape(', '.join(rep.mtf.agree) or '-')} mee)</span>")
    body = (setups_table(rep) + _sec("Score: waar komt hij vandaan?", score_table(rep), True)
            + _sec("Multi-timeframe", mtf_table(rep), True) + render(rep) + detail_sections(rep))
    return f"<details class='ov' id='ta-{escape(rep.ticker)}'{' open' if open_ else ''}><summary>{summary}</summary><div class='ovb'>{body}</div></details>"


def ta_card_line(rep) -> str:
    """One line for other dashboard cards: the engine's verdict + a link to the full report."""
    p = rep.primary
    setup = f"{escape(p.name_nl)} ({escape(p.status_nl)}, {DIR_NL[rep.direction]})" if p else "geen setup"
    conf = f"; {len(rep.score.conflicts)} tegenstrijdigheden" if rep.score.conflicts else ""
    return (f"<b>Technische engine</b>: score {rep.score.total:.0f}/100 -- {setup}; trend {escape(rep.daily.trend.label_nl)}; "
            f"{len(rep.mtf.agree)} timeframes mee, {len(rep.mtf.disagree)} tegen{conf}. "
            f"<a class='tk' href='#ta-{escape(rep.ticker)}' onclick=\"openTa('{escape(rep.ticker)}')\">Volledig rapport &rarr;</a>")


def ta_tab(reports: list, regime=None) -> str:
    reps = sorted([r for r in reports if r.daily.ok], key=lambda r: -(r.score.total if r.score else 0))
    rows = ""
    for r in reps:
        p = r.primary
        rows += (f"<tr><td><a class='tk' href='#ta-{escape(r.ticker)}' onclick=\"openTa('{escape(r.ticker)}')\">{escape(r.ticker)}</a></td>"
                 f"<td>{r.score.total:.0f}</td><td>{escape(p.name_nl) if p else '-'}</td><td>{DIR_NL[r.direction] if p else '-'}</td>"
                 f"<td>{escape(p.status_nl) if p else '-'}</td><td>{escape(r.daily.trend.label_nl)}</td><td>{r.mtf.score:.0f}</td>"
                 f"<td>{_f(p.trigger_price) if p else '-'}</td><td>{_f(p.invalidation_price) if p else '-'}</td></tr>")
    reg = (f"<p>Marktregime: <b>{escape(regime.label_nl)}</b>, {escape({'expansion': 'volatiliteit zet uit', 'contraction': 'volatiliteit krimpt', 'normal': 'normale volatiliteit'}[regime.volatility])}. "
           f"{escape(regime.breakout_context())}</p>" if regime is not None else "")
    return ("<div class='card'><h3 style='margin-top:0'>Technische analyse</h3>" + reg +
            "<p class='sm'>Elk aandeel door de volledige technische engine: trend en structuur (BOS/CHoCH), gescoorde steun/weerstand, "
            "momentum, volume, volatiliteit, candlesticks in context, liquiditeit, chartpatronen, 5 timeframes en relatieve sterkte. "
            "Score 0-100 = hoe volledig en eensgezind het technische beeld is, geen winstkans. Status: in ontwikkeling &rarr; "
            "getriggerd &rarr; bevestigd. Klik op een ticker voor het volledige rapport met interactieve grafiek.</p>"
            "<table class='tat'><thead><tr><th>Ticker</th><th>Score</th><th>Hoofdsetup</th><th>Richting</th><th>Status</th>"
            "<th>Trend (dag)</th><th>MTF</th><th>Trigger</th><th>Invalidatie</th></tr></thead><tbody>" + rows + "</tbody></table></div>"
            + "".join(report_card(r) for r in reps))


TA_CSS = CHART_CSS + (
    ".tat{width:100%;border-collapse:collapse;font-size:12.5px;margin:6px 0}.tat th,.tat td{text-align:left;padding:4px 6px;"
    "border-bottom:1px solid var(--line,#ddd);vertical-align:top}.tat tr.sub td{font-size:12px;color:var(--ink-soft,#666);"
    "border-bottom:2px solid var(--line,#ddd)}.tasec{margin:6px 0}.tasec>summary{cursor:pointer;font-weight:600;font-size:13px}"
    ".tasec>div{padding:4px 0 4px 12px;font-size:12.5px}"
    ".ov details.tasec>summary:before{content:'\\25B6'}.ov details.tasec[open]>summary:before{content:'\\25BC'}")
TA_JS = ("function openTa(t){var b=document.querySelector('[data-tab=ta]');if(b)b.click();var e=document.getElementById('ta-'+t);"
         "if(e){e.open=true;e.scrollIntoView({behavior:'smooth',block:'start'});}}")


def standalone_page(reports: list, regime=None, title: str = "Technische analyse") -> str:
    return ("<!doctype html><html lang='nl'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{escape(title)}</title><style>:root{{--line:#ddd;--ink-soft:#666}}body{{font-family:system-ui,sans-serif;"
            "margin:16px;color:#212529;background:#f8f9fa}.card,.ov{background:#fff;border:1px solid #ddd;border-radius:8px;"
            "padding:10px 14px;margin:0 0 10px}.ov summary{cursor:pointer}.sm{color:#666;font-size:12px}.gb{font-size:11px;font-weight:700;"
            "padding:2px 7px;border-radius:9px;margin-right:6px;color:#fff}.gA{background:#2b8a3e}.gB{background:#5c940d}"
            ".gC{background:#495057}.gW{background:#1971c2}a.tk{color:#1971c2}" + TA_CSS + "</style>"
            f"<script>{TA_JS}</script></head><body>" + ta_tab(reports, regime) + "</body></html>")
