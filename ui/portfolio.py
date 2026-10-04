"""Dashboard pieces for the round-6 portfolio plan (README, "Research round 6"):
a 'Vandaag te doen' card for the Dashboard tab and the full 'Portefeuille'
tab (allocation, MOMENTUM TOP 20, INDEX RSI(2)). Price-only systems."""

from __future__ import annotations

from html import escape

import pandas as pd

STATE_NL = {
    "KOOP": ("KOOP", "gA", "RSI(2) onder 10 boven de 200-daags: koop op de volgende open."),
    "HOUDEN": ("HOUDEN", "gB", "In positie: verkoop op de open na het eerste slot boven de 5-daags."),
    "VERKOOP": ("VERKOOP", "gC", "Slot boven de 5-daags: verkoop op de volgende open."),
    "GEEN": ("GEEN", "gW", "Geen signaal."),
}


def _money(x: float) -> str:
    return f"{x:,.0f}"


def _date(d) -> str:
    return pd.Timestamp(d).strftime("%d-%m-%Y") if d is not None else "-"


def _spark(series: pd.Series | None, w: int = 120, h: int = 26) -> str:
    if series is None:
        return ""
    s = series.dropna().iloc[-252:]
    if len(s) < 10:
        return ""
    lo, hi = float(s.min()), float(s.max())
    rng = hi - lo or 1.0
    pts = " ".join(f"{i * (w - 2) / (len(s) - 1) + 1:.1f},{h - 2 - (v - lo) / rng * (h - 4):.1f}" for i, v in enumerate(s))
    color = "#3fb950" if s.iloc[-1] >= s.iloc[0] else "#f85149"
    return (f"<svg width='{w}' height='{h}' viewBox='0 0 {w} {h}' role='img' aria-label='12 maanden koers'>"
            f"<polyline fill='none' stroke='{color}' stroke-width='1.5' points='{pts}'/></svg>")


BACKTEST_NOTE = {
    (100.0, 0.0): "<p class='sm'>Backtest alleen momentum (juni 2008 - sept 2026): 22,3% per jaar, grootste daling 36%, "
                  "slechtste jaar -14,2% (2022), 89% van de jaren positief; SPY 11,7% / 51%. Aandelen-backtests zijn ~4-5%/jaar "
                  "te rooskleurig (aandelen die uit de index vielen ontbreken) -- reken op ~17-18% met dalingen tot ~35-40%. "
                  "Periodes van maanden onder water horen erbij. Geen garantie. Alleen kopen op sterkte.</p>",
    (50.0, 50.0): "<p class='sm'>Backtest 50% momentum / 50% breakouts (juni 2008 - sept 2026): 16,3% per jaar, grootste daling "
                  "31%; SPY 11,7% / 51%. Min ~4-5%/jaar voor ontbrekende aandelen. Geen garantie.</p>",
    "other": "<p class='sm'>Zie README voor de backtest van deze verdeling. Aandelen-backtests zijn ~4-5%/jaar te rooskleurig.</p>",
}


