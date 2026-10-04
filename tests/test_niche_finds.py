import numpy as np
import pandas as pd

from config.schema import load_config
from data.us_listed import parse_listings

NASDAQ = """Symbol|Security Name|Market Category|Test Issue|Financial Status|Round Lot Size|ETF|NextShares
CDNA|CareDx, Inc. - Common Stock|Q|N|N|100|N|N
QQQ|Invesco QQQ Trust|G|N|N|100|Y|N
ZZZT|Test Stock|Q|Y|N|100|N|N
ABCDW|Abcd Corp - Warrant|S|N|N|100|N|N
SPCU|Space Acquisition Corp - Units|S|N|N|100|N|N
BADX|Bad Co - Common Stock|S|N|D|100|N|N
ADRX|Some Pharma - American Depositary Shares|G|N|N|100|N|N
File Creation Time: 1004202618:00|||||||
"""
OTHER = """ACT Symbol|Security Name|Exchange|CQS Symbol|ETF|Round Lot Size|Test Issue|NASDAQ Symbol
MU|Micron Technology Common Stock|N|MU|N|100|N|MU
ABRD|Arbor Realty 6.375% Preferred|N|ABR$D|N|100|N|ABRD
SPY|SPDR S&P 500 ETF|P|SPY|Y|100|N|SPY
PFND|Some Income Fund|N|PFND|N|100|N|PFND
BRKB|Arca listed thing|P|BRKB|N|100|N|BRKB
File Creation Time: 1004202618:00||||||
"""


def test_listing_parser_keeps_only_common_stock():
    out = parse_listings(NASDAQ, OTHER)
    assert set(out) == {"CDNA", "ADRX", "MU"}


class _Prov:
    def __init__(self):
        self.keys = []

    def get_us_listed(self):
        return {"AAA": "Aaa Inc. - Common Stock", "BBB": "Bbb Corp - Common Stock", "MU": "Micron Technology Common Stock"}

    def get_universe_closes(self, tickers, latest_session=None, key="momuni"):
        self.keys.append((key, tuple(tickers)))
        idx = pd.bdate_range("2025-06-02", "2026-09-30")
        g = {"AAA": 0.004, "BBB": 0.001, "MU": 0.006}
        c = pd.DataFrame({t: 20 * np.exp(g[t] * np.arange(len(idx))) for t in tickers}, index=idx)
        return c, pd.DataFrame(2e6, index=idx, columns=c.columns)


def test_niche_book_excludes_the_sp500_and_uses_its_own_cache():
    from scanner import find_niche_book
    prov = _Prov()
    spy = pd.DataFrame({"close": np.linspace(400, 600, 400)}, index=pd.bdate_range("2025-02-03", periods=400))
    book = find_niche_book(prov, load_config(), spy)
    assert prov.keys[0][0] == "niche" and "MU" not in prov.keys[0][1]      # S&P 500 names are not niche
    assert [p.ticker for p in book.picks] == ["AAA", "BBB"] and book.picks[0].sector == "Aaa Inc."
    cfg = load_config()
    cfg.portfolio.niche_enabled = False
    assert find_niche_book(prov, cfg, spy) is None


def test_decision_card_shows_the_tested_list_first_and_niche_as_follow_only():
    from types import SimpleNamespace as NS

    from ui.portfolio import build_decision_html
    mk = lambda ts, st: [NS(ticker=t, status=st, sector=f"{t} Inc.") for t in ts]  # noqa: E731
    base = dict(as_of=pd.Timestamp("2026-09-30"), invested=True, exits=[], preview_in=[], preview=[],
                next_rebalance=pd.Timestamp("2026-10-30"), preview_date=pd.Timestamp("2026-10-02"), spy_above_200_now=True)
    main = NS(picks=mk(["SNDK", "VICR"], "BLIJFT"), **base)
    niche = NS(picks=mk(["CDNA", "VICR"], "NIEUW"), eligible_count=1234, **{**base, "exits": ["OLDBIO"]})
    html = build_decision_html(load_config().portfolio, main, [], 10_000, niche)
    assert html.index("Momentum top 20") < html.index("Niche finds") and "CDNA Inc." in html
    assert "staat ook in de momentum top 20" in html and "geen voorsprong" in html
    assert "VOLGEN" in html and html.index("VOLGEN") > html.index("Niche finds")
    assert "nu niet meer (heb je ze, dan verkopen): OLDBIO" in html and "openTa('OLDBIO')" not in html


def test_trend_quality_filters_drop_one_day_jumps_and_names_far_below_their_high():
    from analysis.momentum_portfolio import rank_at
    n = 300
    idx = pd.bdate_range("2025-06-02", periods=n)
    steady = 20 * np.exp(0.004 * np.arange(n))                       # trend: gain spread over many days
    jump = np.r_[np.full(100, 20.0), np.full(n - 100, 60.0)]         # +200% in one day (trial news)
    faded = np.r_[20 * np.exp(0.012 * np.arange(200)), np.linspace(20 * np.exp(0.012 * 199), 60, n - 200)]
    c = pd.DataFrame({"STDY": steady, "JUMP": jump, "FADE": faded}, index=idx)
    v = pd.DataFrame(1e6, index=idx, columns=c.columns)
    raw = [t for t, *_ in rank_at(c, v, n - 1, 10)]
    assert set(raw) == {"STDY", "JUMP", "FADE"}                      # main-list rule: unchanged
    assert [t for t, *_ in rank_at(c, v, n - 1, 10, max_jump=0.33)] == [t for t in raw if t != "JUMP"]
    assert "FADE" not in [t for t, *_ in rank_at(c, v, n - 1, 10, near_high=0.75)]
