"""Dashboard overview: per-sector summary, tradeable SETUPS and POSSIBLE setups,
each row clickable (<details>) with a Dutch explanation of WHY (validated
rule, confirmations, and the chart read: daily/4H 200 EMA, EMA stack, zones,
wedges/channels/flags), what is missing, the plan, and the annotated chart.
"""

from __future__ import annotations

from html import escape

from analysis.chart_read import ChartRead
from analysis.patterns import detect_patterns
from analysis.setup_finder import EXCLUDED as PATTERN_EXCLUDED
from sector.rotation import SECTOR_ETF_MAP
from ui.chart_svg import render_chart_svg

PATTERN_NL = {
    "falling wedge": ("dalende wig", "lagere toppen en lagere bodems die naar elkaar toe lopen: de verkoopdruk neemt af"),
    "descending channel": ("dalend kanaal", "de koers zakt tussen twee evenwijdige dalende lijnen"),
    "descending triangle": ("dalende driehoek", "lagere toppen tegen een vlakke bodem"),
    "bull flag": ("bull flag", "een korte, ordelijke terugval na een sterke stijging (de 'vlag' aan de 'mast')"),
    "ascending triangle": ("stijgende driehoek", "een vlakke weerstand met steeds hogere bodems: kopers worden ongeduldiger"),
    "double bottom": ("double bottom (W)", "twee bodems op hetzelfde niveau: die prijs wordt tweemaal verdedigd"),
    "inverse head & shoulders": ("omgekeerde kop-schouders", "drie bodems waarvan de middelste de laagste: een klassieke bodemformatie"),
    "channel up strong breakout": ("stijgend kanaal (steil)", "de koers stijgt binnen twee evenwijdige stijgende lijnen"),
}


def _eur(x: float) -> str:
    return f"{x:,.2f}"


def explain_chart(read: ChartRead, dip_setup: bool = False) -> list[str]:
    """Dutch bullets that explain the chart read -- the 'why' behind the lines."""
    out: list[str] = []
    e = read.daily_emas
    c = read.close
    heads = " | ".join(read.headlines)
    if 200 in e:
        if "CROSSED DTF 200 EMA ABOVE" in heads:
            out.append(f"<b>Net boven de 200 EMA op de dag</b> ({_eur(e[200])}): de langetermijntrend is net heroverd -- "
                       f"dat niveau moet nu als steun houden.")
        elif c > e[200]:
            out.append(f"<b>Boven de 200 EMA op de dag</b> ({_eur(e[200])}): de langetermijntrend is omhoog.")
        else:
            out.append(f"<b>Onder de 200 EMA op de dag</b> ({_eur(e[200])}): de langetermijntrend is (nog) niet hersteld.")
    if all(w in e for w in (9, 21, 50, 200)):
        if e[9] > e[21] > e[50] > e[200]:
            out.append("<b>EMA's gestapeld 9 &gt; 21 &gt; 50 &gt; 200</b>: korte, middellange en lange trend wijzen allemaal omhoog.")
        elif c < e[21]:
            out.append(f"<b>Onder de EMA21</b> ({_eur(e[21])}): de korte trend is gebroken -- bij een leider is dat de dip, "
                       f"niet per se een probleem.")
    if read.ema200_4h is not None:
        if c > read.ema200_4h:
            out.append(f"<b>Boven de 200 EMA op de 4-uursgrafiek</b> ({_eur(read.ema200_4h)}): ook op de kortere timeframe "
                       f"hebben kopers de controle.")
        else:
            txt = (f"<b>Onder de 200 EMA op de 4-uursgrafiek</b> ({_eur(read.ema200_4h)}): die ligt als eerste weerstand "
                   f"boven de koers.")
            if dip_setup:
                txt += " Voor een LEADER DIP is dat geen minpunt: dips onder de 4H 200 EMA deden het in de backtest juist beter (diepere terugval)."
            else:
                txt += " Pas een slot erboven bevestigt herstel; uitbraken eronder verloren geld in de backtest."
            out.append(txt)
    p = read.pattern
    if p is not None:
        nl, what = PATTERN_NL.get(p.name, (p.name, ""))
        if p.broke_out:
            out.append(f"<b>Uitbraak uit een {nl}</b> ({p.breakout_bars_ago} dagen geleden): {what}. "
                       f"Een slot boven de bovenlijn (nu {_eur(p.upper_now)}) betekent dat kopers het overnemen.")
        elif c > p.upper_now:
            out.append(f"<b>Boven een {nl}</b> (al eerder uitgebroken): {what}.")
        else:
            out.append(f"<b>Binnen een {nl}</b>: {what}. Uitbraak pas bij een slot boven {_eur(p.upper_now)}.")
    if read.support_zone is not None:
        z = read.support_zone
        out.append(f"<b>Steunzone {_eur(z.low)}-{_eur(z.high)}</b> ({z.touches}x geraakt): hier kwamen eerder kopers binnen.")
    if read.resistance_zone is not None:
        z = read.resistance_zone
        out.append(f"<b>Weerstandszone {_eur(z.low)}-{_eur(z.high)}</b> ({z.touches}x geraakt): hier werd eerder verkocht -- "
                   f"de eerste plek waar de koers kan stokken.")
    if "BROKE OUT OF ZONE" in heads:
        out.append("<b>Uit een zone gebroken</b>: de oude weerstand is nu steun (role reversal).")
    return out


