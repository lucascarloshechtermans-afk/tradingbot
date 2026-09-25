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
from market_regime.regime import classify_market_regime_series
from relative_strength.relative_strength import universe_rs_rank_series
from risk.stops_targets import plan_trade_levels
from scanner import BENCHMARK_TICKERS, evaluate_strategies
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
    regime_series: pd.Series | None = None,
    rs_rank_series: pd.Series | None = None,
):
    max_holding_days = config.risk.max_holding_days
    gates = config.gates
    # populated by stop_fn (which runs first, on the entry bar, with the real
    # entry price) and consumed by target_fn — avoids computing plan_trade_levels
    # twice for the same trade with two different "entry" numbers.
    planned_levels_by_bar: dict[int, object] = {}

    def _blocked_by_gates(history_so_far: pd.DataFrame) -> bool:
        date = history_so_far.index[-1]
        if gates.regime_gate_enabled and regime_series is not None:
            label = regime_series.get(date)
            if label is not None and label in gates.blocked_regime_labels:
                return True
        if rs_rank_series is not None:
            rank = rs_rank_series.get(date)
            if pd.notna(rank) and rank < gates.min_rs_percentile:
                return True
        return False

    def signal_fn(history_so_far: pd.DataFrame) -> bool:
        if len(history_so_far) < MIN_WARMUP_BARS:
            return False
        if _blocked_by_gates(history_so_far):
            return False

        ctx = cache.get(history_so_far)
        signals = evaluate_strategies(ctx)
        best = best_tradeable_signal(signals)
        if best is None:
            return False

        # Approximate R:R pre-check using today's close as an entry proxy (the
        # real entry is tomorrow's open, unknown right now) — mirrors what
        # scanner.py's build_trade_plan does when it plans a setup for display.
        # This can only ever REJECT trades earlier than the real check in
        # stop_fn/target_fn would (using a slightly different entry price); it
        # never accepts a trade that the real computation would reject, since
        # stop_fn recomputes from the actual entry independently.
        atr = ctx.atr14.iloc[-1]
        if pd.isna(atr) or atr <= 0:
            return False
        trade_levels = plan_trade_levels(ctx.last_close, atr, ctx.levels, max_holding_days, direction="long", rr_multiples=(1.5, 3.0))
        if trade_levels is None or trade_levels.risk_reward < gates.min_risk_reward:
            return False

        # score_ticker only needs ctx + the matched strategies here; sector and
        # multi-timeframe aren't threaded through this per-ticker backtest loop,
        # so those categories fall back to their neutral baselines — market
        # regime and relative-strength ARE now available as hard gates above
        # (not fed into the score itself, to avoid gating and scoring on the
        # same fact twice).
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
        trade_levels = plan_trade_levels(entry, atr, ctx.levels, max_holding_days, direction="long", rr_multiples=(1.5, 3.0))
        if trade_levels is None:
            return entry * 0.95
        planned_levels_by_bar[len(history_before_entry)] = trade_levels
        return trade_levels.stop_levels.final_stop

    def target_fn(history_before_entry: pd.DataFrame, entry: float, stop: float) -> float:
        trade_levels = planned_levels_by_bar.get(len(history_before_entry))
        if trade_levels is not None:
            return trade_levels.target2
        # defensive fallback — stop_fn always runs before target_fn for the same
        # entry, so this should not normally be reached
        return entry * 1.05

    return signal_fn, stop_fn, target_fn