def allocation_rows(cfg, account_size: float, bear: bool | None) -> list[tuple[str, str, str, str]]:
    """(system, % of account, amount, per-position rule) for every system that is switched on."""
    n = max(cfg.momentum_top_n, 1)
    dip_risk = cfg.dip_risk_pct_of_account * (0.5 if bear else 1.0)
    bo_risk = cfg.breakout_risk_pct_of_account
    cash = max(0.0, 100 - cfg.momentum_pct - cfg.breakout_pct - cfg.dip_pct - cfg.index_rsi2_pct)
    rows = []
    if cfg.momentum_pct > 0:
        rows.append(("MOMENTUM TOP 20", f"{cfg.momentum_pct:.0f}%", _money(account_size * cfg.momentum_pct / 100),
                     f"{cfg.momentum_pct / n:.1f}% van je account per aandeel ({_money(account_size * cfg.momentum_pct / 100 / n)}), "
                     f"maandelijks herbalanceren; alles in cash als SPY op het maandeinde onder zijn 200-daags sloot"))
    if cfg.breakout_pct > 0:
        rows.append(("LEADER BREAKOUT", f"{cfg.breakout_pct:.0f}%", _money(account_size * cfg.breakout_pct / 100),
                     f"risico {bo_risk:.2f}% van je account per trade ({_money(account_size * bo_risk / 100)}); "
                     f"max {cfg.breakout_max_positions} tegelijk, max 20% van dit deel per positie; alleen als SPY boven zijn 200-daags staat"))
    if cfg.dip_pct > 0:
        rows.append(("LEADER DIP swings", f"{cfg.dip_pct:.0f}%", _money(account_size * cfg.dip_pct / 100),
                     f"risico {dip_risk:.2f}% van je account per trade ({_money(account_size * dip_risk / 100)})"
                     f"{' -- gehalveerd: SPY onder zijn 200-daags' if bear else ''}; max {cfg.dip_max_positions} tegelijk, "
                     f"max 20% van dit deel per positie"))
    if cfg.index_rsi2_pct > 0:
        rows.append(("INDEX RSI(2)", f"{cfg.index_rsi2_pct:.0f}%", _money(account_size * cfg.index_rsi2_pct / 100),
                     f"{cfg.index_rsi2_pct / 4:.1f}% van je account per ETF met een KOOP-signaal "
                     f"({_money(account_size * cfg.index_rsi2_pct / 400)}); de rest van dit deel in cash / geldmarkt"))
    if cash > 0:
        rows.append(("Cash (niet toegewezen)", f"{cash:.0f}%", _money(account_size * cash / 100), "geldmarkt / T-bills"))
    return rows


def todo_items(cfg, book, signals: list, n_dips: int, bear: bool | None, n_breakouts: int = 0) -> list[str]:
    items = []
    if cfg.momentum_pct > 0 and book is not None:
        if book.as_of is None:
            items.append("Momentum: nog geen volledige maand data -- lijst niet beschikbaar.")
        elif not book.invested:
            items.append(f"Momentum: <b>cash</b> -- SPY sloot op {_date(book.as_of)} onder zijn 200-daags. "
                         f"Volgende check op {_date(book.next_rebalance)}.")
        else:
            new = [p.ticker for p in book.picks if p.status == "NIEUW"]
            items.append(f"Momentum: houd de {len(book.picks)} aandelen van {_date(book.as_of)}"
                         + (f"; nieuw deze maand: <b>{escape(', '.join(new))}</b>" if new else "")
                         + (f"; verkocht: {escape(', '.join(book.exits))}" if book.exits else "")
                         + f". Volgende herbalancering: slot van {_date(book.next_rebalance)}"
                         + (f" (voorlopig {len(book.preview_in)} wissel{'s' if len(book.preview_in) != 1 else ''})" if book.preview else "")
                         + ".")
    if cfg.index_rsi2_pct > 0:
        act = [s for s in signals if s.state in ("KOOP", "VERKOOP")]
        hold = [s.etf for s in signals if s.state == "HOUDEN"]
        if act:
            items.append("Index RSI(2): " + "; ".join(f"<b>{s.state} {s.etf}</b> op de volgende open" for s in act)
                         + (f"; houden: {', '.join(hold)}" if hold else "") + ".")
        elif hold:
            items.append(f"Index RSI(2): houden {', '.join(hold)} -- verkoop na een slot boven de 5-daags.")
        else:
            near = sorted((s for s in signals if s.buy_below is not None and s.above_200), key=lambda s: s.close / s.buy_below)
            items.append("Index RSI(2): geen signaal"
                         + (f"; dichtst bij: {near[0].etf} (slot &le; {near[0].buy_below:,.2f})" if near else "") + ".")
    if cfg.dip_pct > 0:
        items.append(f"Dips: {n_dips} LEADER DIP{'s' if n_dips != 1 else ''} vandaag"
                     + (" (halve risico's: SPY onder zijn 200-daags)" if bear else "") + ".")
    if cfg.breakout_pct > 0:
        items.append(f"Breakouts: <b>{n_breakouts} LEADER BREAKOUT{'s' if n_breakouts != 1 else ''}</b> vandaag"
                     + (" -- geen nieuwe: SPY staat onder zijn 200-daags" if bear else "")
                     + " -- zie Setups, in volgorde (#1 eerst).")
    return items


