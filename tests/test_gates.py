from __future__ import annotations

import numpy as np
import pandas as pd

from config.schema import AppConfig, GatesConfig
from market_regime.regime import MarketRegime, classify_market_regime, classify_market_regime_series
from relative_strength.relative_strength import compute_universe_rs_ranks, universe_rs_rank_series
from risk.stops_targets import plan_trade_levels
from scanner import build_trade_plan
from strategies import COUNTER_TREND_STRATEGY_NAMES
from tests.helpers import breakout_history, context_from, downtrend_oversold_history, mean_reversion_history


def _idx(n):
    return pd.date_range("2023-01-01", periods=n, freq="D")


def _trend_df(n, start, step, noise=0.0, seed=0):
    rng = np.random.default_rng(seed)
    close = pd.Series(start + step * np.arange(n) + rng.normal(0, noise, n), index=_idx(n))
    return pd.DataFrame({"open": close, "high": close + 0.5, "low": close - 0.5, "close": close, "volume": 1_000_000.0})


def _flat_df(n, level):
    close = pd.Series(level, index=_idx(n))
    return pd.DataFrame({"open": close, "high": close + 0.2, "low": close - 0.2, "close": close, "volume": 1_000_000.0})


# --------------------------------------------------------------------------- #
# GatesConfig
# --------------------------------------------------------------------------- #


def test_gates_config_defaults():
    gates = GatesConfig.from_dict({})
    assert gates.min_rs_percentile == 70.0
    assert gates.regime_gate_enabled is True
    assert "BEARISH" in gates.blocked_regime_labels
    assert gates.min_risk_reward == 1.2


def test_gates_config_overrides():
    gates = GatesConfig.from_dict({"min_rs_percentile": 50, "regime_gate_enabled": False, "min_risk_reward": 2.0})
    assert gates.min_rs_percentile == 50
    assert gates.regime_gate_enabled is False
    assert gates.min_risk_reward == 2.0


# --------------------------------------------------------------------------- #
# RS rank vs. universe
# --------------------------------------------------------------------------- #


def test_compute_universe_rs_ranks_strongest_ticker_gets_highest_percentile():
    n = 100
    closes = {
        "STRONG": _trend_df(n, 50, 0.8)["close"],
        "MID": _trend_df(n, 50, 0.2)["close"],
        "WEAK": _trend_df(n, 50, -0.5)["close"],
    }
    ranks = compute_universe_rs_ranks(closes, window=60)
    assert ranks["STRONG"] > ranks["MID"] > ranks["WEAK"]
    assert ranks["STRONG"] == 100.0


def test_universe_rs_rank_series_is_walk_forward_and_causal():
    n = 150
    closes = {
        "STRONG": _trend_df(n, 50, 0.8, seed=1)["close"],
        "WEAK": _trend_df(n, 50, -0.5, seed=2)["close"],
    }
    rank_table = universe_rs_rank_series(closes, window=60)
    # a rank exists at every date once the trailing window is satisfied
    last_date = rank_table.index[-1]
    assert rank_table.loc[last_date, "STRONG"] > rank_table.loc[last_date, "WEAK"]
    # an early date (before the window has enough history) is NaN, not a fabricated rank
    early_date = rank_table.index[10]
    assert pd.isna(rank_table.loc[early_date, "STRONG"])
    # ranks at an early-but-valid date only reflect information through that date
    # (recomputing on a truncated series up to that date gives the same rank)
    mid_date_pos = 90
    mid_date = rank_table.index[mid_date_pos]
    truncated = {t: c.iloc[: mid_date_pos + 1] for t, c in closes.items()}
    truncated_table = universe_rs_rank_series(truncated, window=60)
    assert rank_table.loc[mid_date, "STRONG"] == truncated_table.loc[mid_date, "STRONG"]


# --------------------------------------------------------------------------- #
# Market regime series
# --------------------------------------------------------------------------- #


def test_classify_market_regime_series_bullish_when_trending_up():
    n = 260
    spy = _trend_df(n, 100, 0.5)
    qqq = _trend_df(n, 100, 0.5)
    iwm = _trend_df(n, 100, 0.5)
    vix = _flat_df(n, 15.0)
    series = classify_market_regime_series(spy, qqq, iwm, vix)
    assert series.iloc[-1] == "BULLISH"


def test_classify_market_regime_series_high_volatility_overrides():
    n = 260
    spy = _trend_df(n, 100, 0.5)
    qqq = _trend_df(n, 100, 0.5)
    iwm = _trend_df(n, 100, 0.5)
    vix = _flat_df(n, 40.0)  # elevated
    series = classify_market_regime_series(spy, qqq, iwm, vix)
    assert series.iloc[-1] == "HIGH_VOLATILITY"


