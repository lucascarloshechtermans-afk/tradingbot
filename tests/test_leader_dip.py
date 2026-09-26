import numpy as np
import pandas as pd

from analysis.leader_dip import evaluate, find_leader_dips, market_state


def _frame(close: np.ndarray) -> pd.DataFrame:
    idx = pd.bdate_range("2024-01-01", periods=len(close), tz="UTC")
    c = pd.Series(close, index=idx)
    o = c.shift(1).fillna(c.iloc[0])
    return pd.DataFrame({"open": o, "high": np.maximum(o, c) * 1.02, "low": np.minimum(o, c) * 0.98,
                         "close": c, "volume": 1e6})


def _universe(leader_dip: bool = True) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(0)
    out = {}
    for i in range(12):
        drift = 0.0005 * i
        close = 50 * np.exp(np.cumsum(rng.normal(drift, 0.01, 320)))
        out[f"T{i}"] = _frame(close)
    lead = 50 * np.exp(np.cumsum(np.full(320, 0.008)))  # clearly the strongest name
    if leader_dip:
        lead[-5:] = lead[-6] * np.array([0.97, 0.94, 0.91, 0.88, 0.85])  # sharp 5-day drop
    out["LEAD"] = _frame(lead)
    return out


def test_market_state_reads_vix_and_spy_trend():
    spy = _frame(np.linspace(100, 80, 80))
    vix = _frame(np.full(10, 25.0))
    m = market_state(spy, vix)
    assert m["vix"] == 25.0 and m["spy_below_50"] is True
    assert m["spy_below_200"] is None  # not enough history for a 200-day SMA
    m = market_state(_frame(np.linspace(100, 80, 250)), vix)
    assert m["spy_below_200"] is True


def test_leader_in_a_dip_is_found_and_sized_by_spy_trend():
    hist = _universe()
    bull = find_leader_dips(hist, spy=_frame(np.linspace(80, 100, 250)), vix=_frame(np.full(10, 14.0)))
    bear = find_leader_dips(hist, spy=_frame(np.linspace(100, 80, 250)), vix=_frame(np.full(10, 28.0)))
    lead_bull = next(s for s in bull if s.ticker == "LEAD")
    lead_bear = next(s for s in bear if s.ticker == "LEAD")
    assert lead_bear.confirmations == lead_bull.confirmations + 2  # VIX/50-day still reported as context
    assert lead_bull.grade == "N" and lead_bear.grade == "H"
    assert any("200-day" in m for m in lead_bear.missing)
    assert lead_bear.stop_estimate < lead_bear.close
    assert lead_bear.hold_days == 10


def test_no_dip_or_no_leader_means_no_setup():
    hist = _universe(leader_dip=False)
    assert all(s.ticker != "LEAD" for s in find_leader_dips(hist, None, None))
    assert evaluate("LEAD", _universe()["LEAD"], momentum_rank=50.0, market={}) is None


def test_grade_is_a_trend_risk_dial_not_an_edge_claim():
    from analysis.leader_dip import RISK_PCT, grade_for

    assert grade_for({"spy_below_200": False, "vix": 30.0}, deep_dip=True, moves=True) == "N"
    assert grade_for({"spy_below_200": True, "vix": 12.0}) == "H"
    assert grade_for({}) == "N"  # unknown trend -> normal size
    # stock-level confirmations no longer change the grade (no edge vs random over 2008-2021)
    m = {"spy_below_200": False}
    assert grade_for(m, deep_dip=True, moves=True) == grade_for(m, deep_dip=False, moves=False)
    assert RISK_PCT["H"] == RISK_PCT["N"] / 2
