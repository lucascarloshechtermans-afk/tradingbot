import json

from scanner import TradePlan
from ui.dashboard import build_dashboard_html, trade_plan_to_row


def _sample_plan():
    return TradePlan(
        ticker="AAPL",
        setup="Bullish Breakout",
        trend="bullish",
        score=82.5,
        label="Strong setup",
        entry=190.0,
        stop=184.0,
        target1=199.0,
        target2=208.0,
        risk_reward=3.0,
        atr_pct=2.1,
        relative_volume=1.8,
        market_regime="BULLISH",
        sector="Technology",
        confidence=80.0,
        reasons=["Breakout above 20-day high", "Volume confirmation"],
        risks=["Resistance nearby"],
        rsi=64.0,
        recent_closes=[180, 182, 185, 188, 190],
        category_breakdown=[
            {"category": "trend", "score": 70.0, "weight": 8, "contribution": 5.6, "reasons": ["Above 20/50/200 SMA"]},
            {"category": "market_structure", "score": 85.0, "weight": 7, "contribution": 5.95, "reasons": ["Higher highs, higher lows"]},
        ],
    )


def test_trade_plan_to_row_has_expected_keys():
    row = trade_plan_to_row(_sample_plan())
    assert row["ticker"] == "AAPL"
    assert row["score"] == 82.5
    assert row["recent_closes"] == [180, 182, 185, 188, 190]


def test_trade_plan_to_row_includes_category_breakdown():
    row = trade_plan_to_row(_sample_plan())
    assert len(row["category_breakdown"]) == 2
    assert row["category_breakdown"][0]["category"] == "trend"
    assert row["category_breakdown"][1]["category"] == "market_structure"


def test_trade_plan_to_row_includes_explanation():
    plan = _sample_plan()
    plan.explanation = {
        "why_it_passed": ["Breakout above 20-day high"], "why_it_could_fail": ["Resistance nearby"],
        "structure": [], "momentum": [], "volume": [], "context": [], "levels": ["Entry: 190.00"], "risk": ["ATR: 2.1%"],
    }
    row = trade_plan_to_row(plan)
    assert row["explanation"]["why_it_passed"] == ["Breakout above 20-day high"]
    assert row["explanation"]["levels"] == ["Entry: 190.00"]


def test_build_dashboard_html_embeds_explanation():
    plan = _sample_plan()
    plan.explanation = {"why_it_passed": ["Strong setup"], "why_it_could_fail": [], "structure": [], "momentum": [], "volume": [], "context": [], "levels": [], "risk": []}
    row = trade_plan_to_row(plan)
    html = build_dashboard_html(
        scan_rows=[row], market_regime={}, sector_ranked=[], watchlist_entries=[], universe_size=1, scan_duration_s=0.1,
    )
    assert "renderExplanation" in html
    assert "Strong setup" in html


def test_build_dashboard_html_embeds_category_breakdown():
    row = trade_plan_to_row(_sample_plan())
    html = build_dashboard_html(
        scan_rows=[row], market_regime={}, sector_ranked=[], watchlist_entries=[], universe_size=1, scan_duration_s=0.1,
    )
    assert "renderCategoryBreakdown" in html
    assert "market_structure" in html


def test_build_dashboard_html_embeds_scan_data():
    row = trade_plan_to_row(_sample_plan())
    html = build_dashboard_html(
        scan_rows=[row],
        market_regime={"label": "BULLISH", "score": 40, "factors": {"spy_trend": "bullish"}},
        sector_ranked=[{"rank": 1, "etf": "XLK", "performance_1m": 5.0, "performance_3m": 10.0, "relative_strength_vs_spy": 2.0, "trend": "improving"}],
        watchlist_entries=[],
        universe_size=100,
        scan_duration_s=12.3,
    )
    assert "<html" in html
    assert "AAPL" in html
    assert "BULLISH" in html
    assert "XLK" in html
    # the embedded JSON must be valid and round-trip the ticker
    start = html.index("const SCAN_DATA = ") + len("const SCAN_DATA = ")
    end = html.index(";\n", start)
    parsed = json.loads(html[start:end])
    assert parsed[0]["ticker"] == "AAPL"


def test_build_dashboard_html_handles_empty_results():
    html = build_dashboard_html(
        scan_rows=[], market_regime={}, sector_ranked=[], watchlist_entries=[], universe_size=0, scan_duration_s=0.0,
    )
    assert "No setups found" in html
    assert "<html" in html


def test_build_dashboard_html_includes_watchlist_entries():
    html = build_dashboard_html(
        scan_rows=[], market_regime={}, sector_ranked=[],
        watchlist_entries=[{"ticker": "MSFT", "status": "READY", "added_date": "2024-01-01", "setup_detected_date": "2024-01-05", "notes": "test"}],
        universe_size=0, scan_duration_s=0.0,
    )
    assert "MSFT" in html
