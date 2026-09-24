import pytest

from price_action.levels import Level
from risk.stops_targets import (
    cap_target_to_horizon,
    compute_atr_stop,
    compute_rr_targets,
    compute_stop,
    compute_structure_stop,
    expected_move_for_horizon,
    nearest_structure_target,
    risk_reward_ratio,
)


def test_compute_atr_stop_long_below_entry():
    stop = compute_atr_stop(entry=100.0, atr=2.0, multiplier=2.0, direction="long")
    assert stop == 96.0


def test_compute_atr_stop_short_above_entry():
    stop = compute_atr_stop(entry=100.0, atr=2.0, multiplier=2.0, direction="short")
    assert stop == 104.0


def test_compute_structure_stop_finds_nearest_support_below():
    levels = [
        Level(price=90.0, kind="support", touches=2, strength=40, last_touch=None),
        Level(price=95.0, kind="support", touches=3, strength=60, last_touch=None),
        Level(price=110.0, kind="resistance", touches=2, strength=40, last_touch=None),
    ]
    stop = compute_structure_stop(entry=100.0, levels=levels, direction="long", buffer_pct=1.0)
    assert stop == pytest.approx(95.0 * 0.99)


def test_compute_structure_stop_none_when_no_support():
    stop = compute_structure_stop(entry=100.0, levels=[], direction="long")
    assert stop is None


def test_compute_stop_prefers_structure_when_close():
    levels = [Level(price=98.0, kind="support", touches=3, strength=60, last_touch=None)]
    result = compute_stop(entry=100.0, atr=2.0, levels=levels, direction="long", atr_multiplier=2.0)
    assert result.final_stop_method == "structure"
    assert result.final_stop == pytest.approx(98.0 * 0.997)


def test_compute_stop_falls_back_to_atr_when_structure_too_far():
    levels = [Level(price=50.0, kind="support", touches=3, strength=60, last_touch=None)]
    result = compute_stop(entry=100.0, atr=2.0, levels=levels, direction="long", atr_multiplier=2.0)
    assert result.final_stop_method == "atr"
    assert result.final_stop == 96.0


def test_compute_stop_uses_atr_when_no_levels():
    result = compute_stop(entry=100.0, atr=2.0, levels=[], direction="long", atr_multiplier=2.0)
    assert result.final_stop_method == "atr"
    assert result.structure_stop is None


def test_compute_rr_targets_scales_correctly():
    targets = compute_rr_targets(entry=100.0, stop=96.0, direction="long", rr_multiples=(1.0, 2.0))
    assert targets[0].price == 104.0
    assert targets[1].price == 108.0


def test_compute_rr_targets_short_direction():
    targets = compute_rr_targets(entry=100.0, stop=104.0, direction="short", rr_multiples=(1.0, 2.0))
    assert targets[0].price == 96.0
    assert targets[1].price == 92.0


def test_nearest_structure_target_long():
    levels = [
        Level(price=110.0, kind="resistance", touches=2, strength=40, last_touch=None),
        Level(price=120.0, kind="resistance", touches=2, strength=40, last_touch=None),
    ]
    target = nearest_structure_target(entry=100.0, levels=levels, direction="long")
    assert target.price == 110.0


def test_risk_reward_ratio_basic():
    rr = risk_reward_ratio(entry=100.0, stop=96.0, target=108.0)
    assert rr == 2.0


def test_risk_reward_ratio_rejects_zero_risk():
    with pytest.raises(ValueError):
        risk_reward_ratio(entry=100.0, stop=100.0, target=110.0)


def test_expected_move_grows_with_holding_days():
    move_3d = expected_move_for_horizon(atr=2.0, holding_days=3)
    move_10d = expected_move_for_horizon(atr=2.0, holding_days=10)
    assert move_10d > move_3d


def test_expected_move_scales_with_atr():
    low_vol = expected_move_for_horizon(atr=1.0, holding_days=5)
    high_vol = expected_move_for_horizon(atr=4.0, holding_days=5)
    assert high_vol == pytest.approx(low_vol * 4)


def test_cap_target_to_horizon_pulls_in_unrealistic_target():
    # a target 100 points away is not reachable in 5 days at ATR=1
    capped = cap_target_to_horizon(entry=100.0, target=200.0, atr=1.0, holding_days=5, direction="long")
    assert capped < 200.0
    assert capped > 100.0


def test_cap_target_to_horizon_leaves_realistic_target_untouched():
    # a small, realistic target should not be pulled in further
    small_target = 100.0 + expected_move_for_horizon(atr=2.0, holding_days=5) * 0.5
    capped = cap_target_to_horizon(entry=100.0, target=small_target, atr=2.0, holding_days=5, direction="long")
    assert capped == pytest.approx(small_target)


def test_cap_target_to_horizon_short_direction():
    capped = cap_target_to_horizon(entry=100.0, target=0.0, atr=1.0, holding_days=5, direction="short")
    assert capped > 0.0
    assert capped < 100.0
