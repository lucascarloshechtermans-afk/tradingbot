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
           f"<b>Dip</b>: {d.dip_atr:+.1f} ATR in 5 dagen -- een terugval in een sterk aandeel. Een gedisciplineerde instap: "
           f"je koopt niet achter de koers aan en hebt een duidelijke stop. (Eerlijk: over 2008-2026 deed geen enkele setup "
           f"het beter dan een willekeurig aandeel dat op dezelfde dag gekocht werd -- zie 'Wat het onderzoek zegt'.)"]
    nl = {"moves enough": "beweegt genoeg", "deep dip": "diepe dip", "fear": "angst in de markt", "weak tape": "zwakke markt"}
    for r in d.reasons[2:]:
        for en, du in nl.items():
            r = r.replace(en, du)
        why.append("<b>Context</b>: " + escape(r))
    missing = []
    for m in d.missing:
        if m.startswith("SPY below its 200-day"):
            missing.append("Let op: SPY staat onder zijn 200-daags gemiddelde -- halve positie. "
                           "Die trendfilter is de enige regel die in elke geteste periode de drawdowns verkleinde.")
        else:
            missing.append("Context: " + escape(m))
    return why, missing


GICS_TO_YAHOO = {  # index member lists use GICS names; the sector table uses Yahoo's
    "Information Technology": "Technology", "Health Care": "Healthcare", "Financials": "Financial Services",
    "Consumer Discretionary": "Consumer Cyclical", "Consumer Staples": "Consumer Defensive", "Materials": "Basic Materials",
}


def _first(a: list | None, b: list | None, ticker: str):
    for item, _read in (a or []) + (b or []):
        if item.ticker == ticker:
            return item
    return None


def _card(anchor: str, badge: str, badge_cls: str, title: str, summary: str, why: list[str], missing: list[str],
          plan: str, svg: str) -> str:
    li = lambda xs: "".join(f"<li>{x}</li>" for x in xs)  # noqa: E731
    return (f"<details class='ov' id='{escape(anchor)}'><summary><span class='gb {badge_cls}'>{escape(badge)}</span> "
            f"<b>{escape(title)}</b> <span class='sm'>{summary}</span></summary><div class='ovb'>"
            f"<div class='cols2'><div><h4>Waarom</h4><ul>{li(why)}</ul></div>"
            f"<div><h4>Let op / ontbreekt</h4><ul>{li(missing) or '<li>Niets bijzonders.</li>'}</ul>"
            f"<h4>Plan</h4><p>{plan}</p></div></div>{svg}</div></details>")


def _pct(x: float) -> str:
    return f"{x:.2f}".rstrip("0").rstrip(".").replace(".", ",") + "%"


