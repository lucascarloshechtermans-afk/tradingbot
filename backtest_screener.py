"""Backtest the full screener (all 7 strategies combined — whichever matches with
the highest confidence wins, mirroring scanner.py's own logic) across a universe
of tickers, and report an aggregate win rate plus a per-strategy breakdown.

    python backtest_screener.py --period 5y
    python backtest_screener.py --period 5y --tickers AAPL,MSFT,NVDA
    python backtest_screener.py --dry-run

Performance note: signal/stop/target all share ONE cached TickerContext per bar
(keyed by history length) instead of each rebuilding indicators separately — this
is what makes a 100+-ticker, 5-year, 7-strategy backtest complete in minutes
instead of hours. See SharedContextCache below.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from collections import Counter, defaultdict

import pandas as pd

from backtest import MIN_WARMUP_BARS
from backtesting.engine import run_backtest
from backtesting.metrics import compute_metrics
from config.schema import AppConfig, load_config
from data.cache import DiskCache
from data.provider import DataProvider, DataUnavailable
from data.universe import DEFAULT_UNIVERSE
from data.yfinance_provider import YFinanceProvider
from risk.stops_targets import cap_target_to_horizon, compute_rr_targets, compute_stop, nearest_structure_target
from scanner import evaluate_strategies
from scoring.scorer import score_ticker
from strategies import best_tradeable_signal
from strategies.context import TickerContext, build_context

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("backtest_screener")


class SharedContextCache:
    """Builds each bar's TickerContext at most once, keyed by history length —
    signal_fn, stop_fn and target_fn all hit this same cache for the same bar."""

    def __init__(self, ticker: str):
        self.ticker = ticker
        self._contexts: dict[int, TickerContext] = {}

    def get(self, history_slice: pd.DataFrame) -> TickerContext:
        key = len(history_slice)
        ctx = self._contexts.get(key)
        if ctx is None:
            ctx = build_context(self.ticker, history_slice)
            self._contexts[key] = ctx
        return ctx


def make_screener_functions(
    cache: SharedContextCache,
    config: AppConfig,
    attempted_strategy_by_bar: dict[int, str],
    score_by_bar: dict[int, float],
    min_score: float | None = None,
):
    max_holding_days = config.risk.max_holding_days

    def signal_fn(history_so_far: pd.DataFrame) -> bool:
        if len(history_so_far) < MIN_WARMUP_BARS:
            return False
        ctx = cache.get(history_so_far)
        signals = evaluate_strategies(ctx)
        best = best_tradeable_signal(signals)
        if best is None:
            return False
        # score_ticker only needs ctx + the matched strategies here; market
        # regime/sector/relative-strength/risk-reward aren't threaded through
        # this per-ticker backtest loop, so those categories fall back to their
        # neutral baselines — this still lets us test whether the technicals
        # categories that ARE computed (trend/momentum/volume/price_action/
        # volatility) predict trade quality, which is the open question.
        score_result = score_ticker(ctx, config.scoring, matched_strategies=signals)
        score_by_bar[len(history_so_far)] = score_result.total_score
        if min_score is not None and score_result.total_score < min_score:
            return False
        return True

    def stop_fn(history_before_entry: pd.DataFrame, entry: float) -> float:
        if len(history_before_entry) < MIN_WARMUP_BARS:
            return entry * 0.95
        ctx = cache.get(history_before_entry)
        signals = evaluate_strategies(ctx)
        best = best_tradeable_signal(signals)
        attempted_strategy_by_bar[len(history_before_entry)] = best.strategy if best else "Unknown"

        atr = ctx.atr14.iloc[-1]
        if pd.isna(atr) or atr <= 0:
            return entry * 0.95
        return compute_stop(entry, atr, ctx.levels, direction="long").final_stop

    def target_fn(history_before_entry: pd.DataFrame, entry: float, stop: float) -> float:
        ctx = cache.get(history_before_entry)
        atr = ctx.atr14.iloc[-1]
        structure_target = nearest_structure_target(entry, ctx.levels, direction="long")
        rr_targets = compute_rr_targets(entry, stop, direction="long", rr_multiples=(1.5, 3.0))
        target1, target2 = rr_targets[0].price, rr_targets[1].price
        target = structure_target.price if structure_target and structure_target.price > target1 else target2
        if pd.isna(atr) or atr <= 0:
            return target
        return cap_target_to_horizon(entry, target, atr, max_holding_days, direction="long")

    return signal_fn, stop_fn, target_fn


def backtest_ticker(ticker: str, history: pd.DataFrame, config: AppConfig, min_score: float | None = None):
    cache = SharedContextCache(ticker)
    attempted_strategy_by_bar: dict[int, str] = {}
    score_by_bar: dict[int, float] = {}
    signal_fn, stop_fn, target_fn = make_screener_functions(
        cache, config, attempted_strategy_by_bar, score_by_bar, min_score=min_score
    )

    result = run_backtest(
        history, signal_fn, stop_fn, target_fn,
        initial_capital=config.backtesting.initial_capital,
        risk_per_trade_pct=config.risk.risk_per_trade_pct,
        commission_per_trade=config.backtesting.commission_per_trade,
        slippage_pct=config.backtesting.slippage_pct,
        max_position_pct=config.risk.max_position_pct,
        max_holding_days=config.risk.max_holding_days,
    )

    trade_strategies = []
    trade_scores = []
    for trade in result.trades:
        try:
            bar_index = history.index.get_loc(trade.entry_date)
        except KeyError:
            bar_index = None
        trade_strategies.append(attempted_strategy_by_bar.get(bar_index, "Unknown"))
        trade_scores.append(score_by_bar.get(bar_index))

    return result, trade_strategies, trade_scores


def run_universe_backtest(
    provider: DataProvider, config: AppConfig, tickers: list[str], period: str, min_score: float | None = None
):
    all_trades = []
    all_trade_strategies = []
    all_trade_scores = []
    per_ticker_summaries = []
    errors = []

    for i, ticker in enumerate(tickers, start=1):
        try:
            history = provider.get_history(ticker, period=period)
        except DataUnavailable as exc:
            errors.append((ticker, str(exc)))
            continue
        if len(history) < MIN_WARMUP_BARS + 30:
            errors.append((ticker, f"insufficient history ({len(history)} bars)"))
            continue

        result, trade_strategies, trade_scores = backtest_ticker(ticker, history, config, min_score=min_score)
        all_trades.extend(result.trades)
        all_trade_strategies.extend(trade_strategies)
        all_trade_scores.extend(trade_scores)

        closed = [t for t in result.trades if t.pnl is not None]
        wins = sum(1 for t in closed if t.pnl > 0)
        per_ticker_summaries.append(
            {"ticker": ticker, "trades": len(closed), "wins": wins, "win_rate": (wins / len(closed) * 100) if closed else 0.0,
             "total_return_pct": (result.final_equity / result.initial_capital - 1) * 100}
        )
        logger.info("[%d/%d] %s: %d trades, %d wins", i, len(tickers), ticker, len(closed), wins)

    return all_trades, all_trade_strategies, all_trade_scores, per_ticker_summaries, errors


def print_score_bucket_report(all_trades, all_trade_scores):
    """The actual test of whether the scoring system predicts trade quality:
    bucket closed trades by the score they had at entry and compare win rate /
    expectancy across buckets. If higher-scored setups don't outperform
    lower-scored ones, the score isn't adding predictive value yet."""
    buckets = [(0, 50, "<50"), (50, 60, "50-59"), (60, 70, "60-69"), (70, 80, "70-79"), (80, 101, "80+")]
    print(f"\n{'--- Win rate / expectancy by score bucket (at entry) ---':<40}")
    print(f"{'Score':<10}{'Trades':<9}{'Win rate':<11}{'Avg win':<10}{'Avg loss':<10}{'Expectancy'}")
    for lo, hi, label in buckets:
        bucket_trades = [
            t for t, s in zip(all_trades, all_trade_scores)
            if t.pnl is not None and s is not None and lo <= s < hi
        ]
        if not bucket_trades:
            print(f"{label:<10}{'0':<9}{'-':<11}{'-':<10}{'-':<10}-")
            continue
        wins = [t for t in bucket_trades if t.pnl > 0]
        losses = [t for t in bucket_trades if t.pnl < 0]
        wr = len(wins) / len(bucket_trades) * 100
        avg_w = sum(t.pnl_pct for t in wins) / len(wins) if wins else 0
        avg_l = sum(t.pnl_pct for t in losses) / len(losses) if losses else 0
        expectancy = (len(wins) / len(bucket_trades) * avg_w) + (len(losses) / len(bucket_trades) * avg_l)
        print(
            f"{label:<10}{len(bucket_trades):<9}{f'{wr:.1f}%':<11}{f'{avg_w:.2f}%':<10}"
            f"{f'{avg_l:.2f}%':<10}{expectancy:+.2f}%"
        )
    print()


