import numpy as np
import pandas as pd

from analysis.chart_read import read_chart
from ui.overview import build_overview_html, explain_chart


def _daily(n=320):
    idx = pd.bdate_range("2025-01-01", periods=n, tz="UTC")
    c = pd.Series(50 * np.exp(np.cumsum(np.full(n, 0.002))), index=idx)
    return pd.DataFrame({"open": c.shift(1).fillna(c.iloc[0]), "high": c * 1.01, "low": c * 0.99, "close": c, "volume": 1e6})


SECTORS = [{"rank": 1, "etf": "XLK", "performance_1m": 4.1, "performance_3m": 5.7, "relative_strength_vs_spy": 4.0,
            "trend": "stable"}]


def test_explain_chart_gives_dutch_reasons_for_the_emas():
    read = read_chart("TEST", _daily(), hourly=None)
    bullets = explain_chart(read)
    assert any("200 EMA op de dag" in b for b in bullets)
    assert any("gestapeld" in b for b in bullets)


def test_overview_says_no_trade_without_grade_a_or_b_and_lists_sectors():
    html = build_overview_html([], [], [], SECTORS, {}, {"vix": 14.9, "spy_below_50": False})
    assert "NO TRADE vandaag" in html
    assert "Technology" in html and "Overzicht per sector" in html


def test_overview_shows_research_note_and_trend_sizing():
    html = build_overview_html([], [], [], SECTORS, {}, {"vix": 22.0, "spy_below_50": True, "spy_below_200": True})
    assert "Wat het onderzoek zegt" in html
    assert "willekeurig aandeel" in html
    assert "ONDER zijn 200-daags" in html and "halve posities" in html