def _breakout_cards(items: list, risk_pct: float, sector_of) -> list[tuple[str, str]]:
    cards = []
    for b, read in items:
        why = [f"<b>Momentum-leider</b>: #{b.leader_rank} van de top 50 op 12-1 maand rendement ({b.mom_12_1:+.0f}%).",
               (f"<b>Bijna breakout</b>: sluit hij boven <b>{_eur(b.breakout_level)}</b> ({b.distance_pct:+.1f}% vanaf nu), dan is "
                f"het een LEADER BREAKOUT -- het hoogste slot van de voorbije 50 dagen." if b.near else
                f"<b>Breakout</b>: slot {_eur(b.close)} boven het hoogste slot van de vorige 50 dagen ({_eur(b.breakout_level)}), "
                f"voor het eerst.")]
        why += explain_chart(read) + _patterns_nl(b.daily)
        missing = ["Eerlijk: getest beter dan een willekeurig aandeel (alle 4 testcellen), maar niet beter dan een leider "
                   "zonder breakout kopen, en niet significant. Losse breakouts buiten leiders deden het slechter dan willekeurig."]
        if b.action == "OVERLAP":
            missing.insert(0, "<b>Staat al in je MOMENTUM TOP 20</b> -- niet nog eens kopen (dubbele positie).")
        stop = (f"initiële stop 2,5 ATR onder je instap (~{_eur(b.stop_estimate)}, {b.risk_pct:.1f}% koersrisico -- positie zo "
                f"groot dat dit {_pct(risk_pct)} van je account is)" if b.stop_estimate is not None else "initiële stop 2,5 ATR")
        trail = (f"Trailing exit: verkoop op de open na een slot onder het laagste slot van de vorige 20 dagen "
                 f"(nu {_eur(b.exit_level)}; dat niveau schuift mee omhoog). Geen koersdoel -- winnaars laten lopen "
                 f"(gemiddeld ~24 handelsdagen; 38% winnaars, maar +2,1R per winnaar tegen -0,8R per verliezer). "
                 f"Opent hij de volgende ochtend met een gap terug onder het breakout-niveau? Toch kopen: getest, zulke "
                 f"breakouts deden het even goed (+0,28R per trade) -- een 'mislukte breakout'-filter hielp niet.")
        plan = (f"<b>Beste instap (getest): op het slot.</b> Staat de koers vlak voor sluitingstijd (~21:50 Belgische tijd) boven "
                f"{_eur(b.breakout_level)}, koop dan met een slotorder (MOC); zo niet, geen trade. Lukt dat niet, koop dan op de open "
                f"na een slot boven {_eur(b.breakout_level)}. {stop[0].upper() + stop[1:]}. {trail}"
                if b.near else
                f"Het slot van vandaag was al de breakout, dus koop op de volgende open (~{_eur(b.close)}). Volgende keer beter: "
                f"koop al op het slot van de breakout-dag (zie BIJNA BREAKOUT) -- dat gaf in alle 4 testperiodes meer rendement "
                f"en een kleinere daling. {stop[0].upper() + stop[1:]}. {trail}")
        if b.action == "OVERLAP":
            plan = "Overslaan: je houdt dit aandeel al via de momentum-lijst."
        levels = {"BREAKOUT": b.breakout_level, "TRAIL EXIT": b.exit_level}
        if b.stop_estimate is not None:
            levels["STOP (est.)"] = b.stop_estimate
        svg = render_chart_svg(b.daily, read, levels=levels) if b.daily is not None else ""
        label = ("BIJNA BREAKOUT" if b.near else f"#{b.priority} {b.action} · score {b.score:.0f} · LEADER BREAKOUT")
        cls = "gW" if b.near else ("gC" if b.action == "OVERLAP" else "gP")
        summary = (f"{escape(sector_of(b.ticker))} · slot {_eur(b.close)} · 50d-high {_eur(b.breakout_level)}"
                   + (f" ({b.distance_pct:+.1f}%)" if b.near else "") + f" · leider #{b.leader_rank}")
        anchor = f"ov-{'nb' if b.near else 'bo'}-{b.ticker}"
        cards.append((b.ticker, _card(anchor, label, cls, b.ticker, summary, why, missing, plan, svg)))
    return cards


