"""Backtest CLI for a single strategy against a single ticker.

    python backtest.py --ticker AAPL --strategy breakout --period 3y
    python backtest.py --ticker AAPL --strategy pullback --walk-forward
    python backtest.py --dry-run --strategy breakout   # synthetic data, no network

Strategy slugs: breakout, pullback, trend_continuation, support_bounce,
momentum_continuation, mean_reversion, volatility_contraction.

Note on cost: this CLI rebuilds the full indicator set on every growing history
slice as the backtest steps bar-by-bar (needed so each signal decision only ever
sees data through that bar). That's fine for one ticker over a few years of daily
bars; it is NOT how the daily scanner works (scanner.py computes each ticker's
indicators exactly once per scan) and isn't meant to be run across hundreds of
tickers' full histories.
"""

from __future__ import annotations

import argparse
import logging
import sys

import pandas as pd

from backtesting.engine import run_backtest
from backtesting.metrics import buy_and_hold_return_pct, compute_metrics
from backtesting.walk_forward import run_walk_forward
from config.schema import load_config
from data.cache import DiskCache
from data.provider import DataProvider
from data.yfinance_provider import YFinanceProvider
from risk.stops_targets import compute_rr_targets, compute_stop
from strategies import ALL_STRATEGIES
from strategies.context import build_context

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("backtest")

STRATEGY_SLUGS = {
    "breakout": "Bullish Breakout",
    "pullback": "Bullish Pullback",
    "trend_continuation": "Trend Continuation",
    "support_bounce": "Support Bounce",
    "momentum_continuation": "Momentum Continuation",
    "mean_reversion": "Mean Reversion",
    "volatility_contraction": "Volatility Contraction",
}

MIN_WARMUP_BARS = 210  # enough for SMA200 + a margin


def find_strategy(slug: str):
    name = STRATEGY_SLUGS.get(slug)
    if name is None:
        raise ValueError(f"Unknown strategy '{slug}'. Choose from: {list(STRATEGY_SLUGS)}")
    return next(s for s in ALL_STRATEGIES if s.name == name)


def make_strategy_signal_fn(strategy):
    def signal_fn(history_so_far: pd.DataFrame) -> bool:
        if len(history_so_far) < MIN_WARMUP_BARS:
            return False
        ctx = build_context("BT", history_so_far)
        return strategy.evaluate(ctx).matched

    return signal_fn


def make_stop_fn(fallback_stop_pct: float = 5.0):
    def stop_fn(history_before_entry: pd.DataFrame, entry: float) -> float:
        if len(history_before_entry) < 20:
            return entry * (1 - fallback_stop_pct / 100)
        ctx = build_context("BT", history_before_entry)
        atr = ctx.atr14.iloc[-1]
        if pd.isna(atr) or atr <= 0:
            return entry * (1 - fallback_stop_pct / 100)
        return compute_stop(entry, atr, ctx.levels, direction="long").final_stop

    return stop_fn


def make_target_fn(rr_multiple: float = 2.0):
    def target_fn(history_before_entry: pd.DataFrame, entry: float, stop: float) -> float:
        return compute_rr_targets(entry, stop, direction="long", rr_multiples=(rr_multiple,))[0].price

    return target_fn


def print_backtest_report(ticker: str, strategy_name: str, metrics, buy_hold_pct: float) -> None:
    print(f"\nBacktest: {ticker} — {strategy_name}")
    print("=" * 50)
    print(f"{'Trades:':<24}{metrics.num_trades}")
    print(f"{'Total return:':<24}{metrics.total_return_pct:.2f}%")
    print(f"{'CAGR:':<24}{metrics.cagr_pct:.2f}%")
    print(f"{'Buy & Hold return:':<24}{buy_hold_pct:.2f}%")
    print(f"{'Win rate:':<24}{metrics.win_rate_pct:.1f}%")
    print(f"{'Avg win / loss:':<24}{metrics.avg_win_pct:.2f}% / {metrics.avg_loss_pct:.2f}%")
    print(f"{'Profit factor:':<24}{metrics.profit_factor}")
    print(f"{'Expectancy:':<24}{metrics.expectancy:.2f}%")
    print(f"{'Max drawdown:':<24}{metrics.max_drawdown_pct:.2f}%")
    print(f"{'Sharpe / Sortino:':<24}{metrics.sharpe_ratio} / {metrics.sortino_ratio}")
    print(f"{'Avg holding period:':<24}{metrics.avg_holding_days:.1f} days")
    print(f"{'Largest win / loss:':<24}{metrics.largest_win_pct:.2f}% / {metrics.largest_loss_pct:.2f}%")
    print(f"{'Consecutive W / L:':<24}{metrics.max_consecutive_wins} / {metrics.max_consecutive_losses}")
    print()