def test_classify_market_regime_series_matches_snapshot_at_last_date():
    n = 260
    spy = _trend_df(n, 100, -0.3)  # downtrend
    qqq = _trend_df(n, 100, -0.3)
    iwm = _trend_df(n, 100, -0.3)
    vix = _flat_df(n, 20.0)
    series = classify_market_regime_series(spy, qqq, iwm, vix)
    snapshot = classify_market_regime(spy, qqq, iwm, vix)
    # the walk-forward series (no breadth factor) should broadly agree with the
    # single-point-in-time classification at the same final date
    assert series.iloc[-1] == snapshot.label


def test_classify_market_regime_series_no_look_ahead():
    n = 260
    spy = _trend_df(n, 100, 0.5, seed=3)
    qqq = _trend_df(n, 100, 0.5, seed=4)
    iwm = _trend_df(n, 100, 0.5, seed=5)
    vix = _flat_df(n, 15.0)
    full_series = classify_market_regime_series(spy, qqq, iwm, vix)

    cutoff = 200
    truncated_label = classify_market_regime_series(
        spy.iloc[:cutoff], qqq.iloc[:cutoff], iwm.iloc[:cutoff], vix.iloc[:cutoff]
    ).iloc[-1]
    assert full_series.iloc[cutoff - 1] == truncated_label


# --------------------------------------------------------------------------- #
# plan_trade_levels / min R:R gate
# --------------------------------------------------------------------------- #


def test_plan_trade_levels_returns_positive_rr():
    result = plan_trade_levels(entry=100.0, atr=2.0, levels=[], max_holding_days=5)
    assert result is not None
    assert result.risk_reward > 0
    assert result.target2 > 100.0
    assert result.stop_levels.final_stop < 100.0


def test_plan_trade_levels_none_when_atr_zero_gives_zero_risk():
    # an ATR of 0 collapses the ATR-stop onto entry itself -> zero risk -> None
    result = plan_trade_levels(entry=100.0, atr=0.0, levels=[], max_holding_days=5)
    assert result is None


# --------------------------------------------------------------------------- #
# Counter-trend strategy exemption from the RS/regime gates
# --------------------------------------------------------------------------- #


def test_mean_reversion_is_counter_trend():
    assert "Mean Reversion" in COUNTER_TREND_STRATEGY_NAMES
    assert "Support Bounce" in COUNTER_TREND_STRATEGY_NAMES
    assert "Bullish Breakout" not in COUNTER_TREND_STRATEGY_NAMES


def test_build_trade_plan_exempts_counter_trend_setup_from_regime_gate():
    ctx = context_from(mean_reversion_history())
    config = AppConfig()
    bearish = MarketRegime(label="BEARISH", score=-50, factors={})
    plan = build_trade_plan("MR", ctx, ctx, config, bearish, None, rs_rank=5.0)
    assert plan is not None
    assert plan.setup == "Mean Reversion"


def test_build_trade_plan_blocks_trend_following_setup_on_low_rs_rank():
    ctx = context_from(breakout_history())
    config = AppConfig()
    plan = build_trade_plan("BRK", ctx, ctx, config, None, None, rs_rank=5.0)
    assert plan is None


def test_build_trade_plan_flags_low_float_as_risk_not_score():
    from dataclasses import replace

    ctx = context_from(breakout_history())
    config = AppConfig()
    low_float_ctx = replace(ctx, shares_outstanding=1_000_000_000.0, float_shares=100_000_000.0)  # 10% free float
    plan = build_trade_plan("LOWFLOAT", low_float_ctx, low_float_ctx, config, None, None, rs_rank=100.0)
    assert plan is not None
    assert any("free float" in r.lower() for r in plan.risks)
    # context, not a score input: two otherwise-identical setups shouldn't score
    # differently just because one has a float figure attached
    high_float_ctx = replace(ctx, shares_outstanding=1_000_000_000.0, float_shares=950_000_000.0)
    plan_high_float = build_trade_plan("HIGHFLOAT", high_float_ctx, high_float_ctx, config, None, None, rs_rank=100.0)
    assert plan_high_float.score == plan.score


def test_build_trade_plan_populates_structured_explanation():
    ctx = context_from(breakout_history())
    config = AppConfig()
    plan = build_trade_plan("BRK", ctx, ctx, config, None, None, rs_rank=100.0)
    assert plan is not None
    expected_keys = {"why_it_passed", "why_it_could_fail", "structure", "momentum", "volume", "context", "levels", "risk"}
    assert expected_keys <= plan.explanation.keys()
    assert len(plan.explanation["why_it_passed"]) > 0
    assert any("Entry:" in line for line in plan.explanation["levels"])
    assert any("ATR:" in line for line in plan.explanation["risk"])