def _patterns_nl(daily) -> list[str]:
    out = []
    for h in detect_patterns(daily):
        if h.name in PATTERN_EXCLUDED or not (h.broke_out_today or 0 < h.distance_pct <= 10):
            continue  # far from its trigger: noise, not confirmation
        nl, what = PATTERN_NL.get(h.name, (h.name, ""))
        state = "brak vandaag uit" if h.broke_out_today else (
            f"{h.distance_pct:.1f}% onder de trigger {_eur(h.trigger)}" if h.distance_pct > 0 else f"boven de trigger {_eur(h.trigger)}")
        out.append(f"<b>Patroon: {nl}</b> ({h.bars} dagen) -- {state}. {what.capitalize()}. (Alleen bevestiging, geen reden op zich.)")
    return out[:3]


def _dip_why(d) -> tuple[list[str], list[str]]:
    why = [f"<b>Momentum-leider</b>: rank {d.momentum_rank:.0f}/100 -- bij de sterkste 20% van het universum over 3, 6 en 12 maanden.",
           f"<b>Dip</b>: {d.dip_atr:+.1f} ATR in 5 dagen -- een terugval in een sterk aandeel. Korte bewegingen keren vaak terug; "
           f"bij een leider is dat het kantelmoment (de enige setup die al onze out-of-sample tests doorstond)."]
    for r in d.reasons[2:]:
        why.append("<b>Bevestiging</b>: " + escape(r))
    missing = ["Ontbreekt: " + escape(m) for m in d.missing]
    return why, missing


def _card(anchor: str, badge: str, badge_cls: str, title: str, summary: str, why: list[str], missing: list[str],
          plan: str, svg: str) -> str:
    li = lambda xs: "".join(f"<li>{x}</li>" for x in xs)  # noqa: E731
    return (f"<details class='ov' id='{escape(anchor)}'><summary><span class='gb {badge_cls}'>{escape(badge)}</span> "
            f"<b>{escape(title)}</b> <span class='sm'>{summary}</span></summary><div class='ovb'>"
            f"<div class='cols2'><div><h4>Waarom</h4><ul>{li(why)}</ul></div>"
            f"<div><h4>Let op / ontbreekt</h4><ul>{li(missing) or '<li>Niets bijzonders.</li>'}</ul>"
            f"<h4>Plan</h4><p>{plan}</p></div></div>{svg}</div></details>")