def print_walk_forward_report(ticker: str, strategy_name: str, windows) -> None:
    print(f"\nWalk-forward validation: {ticker} — {strategy_name}")
    print("=" * 50)
    if not windows:
        print("No walk-forward windows fit within the available history.")
        return
    for w in windows:
        print(
            f"{w.label}: test {w.test_start.date()}–{w.test_end.date()} | "
            f"trades={w.trade_count} win_rate={w.metrics.win_rate_pct:.0f}% "
            f"return={w.metrics.total_return_pct:.1f}% max_dd={w.metrics.max_drawdown_pct:.1f}%"
        )
    print()


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Backtest a single strategy against a single ticker")
    parser.add_argument("--ticker", type=str, default=None, help="Ticker to backtest (required unless --dry-run)")
    parser.add_argument("--strategy", type=str, required=True, choices=list(STRATEGY_SLUGS), help="Strategy to test")
    parser.add_argument("--period", type=str, default="3y", help="History period to fetch (yfinance format, e.g. 3y, 5y)")
    parser.add_argument("--config", type=str, default=None)
    parser.add_argument("--walk-forward", action="store_true", help="Run walk-forward validation instead of a single backtest")
    parser.add_argument("--train-days", type=int, default=252)
    parser.add_argument("--test-days", type=int, default=63)
    parser.add_argument("--rr-multiple", type=float, default=2.0, help="Risk:reward multiple used for the target")
    parser.add_argument("--dry-run", action="store_true", help="Use built-in synthetic data instead of live network data")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    config = load_config(args.config)
    strategy = find_strategy(args.strategy)

    provider: DataProvider
    if args.dry_run:
        from scanner import SyntheticDataProvider

        provider = SyntheticDataProvider()
        ticker = args.ticker or "SYNA"
    else:
        if not args.ticker:
            print("error: --ticker is required unless --dry-run is set", file=sys.stderr)
            return 2
        cache = DiskCache(cache_dir=config.data.cache_dir, ttl_hours=config.data.cache_ttl_hours)
        provider = YFinanceProvider(cache=cache, max_retries=config.data.max_retries, retry_backoff_seconds=config.data.retry_backoff_seconds)
        ticker = args.ticker

    history = provider.get_history(ticker, period=args.period)
    signal_fn = make_strategy_signal_fn(strategy)
    stop_fn = make_stop_fn()
    target_fn = make_target_fn(args.rr_multiple)

    backtest_kwargs = dict(
        initial_capital=config.backtesting.initial_capital,
        risk_per_trade_pct=config.risk.risk_per_trade_pct,
        commission_per_trade=config.backtesting.commission_per_trade,
        slippage_pct=config.backtesting.slippage_pct,
        max_position_pct=config.risk.max_position_pct,
    )

    if args.walk_forward:
        windows = run_walk_forward(
            history, signal_fn, stop_fn, target_fn,
            train_days=args.train_days, test_days=args.test_days, **backtest_kwargs,
        )
        print_walk_forward_report(ticker, strategy.name, windows)
    else:
        result = run_backtest(history, signal_fn, stop_fn, target_fn, **backtest_kwargs)
        metrics = compute_metrics(result.trades, result.equity_curve, initial_capital=backtest_kwargs["initial_capital"])
        buy_hold_pct = buy_and_hold_return_pct(history)
        print_backtest_report(ticker, strategy.name, metrics, buy_hold_pct)

    return 0


if __name__ == "__main__":
    sys.exit(main())