def test_build_trade_plan_populates_category_breakdown():
    ctx = context_from(breakout_history())
    config = AppConfig()
    plan = build_trade_plan("BRK", ctx, ctx, config, None, None, rs_rank=100.0)
    assert plan is not None
    categories = {c["category"] for c in plan.category_breakdown}
    assert {"trend", "market_structure", "momentum", "volume"} <= categories
    for cat in plan.category_breakdown:
        assert 0 <= cat["score"] <= 100


def test_build_trade_plan_blocks_trend_following_setup_on_bearish_regime():
    ctx = context_from(breakout_history())
    config = AppConfig()
    bearish = MarketRegime(label="BEARISH", score=-50, factors={})
    plan = build_trade_plan("BRK", ctx, ctx, config, bearish, None, rs_rank=100.0)
    assert plan is None


# --------------------------------------------------------------------------- #
# NO-TRADE engine: named rejection reasons
# --------------------------------------------------------------------------- #


def test_no_trade_log_records_specific_reason_for_weak_regime():
    ctx = context_from(breakout_history())
    config = AppConfig()
    bearish = MarketRegime(label="BEARISH", score=-50, factors={})
    log: dict[str, str] = {}
    plan = build_trade_plan("BRK", ctx, ctx, config, bearish, None, rs_rank=100.0, no_trade_log=log)
    assert plan is None
    assert "BRK" in log
    assert log["BRK"].startswith("weak_market_regime")


def test_no_trade_log_records_earnings_too_close():
    from datetime import datetime

    from events.earnings import check_earnings_proximity

    ctx = context_from(breakout_history())
    config = AppConfig()
    earnings_warning = check_earnings_proximity(
        [datetime.now()], as_of=datetime.now(), buffer_days=5, avoid_earnings=True,
    )
    log: dict[str, str] = {}
    plan = build_trade_plan("BRK", ctx, ctx, config, None, earnings_warning, rs_rank=100.0, no_trade_log=log)
    assert plan is None
    assert log["BRK"].startswith("earnings_too_close")


def test_no_trade_log_records_resistance_too_close():
    from dataclasses import replace

    ctx = context_from(breakout_history())
    config = AppConfig()
    tight_ctx = replace(ctx, distance_to_resistance_atr=0.1)
    log: dict[str, str] = {}
    plan = build_trade_plan("BRK", tight_ctx, tight_ctx, config, None, None, rs_rank=100.0, no_trade_log=log)
    assert plan is None
    assert log["BRK"].startswith("resistance_too_close")


def test_no_trade_log_records_extreme_overextension():
    from dataclasses import replace

    from risk.overextension import OverextensionProfile

    ctx = context_from(breakout_history())
    config = AppConfig()
    stretched = OverextensionProfile(
        distance_from_ema8_atr=10.0, distance_from_ema21_atr=10.0, distance_from_ema50_atr=10.0,
        distance_from_vwap_atr=10.0, distance_from_swing_low_atr=10.0,
        gain_1d_pct=1.0, gain_3d_pct=2.0, gain_5d_pct=3.0, gain_20d_pct=5.0,
        stretched_reference_count=5, is_severely_overextended=True,
    )
    extreme_ctx = replace(ctx, overextension=stretched)
    log: dict[str, str] = {}
    plan = build_trade_plan("BRK", extreme_ctx, extreme_ctx, config, None, None, rs_rank=100.0, no_trade_log=log)
    assert plan is None
    assert log["BRK"].startswith("extreme_overextension")


def test_no_trade_log_records_bearish_higher_timeframe():
    daily_ctx = context_from(breakout_history())
    weekly_bearish_ctx = context_from(downtrend_oversold_history())
    config = AppConfig()
    log: dict[str, str] = {}
    plan = build_trade_plan("BRK", daily_ctx, weekly_bearish_ctx, config, None, None, rs_rank=100.0, no_trade_log=log)
    assert plan is None
    assert log["BRK"].startswith("bearish_higher_timeframe")


def test_successful_plan_is_not_added_to_no_trade_log():
    ctx = context_from(breakout_history())
    config = AppConfig()
    log: dict[str, str] = {}
    plan = build_trade_plan("BRK", ctx, ctx, config, None, None, rs_rank=100.0, no_trade_log=log)
    assert plan is not None
    assert "BRK" not in log
