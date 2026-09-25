from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from config.presets import UNIVERSE_PRESETS


class ConfigError(Exception):
    pass


@dataclass
class UniverseConfig:
    preset: str = "BALANCED"
    min_price: float = 10.0
    min_avg_dollar_volume: float = 5_000_000
    min_market_cap: float = 2_000_000_000
    exclude_penny_stocks: bool = True
    sectors: list[str] = field(default_factory=list)
    # Corwin-Schultz ESTIMATED spread, see liquidity/liquidity.py. Calibrated
    # loose (1.5% default) on purpose: the estimator is known to run higher
    # for genuinely volatile-but-liquid names (their wide daily high-low range
    # partly reads as "spread" even though real execution cost is small) — a
    # tight threshold here would systematically filter out exactly the
    # higher-beta swing candidates this scanner is meant to surface, while a
    # true illiquidity problem (small/thin names) shows up far above 1.5%.
    max_spread_pct_estimate: float = 1.5
    # Floor on 14-day ATR% (ATR / close * 100). 0 = no filter. Added on request to
    # exclude low-movement large caps (e.g. mega-cap "MAG7"-type names) that pass
    # every liquidity/cap filter but rarely move enough in a 5-day swing to hit a
    # meaningful target.
    min_atr_pct: float = 0.0
    # Optional ceiling on share price (None = no ceiling). Added on explicit
    # request to avoid pricier names (e.g. $600+ AMD/NET-style tickers) in
    # favor of a $100-200 band, independent of min_atr_pct/ATR% -- ATR% already
    # normalizes volatility for price level, so this is a stated preference
    # (fewer shares per trade, different per-tick feel), not a claim that
    # cheaper-per-share names are objectively more volatile.
    max_price: float | None = None

    @classmethod
    def from_dict(cls, raw: dict) -> "UniverseConfig":
        preset = raw.get("preset", "BALANCED").upper()
        defaults = dict(UNIVERSE_PRESETS.get(preset, UNIVERSE_PRESETS["BALANCED"]))
        if preset not in UNIVERSE_PRESETS and preset != "CUSTOM":
            raise ConfigError(
                f"Unknown universe preset '{preset}'. "
                f"Valid: {list(UNIVERSE_PRESETS)} or CUSTOM."
            )
        merged = {**defaults, **{k: v for k, v in raw.items() if k != "preset"}}
        return cls(
            preset=preset,
            min_price=float(merged.get("min_price", defaults.get("min_price", 10.0))),
            min_avg_dollar_volume=float(
                merged.get("min_avg_dollar_volume", defaults.get("min_avg_dollar_volume", 5_000_000))
            ),
            min_market_cap=float(
                merged.get("min_market_cap", defaults.get("min_market_cap", 2_000_000_000))
            ),
            exclude_penny_stocks=bool(
                merged.get("exclude_penny_stocks", defaults.get("exclude_penny_stocks", True))
            ),
            sectors=list(merged.get("sectors", [])),
            max_spread_pct_estimate=float(
                merged.get("max_spread_pct_estimate", defaults.get("max_spread_pct_estimate", 1.5))
            ),
            min_atr_pct=float(merged.get("min_atr_pct", defaults.get("min_atr_pct", 0.0))),
            max_price=(
                float(merged.get("max_price", defaults.get("max_price")))
                if merged.get("max_price", defaults.get("max_price")) is not None
                else None
            ),
        )


@dataclass
class DataConfig:
    period: str = "1y"
    cache_dir: str = ".cache"
    cache_ttl_hours: float = 20.0
    max_retries: int = 3
    retry_backoff_seconds: float = 2.0

    @classmethod
    def from_dict(cls, raw: dict) -> "DataConfig":
        return cls(
            period=raw.get("period", "1y"),
            cache_dir=raw.get("cache_dir", ".cache"),
            cache_ttl_hours=float(raw.get("cache_ttl_hours", 20.0)),
            max_retries=int(raw.get("max_retries", 3)),
            retry_backoff_seconds=float(raw.get("retry_backoff_seconds", 2.0)),
        )


