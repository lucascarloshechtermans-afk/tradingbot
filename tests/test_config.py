import pytest

from config.schema import AppConfig, ConfigError, UniverseConfig


def test_universe_preset_defaults_applied():
    cfg = UniverseConfig.from_dict({"preset": "AGGRESSIVE"})
    assert cfg.min_price == 3.0
    assert cfg.exclude_penny_stocks is False


def test_universe_preset_can_be_overridden():
    cfg = UniverseConfig.from_dict({"preset": "BALANCED", "min_price": 25.0})
    assert cfg.min_price == 25.0
    assert cfg.min_market_cap == 2_000_000_000


def test_unknown_preset_rejected():
    with pytest.raises(ConfigError):
        UniverseConfig.from_dict({"preset": "SUPER_RISKY"})


def test_custom_preset_uses_raw_values_only():
    cfg = UniverseConfig.from_dict({"preset": "CUSTOM", "min_price": 1.0})
    assert cfg.min_price == 1.0


def test_scoring_weights_must_sum_to_100():
    with pytest.raises(ConfigError):
        AppConfig.from_dict({
            "scoring": {
                "weights": {
                    "trend": 50, "momentum": 50, "volume": 50, "price_action": 50,
                    "volatility": 50, "relative_strength": 50, "market_regime": 50,
                    "sector": 50, "risk_reward": 50, "multi_timeframe": 50,
                }
            }
        })


def test_scoring_weights_partial_override_merges_with_defaults():
    # trend(8) + market_structure(7) = 15 originally; shift 5 points from trend to
    # momentum here so the total still lands in the accepted 95-105 range
    cfg = AppConfig.from_dict({"scoring": {"weights": {"trend": 3, "momentum": 15}}})
    assert cfg.scoring.weights["trend"] == 3
    assert cfg.scoring.weights["momentum"] == 15
    assert cfg.scoring.weights["market_structure"] == 7


def test_default_config_is_valid():
    cfg = AppConfig.from_dict({})
    assert cfg.universe.preset == "BALANCED"
    assert sum(cfg.scoring.weights.values()) == 100


def test_risk_rejects_nonpositive_account_size():
    with pytest.raises(ConfigError):
        AppConfig.from_dict({"risk": {"account_size": 0}})


def test_risk_max_holding_days_defaults_to_five():
    cfg = AppConfig.from_dict({})
    assert cfg.risk.max_holding_days == 5


def test_risk_rejects_nonpositive_max_holding_days():
    with pytest.raises(ConfigError):
        AppConfig.from_dict({"risk": {"max_holding_days": 0}})


def test_risk_max_holding_days_overridable():
    cfg = AppConfig.from_dict({"risk": {"max_holding_days": 10}})
    assert cfg.risk.max_holding_days == 10
