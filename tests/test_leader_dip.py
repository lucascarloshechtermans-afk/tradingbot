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


def test_leader_in_a_dip_is_found_and_graded_by_confirmations():
    hist = _universe()
    calm = find_leader_dips(hist, spy=_frame(np.linspace(80, 100, 80)), vix=_frame(np.full(10, 14.0)))
    fear = find_leader_dips(hist, spy=_frame(np.linspace(100, 80, 80)), vix=_frame(np.full(10, 28.0)))
    lead_calm = next(s for s in calm if s.ticker == "LEAD")
    lead_fear = next(s for s in fear if s.ticker == "LEAD")
    assert lead_fear.confirmations == lead_calm.confirmations + 2
    assert lead_calm.grade == "R"  # calm market: every leader dip, half size
    assert lead_fear.grade in ("A", "B")
    assert lead_fear.stop_estimate < lead_fear.close
    assert lead_fear.hold_days == 10


def test_no_dip_or_no_leader_means_no_setup():
    hist = _universe(leader_dip=False)
    assert all(s.ticker != "LEAD" for s in find_leader_dips(hist, None, None))
    assert evaluate("LEAD", _universe()["LEAD"], momentum_rank=50.0, market={}) is None


def test_grade_is_regime_dependent():
    from analysis.leader_dip import grade_for

    calm = {"vix": 14.0, "spy_below_50": False}
    stressed = {"vix": 26.0, "spy_below_50": False}
    weak_tape = {"vix": 15.0, "spy_below_50": True}
    assert grade_for(calm, deep_dip=True, moves=True) == "R"
    assert grade_for(calm, deep_dip=False, moves=False) == "R"
    assert grade_for(stressed, deep_dip=True, moves=True) == "A"
    assert grade_for(weak_tape, deep_dip=False, moves=True) == "B"
    assert grade_for(stressed, deep_dip=False, moves=False) == "C"
