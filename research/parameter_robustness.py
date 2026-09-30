"""Item 10 (parameter robustness): if only one exact threshold value works
and its neighbors are meaningfully worse, that's a sign of overfitting to
this particular backtest window rather than a real, generalizable edge.

Sweeps the two hard-gate thresholds that are already config-driven
(`gates.min_rs_percentile`, `gates.min_risk_reward`) across a neighborhood
around their current values, on a reduced ticker/period sample to keep this
a lightweight sanity check rather than a full re-validation (the full-
universe/full-period numbers are what backtest_screener.py's own CLI
reports; this only asks "is the CURRENT value a lonely local optimum").

    python -m research.parameter_robustness --period 2y --tickers ... (default: a 20-ticker sample)
"""

from __future__ import annotations

import argparse
import logging
import sys

from backtest_screener import run_universe_backtest
from backtesting.metrics import compute_metrics
from config.schema import load_config
from data.cache import DiskCache
from data.provider import DataProvider
from data.yfinance_provider import YFinanceProvider

logging.basicConfig(level=logging.WARNING)  # keep this script's own output the focus

DEFAULT_SAMPLE = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "AVGO", "CRM", "ADBE",
    "JPM", "V", "UNH", "HD", "COST", "NFLX", "AMD", "PANW", "CRWD", "SHOP",
]


def run_one(provider, config, tickers, period, label) -> None:
    all_trades, *_rest = run_universe_backtest(provider, config, tickers, period, min_score=None)
    closed = [t for t in all_trades if t.pnl is not None]
    if not closed:
        print(f"{label:<28}{'0 trades':<12}")
        return
    import pandas as pd

    cum_pnl = pd.Series([t.pnl for t in closed]).cumsum() + config.backtesting.initial_capital
    metrics = compute_metrics(closed, cum_pnl, initial_capital=config.backtesting.initial_capital)
    print(
        f"{label:<28}{len(closed):<9}{f'{metrics.win_rate_pct:.1f}%':<9}"
        f"{metrics.profit_factor:<9.2f}{metrics.expectancy:+.2f}%"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--period", type=str, default="2y")
    parser.add_argument("--tickers", type=str, default=None)
    parser.add_argument("--config", type=str, default=None)
    args = parser.parse_args(argv)

    tickers = args.tickers.split(",") if args.tickers else DEFAULT_SAMPLE
    cache = DiskCache(cache_dir=".cache", ttl_hours=200.0)
    provider: DataProvider = YFinanceProvider(cache=cache, max_retries=3, retry_backoff_seconds=2.0)

    print(f"\n{'=' * 60}")
    print(f"PARAMETER ROBUSTNESS  ({len(tickers)} tickers, {args.period})")
    print(f"{'=' * 60}")

    print("\n--- gates.min_rs_percentile (current default: 50) ---")
    print(f"{'Value':<28}{'Trades':<9}{'Win rate':<9}{'PF':<9}{'Expectancy'}")
    for value in (30.0, 40.0, 50.0, 60.0, 70.0):
        config = load_config(args.config)
        config.gates.min_rs_percentile = value
        run_one(provider, config, tickers, args.period, f"rs_percentile={value:.0f}")

    print("\n--- gates.min_risk_reward (current default: 1.2) ---")
    print(f"{'Value':<28}{'Trades':<9}{'Win rate':<9}{'PF':<9}{'Expectancy'}")
    for value in (1.0, 1.2, 1.5, 1.8, 2.0):
        config = load_config(args.config)
        config.gates.min_risk_reward = value
        run_one(provider, config, tickers, args.period, f"min_risk_reward={value:.1f}")

    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