def backtest_ticker(
    ticker: str,
    history: pd.DataFrame,
    config: AppConfig,
    min_score: float | None = None,
    regime_series: pd.Series | None = None,
    rs_rank_series: pd.Series | None = None,
):
    cache = SharedContextCache(ticker)
    attempted_strategy_by_bar: dict[int, str] = {}
    score_by_bar: dict[int, float] = {}
    signal_fn, stop_fn, target_fn = make_screener_functions(
        cache, config, attempted_strategy_by_bar, score_by_bar,
        min_score=min_score, regime_series=regime_series, rs_rank_series=rs_rank_series,
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


def build_gate_tables(provider: DataProvider, config: AppConfig, histories: dict[str, pd.DataFrame]):
    """Two walk-forward, no-look-ahead gate tables shared by every ticker in the
    backtest:
    - `regime_series`: the market regime label at every historical date (one
      series, market-wide — doesn't depend on which ticker is being evaluated).
    - `rs_rank_table`: for every date, each ticker's percentile rank vs. every
      OTHER ticker in this same backtest universe on trailing return — the
      walk-forward equivalent of an RS Rating. Built once from all tickers
      together (not per-ticker) since a percentile rank is inherently relative
      to the whole group.
    Both are computed once, up front, and then looked up (not recomputed) inside
    each ticker's per-bar walk-forward loop.
    """
    gates = config.gates
    regime_series = None
    if gates.regime_gate_enabled:
        try:
            benchmarks = {key: provider.get_history(ticker, period="5y") for key, ticker in BENCHMARK_TICKERS.items()}
            regime_series = classify_market_regime_series(benchmarks["spy"], benchmarks["qqq"], benchmarks["iwm"], benchmarks["vix"])
            logger.info("computed market regime series: %d dates", len(regime_series))
        except DataUnavailable as exc:
            logger.warning("could not fetch benchmark data for the regime gate, disabling it: %s", exc)

    closes = {ticker: history["close"] for ticker, history in histories.items()}
    rs_rank_table = universe_rs_rank_series(closes, window=gates.rs_window)
    logger.info("computed RS rank table: %d dates x %d tickers", *rs_rank_table.shape)

    return regime_series, rs_rank_table


def run_universe_backtest(
    provider: DataProvider, config: AppConfig, tickers: list[str], period: str, min_score: float | None = None
):
    all_trades = []
    all_trade_strategies = []
    all_trade_scores = []
    per_ticker_summaries = []
    errors = []

    histories: dict[str, pd.DataFrame] = {}
    for ticker in tickers:
        try:
            history = provider.get_history(ticker, period=period)
        except DataUnavailable as exc:
            errors.append((ticker, str(exc)))
            continue
        if len(history) < MIN_WARMUP_BARS + 30:
            errors.append((ticker, f"insufficient history ({len(history)} bars)"))
            continue
        histories[ticker] = history

    regime_series, rs_rank_table = build_gate_tables(provider, config, histories)

    for i, (ticker, history) in enumerate(histories.items(), start=1):
        rs_rank_series = rs_rank_table[ticker] if ticker in rs_rank_table.columns else None
        result, trade_strategies, trade_scores = backtest_ticker(
            ticker, history, config, min_score=min_score, regime_series=regime_series, rs_rank_series=rs_rank_series
        )
        all_trades.extend(result.trades)
        all_trade_strategies.extend(trade_strategies)
        all_trade_scores.extend(trade_scores)

        closed = [t for t in result.trades if t.pnl is not None]
        wins = sum(1 for t in closed if t.pnl > 0)
        per_ticker_summaries.append(
            {"ticker": ticker, "trades": len(closed), "wins": wins, "win_rate": (wins / len(closed) * 100) if closed else 0.0,
             "total_return_pct": (result.final_equity / result.initial_capital - 1) * 100}
        )
        logger.info("[%d/%d] %s: %d trades, %d wins", i, len(histories), ticker, len(closed), wins)

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
    parser.add_argument("--no-regime-gate", action="store_true", help="Disable the market-regime hard gate (config.gates.regime_gate_enabled), for A/B comparison")
    parser.add_argument("--no-rs-gate", action="store_true", help="Disable the RS-vs-universe hard gate (sets min_rs_percentile to 0), for A/B comparison")
    parser.add_argument("--min-rr", type=float, default=None, help="Override config.gates.min_risk_reward")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    config = load_config(args.config)
    if args.no_regime_gate:
        config.gates.regime_gate_enabled = False
    if args.no_rs_gate:
        config.gates.min_rs_percentile = 0.0
    if args.min_rr is not None:
        config.gates.min_risk_reward = args.min_rr

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