def build_overview_html(leader_dips: list, dip_alerts: list, pattern_setups: list, sector_ranked: list[dict],
                        sector_by_ticker: dict[str, str | None], market_state: dict, dip_risk_pct: float = 0.5,
                        leader_breakouts: list | None = None, near_breakouts: list | None = None,
                        breakout_risk_pct: float | None = None, momentum: tuple | None = None) -> str:
    mo_sectors = {}
    if momentum is not None and momentum[0] is not None:
        mo_sectors = {p.ticker: p.sector for p in list(momentum[0].picks) + list(momentum[0].preview)}

    def sector_of(t: str) -> str:
        sec = (sector_by_ticker.get(t) or mo_sectors.get(t)
               or getattr(_first(leader_breakouts, near_breakouts, t), "sector", None) or "Onbekend")
        sec = sec.replace(" (small cap)", "")
        return GICS_TO_YAHOO.get(sec, sec)
    setups, possible = [], []
    if momentum is not None:
        mo_set, mo_pos = momentum_cards(*momentum)
        setups += mo_set
        possible += mo_pos
    bo_risk = dip_risk_pct if breakout_risk_pct is None else breakout_risk_pct
    setups += _breakout_cards(leader_breakouts or [], bo_risk, sector_of)
    possible += _breakout_cards(near_breakouts or [], bo_risk, sector_of)
    for d, read in leader_dips:
        why, missing = _dip_why(d)
        why += explain_chart(read, dip_setup=True) + _patterns_nl(d.daily)
        risk_acct = (f"{_pct(dip_risk_pct / 2)} (halve positie: SPY onder zijn 200-daags)" if d.grade == "H"
                     else _pct(dip_risk_pct))
        plan = (f"Koop op de volgende open (~{_eur(d.close)}), stop 2,5 ATR onder je instap (~{_eur(d.stop_estimate)}, "
                f"{d.risk_pct:.1f}% koersrisico -- positie zo groot dat dit {risk_acct} van je account is), verkoop op het "
                f"slot van de 10e handelsdag. Geen vast koersdoel.")
        svg = render_chart_svg(d.daily, read, levels={"STOP (est.)": d.stop_estimate})
        summary = (f"{escape(sector_of(d.ticker))} · slot {_eur(d.close)} · dip {d.dip_atr:+.1f} ATR · momentum "
                   f"{d.momentum_rank:.0f}")
        cls = "gR" if d.grade == "H" else "gA"
        label = "LEADER DIP" + (" (halve positie)" if d.grade == "H" else "")
        if d.priority is not None:
            label = f"#{d.priority} {d.action} · score {d.score:.0f} · " + label
            cls = {"NEEM": cls, "RESERVE": "gW", "OVERLAP": "gC"}.get(d.action, cls)
        if d.action == "OVERLAP":
            missing.insert(0, "<b>Staat al in je MOMENTUM TOP 20</b> -- niet nog eens kopen (anders zit je dubbel in "
                              "hetzelfde aandeel). Overslaan kost niets meetbaars: een dip-instap was niet beter dan willekeurig.")
            plan = "Overslaan: je houdt dit aandeel al via de momentum-lijst. " + plan
        elif d.action == "RESERVE":
            missing.insert(0, "Reserve: je maximum aantal dip-posities is al gevuld door hogere scores. Alleen nemen als er een plaats vrijkomt.")
        card = _card(f"ov-{d.ticker}", label, cls, d.ticker, summary, why, missing, plan, svg)
        setups.append((d.ticker, card))
    for a, read in dip_alerts:
        why = [f"<b>Momentum-leider</b>: rank {a.momentum_rank:.0f}/100.",
               f"<b>Nog geen dip</b>: wordt een LEADER DIP als hij sluit op of onder <b>{_eur(a.alert_price)}</b> "
               f"({-a.distance_pct:+.1f}% vanaf nu). "
               + (f"Hij staat al onder {_eur(a.deep_dip_price)} (21 EMA - 1 ATR), dus de 'diepe dip'-bevestiging heeft hij al: "
                  f"triggert hij, dan is het meteen een diepe dip."
                  if a.close <= a.deep_dip_price else
                  f"Onder {_eur(a.deep_dip_price)} krijgt hij ook de 'diepe dip'-bevestiging.")]
        why += explain_chart(read, dip_setup=True) + _patterns_nl(a.daily)
        missing = []
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
    vix, weak, bear = market_state.get("vix"), market_state.get("spy_below_50"), market_state.get("spy_below_200")
    mkt = (f"VIX {vix:.1f}, SPY {'ONDER' if weak else 'boven'} zijn 50-daags"
           + ("" if bear is None else f" en {'ONDER' if bear else 'boven'} zijn 200-daags gemiddelde")
           + (" -> halve posities" if bear else " -> normale posities")
           if vix is not None else "marktdata niet beschikbaar")
    setup_intro = (
        ("<p class='sm'>MOMENTUM TOP 20: de maandlijst, elk aandeel met volledige chartanalyse (EMA's, 4H 200 EMA, steun, "
         "weerstand, patronen). Groen = nieuw deze maand, blauw-groen = blijft. Klik voor chart en uitleg.</p>" if momentum else "")
        + ("" if not (leader_breakouts or near_breakouts) else "<p class='sm'>LEADER BREAKOUT: eerste slot boven de hoogste slotkoers van de vorige 50 dagen, in een top-50 momentum-leider, "
        "alleen als SPY boven zijn 200-daags staat. Koop op de volgende open, stop 2,5 ATR, trailing exit (verkoop na een slot "
        f"onder het laagste slot van 20 dagen). Risico {_pct(bo_risk)} van je account per trade. <b>Volgorde</b>: #1 eerst, score = "
        "plaats in de leiderslijst; OVERLAP = zit al in je momentum-lijst, overslaan.</p>")
        + ("" if not leader_dips and not dip_alerts else
           f"<p class='sm'>LEADER DIP: dip-instap in een momentum-leider, risico {_pct(dip_risk_pct)} "
           f"(half onder de 200-daags van SPY). NEEM / RESERVE / OVERLAP zoals hierboven.</p>")
        + "<p class='sm'>Klik voor uitleg en chart.</p>")
    no_trade = ("" if setups else "<p class='nt'><b>Niets te doen</b> -- geen signalen vandaag. "
                "Kijk naar de mogelijke setups hieronder.</p>")
    return (
        "<div class='card'><h3 style='margin-top:0'>Overzicht per sector</h3>"
        f"<p class='sm'>Markt nu: {escape(mkt)}. Klik op een ticker om de setup te openen.</p>"
        "<table><thead><tr><th>#</th><th>Sector</th><th>1M</th><th>3M</th><th>RS vs SPY</th><th>Trend</th>"
        "<th>Setups</th><th>Mogelijke setups</th></tr></thead><tbody>" + rows + "</tbody></table></div>"
        + RESEARCH_NOTE_HTML +
        "<div class='card'><h3 style='margin-top:0'>Setups (verhandelbaar)</h3>"
        + setup_intro
        + no_trade + "".join(c for _, c in setups) + "</div>"
        "<div class='card'><h3 style='margin-top:0'>Mogelijke setups (nog niet verhandelbaar)</h3>"
        "<p class='sm'>Aandelen die bij de volgende herbalancering in de momentum-lijst komen (voorlopig), leiders binnen 3% van een breakout"
        + (", leiders vlak bij hun dip-trigger" if dip_alerts else "") + " en chart-patronen die klaarstaan (alleen info). "
        "Klik voor uitleg en chart.</p>"
        + ("".join(c for _, c in possible) or "<p>Geen.</p>") + "</div>"
    )


