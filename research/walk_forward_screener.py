"""Item 7 (walk-forward testing), wired to the FULL multi-strategy screener.

README's own "remaining risks" flags this gap: `backtesting/walk_forward.py`
exists and is correct, but was only ever wired into the single-strategy
`backtest.py`, never the multi-strategy `backtest_screener.py` every real
validation in this project actually uses. `run_walk_forward` takes exactly
the same `signal_fn`/`stop_fn`/`target_fn` shape `make_screener_functions`
already builds, so no new backtest engine is needed -- only the plumbing to
call it per ticker instead of `run_backtest`, and aggregate results across
tickers PER WINDOW INDEX (each ticker's window i covers the same relative
train/test split, and since every ticker is fetched with the same `period`,
window i is the same approximate calendar range across tickers -- not an
exact date match, but close enough for a cross-ticker aggregate, which is
what's needed to answer "does this fixed rule set hold up window over
window" rather than "what happened on ticker X in window i" specifically).

No re-fitting happens per window (see walk_forward.py's own docstring) --
this is walk-forward VALIDATION of the current fixed rules, not
optimization. That is the correct scope for this question ("is the system
overfit to one static backtest window") and deliberately not a bigger
per-window parameter search project.

    python -m research.walk_forward_screener --period 5y --train-days 252 --test-days 63
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections import defaultdict

import pandas as pd

from backtest import MIN_WARMUP_BARS
from backtest_screener import SharedContextCache, make_screener_functions
from backtesting.metrics import compute_metrics
from backtesting.walk_forward import run_walk_forward
from config.schema import load_config
from data.cache import DiskCache
from data.provider import DataProvider, DataUnavailable
from data.universe import DEFAULT_UNIVERSE
from data.yfinance_provider import YFinanceProvider
from relative_strength.relative_strength import universe_rs_rank_series
from sector.rotation import SECTOR_ETF_MAP, SECTOR_ETFS, sector_rank_series
from market_regime.regime import classify_market_regime_series
from scanner import BENCHMARK_TICKERS

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("walk_forward_screener")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--period", type=str, default="5y")
    parser.add_argument("--tickers", type=str, default=None)
    parser.add_argument("--config", type=str, default=None)
    parser.add_argument("--train-days", type=int, default=252)
    parser.add_argument("--test-days", type=int, default=63)
    args = parser.parse_args(argv)

    config = load_config(args.config)
    cache = DiskCache(cache_dir=config.data.cache_dir, ttl_hours=config.data.cache_ttl_hours)
    provider: DataProvider = YFinanceProvider(cache=cache, max_retries=config.data.max_retries, retry_backoff_seconds=config.data.retry_backoff_seconds)
    tickers = args.tickers.split(",") if args.tickers else DEFAULT_UNIVERSE

    histories: dict[str, pd.DataFrame] = {}
    sector_by_ticker: dict[str, str | None] = {}
    for ticker in tickers:
        try:
            history = provider.get_history(ticker, period=args.period)
        except DataUnavailable:
            continue
        if len(history) < MIN_WARMUP_BARS + args.train_days + args.test_days:
            continue
        histories[ticker] = history
        try:
            sector_by_ticker[ticker] = provider.get_info(ticker).sector
        except DataUnavailable:
            sector_by_ticker[ticker] = None

    logger.info("%d/%d tickers have enough history for at least one walk-forward window", len(histories), len(tickers))

    benchmarks = {key: provider.get_history(ticker, period=args.period) for key, ticker in BENCHMARK_TICKERS.items()}
    spy_close, qqq_close = benchmarks["spy"]["close"], benchmarks["qqq"]["close"]
    regime_series = None
    if config.gates.regime_gate_enabled:
        try:
            regime_series = classify_market_regime_series(benchmarks["spy"], benchmarks["qqq"], benchmarks["iwm"], benchmarks["vix"])
        except DataUnavailable:
            pass
    closes = {ticker: h["close"] for ticker, h in histories.items()}
    rs_rank_table = universe_rs_rank_series(closes, window=config.gates.rs_window)
    sector_histories = {etf: provider.get_history(etf, period=args.period) for etf in SECTOR_ETFS}
    sector_closes = {etf: df["close"] for etf, df in sector_histories.items()}
    sector_rank_df, sector_trend_df = sector_rank_series(sector_histories, benchmarks["spy"])

    # window_index -> list of per-ticker WalkForwardWindow objects that landed
    # in that slot (same relative position, not an exact shared calendar date)
    windows_by_index: dict[int, list] = defaultdict(list)
    windows_by_index_dates: dict[int, tuple] = {}

    for i, (ticker, history) in enumerate(histories.items(), start=1):
        rs_rank_series = rs_rank_table[ticker] if ticker in rs_rank_table.columns else None
        sector_name = sector_by_ticker.get(ticker)
        sector_etf = SECTOR_ETF_MAP.get(sector_name) if sector_name else None
        cache_obj = SharedContextCache(
            ticker, spy_close=spy_close, qqq_close=qqq_close, sector_name=sector_name,
            sector_close=sector_closes.get(sector_etf) if sector_etf else None,
            sector_rank_df=sector_rank_df, sector_trend_df=sector_trend_df,
        )
        signal_fn, stop_fn, target_fn, holding_days_fn = make_screener_functions(
            cache_obj, config, {}, {}, {}, {}, {},
            regime_series=regime_series, rs_rank_series=rs_rank_series,
        )
        windows = run_walk_forward(
            history, signal_fn, stop_fn, target_fn,
            train_days=args.train_days, test_days=args.test_days,
            initial_capital=config.backtesting.initial_capital,
            risk_per_trade_pct=config.risk.risk_per_trade_pct,
            commission_per_trade=config.backtesting.commission_per_trade,
            slippage_pct=config.backtesting.slippage_pct,
            max_position_pct=config.risk.max_position_pct,
            max_holding_days=config.risk.max_holding_days,
            holding_days_fn=holding_days_fn,
        )
        for idx, w in enumerate(windows, start=1):
            windows_by_index[idx].append(w)
            windows_by_index_dates.setdefault(idx, (w.test_start, w.test_end))
        logger.info("[%d/%d] %s: %d windows", i, len(histories), ticker, len(windows))

    print(f"\n{'=' * 90}")
    print(f"WALK-FORWARD VALIDATION — {len(histories)} tickers, train={args.train_days}d / test={args.test_days}d")
    print("(same fixed rule set every window -- no re-fitting; see module docstring)")
    print(f"{'=' * 90}")
    print(f"{'Window':<10}{'Test period (approx)':<28}{'Trades':<9}{'Win rate':<11}{'Profit factor':<15}{'Expectancy'}")
    for idx in sorted(windows_by_index):
        total_trades = sum(w.trade_count for w in windows_by_index[idx])
        if total_trades == 0:
            continue
        # metrics.win_rate_pct etc. are per-ticker -- recompute a trade-weighted
        # aggregate rather than an unweighted average of per-ticker percentages,
        # since ticker trade counts vary a lot (a 3-trade ticker shouldn't count
        # as much as an 80-trade one).
        total_wins = sum(round(w.metrics.win_rate_pct / 100 * w.trade_count) for w in windows_by_index[idx])
        weighted_expectancy = sum(w.metrics.expectancy * w.trade_count for w in windows_by_index[idx]) / total_trades
        pf_values = [w.metrics.profit_factor for w in windows_by_index[idx] if w.trade_count > 0 and w.metrics.profit_factor not in (None, float("inf"))]
        avg_pf = sum(pf_values) / len(pf_values) if pf_values else float("nan")
        test_start, test_end = windows_by_index_dates[idx]
        period_str = f"{test_start.date()} - {test_end.date()}"
        print(f"{idx:<10}{period_str:<28}{total_trades:<9}{total_wins / total_trades * 100:.1f}%{'':<6}{avg_pf:<15.2f}{weighted_expectancy:+.2f}%")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
