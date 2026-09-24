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
    cfg = AppConfig.from_dict({"scoring": {"weights": {"trend": 20}}})
    assert cfg.scoring.weights["trend"] == 20
    assert cfg.scoring.weights["momentum"] == 10


def test_default_config_is_valid():
    cfg = AppConfig.from_dict({})
    assert cfg.universe.preset == "BALANCED"
    assert sum(cfg.scoring.weights.values()) == 100


def test_risk_rejects_nonpositive_account_size():
    with pytest.raises(ConfigError):
        AppConfig.from_dict({"risk": {"account_size": 0}})
