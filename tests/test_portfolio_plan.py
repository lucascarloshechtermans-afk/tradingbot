import pandas as pd
import pytest

from analysis.index_rsi2 import IndexSignal
from analysis.momentum_portfolio import MomentumBook, MomentumPick
from config.schema import ConfigError, PortfolioConfig
from ui.dashboard import build_dashboard_html
from ui.portfolio import allocation_rows, build_portfolio_tab_html, build_todo_html


def _book(invested=True):
    picks = [MomentumPick(1, "AAA", "Tech", 150.0, 3.0, 10.0, "NIEUW"), MomentumPick(2, "BBB", None, 90.0, -2.0, 20.0, "BLIJFT")]
    return MomentumBook(as_of=pd.Timestamp("2026-08-31"), invested=invested, picks=picks, exits=["CCC"],
                        preview_date=pd.Timestamp("2026-09-25"), preview=picks, preview_in=[], preview_out=[],
                        spy_above_200_now=True, next_rebalance=pd.Timestamp("2026-09-30"), eligible_count=900, universe_size=960)


def _sig(state="KOOP"):
    return IndexSignal("QQQ", pd.Timestamp("2026-09-25"), 500.0, 5.0, 510.0, 450.0, state, None, 505.0)


def test_portfolio_config_defaults_and_validation():
    cfg = PortfolioConfig.from_dict({})
    assert (cfg.momentum_pct, cfg.dip_pct, cfg.index_rsi2_pct) == (40, 40, 20)
    assert cfg.dip_risk_pct_of_account == pytest.approx(0.4)
    with pytest.raises(ConfigError):
        PortfolioConfig.from_dict({"momentum_pct": 80, "dip_pct": 40})


def test_allocation_rows_amounts_and_bear_halving():
    cfg = PortfolioConfig()
    rows = allocation_rows(cfg, 10_000, bear=False)
    assert [r[2] for r in rows] == ["4,000", "4,000", "2,000"]
    assert "2.0% van je account per aandeel" in rows[0][3]
    assert "0.40%" in rows[1][3] and "0.20%" in allocation_rows(cfg, 10_000, bear=True)[1][3]
    assert rows[-1][0] != "Cash (niet toegewezen)"
    assert allocation_rows(PortfolioConfig(50, 30, 0), 10_000, bear=False)[-1][0] == "Cash (niet toegewezen)"


def test_todo_and_tab_render_every_system():
    cfg = PortfolioConfig()
    todo = build_todo_html(cfg, _book(), [_sig()], n_dips=2, bear=False)
    assert "KOOP QQQ" in todo and "AAA" in todo and "2 LEADER DIPs" in todo
    tab = build_portfolio_tab_html(cfg, 10_000, _book(), [_sig("HOUDEN")], bear=False)
    assert "MOMENTUM TOP 20" in tab and "INDEX RSI(2)" in tab and "verkoop als slot &gt; 505.00" in tab
    assert "CCC" in tab
    cash = build_portfolio_tab_html(cfg, 10_000, _book(invested=False), [], bear=True)
    assert "CASH" in cash


def test_dashboard_has_portfolio_tab():
    html = build_dashboard_html([], {}, [], [], 0, 0.0, portfolio_cfg=PortfolioConfig(), momentum_book=_book(),
                                index_signals=[_sig()], market_state={"spy_below_200": False})
    assert 'data-tab="portfolio"' in html and "Vandaag te doen" in html and "Portefeuilleplan" in html