def build_todo_html(cfg, book, signals: list, n_dips: int, bear: bool | None, n_breakouts: int = 0) -> str:
    items = todo_items(cfg, book, signals, n_dips, bear, n_breakouts)
    if book is not None and book.preview_date is not None:
        items.insert(0, f"Koersen t/m het <b>slot van {_date(book.preview_date)}</b> (alleen afgesloten beursdagen; "
                        "een run tijdens de beurs gebruikt nog de vorige slotkoers).")
    return ("<div class='card'><h3 style='margin-top:0'>Vandaag te doen "
            "<span class='sm'>portefeuilleplan: " + " / ".join(f"{name} {pct:.0f}%" for name, pct in (
                ("momentum", cfg.momentum_pct), ("breakouts", cfg.breakout_pct), ("dips", cfg.dip_pct),
                ("index RSI(2)", cfg.index_rsi2_pct)) if pct > 0)
            + " -- details in de tab Portefeuille</span></h3><ul>"
            + "".join(f"<li>{i}</li>" for i in items) + "</ul></div>")


def _pick_rows(picks: list, closes: pd.DataFrame | None) -> str:
    rows = ""
    for p in picks:
        spark = _spark(closes[p.ticker]) if closes is not None and p.ticker in closes else ""
        badge = "gA" if p.status == "NIEUW" else "gB"
        link = f"<a class='tk' href='#ov-mo-{escape(p.ticker)}' onclick=\"openCard('{escape(p.ticker)}')\">{escape(p.ticker)}</a>"
        rows += (f"<tr><td>{p.rank}</td><td><b>{link}</b></td><td>{escape(p.sector or '-')}</td>"
                 f"<td>{p.mom_12_1:+.0f}%</td><td>{p.ret_1m:+.1f}%</td><td>{p.close:,.2f}</td><td>{spark}</td>"
                 f"<td><span class='gb {badge}'>{p.status}</span></td></tr>")
    return rows