RESEARCH_NOTE_HTML = (
    "<div class='card'><details class='ov'><summary><span class='gb gW'>ONDERZOEK</span> <b>Wat het onderzoek zegt</b> "
    "<span class='sm'>966 aandelen (S&amp;P 500 + 400), 2008-2026, 26 vooraf vastgelegde hypotheses -- klik</span></summary>"
    "<div class='ovb'><ul>"
    "<li><b>Geen enkele setup</b> (dips, breakouts, 52-weken-high, pocket pivot, squeeze, NR7, relatieve sterkte, sector, "
    "earnings-gap, earnings-surprise) deed het beter dan een <b>willekeurig aandeel dat op dezelfde dag</b> gekocht werd. "
    "Breakouts en nieuwe highs waren in 3 van de 4 testcellen zelfs iets <i>slechter</i>.</li>"
    "<li>Eerdere 'edges' kwamen door een scheve vergelijking (maandgemiddelde van hetzelfde aandeel bevat de beweging zelf) "
    "en door <b>marktmoment</b>: kopen na een marktdip met VIX &ge; 15 werkte in 2008-2021 (+0,26R per 20 dagen), maar "
    "<b>niet in 2022-2026</b>.</li>"
    "<li>Een rangschikkingsmodel (LightGBM, jaar-voor-jaar getraind) vond geen stabiele volgorde: welk aandeel je kiest "
    "maakte binnen dezelfde dag &plusmn;0,01-0,03R uit.</li>"
    "<li><b>Wat wel stand hield in elke periode</b> (1993-2007, 2008-2021, 2022-2026): de 200-daagse trendfilter op SPY "
    "verkleinde de maximale drawdown (47&rarr;29%, 52&rarr;21%, 25&rarr;21%). Daarom stuurt die nu je positiegrootte.</li>"
    "<li>Conclusie: de scanner is een <b>discipline- en risicotool</b>, geen voorspeller. Zet risico klein en vast, "
    "koop niet achter de koers aan, en weet dat een index-ETF met trendfilter statistisch even goed deed.</li>"
    "</ul></div></details></div>"
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


def _atr14(daily) -> float | None:
    d = daily.dropna(subset=["high", "low", "close"])
    if len(d) < 15:
        return None
    pc = d["close"].shift()
    tr = __import__("pandas").concat([d["high"] - d["low"], (d["high"] - pc).abs(), (d["low"] - pc).abs()], axis=1).max(axis=1)
    v = float(tr.rolling(14).mean().iloc[-1])
    return v if v > 0 else None


def resistance_room(read: ChartRead, daily) -> tuple[float | None, float | None]:
    """(room to the nearest resistance zone in ATR, in %) -- None when there is no zone above."""
    z = read.resistance_zone
    atr = _atr14(daily)
    if z is None or atr is None:
        return None, None
    return (z.low - read.close) / atr, (z.low / read.close - 1) * 100


RESISTANCE_NOTE = ("Getest (research round 13, 7.000 momentum-aandelen 2008-2026): aandelen met weerstand binnen 1 ATR erboven "
                   "deden het de maand erna niet slechter dan de andere 19 (in 2 van de 4 testperiodes zelfs beter). "
                   "Informatie, geen reden om over te slaan.")


def momentum_cards(book, reads: dict, pct_per_stock: float,
                   ta_lines: dict[str, str] | None = None) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Analysis cards for the MOMENTUM TOP 20 (setups) and the names that would enter
    at the next rebalance (possible setups). reads: ticker -> (ChartRead, daily);
    ta_lines: ticker -> one-line summary of the ta/ engine report (with a link to it)."""
    if book is None:
        return [], []
    setups, possible = [], []
    entries = [(p, False) for p in book.picks] + [(p, True) for p in book.preview if p.ticker in set(book.preview_in)]
    for p, is_preview in entries:
        if p.ticker not in reads:
            continue
        read, daily = reads[p.ticker]
        why = [f"<b>Momentum</b>: #{p.rank} van {len(book.picks) or 20} -- {p.mom_12_1:+.0f}% van 12 tot 1 maand geleden; "
               f"laatste maand {p.ret_1m:+.1f}%."]
        if ta_lines and p.ticker in ta_lines:
            why.append(ta_lines[p.ticker])
        why += explain_chart(read) + _patterns_nl(daily)
        room_atr, room_pct = resistance_room(read, daily)
        missing = []
        if room_atr is not None and room_atr <= 1:
            z = read.resistance_zone
            missing.append(f"<b>Weerstand vlak erboven</b>: zone {_eur(z.low)}-{_eur(z.high)} ({room_atr:.1f} ATR / {room_pct:+.1f}%, "
                           f"{z.touches}x geraakt). {RESISTANCE_NOTE}")
        elif room_atr is not None:
            z = read.resistance_zone
            missing.append(f"Eerstvolgende weerstand: {_eur(z.low)}-{_eur(z.high)} ({room_atr:.1f} ATR / {room_pct:+.1f}% hoger).")
        else:
            missing.append("Geen weerstandszone boven de koers in de laatste 2 jaar (open lucht).")
        if read.support_zone is not None:
            s = read.support_zone
            missing.append(f"Steun: {_eur(s.low)}-{_eur(s.high)} ({(s.high / read.close - 1) * 100:+.1f}%).")
        plan = (f"{'Wordt gekocht bij de volgende herbalancering als hij dan nog in de top 20 staat' if is_preview else 'In de maandlijst'}: "
                f"{pct_per_stock:.1f}% van je account, kopen op de open na het maandeinde, een maand houden, geen stop -- "
                f"de trendfilter (SPY onder zijn 200-daags op het maandeinde = alles cash) is de rem. Blijft hij in de top 20, "
                f"dan hou je hem.")
        levels = {}
        if read.resistance_zone is not None:
            levels["WEERSTAND"] = read.resistance_zone.low
        if read.support_zone is not None:
            levels["STEUN"] = read.support_zone.high
        svg = render_chart_svg(daily, read, levels=levels)
        flag = " ⚠ weerstand" if room_atr is not None and room_atr <= 1 else ""
        label = (f"VOLGENDE MAAND ERIN{flag}" if is_preview else f"MOMENTUM #{p.rank} · {p.status}{flag}")
        cls = "gW" if is_preview else ("gA" if p.status == "NIEUW" else "gB")
        summary = (f"{escape(p.sector or '-')} · slot {_eur(read.close)} · 12-1m {p.mom_12_1:+.0f}%"
                   + (f" · weerstand {room_pct:+.1f}%" if room_pct is not None else " · open lucht"))
        card = _card(f"ov-mo-{p.ticker}", label, cls, p.ticker, summary, why, missing, plan, svg)
        (possible if is_preview else setups).append((p.ticker, card))
    return setups, possible
