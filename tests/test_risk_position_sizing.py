import pytest

from risk.position_sizing import compute_position_size


def test_position_size_basic_math():
    result = compute_position_size(
        entry=100.0, stop=98.0, account_size=10_000, risk_per_trade_pct=1.0, max_position_pct=100.0
    )
    # risk_amount = 100, stop_distance = 2 -> 50 shares
    assert result.risk_amount == 100.0
    assert result.stop_distance == 2.0
    assert result.shares == 50
    assert result.capped_by_max_position is False


def test_position_size_rounds_down_never_up():
    # risk_amount=100, stop_distance=3 -> 33.33 shares -> must round DOWN to 33
    result = compute_position_size(
        entry=100.0, stop=97.0, account_size=10_000, risk_per_trade_pct=1.0, max_position_pct=100.0
    )
    assert result.shares == 33
    assert result.shares * result.stop_distance <= result.risk_amount


def test_position_size_capped_by_max_position_pct():
    # huge risk tolerance would size a massive position; max_position_pct caps it
    result = compute_position_size(
        entry=100.0, stop=99.0, account_size=10_000, risk_per_trade_pct=50.0, max_position_pct=20.0
    )
    assert result.capped_by_max_position is True
    assert result.position_value <= 10_000 * 0.20 + 1e-6


def test_position_size_rejects_equal_entry_and_stop():
    with pytest.raises(ValueError):
        compute_position_size(entry=100.0, stop=100.0, account_size=10_000, risk_per_trade_pct=1.0)


def test_position_size_rejects_nonpositive_entry():
    with pytest.raises(ValueError):
        compute_position_size(entry=0.0, stop=-1.0, account_size=10_000, risk_per_trade_pct=1.0)


def test_position_size_zero_shares_when_risk_too_small():
    result = compute_position_size(entry=1000.0, stop=999.0, account_size=100, risk_per_trade_pct=0.5)
    # risk_amount = 0.5, stop_distance = 1 -> 0 shares (rounds down, never fractional)
    assert result.shares == 0