def build_portfolio_tab_html(cfg, account_size: float, book, signals: list, bear: bool | None,
                             closes: pd.DataFrame | None = None) -> str:
    alloc = "".join(f"<tr><td><b>{escape(a)}</b></td><td>{b}</td><td>{c}</td><td>{escape(d)}</td></tr>"
                    for a, b, c, d in allocation_rows(cfg, account_size, bear))
    parts = [
        "<div class='card'><h3 style='margin-top:0'>Portefeuilleplan</h3>"
        f"<p class='sm'>Accountgrootte uit config (risk.account_size): {_money(account_size)}. Alleen koersdata. "
        "Verdeling instelbaar onder <code>portfolio:</code> in config.yaml (momentum_pct, breakout_pct, dip_pct, "
        "index_rsi2_pct).</p>"
        "<table><thead><tr><th>Systeem</th><th>Deel</th><th>Bedrag</th><th>Per positie</th></tr></thead><tbody>"
        + alloc + "</tbody></table>"
        + BACKTEST_NOTE.get((cfg.momentum_pct, cfg.breakout_pct), BACKTEST_NOTE["other"]) + "</div>"
    ]
    if book is not None:
        head = ("<table><thead><tr><th>#</th><th>Ticker</th><th>Sector</th><th>12-1 mnd</th><th>Laatste mnd</th>"
                "<th>Slot (lijstdatum)</th><th>12 mnd</th><th>Status</th></tr></thead><tbody>")
        if book.as_of is None:
            official = "<p>Nog niet genoeg data voor een maandlijst.</p>"
        elif not book.invested:
            official = (f"<p class='nt'><b>CASH</b> -- SPY sloot op {_date(book.as_of)} onder zijn 200-daags gemiddelde. "
                        "Deze maand geen momentum-posities (zo werd de daling van 2008 grotendeels ontweken).</p>"
                        + "<p class='sm'>Ter info, de ranglijst van die dag:</p>" + head + _pick_rows(book.picks, closes) + "</tbody></table>")
        else:
            official = head + _pick_rows(book.picks, closes) + "</tbody></table>"
        exits = (f"<p><b>Verkopen</b> (stonden vorige maand in de lijst): {escape(', '.join(book.exits))}</p>" if book.exits else "")
        preview = ""
        if book.preview:
            preview = (f"<details class='ov'><summary><span class='gb gW'>VOORLOPIG</span> <b>Als de maand vandaag eindigde</b> "
                       f"<span class='sm'>slot {_date(book.preview_date)} &middot; erin: {escape(', '.join(book.preview_in) or '-')} "
                       f"&middot; eruit: {escape(', '.join(book.preview_out) or '-')} &middot; SPY "
                       f"{'boven' if book.spy_above_200_now else 'ONDER'} zijn 200-daags</span></summary><div class='ovb'>"
                       + head + _pick_rows(book.preview, closes) + "</tbody></table><p class='sm'>Niet handelen op deze lijst: "
                       f"alleen het slot van de laatste handelsdag van de maand telt ({_date(book.next_rebalance)}).</p></div></details>")
        parts.append(
            "<div class='card'><h3 style='margin-top:0'>MOMENTUM TOP 20 <span class='sm'>maandlijst van "
            f"{_date(book.as_of)} &middot; {book.eligible_count} van {book.universe_size} aandelen (S&amp;P 500 + 400 + scannerlijst + S&amp;P 600 small caps vanaf $50 als ingeschakeld) komen in aanmerking</span></h3>"
            "<p class='sm'>Regel: op het slot van de laatste handelsdag van de maand de 20 aandelen met het hoogste rendement van 12 tot 1 maand "
            "geleden, gelijk gewogen, kopen op de volgende open -- alleen als SPY boven zijn 200-daags sloot. Een maand vasthouden, "
            "geen stops (de trendfilter is de rem).</p>"
            + official + exits + preview + "</div>")
    if signals:
        rows = ""
        for s in signals:
            label, cls, expl = STATE_NL[s.state]
            trig = (f"verkoop als slot &gt; {s.sell_above:,.2f}" if s.sell_above is not None else
                    (f"koop als slot &le; {s.buy_below:,.2f}" + ("" if s.above_200 else " (maar onder de 200-daags: geen trade)")
                     if s.buy_below is not None else "-"))
            rows += (f"<tr><td><b>{s.etf}</b></td><td><span class='gb {cls}'>{label}</span></td><td>{s.close:,.2f}</td>"
                     f"<td>{s.rsi2:.1f}</td><td>{s.sma5:,.2f}</td><td>{s.sma200:,.2f} ({'boven' if s.above_200 else 'ONDER'})</td>"
                     f"<td>{trig}</td><td class='sm'>{escape(expl)}"
                     + (f" In positie sinds signaal van {_date(s.entry_date)}." if s.entry_date is not None and s.state == 'HOUDEN' else "")
                     + "</td></tr>")
        parts.append(
            "<div class='card'><h3 style='margin-top:0'>INDEX RSI(2)</h3>"
            "<p class='sm'>Koop een index-ETF op de open na een slot boven zijn 200-daags met RSI(2) &lt; 10; verkoop op de open na het "
            "eerste slot boven zijn 5-daags. Positief in 1999-2007, 2008-2021 en 2022-2026 op alle vier: +0,2..+0,6% per trade in "
            "~3,5 dagen, 64-79% winnaars. De trigger-kolom is de slotkoers voor morgen die het signaal geeft.</p>"
            "<table><thead><tr><th>ETF</th><th>Status</th><th>Slot</th><th>RSI(2)</th><th>5-daags</th><th>200-daags</th>"
            "<th>Trigger morgen</th><th>Uitleg</th></tr></thead><tbody>" + rows + "</tbody></table></div>")
    return "".join(parts)


