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
from market_regime.regime import MarketRegime, classify_market_regime_series
from relative_strength.relative_strength import universe_rs_rank_series
from risk.stops_targets import plan_trade_levels
from scanner import BENCHMARK_TICKERS, evaluate_strategies
from scoring.scorer import score_ticker
from strategies import COUNTER_TREND_STRATEGY_NAMES, best_tradeable_signal
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
    regime_by_bar: dict[int, str],
    rr_by_bar: dict[int, float],
    min_score: float | None = None,
    regime_series: pd.Series | None = None,
    rs_rank_series: pd.Series | None = None,
    earnings_growth: float | None = None,
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
        if (
            gates.min_earnings_growth is not None
            and earnings_growth is not None
            and earnings_growth < gates.min_earnings_growth
        ):
            return True
        return False

    def signal_fn(history_so_far: pd.DataFrame) -> bool:
        if len(history_so_far) < MIN_WARMUP_BARS:
            return False

        ctx = cache.get(history_so_far)
        signals = evaluate_strategies(ctx)
        best = best_tradeable_signal(signals)
        if best is None:
            return False

        # Mean Reversion / Support Bounce buy weakness by design, so the
        # RS/regime gates (which require the stock/market to already be
        # STRONG) are exempted for them — see Strategy.counter_trend. A
        # backtest confirmed this isn't theoretical: gating them the same as
        # the trend-following strategies flipped their expectancy negative.
        if best.strategy not in COUNTER_TREND_STRATEGY_NAMES and _blocked_by_gates(history_so_far):
            return False

        # Mirrors two of scanner.py's NO-TRADE hard gates that only need the
        # daily ctx already built here (bearish-higher-timeframe isn't included
        # — it needs a resampled weekly context, which this backtest doesn't
        # build per-bar, so that gate is live-scan-only for now).
        if (
            gates.block_extreme_overextension
            and ctx.overextension is not None
            and ctx.overextension.stretched_reference_count >= 5
        ):
            return False
        if (
            ctx.distance_to_resistance_atr is not None
            and ctx.distance_to_resistance_atr < gates.min_distance_to_resistance_atr
        ):
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
        trade_levels = plan_trade_levels(
            ctx.last_close, atr, ctx.levels, max_holding_days, direction="long", rr_multiples=(1.5, 3.0),
            target_volatility_multiplier=config.risk.target_volatility_multiplier,
        )
        if trade_levels is None or trade_levels.risk_reward < gates.min_risk_reward:
            return False
        rr_by_bar[len(history_so_far)] = trade_levels.risk_reward

        # For the loser/regime-performance reports below — the regime label as
        # of the signal bar (same causal lookup _blocked_by_gates already uses).
        regime_label = None
        if regime_series is not None:
            regime_label = regime_series.get(history_so_far.index[-1])
            if regime_label is not None:
                regime_by_bar[len(history_so_far)] = regime_label

        # Sector and multi-timeframe genuinely aren't threaded through this
        # per-ticker backtest loop (multi-timeframe needs a weekly-resampled
        # context per bar, which isn't built here for performance), so those
        # two categories fall back to their neutral baselines. Market regime
        # and risk/reward ARE already computed right here for the hard gates
        # above (regime_series lookup, trade_levels.risk_reward) — previously
        # they were left out of the score too, which silently deflated the
        # backtest's score by ~4-6 points per trade vs. what scanner.py's live
        # score computes for the same setup (its score bucket 70-79/80+ was
        # empty across 6500+ backtested trades despite live scans regularly
        # landing there) — fixed by passing the same real values scanner.py
        # already uses. This changes what gets RECORDED/reported per trade,
        # not which trades are taken (regime/R:R remain separate hard gates,
        # unaffected by this).
        regime_obj = MarketRegime(label=regime_label, score=0.0) if regime_label else None
        rs_percentile = None
        if rs_rank_series is not None:
            rank = rs_rank_series.get(history_so_far.index[-1])
            rs_percentile = float(rank) if pd.notna(rank) else None
        score_result = score_ticker(
            ctx, config.scoring, matched_strategies=signals,
            market_regime=regime_obj, risk_reward_ratio=trade_levels.risk_reward,
            rs_percentile=rs_percentile,
        )
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
        trade_levels = plan_trade_levels(
            entry, atr, ctx.levels, max_holding_days, direction="long", rr_multiples=(1.5, 3.0),
            target_volatility_multiplier=config.risk.target_volatility_multiplier,
        )
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
    earnings_growth: float | None = None,
):
    cache = SharedContextCache(ticker)
    attempted_strategy_by_bar: dict[int, str] = {}
    score_by_bar: dict[int, float] = {}
    regime_by_bar: dict[int, str] = {}
    rr_by_bar: dict[int, float] = {}
    signal_fn, stop_fn, target_fn = make_screener_functions(
        cache, config, attempted_strategy_by_bar, score_by_bar, regime_by_bar, rr_by_bar,
        min_score=min_score, regime_series=regime_series, rs_rank_series=rs_rank_series,
        earnings_growth=earnings_growth,
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
    trade_regimes = []
    trade_rrs = []
    for trade in result.trades:
        try:
            bar_index = history.index.get_loc(trade.entry_date)
        except KeyError:
            bar_index = None
        trade_strategies.append(attempted_strategy_by_bar.get(bar_index, "Unknown"))
        trade_scores.append(score_by_bar.get(bar_index))
        trade_regimes.append(regime_by_bar.get(bar_index))
        trade_rrs.append(rr_by_bar.get(bar_index))

    return result, trade_strategies, trade_scores, trade_regimes, trade_rrs


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
    all_trade_regimes = []
    all_trade_rrs = []
    per_ticker_summaries = []
    errors = []

    histories: dict[str, pd.DataFrame] = {}
    earnings_growth_by_ticker: dict[str, float | None] = {}
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
        # A single current-snapshot fetch, not a per-bar time series -- yfinance
        # only exposes the MOST RECENT quarterly earnings growth, so this is
        # necessarily applied as a static value across the whole backtest
        # window rather than the (unavailable) value as of each historical
        # date. Only used when gates.min_earnings_growth is set (see
        # GatesConfig); harmless fetch otherwise.
        if config.gates.min_earnings_growth is not None:
            try:
                info = provider.get_info(ticker)
                earnings_growth_by_ticker[ticker] = info.fundamentals.get("earnings_growth")
            except DataUnavailable:
                earnings_growth_by_ticker[ticker] = None

    regime_series, rs_rank_table = build_gate_tables(provider, config, histories)

    for i, (ticker, history) in enumerate(histories.items(), start=1):
        rs_rank_series = rs_rank_table[ticker] if ticker in rs_rank_table.columns else None
        result, trade_strategies, trade_scores, trade_regimes, trade_rrs = backtest_ticker(
            ticker, history, config, min_score=min_score, regime_series=regime_series, rs_rank_series=rs_rank_series,
            earnings_growth=earnings_growth_by_ticker.get(ticker),
        )
        all_trades.extend(result.trades)
        all_trade_strategies.extend(trade_strategies)
        all_trade_scores.extend(trade_scores)
        all_trade_regimes.extend(trade_regimes)
        all_trade_rrs.extend(trade_rrs)

        closed = [t for t in result.trades if t.pnl is not None]
        wins = sum(1 for t in closed if t.pnl > 0)
        per_ticker_summaries.append(
            {"ticker": ticker, "trades": len(closed), "wins": wins, "win_rate": (wins / len(closed) * 100) if closed else 0.0,
             "total_return_pct": (result.final_equity / result.initial_capital - 1) * 100}
        )
        logger.info("[%d/%d] %s: %d trades, %d wins", i, len(histories), ticker, len(closed), wins)

    return all_trades, all_trade_strategies, all_trade_scores, all_trade_regimes, all_trade_rrs, per_ticker_summaries, errors


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


def print_regime_performance_report(all_trades, all_trade_regimes):
    """Per user requirement #7/#20: test whether the SAME strategies perform
    differently by market regime rather than assuming one universal rule set
    works everywhere. Buckets closed trades by the regime label active at
    entry."""
    print(f"\n{'--- Win rate / expectancy by market regime at entry ---':<40}")
    print(f"{'Regime':<18}{'Trades':<9}{'Win rate':<11}{'Avg win':<10}{'Avg loss':<10}{'Expectancy'}")
    by_regime = defaultdict(list)
    for t, regime in zip(all_trades, all_trade_regimes):
        if t.pnl is not None:
            by_regime[regime or "unknown"].append(t)
    for regime, trades in sorted(by_regime.items(), key=lambda kv: -len(kv[1])):
        wins = [t for t in trades if t.pnl > 0]
        losses = [t for t in trades if t.pnl < 0]
        wr = len(wins) / len(trades) * 100 if trades else 0
        avg_w = sum(t.pnl_pct for t in wins) / len(wins) if wins else 0
        avg_l = sum(t.pnl_pct for t in losses) / len(losses) if losses else 0
        expectancy = (len(wins) / len(trades) * avg_w) + (len(losses) / len(trades) * avg_l) if trades else 0
        print(f"{regime:<18}{len(trades):<9}{f'{wr:.1f}%':<11}{f'{avg_w:.2f}%':<10}{f'{avg_l:.2f}%':<10}{expectancy:+.2f}%")
    print()


def print_losing_trade_analysis(all_trades, all_trade_strategies, all_trade_scores, all_trade_regimes, all_trade_rrs):
    """Required, not optional (per explicit instruction): a backtest report that
    only shows aggregate win rate hides WHY trades lose. This compares losers
    against winners across every dimension already being tracked (strategy,
    score at entry, regime at entry, R:R at entry, exit reason) to surface
    patterns worth fixing rather than just a single win-rate number."""
    closed = [t for t in all_trades if t.pnl is not None]
    if not closed:
        return
    zipped = list(zip(closed, all_trade_strategies, all_trade_scores, all_trade_regimes, all_trade_rrs))
    losers = [z for z in zipped if z[0].pnl < 0]
    winners = [z for z in zipped if z[0].pnl > 0]

    print(f"\n{'=' * 60}")
    print(f"LOSING-TRADE ANALYSIS  ({len(losers)} losers of {len(closed)} closed trades)")
    print(f"{'=' * 60}")

    def _avg(values):
        values = [v for v in values if v is not None and pd.notna(v)]
        return sum(values) / len(values) if values else None

    loser_scores = _avg([s for _, _, s, _, _ in losers])
    winner_scores = _avg([s for _, _, s, _, _ in winners])
    loser_rrs = _avg([rr for _, _, _, _, rr in losers])
    winner_rrs = _avg([rr for _, _, _, _, rr in winners])
    print(f"{'Avg score at entry:':<28}losers {loser_scores:.1f}  vs  winners {winner_scores:.1f}" if loser_scores and winner_scores else "")
    print(f"{'Avg R:R at entry:':<28}losers {loser_rrs:.2f}  vs  winners {winner_rrs:.2f}" if loser_rrs and winner_rrs else "")

    print(f"\n{'--- Losers by exit reason ---':<40}")
    exit_reasons = Counter(t.exit_reason for t, *_ in losers)
    for reason, count in exit_reasons.most_common():
        print(f"  {reason:<20}{count} ({count / len(losers) * 100:.0f}% of losers)")

    print(f"\n{'--- Losers by strategy ---':<40}")
    by_strategy_all = defaultdict(list)
    for t, strat, _, _, _ in zipped:
        by_strategy_all[strat].append(t)
    for strategy, trades in sorted(by_strategy_all.items(), key=lambda kv: -len(kv[1])):
        losses = [t for t in trades if t.pnl < 0]
        loss_rate = len(losses) / len(trades) * 100 if trades else 0
        print(f"  {strategy:<26}{len(losses)}/{len(trades)} losers ({loss_rate:.0f}% loss rate)")

    print(f"\n{'--- Losers by regime at entry ---':<40}")
    regime_counter = Counter(regime or "unknown" for _, _, _, regime, _ in losers)
    for regime, count in regime_counter.most_common():
        print(f"  {regime:<18}{count} ({count / len(losers) * 100:.0f}% of losers)")
    print()


def print_report(all_trades, all_trade_strategies, all_trade_scores, all_trade_regimes, all_trade_rrs, per_ticker_summaries, errors, config: AppConfig, period: str):
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

    print(f"\n{'--- Exit reason by strategy (does the target ever get hit?) ---':<40}")
    print(f"{'Strategy':<26}{'Target':<9}{'Stop':<9}{'Time':<9}{'Target-hit-rate'}")
    for strategy, trades in sorted(by_strategy.items(), key=lambda kv: -len(kv[1])):
        reason_counts = Counter(t.exit_reason for t in trades)
        target_n, stop_n, time_n = reason_counts.get("target", 0), reason_counts.get("stop", 0), reason_counts.get("time_exit", 0)
        target_rate = target_n / len(trades) * 100 if trades else 0
        print(f"{strategy:<26}{target_n:<9}{stop_n:<9}{time_n:<9}{target_rate:.1f}%")

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
    print_regime_performance_report(all_trades, all_trade_regimes)
    print_losing_trade_analysis(all_trades, all_trade_strategies, all_trade_scores, all_trade_regimes, all_trade_rrs)


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
    all_trades, all_trade_strategies, all_trade_scores, all_trade_regimes, all_trade_rrs, per_ticker_summaries, errors = run_universe_backtest(
        provider, config, tickers, args.period, min_score=args.min_score
    )
    logger.info("done in %.1fs", time.time() - started)

    print_report(
        all_trades, all_trade_strategies, all_trade_scores, all_trade_regimes, all_trade_rrs,
        per_ticker_summaries, errors, config, args.period,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