def print_report(all_trades, all_trade_strategies, all_trade_scores, per_ticker_summaries, errors, config: AppConfig, period: str):
    closed = [t for t in all_trades if t.pnl is not None]
    # build a pseudo equity curve from cumulative pnl for drawdown/sharpe purposes
    cum_pnl = pd.Series([t.pnl for t in closed]).cumsum() + config.backtesting.initial_capital
    if cum_pnl.empty:
        cum_pnl = pd.Series([config.backtesting.initial_capital])
    metrics = compute_metrics(closed, cum_pnl, initial_capital=config.backtesting.initial_capital)

    print(f"\n{'=' * 60}")
    print(f"SCREENER BACKTEST — {period} — {len(per_ticker_summaries)} tickers, {len(errors)} skipped")
    print(f"{'=' * 60}")
    print(f"{'Total trades:':<28}{len(closed)}")
    print(f"{'Overall win rate:':<28}{metrics.win_rate_pct:.1f}%")
    print(f"{'Avg win / loss:':<28}{metrics.avg_win_pct:.2f}% / {metrics.avg_loss_pct:.2f}%")
    print(f"{'Profit factor:':<28}{metrics.profit_factor}")
    print(f"{'Expectancy per trade:':<28}{metrics.expectancy:.2f}%")
    print(f"{'Avg holding period:':<28}{metrics.avg_holding_days:.1f} days")
    print(f"{'Largest win / loss:':<28}{metrics.largest_win_pct:.2f}% / {metrics.largest_loss_pct:.2f}%")
    print(f"{'Max consecutive losses:':<28}{metrics.max_consecutive_losses}")

    print(f"\n{'--- Per-strategy breakdown ---':<40}")
    by_strategy = defaultdict(list)
    for t, s in zip(closed, [s for s, t2 in zip(all_trade_strategies, all_trades) if t2.pnl is not None]):
        by_strategy[s].append(t)
    print(f"{'Strategy':<26}{'Trades':<9}{'Win rate':<11}{'Avg win':<10}{'Avg loss':<10}{'Expectancy'}")
    for strategy, trades in sorted(by_strategy.items(), key=lambda kv: -len(kv[1])):
        wins = [t for t in trades if t.pnl > 0]
        losses = [t for t in trades if t.pnl < 0]
        wr = len(wins) / len(trades) * 100 if trades else 0
        avg_w = sum(t.pnl_pct for t in wins) / len(wins) if wins else 0
        avg_l = sum(t.pnl_pct for t in losses) / len(losses) if losses else 0
        expectancy = (len(wins) / len(trades) * avg_w) + (len(losses) / len(trades) * avg_l) if trades else 0
        print(
            f"{strategy:<26}{len(trades):<9}{f'{wr:.1f}%':<11}{f'{avg_w:.2f}%':<10}"
            f"{f'{avg_l:.2f}%':<10}{expectancy:+.2f}%"
        )

    exit_reasons = Counter(t.exit_reason for t in closed)
    print(f"\n{'--- Exit reasons ---':<40}")
    for reason, count in exit_reasons.most_common():
        print(f"{reason:<20}{count} ({count / len(closed) * 100:.0f}%)" if closed else "")

    print(f"\n{'--- Best / worst tickers (min 3 trades) ---':<40}")
    qualifying = [s for s in per_ticker_summaries if s["trades"] >= 3]
    qualifying.sort(key=lambda s: s["win_rate"], reverse=True)
    for s in qualifying[:5]:
        print(f"  {s['ticker']:<8} {s['trades']} trades, {s['win_rate']:.0f}% win rate")
    print("  ...")
    for s in qualifying[-5:]:
        print(f"  {s['ticker']:<8} {s['trades']} trades, {s['win_rate']:.0f}% win rate")

    if errors:
        print(f"\n{'--- Skipped tickers ---':<40}")
        for ticker, reason in errors[:15]:
            print(f"  {ticker}: {reason}")
        if len(errors) > 15:
            print(f"  ... and {len(errors) - 15} more")
    print()

    print_score_bucket_report(all_trades, all_trade_scores)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Backtest the full screener across a universe of tickers")
    parser.add_argument("--tickers", type=str, default=None, help="Comma-separated ticker list (default: the built-in DEFAULT_UNIVERSE)")
    parser.add_argument("--period", type=str, default="5y")
    parser.add_argument("--config", type=str, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--min-score", type=float, default=None,
        help="Only take trades whose computed score at entry is >= this (default: no gate, matches scanner.py's current behavior)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    config = load_config(args.config)

    if args.dry_run:
        from scanner import SyntheticDataProvider

        provider: DataProvider = SyntheticDataProvider()
        tickers = ["SYNA", "SYNB", "SYNC"]
    else:
        cache = DiskCache(cache_dir=config.data.cache_dir, ttl_hours=config.data.cache_ttl_hours)
        provider = YFinanceProvider(cache=cache, max_retries=config.data.max_retries, retry_backoff_seconds=config.data.retry_backoff_seconds)
        tickers = args.tickers.split(",") if args.tickers else DEFAULT_UNIVERSE

    started = time.time()
    all_trades, all_trade_strategies, all_trade_scores, per_ticker_summaries, errors = run_universe_backtest(
        provider, config, tickers, args.period, min_score=args.min_score
    )
    logger.info("done in %.1fs", time.time() - started)

    print_report(all_trades, all_trade_strategies, all_trade_scores, per_ticker_summaries, errors, config, args.period)
    return 0


if __name__ == "__main__":
    sys.exit(main())