def build_forward_html(summ: dict | None, results: list, momentum: pd.DataFrame | None) -> str:
    """'Live logboek' card: how the logged signals actually turned out."""
    if summ is None:
        return ""
    rows = ""
    for b in sorted(results, key=lambda x: x.signal_date, reverse=True)[:30]:
        r = "-" if b.r is None else f"{b.r:+.2f}R"
        rows += (f"<tr><td>{_date(b.signal_date)}</td><td><b>{escape(b.ticker)}</b></td><td>{b.status}</td>"
                 f"<td>{'-' if b.entry is None else f'{b.entry:,.2f}'}</td><td>{'-' if b.exit is None else f'{b.exit:,.2f}'}</td>"
                 f"<td>{r}</td><td>{b.days}</td><td class='sm'>{escape(b.reason)}</td></tr>")
    mom_rows = ""
    if momentum is not None and len(momentum):
        for m in momentum.sort_values("as_of", ascending=False).itertuples():
            mom_rows += (f"<tr><td>{_date(m.as_of)}</td><td>{_date(m.until)}</td><td>{'belegd' if m.invested else 'cash'}</td>"
                         f"<td>{m.book_pct:+.1f}%</td><td>{m.spy_pct:+.1f}%</td></tr>")
    wr = "-" if summ["win_pct"] is None else f"{summ['win_pct']:.0f}%"
    ar = "-" if summ["avg_r"] is None else f"{summ['avg_r']:+.2f}R"
    return (
        "<div class='card'><h3 style='margin-top:0'>Live logboek (forward test)</h3>"
        "<p class='sm'>Elke scan schrijft zijn signalen weg (logs/signal_log.csv) en volgt ze met exact de backtest-regels. "
        "Dit is de enige echte test: na een paar maanden zie je of het systeem live doet wat de backtest belooft "
        "(breakouts: backtest ~+0,2..+0,5R per trade, 38% winnaars).</p>"
        f"<p><b>Breakouts</b>: {summ['signals']} signalen, {summ['closed']} gesloten, {summ['open']} open &middot; "
        f"winnaars {wr} &middot; gemiddeld {ar} &middot; totaal {summ['total_r']:+.1f}R</p>"
        + ("<table><thead><tr><th>Signaal</th><th>Ticker</th><th>Status</th><th>Instap</th><th>Uitstap</th><th>R</th>"
           "<th>Dagen</th><th>Reden</th></tr></thead><tbody>" + rows + "</tbody></table>" if rows else "<p class='sm'>Nog geen breakouts gelogd.</p>")
        + ("<p><b>Momentum-maandlijsten</b> (gelijk gewogen, slot tot slot, tegenover SPY)</p><table><thead><tr><th>Lijst van</th>"
           "<th>Tot</th><th>Stand</th><th>Lijst</th><th>SPY</th></tr></thead><tbody>" + mom_rows + "</tbody></table>" if mom_rows else "")
        + "</div>")


# --------------------------------------------------------------------------- #
# "Instappen of niet?" -- one decision per stock, from the TESTED monthly rule
# --------------------------------------------------------------------------- #

def chart_flags(rep) -> tuple[bool, str]:
    """(warning?, short text) from a ta/ TechnicalReport. Information only: research rounds 13
    and 14 (Q4) found that none of these warnings predicted the next month of a momentum pick."""
    if rep is None or not rep.daily.ok or rep.score is None:
        return False, "geen grafiekanalyse"
    fa, p = rep.daily, rep.primary
    warn = []
    above = [z for z in fa.zones if z.low > fa.close]
    if above and fa.atr > 0:
        z = min(above, key=lambda z: z.low)
        room = (z.low - fa.close) / fa.atr
        if room <= 1:
            warn.append(f"weerstand vlak erboven ({z.low:,.2f}, {room:.1f} ATR)")
    if fa.trend.direction < 0:
        warn.append(f"dagtrend omlaag ({fa.trend.label_nl})")
    elif p is not None and p.direction < 0 and p.status in ("triggered", "confirmed"):
        warn.append(f"grafiek wijst omlaag ({p.name_nl})")
    if fa.trend.exhaustion:
        warn.append("overstrekt")
    setup = f"{p.name_nl} ({p.status_nl})" if p is not None else "geen setup"
    return bool(warn), ("⚠ " + "; ".join(warn) if warn else "✓ grafiek in lijn") + f" -- {setup}, score {rep.score.total:.0f}"


