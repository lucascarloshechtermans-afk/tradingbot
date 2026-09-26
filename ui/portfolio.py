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


def allocation_rows(cfg, account_size: float, bear: bool | None) -> list[tuple[str, str, str, str]]:
    """(system, % of account, amount, per-position rule)"""
    n = max(cfg.momentum_top_n, 1)
    dip_risk = cfg.dip_risk_pct_of_account * (0.5 if bear else 1.0)
    cash = max(0.0, 100 - cfg.momentum_pct - cfg.dip_pct - cfg.index_rsi2_pct)
    rows = [
        ("MOMENTUM TOP 20", f"{cfg.momentum_pct:.0f}%", _money(account_size * cfg.momentum_pct / 100),
         f"{cfg.momentum_pct / n:.1f}% van je account per aandeel ({_money(account_size * cfg.momentum_pct / 100 / n)}), "
         f"maandelijks herbalanceren; alles in cash als SPY op het maandeinde onder zijn 200-daags sloot"),
        ("LEADER DIP swings", f"{cfg.dip_pct:.0f}%", _money(account_size * cfg.dip_pct / 100),
         f"risico {dip_risk:.2f}% van je account per trade ({_money(account_size * dip_risk / 100)})"
         f"{' -- gehalveerd: SPY onder zijn 200-daags' if bear else ''}; max {cfg.dip_max_positions} tegelijk, "
         f"max 20% van dit deel per positie"),
        ("INDEX RSI(2)", f"{cfg.index_rsi2_pct:.0f}%", _money(account_size * cfg.index_rsi2_pct / 100),
         f"{cfg.index_rsi2_pct / 4:.1f}% van je account per ETF met een KOOP-signaal "
         f"({_money(account_size * cfg.index_rsi2_pct / 400)}); de rest van dit deel in cash / geldmarkt"),
    ]
    if cash > 0:
        rows.append(("Cash (niet toegewezen)", f"{cash:.0f}%", _money(account_size * cash / 100), "geldmarkt / T-bills"))
    return rows


def todo_items(cfg, book, signals: list, n_dips: int, bear: bool | None) -> list[str]:
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
        items.append(f"Dip-swings: {n_dips} LEADER DIP{'s' if n_dips != 1 else ''} vandaag"
                     + (" (halve risico's: SPY onder zijn 200-daags)" if bear else "") + " -- zie hieronder.")
    return items


def build_todo_html(cfg, book, signals: list, n_dips: int, bear: bool | None) -> str:
    items = todo_items(cfg, book, signals, n_dips, bear)
    return ("<div class='card'><h3 style='margin-top:0'>Vandaag te doen "
            f"<span class='sm'>portefeuilleplan {cfg.momentum_pct:.0f}/{cfg.dip_pct:.0f}/{cfg.index_rsi2_pct:.0f} "
            "(momentum / dip / index) -- details in de tab Portefeuille</span></h3><ul>"
            + "".join(f"<li>{i}</li>" for i in items) + "</ul></div>")


def _pick_rows(picks: list, closes: pd.DataFrame | None) -> str:
    rows = ""
    for p in picks:
        spark = _spark(closes[p.ticker]) if closes is not None and p.ticker in closes else ""
        badge = "gA" if p.status == "NIEUW" else "gB"
        rows += (f"<tr><td>{p.rank}</td><td><b>{escape(p.ticker)}</b></td><td>{escape(p.sector or '-')}</td>"
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
        "Verdeling instelbaar onder <code>portfolio:</code> in config.yaml (optie 1 = 100/0/0, 2 = 0/100/0, 3 = 50/50/0, "
        "4 = 0/0/100, 5 = 40/40/20).</p>"
        "<table><thead><tr><th>Systeem</th><th>Deel</th><th>Bedrag</th><th>Per positie</th></tr></thead><tbody>"
        + alloc + "</tbody></table>"
        "<p class='sm'>Backtest 2008-2021 / 2022-2026 (40/40/20, onderzoeks- en controle-aandelen): 11.8-13.2% / 13.7-17.8% per jaar, "
        "grootste daling 24-25% / 19-20%. Aandelen-backtests zijn ~4-5%/jaar te rooskleurig (aandelen die uit de index "
        "vielen ontbreken) -- reken op ~9-14% met dalingen tot ~25%. Geen garantie.</p></div>"
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
            f"{_date(book.as_of)} &middot; {book.eligible_count} van {book.universe_size} aandelen (S&amp;P 500 + 400 + scannerlijst) komen in aanmerking</span></h3>"
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