def build_overview_html(leader_dips: list, dip_alerts: list, pattern_setups: list, sector_ranked: list[dict],
                        sector_by_ticker: dict[str, str | None], market_state: dict) -> str:
    sector_of = lambda t: sector_by_ticker.get(t) or "Onbekend"  # noqa: E731
    setups, possible = [], []
    for d, read in leader_dips:
        why, missing = _dip_why(d)
        why += explain_chart(read, dip_setup=True) + _patterns_nl(d.daily)
        risk_acct = "0,25% (halve positie: rustige markt, kleine edge)" if d.grade == "R" else "0,5%"
        plan = (f"Koop op de volgende open (~{_eur(d.close)}), stop 2,5 ATR onder je instap (~{_eur(d.stop_estimate)}, "
                f"{d.risk_pct:.1f}% koersrisico -- positie zo groot dat dit {risk_acct} van je account is), verkoop op het "
                f"slot van de 10e handelsdag. Geen vast koersdoel.")
        if d.grade == "C":
            plan = "Nog niet traden: onrustige markt maar geen van beide aandeel-bevestigingen -- dat deed het historisch slecht."
        svg = render_chart_svg(d.daily, read, levels={"STOP (est.)": d.stop_estimate})
        summary = (f"{escape(sector_of(d.ticker))} · slot {_eur(d.close)} · dip {d.dip_atr:+.1f} ATR · momentum "
                   f"{d.momentum_rank:.0f} · {d.confirmations}/4 bevestigingen")
        cls = {"A": "gA", "B": "gB", "R": "gR"}.get(d.grade, "gC")
        label = f"LEADER DIP {d.grade}" + (" (halve positie)" if d.grade == "R" else "")
        card = _card(f"ov-{d.ticker}", label, cls, d.ticker, summary, why, missing, plan, svg)
        (setups if d.grade in ("A", "B", "R") else possible).append((d.ticker, card))
    for a, read in dip_alerts:
        why = [f"<b>Momentum-leider</b>: rank {a.momentum_rank:.0f}/100.",
               f"<b>Nog geen dip</b>: wordt een LEADER DIP als hij sluit op of onder <b>{_eur(a.alert_price)}</b> "
               f"({-a.distance_pct:+.1f}% vanaf nu). "
               + (f"Hij staat al onder {_eur(a.deep_dip_price)} (21 EMA - 1 ATR), dus de 'diepe dip'-bevestiging heeft hij al: "
                  f"triggert hij, dan is het meteen minstens graad B als ook de ATR-bevestiging er is."
                  if a.close <= a.deep_dip_price else
                  f"Onder {_eur(a.deep_dip_price)} krijgt hij ook de 'diepe dip'-bevestiging.")]
        why += explain_chart(read, dip_setup=True) + _patterns_nl(a.daily)
        missing = [] if a.atr_pct >= 3 else [f"ATR {a.atr_pct:.1f}% (&lt; 3%): beweegt weinig, mist die bevestiging."]
        plan = ("Nog niets doen. Zet een alert op de dip-trigger; de trigger schuift elke dag mee, dus draai de scan "
                "elke avond opnieuw.")
        svg = render_chart_svg(a.daily, read, levels={"TRIGGER dip": a.alert_price, "TARGET deep-dip": a.deep_dip_price})
        summary = (f"{escape(sector_of(a.ticker))} · slot {_eur(a.close)} · trigger &le; {_eur(a.alert_price)} "
                   f"({-a.distance_pct:+.1f}%) · momentum {a.momentum_rank:.0f}")
        possible.append((a.ticker, _card(f"ov-alert-{a.ticker}", "BIJNA DIP", "gW", a.ticker, summary, why, missing, plan, svg)))
    for s, read in pattern_setups:
        if s.status != "READY":
            continue
        why = [f"<b>Patroon klaar voor uitbraak</b>: {escape(s.names)} -- trigger {_eur(s.trigger)}."]
        why += explain_chart(read) + [escape(r) for r in s.reasons[:3]]
        missing = ["Patronen zijn alleen bevestiging: op zichzelf gaven ze out-of-sample geen voordeel."]
        plan = (f"Alleen ter info. Een slot boven {_eur(s.trigger)} is de uitbraak; stop {_eur(s.stop)}, "
                f"doel {_eur(s.target)}.")
        svg = render_chart_svg(s.daily, read, patterns=s.patterns, levels={"TRIGGER": s.trigger, "STOP": s.stop, "TARGET": s.target})
        summary = f"{escape(sector_of(s.ticker))} · slot {_eur(s.close)} · trigger {_eur(s.trigger)}"
        possible.append((s.ticker, _card(f"ov-pat-{s.ticker}", "PATROON", "gP", s.ticker, summary, why, missing, plan, svg)))

    # --- per sector
    etf_to_sector = {}
    for name, etf in SECTOR_ETF_MAP.items():
        etf_to_sector.setdefault(etf, name)
    set_by_sector: dict[str, list[str]] = {}
    pos_by_sector: dict[str, list[str]] = {}
    for t, _ in setups:
        set_by_sector.setdefault(SECTOR_ETF_MAP.get(sector_of(t), "?"), []).append(t)
    for t, _ in possible:
        lst = pos_by_sector.setdefault(SECTOR_ETF_MAP.get(sector_of(t), "?"), [])
        if t not in lst:
            lst.append(t)
    link = lambda t: f"<a class='tk' href='#ov-{escape(t)}' onclick=\"openCard('{escape(t)}')\">{escape(t)}</a>"  # noqa: E731
    rows = ""
    for s in sector_ranked:
        etf = s["etf"]
        rows += (f"<tr><td>{s['rank']}</td><td><b>{escape(etf_to_sector.get(etf, etf))}</b> <span class='sm'>{etf}</span></td>"
                 f"<td>{s['performance_1m']:+.1f}%</td><td>{s['performance_3m']:+.1f}%</td><td>{s['relative_strength_vs_spy']:+.1f}%</td>"
                 f"<td>{escape(s['trend'])}</td><td>{' '.join(link(t) for t in set_by_sector.get(etf, [])) or '-'}</td>"
                 f"<td>{' '.join(link(t) for t in pos_by_sector.get(etf, [])) or '-'}</td></tr>")
    vix, weak = market_state.get("vix"), market_state.get("spy_below_50")
    mkt = (f"VIX {vix:.1f}{' (angst)' if vix and vix > 20 else ' (rustig)'}, SPY {'ONDER' if weak else 'boven'} zijn 50-daags gemiddelde"
           if vix is not None else "marktdata niet beschikbaar")
    no_trade = ("" if setups else "<p class='nt'><b>NO TRADE vandaag</b> -- geen enkele momentum-leider staat in een dip. "
                "Kijk naar de mogelijke setups hieronder.</p>")
    return (
        "<div class='card'><h3 style='margin-top:0'>Overzicht per sector</h3>"
        f"<p class='sm'>Markt nu: {escape(mkt)}. Klik op een ticker om de setup te openen.</p>"
        "<table><thead><tr><th>#</th><th>Sector</th><th>1M</th><th>3M</th><th>RS vs SPY</th><th>Trend</th>"
        "<th>Setups</th><th>Mogelijke setups</th></tr></thead><tbody>" + rows + "</tbody></table></div>"
        "<div class='card'><h3 style='margin-top:0'>Setups (verhandelbaar)</h3>"
        "<p class='sm'>LEADER DIP: de enige setup die alle out-of-sample tests doorstond. Onrustige markt: A (beste) en B; "
        "rustige markt: R, met een halve positie omdat de edge dan klein is. Klik voor uitleg en chart.</p>"
        + no_trade + "".join(c for _, c in setups) + "</div>"
        "<div class='card'><h3 style='margin-top:0'>Mogelijke setups (nog niet verhandelbaar)</h3>"
        "<p class='sm'>LEADER DIP graad C (onrustige markt zonder aandeel-bevestiging), leiders vlak bij hun dip-trigger, en chart-patronen "
        "die klaarstaan (alleen info). Klik voor uitleg en chart.</p>"
        + ("".join(c for _, c in possible) or "<p>Geen.</p>") + "</div>"
    )