def decision_rows(book, ta_by_ticker: dict | None = None) -> list[dict]:
    """One row per stock that matters this month: verdict (JA / NEE / NOG NIET), what to do,
    and the chart note. The verdict follows ONLY the tested month-end rule."""
    ta_by_ticker = ta_by_ticker or {}
    if book is None or book.as_of is None:
        return []
    nxt = _date(book.next_rebalance)
    rows = []
    for p in book.picks:
        warn, chart = chart_flags(ta_by_ticker.get(p.ticker))
        if not book.invested:
            rows.append({"ticker": p.ticker, "verdict": "NEE", "cls": "no",
                         "do": "Niet kopen: markt uit (alles cash)", "chart": chart, "warn": warn})
        elif p.status == "NIEUW":
            rows.append({"ticker": p.ticker, "verdict": "JA", "cls": "yes",
                         "do": "Kopen (nieuw deze maand)", "chart": chart, "warn": warn})
        else:
            rows.append({"ticker": p.ticker, "verdict": "JA", "cls": "yes",
                         "do": "Houden (nog niet in bezit? kopen)", "chart": chart, "warn": warn})
    back = set(book.preview_in)
    for t in book.exits:
        rows.append({"ticker": t, "verdict": "NEE", "cls": "no",
                     "do": "Verkopen (uit de lijst)" + (
                         f"; komt mogelijk terug op {nxt}, pas dan weer kopen"
                         if t in back else ""), "chart": "", "warn": False})
    held = {p.ticker for p in book.picks} | set(book.exits)
    for t in book.preview_in:
        if t not in held:
            warn, chart = chart_flags(ta_by_ticker.get(t))
            rows.append({"ticker": t, "verdict": "NOG NIET", "cls": "wait",
                         "do": f"Nu niet; komt mogelijk in de lijst op {nxt}",
                         "chart": chart, "warn": warn})
    return rows


DECISION_CSS = (
    ".dec h2{margin:0 0 4px;font-size:20px}.dec .mkt{font-size:15px;margin:6px 0 12px}"
    ".dec table{width:100%;border-collapse:collapse}.dec td,.dec th{padding:7px 8px;border-bottom:1px solid var(--line);"
    "vertical-align:top;text-align:left}.dec th{cursor:default}"
    ".vd{display:inline-block;min-width:74px;text-align:center;font-weight:800;font-size:13px;padding:4px 8px;border-radius:6px}"
    ".vd.yes{background:rgba(63,185,80,.18);color:var(--green)}.vd.no{background:rgba(248,81,73,.18);color:var(--red)}"
    ".vd.wait{background:rgba(210,153,34,.18);color:var(--amber)}.dec .ch{color:var(--ink-soft);font-size:12px}"
    ".dec .ch.w{color:var(--ink-soft)}.dec .tk{font-weight:700;font-size:15px}"
    "")


def _decision_table(rows: list[dict], names: dict | None = None) -> str:
    names = names or {}
    body = "".join(
        f"<tr><td><a class='tk' href='#ta-{escape(r['ticker'])}' onclick=\"openTa('{escape(r['ticker'])}')\">{escape(r['ticker'])}</a>"
        + (f"<div class='ch'>{escape(names[r['ticker']][:28])}</div>" if names.get(r["ticker"]) else "") + "</td>"
        f"<td><span class='vd {r['cls']}'>{r['verdict']}</span></td><td>{escape(r['do'])}"
        + (f"<div class='ch{' w' if r['warn'] else ''}'>{escape(r['chart'])}</div>" if r["chart"] else "")
        + "</td></tr>" for r in rows)
    return ("<table><thead><tr><th>Aandeel</th><th>Instappen?</th><th>Wat doen <span class='sm'>(grijs: grafiek, info)</span></th>"
            f"</tr></thead><tbody>{body}</tbody></table>")


