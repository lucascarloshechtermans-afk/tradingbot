import numpy as np
import pandas as pd

from analysis.momentum_portfolio import build_book, month_end_rows, rank_at


def _panel(n_days=320, n=30, end="2026-03-17", seed=0):
    idx = pd.bdate_range(end=end, periods=n_days)
    rng = np.random.default_rng(seed)
    closes = {}
    for i in range(n):
        drift = 0.0002 * i  # T29 has the strongest trend
        closes[f"T{i:02d}"] = 50 * np.exp(np.cumsum(rng.normal(drift, 0.005, n_days)))
    c = pd.DataFrame(closes, index=idx)
    v = pd.DataFrame(1e6, index=idx, columns=c.columns)  # $50M a day
    return c, v


def test_month_end_rows_only_completed_months():
    idx = pd.bdate_range("2026-01-01", "2026-03-17")
    rows = month_end_rows(idx)
    assert [idx[r].strftime("%Y-%m-%d") for r in rows] == ["2026-01-30", "2026-02-27"]
    idx2 = pd.bdate_range("2026-01-01", "2026-03-31")
    assert idx2[month_end_rows(idx2)[-1]].strftime("%Y-%m-%d") == "2026-03-31"


def test_rank_uses_12_minus_1_month_return_and_skips_last_month():
    c, v = _panel()
    ranked = [t for t, *_ in rank_at(c, v, len(c) - 1, top_n=5)]
    assert ranked[0] in ("T29", "T28", "T27")
    # a huge jump inside the skipped last month must not move a flat stock to the top
    c2 = c.copy()
    c2.iloc[-10:, c2.columns.get_loc("T00")] *= 3
    ranked2 = [t for t, *_ in rank_at(c2, v, len(c2) - 1, top_n=5)]
    assert "T00" not in ranked2


def test_rank_filters_price_and_liquidity():
    c, v = _panel()
    c["T29"] = c["T29"] / 100          # below $5
    v["T28"] = 1.0                     # no dollar volume
    ranked = [t for t, *_ in rank_at(c, v, len(c) - 1, top_n=30)]
    assert "T29" not in ranked and "T28" not in ranked


def test_book_goes_to_cash_below_spy_200d_and_tracks_changes():
    c, v = _panel()
    up = pd.Series(np.linspace(100, 200, len(c)), index=c.index)
    down = pd.Series(np.linspace(200, 100, len(c)), index=c.index)
    b_up = build_book(c, v, up, {}, top_n=5)
    b_dn = build_book(c, v, down, {}, top_n=5)
    assert b_up.invested and not b_dn.invested
    assert b_up.as_of == pd.Timestamp("2026-02-27")
    assert len(b_up.picks) == 5 and {p.status for p in b_up.picks} <= {"NIEUW", "BLIJFT"}
    assert b_up.next_rebalance == pd.Timestamp("2026-03-31")
    assert set(b_up.preview_in) <= {p.ticker for p in b_up.preview}
