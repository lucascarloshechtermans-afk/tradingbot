"""Universe filter presets.

These are starting points, not hardcoded limits — any value can be overridden in
config.yaml. CUSTOM means "use whatever is in config.yaml verbatim, no preset applied".
"""

UNIVERSE_PRESETS = {
    "CONSERVATIVE": {
        "min_price": 20.0,
        "min_avg_dollar_volume": 20_000_000,
        "min_market_cap": 10_000_000_000,
        "exclude_penny_stocks": True,
        "max_spread_pct_estimate": 0.3,
    },
    "BALANCED": {
        "min_price": 10.0,
        "min_avg_dollar_volume": 5_000_000,
        "min_market_cap": 2_000_000_000,
        "exclude_penny_stocks": True,
        "max_spread_pct_estimate": 0.5,
    },
    "AGGRESSIVE": {
        "min_price": 3.0,
        "min_avg_dollar_volume": 1_000_000,
        "min_market_cap": 300_000_000,
        "exclude_penny_stocks": False,
        "max_spread_pct_estimate": 1.0,
    },
}