def build_niche_html(niche, ta: dict, main_book=None) -> str:
    """NICHE FINDS section: same month-end rule over US stocks outside the S&P 500. Not tested."""
    if niche is None or niche.as_of is None:
        return ""
    # names that left the niche list get one small line, not a red row each (you most likely never held them)
    rows = [r for r in decision_rows(niche, ta) if r["ticker"] not in set(niche.exits)]
    for r in rows:    # round 14: no edge in the test -> follow, never a tested buy
        if r["verdict"] == "JA":
            r.update(verdict="VOLGEN", cls="wait", do="Volgen, geen geteste koop" + (" (nieuw in de lijst)" if "nieuw" in r["do"] else ""))
    gone = (f"<p class='sm'>Vorige maand nog in de niche-lijst, nu niet meer (heb je ze, dan verkopen): "
            f"{escape(', '.join(niche.exits))}.</p>" if niche.exits else "")
    in_main = {p.ticker for p in main_book.picks} if main_book is not None else set()
    for r in rows:
        if r["ticker"] in in_main:
            r["do"] += " -- staat ook in de momentum top 20"
    names = {p.ticker: p.sector for p in niche.picks + niche.preview}
    return (
        "<h3 style='margin:4px 0 2px'>Niche finds <span class='sm'>minder bekende aandelen</span></h3>"
        f"<p class='sm'>Dezelfde maandregel (top {len(niche.picks)} op 12-1 maand momentum, SPY-filter), maar over alle "
        f"Amerikaanse aandelen <b>buiten de S&amp;P 500</b> vanaf $10 en $10M omzet per dag "
        f"({niche.eligible_count:,} kwamen in aanmerking), alleen binnen 25% van hun 52-weekse top. "
        "<b>Getest in ronde 14 (2011-2026): geen voorsprong.</b> Deze lijst deed het niet beter dan een willekeurig klein "
        "aandeel en slechter dan SPY (Sharpe 0,41 / 0,38 / 0,41 tegen SPY 0,80 / 0,66 / 1,40), met dalingen tot ~40%, "
        "terwijl de test kleine aandelen zelfs bevoordeelt. Alleen om te volgen; de geteste koop staat in de momentum top 20.</p>"
        + _decision_table(rows, names) + gone)


def build_decision_html(cfg, book, ta_reports: list | None = None, account_size: float | None = None,
                        niche_book=None) -> str:
    """The first thing on the dashboard: enter or not, per stock."""
    if cfg.momentum_pct <= 0 or book is None:
        niche = build_niche_html(niche_book, {r.ticker: r for r in (ta_reports or [])})
        return f"<div class='card dec'><h2>Instappen of niet?</h2>{niche}</div>" if niche else ""
    if book.as_of is None:
        return "<div class='card dec'><h2>Instappen of niet?</h2><p>Nog geen maandlijst: te weinig data.</p></div>"
    ta = {r.ticker: r for r in (ta_reports or [])}
    rows = decision_rows(book, ta)
    n = max(cfg.momentum_top_n, 1)
    per = cfg.momentum_pct / n
    amount = f" (&asymp; {_money(account_size * per / 100)})" if account_size else ""
    if book.invested:
        mkt = (f"<b style='color:var(--green)'>Markt AAN</b> -- SPY sloot op {_date(book.as_of)} boven zijn 200-daags: "
               f"belegd in de momentum top {len(book.picks)} hieronder, elk {per:.1f}% van je account{amount}.")
    else:
        mkt = (f"<b style='color:var(--red)'>Markt UIT</b> -- SPY sloot op {_date(book.as_of)} onder zijn 200-daags: "
               "alles in cash, nergens instappen.")
    now = ""
    if book.spy_above_200_now is not None and book.spy_above_200_now != book.invested:
        now = (f"<p class='sm'>Let op: SPY staat nu {'boven' if book.spy_above_200_now else 'ONDER'} zijn 200-daags. "
               f"Dat telt pas bij het slot van {_date(book.next_rebalance)}.</p>")
    return (
        "<div class='card dec'><h2>Instappen of niet?</h2>"
        f"<p class='sm'>Koersen t/m het slot van {_date(book.preview_date)}. Volgende beslismoment: slot van "
        f"<b>{_date(book.next_rebalance)}</b> (kopen/verkopen op de open daarna).</p>"
        f"<p class='mkt'>{mkt}</p>{now}"
        + "<h3 style='margin:12px 0 2px'>Momentum top 20 <span class='sm'>het geteste plan</span></h3>"
        + _decision_table(rows)
        + "<div style='margin-top:18px'>" + build_niche_html(niche_book, ta, book) + "</div>" +
        "<p class='sm'><b>Niet in deze tabellen = niet instappen.</b> Chartpatronen, breakouts en de andere setups op dit dashboard "
        "zijn info: in de tests deden ze het niet beter dan een willekeurig aandeel. Het advies volgt alleen de geteste "
        "maandregel. De grijze grafiekregel verandert het advies niet: in ronde 14 voorspelden de waarschuwingen "
        "(weerstand vlak erboven, dagtrend omlaag, overstrekt) en de technische score niets over de volgende maand; "
        "aandelen met weerstand vlak erboven deden het zelfs iets beter. Klik op een ticker voor de volledige analyse.</p></div>")