@dataclass
class RiskConfig:
    account_size: float = 10_000.0
    risk_per_trade_pct: float = 0.5
    max_portfolio_risk_pct: float = 6.0
    max_position_pct: float = 20.0
    max_holding_days: int = 5
    # How far a target is allowed to sit (in ATR*sqrt(holding_days) units) before
    # cap_target_to_horizon pulls it in — see risk/stops_targets.py. Lowered from
    # the function's own 1.5 default after a backtest showed only 21.7% of
    # winning trades ever actually reached their formal target (the rest were
    # merely still-positive at the 5-day forced close) — 1.5x implied a target
    # ~3.35 ATRs away against a 2-ATR stop, a move that a 5-day swing rarely
    # completes. See README's "Target realism" section for the validated effect.
    target_volatility_multiplier: float = 1.5

    @classmethod
    def from_dict(cls, raw: dict) -> "RiskConfig":
        cfg = cls(
            account_size=float(raw.get("account_size", 10_000.0)),
            risk_per_trade_pct=float(raw.get("risk_per_trade_pct", 0.5)),
            max_portfolio_risk_pct=float(raw.get("max_portfolio_risk_pct", 6.0)),
            max_position_pct=float(raw.get("max_position_pct", 20.0)),
            max_holding_days=int(raw.get("max_holding_days", 5)),
            target_volatility_multiplier=float(raw.get("target_volatility_multiplier", 1.5)),
        )
        if cfg.account_size <= 0:
            raise ConfigError("risk.account_size must be positive")
        if not (0 < cfg.risk_per_trade_pct <= 100):
            raise ConfigError("risk.risk_per_trade_pct must be between 0 and 100")
        if cfg.max_holding_days <= 0:
            raise ConfigError("risk.max_holding_days must be positive")
        return cfg


@dataclass
class GatesConfig:
    """Hard, sequential pre-filters applied BEFORE a setup is scored — as opposed
    to the weighted 0-100 composite in ScoringConfig. Research on systems with a
    documented, replicated edge (Minervini's Trend Template, CANSLIM, academic
    momentum studies) consistently uses hard gates like these rather than folding
    everything into one weighted score, specifically because a weighted score lets
    a strong showing in unrelated categories compensate for a fundamentally weak
    setup (e.g. a laggard stock in a bear market with a pretty chart pattern)."""

    # ticker must rank >= this percentile vs. the rest of the scanned universe
    # on trailing rs_window-day return. Lowered from an initial 70 after a
    # direct A/B backtest (5y, 103 tickers): 50 produced 22.6% more trades
    # (5768 -> 7070) at essentially the same profit factor (1.14 -> 1.15) and
    # expectancy (+0.22% -> +0.20%, within noise), a higher win rate, and
    # specifically fixed Bullish Breakout (-0.00% -> +0.24% expectancy) —
    # while the score-bucket monotonicity (higher score = better expectancy)
    # that originally justified this gate stayed intact. 70 wasn't wrong, just
    # needlessly strict: it discarded real opportunities without adding
    # quality.
    min_rs_percentile: float = 50.0
    rs_window: int = 60
    regime_gate_enabled: bool = True
    blocked_regime_labels: list[str] = field(default_factory=lambda: ["BEARISH", "HIGH_VOLATILITY"])
    min_risk_reward: float = 1.2  # reject a setup outright if its computed (horizon-capped) R:R falls below this
    min_distance_to_resistance_atr: float = 0.5  # reject when there's virtually no room before resistance
    block_bearish_higher_timeframe: bool = True  # reject a long setup when the WEEKLY trend is bearish
    block_extreme_overextension: bool = True  # reject when ALL distance references agree price is stretched

    @classmethod
    def from_dict(cls, raw: dict) -> "GatesConfig":
        return cls(
            min_rs_percentile=float(raw.get("min_rs_percentile", 50.0)),
            rs_window=int(raw.get("rs_window", 60)),
            regime_gate_enabled=bool(raw.get("regime_gate_enabled", True)),
            blocked_regime_labels=list(raw.get("blocked_regime_labels", ["BEARISH", "HIGH_VOLATILITY"])),
            min_risk_reward=float(raw.get("min_risk_reward", 1.2)),
            min_distance_to_resistance_atr=float(raw.get("min_distance_to_resistance_atr", 0.5)),
            block_bearish_higher_timeframe=bool(raw.get("block_bearish_higher_timeframe", True)),
            block_extreme_overextension=bool(raw.get("block_extreme_overextension", True)),
        )


DEFAULT_SCORING_WEIGHTS = {
    "trend": 8,
    "market_structure": 7,
    "momentum": 10,
    "volume": 10,
    "price_action": 15,
    "volatility": 10,
    "relative_strength": 10,
    "market_regime": 10,
    "sector": 5,
    "risk_reward": 10,
    "multi_timeframe": 5,
}

# Recalibrated against the REAL achievable score distribution (5y, 134-ticker
# backtest, AFTER fixing the backtest's score-deflation bug -- see
# backtest_screener.py's score_ticker call): <50: 1485 trades, 50-59: 4077,
# 60-69: 3357, 70-79: 39, 80+: 0. Composite scoring averages 11 independently-
# computed categories, so a real setup needs almost every category maxed at
# once to clear 70, and 80 never happened even once across 8958 trades -- the
# old 80/90 thresholds were unreachable in practice, not a high bar being
# cleared rarely. "strong"/"exceptional" are now set where real (if thin —
# n=39) separation actually exists; revisit as more live data accumulates,
# since 39 trades is not a lot to calibrate an exact boundary on.
DEFAULT_SCORE_THRESHOLDS = {
    "exceptional": 78,
    "strong": 72,
    "interesting": 65,
    "watchlist": 55,
}