OVERVIEW_CSS = (
    ".ov{border:1px solid var(--line);border-radius:8px;margin:0 0 8px;background:rgba(255,255,255,0.02)}"
    ".ov summary{cursor:pointer;padding:9px 12px;list-style:none}.ov summary::-webkit-details-marker{display:none}"
    ".ov summary:before{content:'\\25B6';font-size:10px;margin-right:8px;color:var(--ink-soft)}"
    ".ov[open] summary:before{content:'\\25BC'}"
    ".ov .ovb{padding:4px 14px 14px}.ov h4{margin:8px 0 4px}.ov ul{margin:0;padding-left:18px;font-size:13px;line-height:1.5}"
    ".ov .cols2{display:flex;gap:24px;flex-wrap:wrap}.ov .cols2>div{flex:1 1 360px}"
    ".sm{color:var(--ink-soft);font-size:12.5px}.nt{padding:8px 10px;border-left:3px solid #fab005;background:rgba(250,176,5,0.08)}"
    ".gb{font-size:11px;font-weight:700;padding:2px 7px;border-radius:9px;margin-right:6px}"
    ".gA{background:#2b8a3e;color:#fff}.gB{background:#5c940d;color:#fff}.gC{background:#495057;color:#fff}"
    ".gR{background:#0c8599;color:#fff}.gW{background:#1971c2;color:#fff}.gP{background:#e8590c;color:#fff}"
    "a.tk{color:#74c0fc;margin-right:6px}"
)