@dataclass
class ScoringConfig:
    weights: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_SCORING_WEIGHTS))
    thresholds: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_SCORE_THRESHOLDS))

    @classmethod
    def from_dict(cls, raw: dict) -> "ScoringConfig":
        weights = {**DEFAULT_SCORING_WEIGHTS, **raw.get("weights", {})}
        thresholds = {**DEFAULT_SCORE_THRESHOLDS, **raw.get("thresholds", {})}
        total = sum(weights.values())
        if not (95 <= total <= 105):
            raise ConfigError(
                f"scoring.weights must sum to ~100 (got {total}). "
                f"Weights: {weights}"
            )
        return cls(weights=weights, thresholds=thresholds)


@dataclass
class EarningsConfig:
    avoid_earnings: bool = True
    buffer_days: int = 5

    @classmethod
    def from_dict(cls, raw: dict) -> "EarningsConfig":
        return cls(
            avoid_earnings=bool(raw.get("avoid_earnings", True)),
            buffer_days=int(raw.get("buffer_days", 5)),
        )


@dataclass
class BacktestConfig:
    commission_per_trade: float = 1.0
    slippage_pct: float = 0.05
    initial_capital: float = 10_000.0

    @classmethod
    def from_dict(cls, raw: dict) -> "BacktestConfig":
        return cls(
            commission_per_trade=float(raw.get("commission_per_trade", 1.0)),
            slippage_pct=float(raw.get("slippage_pct", 0.05)),
            initial_capital=float(raw.get("initial_capital", 10_000.0)),
        )


@dataclass
class AlertsConfig:
    enabled: bool = True
    log_path: str = "alerts_log.json"
    score_threshold: float = 75.0
    triggers: dict[str, bool] = field(default_factory=lambda: {
        "breakout": True,
        "volume_spike": True,
        "rsi_condition": True,
        "ma_cross": True,
        "entry_triggered": True,
        "stop_hit": True,
        "target_hit": True,
        "earnings_approaching": True,
    })

    @classmethod
    def from_dict(cls, raw: dict) -> "AlertsConfig":
        default_triggers = cls().triggers
        return cls(
            enabled=bool(raw.get("enabled", True)),
            log_path=raw.get("log_path", "alerts_log.json"),
            score_threshold=float(raw.get("score_threshold", 75.0)),
            triggers={**default_triggers, **raw.get("triggers", {})},
        )


@dataclass
class AppConfig:
    universe: UniverseConfig = field(default_factory=UniverseConfig)
    data: DataConfig = field(default_factory=DataConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    scoring: ScoringConfig = field(default_factory=ScoringConfig)
    gates: GatesConfig = field(default_factory=GatesConfig)
    earnings: EarningsConfig = field(default_factory=EarningsConfig)
    backtesting: BacktestConfig = field(default_factory=BacktestConfig)
    alerts: AlertsConfig = field(default_factory=AlertsConfig)

    @classmethod
    def from_dict(cls, raw: dict) -> "AppConfig":
        return cls(
            universe=UniverseConfig.from_dict(raw.get("universe", {})),
            data=DataConfig.from_dict(raw.get("data", {})),
            risk=RiskConfig.from_dict(raw.get("risk", {})),
            scoring=ScoringConfig.from_dict(raw.get("scoring", {})),
            gates=GatesConfig.from_dict(raw.get("gates", {})),
            earnings=EarningsConfig.from_dict(raw.get("earnings", {})),
            backtesting=BacktestConfig.from_dict(raw.get("backtesting", {})),
            alerts=AlertsConfig.from_dict(raw.get("alerts", {})),
        )


def load_config(path: str | Path | None = None, preset_override: str | None = None) -> AppConfig:
    if path is None:
        candidate = Path("config.yaml")
        path = candidate if candidate.exists() else Path("config/config.example.yaml")
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")
    with open(path) as f:
        raw = yaml.safe_load(f) or {}
    if preset_override:
        # Re-derive the FULL preset (thresholds, not just the label) by overriding
        # the preset key in the raw dict before parsing, rather than mutating the
        # already-built AppConfig afterwards -- setting .universe.preset on a
        # built config only relabels it, it doesn't reapply min_price/
        # min_avg_dollar_volume/min_market_cap/max_spread_pct_estimate for the
        # new preset, silently leaving the OLD preset's thresholds in effect.
        raw = {**raw, "universe": {**raw.get("universe", {}), "preset": preset_override}}
    return AppConfig.from_dict(raw)
