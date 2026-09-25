"""Swing-trade scanner CLI.

    python scanner.py                  # full scan using config.yaml (or the example config)
    python scanner.py --dry-run        # runs the full pipeline on built-in synthetic
                                        # data, no network required — proves the
                                        # wiring works before real data access exists
    python scanner.py --preset AGGRESSIVE --min-score 70

See README.md for the full option list and an explanation of every output column.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np
import pandas as pd

from config.schema import AppConfig, load_config
from data.cache import DiskCache
from data.provider import DataProvider, DataUnavailable, TickerInfo
from data.universe import DEFAULT_UNIVERSE, apply_universe_filters
from data.yfinance_provider import YFinanceProvider
from events.earnings import EarningsWarning, check_earnings_proximity
from indicators.trend import sma
from market_regime.regime import MarketRegime, classify_market_regime
from relative_strength.relative_strength import compute_universe_rs_ranks
from risk.stops_targets import plan_trade_levels
from scoring.multi_timeframe import multi_timeframe_confluence, resample_weekly
from scoring.scorer import ScoreResult, score_ticker
from sector.rotation import SECTOR_ETFS, SectorStrength, rank_sectors, sector_strength_for
from strategies import ALL_STRATEGIES, best_tradeable_signal
from strategies.base import StrategySignal
from strategies.context import TickerContext, build_context

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("scanner")

BENCHMARK_TICKERS = {"spy": "SPY", "qqq": "QQQ", "iwm": "IWM", "vix": "^VIX"}
SPARKLINE_BARS = 60


@dataclass
class TradePlan:
    ticker: str
    setup: str
    trend: str
    score: float
    label: str
    entry: float
    stop: float
    target1: float
    target2: float
    risk_reward: float
    atr_pct: float
    relative_volume: float
    market_regime: str
    sector: str | None
    confidence: float
    reasons: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    rsi: float = 0.0
    recent_closes: list[float] = field(default_factory=list)
    max_holding_days: int = 5


def compute_breadth_pct_above_50ma(universe_histories: dict[str, pd.DataFrame]) -> float | None:
    above = 0
    total = 0
    for df in universe_histories.values():
        if len(df) < 50:
            continue
        s50 = sma(df["close"], 50).iloc[-1]
        if pd.isna(s50):
            continue
        total += 1
        if df["close"].iloc[-1] > s50:
            above += 1
    return (above / total * 100) if total else None


def evaluate_strategies(ctx: TickerContext) -> list[StrategySignal]:
    return [strategy.evaluate(ctx) for strategy in ALL_STRATEGIES]


def build_trade_plan(
    ticker: str,
    ctx: TickerContext,
    weekly_ctx: TickerContext,
    config: AppConfig,
    market_regime: MarketRegime | None,
    earnings_warning: EarningsWarning | None,
) -> TradePlan | None:
    atr = ctx.atr14.iloc[-1]
    if pd.isna(atr) or atr <= 0:
        return None

    entry = ctx.last_close
    matched_strategies = evaluate_strategies(ctx)
    best = best_tradeable_signal(matched_strategies)

    max_holding_days = config.risk.max_holding_days

    trade_levels = plan_trade_levels(entry, atr, ctx.levels, max_holding_days, direction="long", rr_multiples=(1.5, 3.0))
    if trade_levels is None:
        return None
    stop_levels = trade_levels.stop_levels
    target1, target2, rr = trade_levels.target1, trade_levels.target2, trade_levels.risk_reward

    # Hard gate, not just a scoring input: a setup whose realistically-achievable
    # (horizon-capped) reward doesn't clear the risk by a wide enough margin gets
    # rejected outright, rather than merely scoring lower in one category among
    # ten — this is what actually makes a win rate below 50% still profitable.
    if rr < config.gates.min_risk_reward:
        return None

    mtf_score, mtf_reasons = multi_timeframe_confluence(ctx, weekly_ctx)

    score_result: ScoreResult = score_ticker(
        ctx,
        config.scoring,
        matched_strategies=matched_strategies,
        market_regime=market_regime,
        risk_reward_ratio=rr,
        multi_timeframe_score=mtf_score,
        multi_timeframe_reasons=mtf_reasons,
    )

    reasons = list(best.reasons) if best else []
    reasons.append(f"Doel is berekend om binnen ~{max_holding_days} handelsdagen haalbaar te zijn (op basis van ATR)")
    risks = list(best.risks) if best else []
    if earnings_warning and earnings_warning.message:
        risks.append(earnings_warning.message)

    return TradePlan(
        ticker=ticker,
        setup=best.strategy if best else "No confirmed setup",
        trend=str(ctx.trend.iloc[-1]),
        score=score_result.total_score,
        label=score_result.label,
        entry=round(entry, 2),
        stop=round(stop_levels.final_stop, 2),
        target1=round(target1, 2),
        target2=round(target2, 2),
        risk_reward=round(rr, 2),
        atr_pct=round(float(ctx.atr_pct.iloc[-1]), 2) if pd.notna(ctx.atr_pct.iloc[-1]) else 0.0,
        relative_volume=round(float(ctx.rvol.iloc[-1]), 2) if pd.notna(ctx.rvol.iloc[-1]) else 0.0,
        market_regime=market_regime.label if market_regime else "UNKNOWN",
        sector=ctx.sector_name,
        confidence=round(best.confidence, 1) if best else round(score_result.total_score, 1),
        reasons=reasons,
        risks=risks,
        rsi=round(float(ctx.rsi14.iloc[-1]), 1) if pd.notna(ctx.rsi14.iloc[-1]) else 50.0,
        recent_closes=[round(float(c), 2) for c in ctx.close.tail(SPARKLINE_BARS).tolist()],
        max_holding_days=max_holding_days,
    )


def scan_ticker(
    ticker: str,
    provider: DataProvider,
    config: AppConfig,
    spy_close: pd.Series,
    sector_ranked: list[SectorStrength],
    market_regime: MarketRegime | None,
    rs_rank: float | None,
) -> TradePlan | None:
    try:
        history = provider.get_history(ticker, period=config.data.period)
        info = provider.get_info(ticker)
    except DataUnavailable as exc:
        logger.warning("skipping %s: %s", ticker, exc)
        return None

    if len(history) < 60:
        logger.info("skipping %s: insufficient history (%d bars)", ticker, len(history))
        return None

    gates = config.gates
    if gates.regime_gate_enabled and market_regime is not None and market_regime.label in gates.blocked_regime_labels:
        logger.info("skipping %s: market regime %s is blocked by the regime gate", ticker, market_regime.label)
        return None

    if rs_rank is not None and rs_rank < gates.min_rs_percentile:
        logger.info("skipping %s: RS rank %.0f < min_rs_percentile %.0f (not a market leader)", ticker, rs_rank, gates.min_rs_percentile)
        return None

    sector_strength = sector_strength_for(info.sector, sector_ranked)
    ctx = build_context(
        ticker, history, benchmark_close=spy_close, sector_strength=sector_strength,
        market_cap=info.market_cap, sector_name=info.sector,
    )

    weekly_history = resample_weekly(history)
    weekly_ctx = build_context(f"{ticker}_weekly", weekly_history) if len(weekly_history) >= 60 else ctx

    try:
        earnings_dates = provider.get_earnings_dates(ticker)
    except DataUnavailable:
        earnings_dates = []
    earnings_warning = check_earnings_proximity(
        earnings_dates, as_of=datetime.now(), buffer_days=config.earnings.buffer_days,
        avoid_earnings=config.earnings.avoid_earnings,
    )

    return build_trade_plan(ticker, ctx, weekly_ctx, config, market_regime, earnings_warning)


@dataclass
class ScanRun:
    trade_plans: list[TradePlan]
    market_regime: MarketRegime | None
    sector_ranked: list[SectorStrength]
    universe_size: int
    scan_duration_s: float


def run_scan(provider: DataProvider, config: AppConfig, universe: list[str] | None = None, max_workers: int = 8) -> ScanRun:
    started = time.time()
    universe = universe if universe is not None else DEFAULT_UNIVERSE

    logger.info("fetching benchmark data (SPY/QQQ/IWM/VIX)")
    try:
        benchmarks = {
            key: provider.get_history(ticker, period=config.data.period) for key, ticker in BENCHMARK_TICKERS.items()
        }
    except DataUnavailable as exc:
        logger.error("could not fetch benchmark data, market regime will be unavailable: %s", exc)
        benchmarks = {}

    logger.info("fetching sector ETF data")
    sector_histories = {}
    for etf in SECTOR_ETFS:
        try:
            sector_histories[etf] = provider.get_history(etf, period=config.data.period)
        except DataUnavailable as exc:
            logger.warning("skipping sector ETF %s: %s", etf, exc)

    sector_ranked: list[SectorStrength] = []
    if "spy" in benchmarks and sector_histories:
        sector_ranked = rank_sectors(sector_histories, benchmarks["spy"])

    logger.info("fetching universe candidate data (%d tickers) for filtering", len(universe))
    candidates: dict[str, tuple[TickerInfo, pd.DataFrame]] = {}
    for ticker in universe:
        try:
            hist = provider.get_history(ticker, period=config.data.period)
            info = provider.get_info(ticker)
            candidates[ticker] = (info, hist)
        except DataUnavailable as exc:
            logger.warning("skipping %s during universe filtering: %s", ticker, exc)

    filter_result = apply_universe_filters(candidates, config.universe)
    logger.info("universe filter: %d/%d tickers passed", len(filter_result.included), len(universe))

    market_regime = None
    if all(k in benchmarks for k in ("spy", "qqq", "iwm", "vix")):
        breadth = compute_breadth_pct_above_50ma({t: candidates[t][1] for t in filter_result.included if t in candidates})
        market_regime = classify_market_regime(
            benchmarks["spy"], benchmarks["qqq"], benchmarks["iwm"], benchmarks["vix"], breadth_pct_above_50ma=breadth
        )
        logger.info("market regime: %s (score %.0f)", market_regime.label, market_regime.score)

    spy_close = benchmarks["spy"]["close"] if "spy" in benchmarks else None

    # RS rank vs. the rest of the SCANNED universe (not vs. SPY) — a hard
    # pre-filter (see GatesConfig) modeled on the IBD/Minervini RS Rating: only
    # tickers that are themselves leaders relative to their peers pass through.
    rs_ranks = compute_universe_rs_ranks(
        {t: candidates[t][1]["close"] for t in filter_result.included if t in candidates},
        window=config.gates.rs_window,
    )
    logger.info("computed RS rank for %d/%d tickers (min_rs_percentile=%.0f)", len(rs_ranks), len(filter_result.included), config.gates.min_rs_percentile)

    trade_plans: list[TradePlan] = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(scan_ticker, ticker, provider, config, spy_close, sector_ranked, market_regime, rs_ranks.get(ticker)): ticker
            for ticker in filter_result.included
        }
        for future in as_completed(futures):
            ticker = futures[future]
            try:
                plan = future.result()
            except Exception as exc:  # noqa: BLE001 - a single ticker failure must not kill the scan
                logger.warning("error scanning %s: %s", ticker, exc)
                plan = None
            if plan is not None:
                trade_plans.append(plan)

    trade_plans.sort(key=lambda p: p.score, reverse=True)
    duration = time.time() - started
    logger.info("scan complete: %d tickers scanned, %d setups found in %.1fs", len(filter_result.included), len(trade_plans), duration)

    return ScanRun(
        trade_plans=trade_plans, market_regime=market_regime, sector_ranked=sector_ranked,
        universe_size=len(filter_result.included), scan_duration_s=duration,
    )


def print_scan_results(trade_plans: list[TradePlan], min_score: float = 60.0) -> None:
    shown = [p for p in trade_plans if p.score >= min_score]
    if not shown:
        print("No setups scored above the minimum threshold.")
        return

    print()
    for i, plan in enumerate(shown, start=1):
        print(f"{i}. {plan.ticker} — Score {plan.score:.0f} — {plan.setup}")
    print()

    header = f"{'RANK':<5}{'TICKER':<8}{'SCORE':<7}{'SETUP':<24}{'ENTRY':<9}{'STOP':<9}{'TARGET':<9}{'R:R':<6}{'TREND':<10}{'RVOL':<7}{'RSI':<6}{'MARKET':<10}"
    print(header)
    print("-" * len(header))
    for i, plan in enumerate(shown, start=1):
        print(
            f"{i:<5}{plan.ticker:<8}{plan.score:<7.1f}{plan.setup[:23]:<24}{plan.entry:<9.2f}"
            f"{plan.stop:<9.2f}{plan.target2:<9.2f}{plan.risk_reward:<6.1f}{plan.trend:<10}"
            f"{plan.relative_volume:<7.1f}{plan.rsi:<6.0f}{plan.market_regime:<10}"
        )
    print()


# --------------------------------------------------------------------------- #
# --dry-run: fully synthetic, network-free pipeline proof
# --------------------------------------------------------------------------- #


class SyntheticDataProvider(DataProvider):
    """Deterministic, network-free data source for `--dry-run`. Not a mock of real
    market data — it exists purely to prove the scan pipeline (universe filtering,
    indicators, strategies, scoring, risk, dashboard) wires together correctly
    without requiring the network access this sandbox doesn't have.
    """

    def __init__(self, seed: int = 42):
        self._rng = np.random.default_rng(seed)

    def get_history(self, ticker: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
        n = 300
        idx = pd.date_range(end=pd.Timestamp.today(), periods=n, freq="B", tz="UTC")
        if ticker == "^VIX":
            # VIX trades in a characteristic ~10-35 band, not the arbitrary
            # 50-150 range the generic formula below produces for a "price" —
            # generating it unrealistically high would make classify_market_regime's
            # high-volatility override fire on every single dry-run scan.
            drift = self._rng.uniform(-0.05, 0.05)
            noise_scale = self._rng.uniform(0.1, 0.3)
            base = 18.0
            close = pd.Series(
                base + np.cumsum(self._rng.normal(drift, noise_scale, n)), index=idx
            ).clip(lower=10.0, upper=35.0)
            open_ = close.shift(1).fillna(close.iloc[0])
            high = pd.concat([open_, close], axis=1).max(axis=1) + self._rng.uniform(0.1, 0.3)
            low = pd.concat([open_, close], axis=1).min(axis=1) - self._rng.uniform(0.1, 0.3)
            volume = pd.Series(self._rng.uniform(500_000, 5_000_000, n), index=idx)
            return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "adj_close": close, "volume": volume})

        drift = self._rng.uniform(-0.1, 0.4)
        noise_scale = self._rng.uniform(0.5, 2.0)
        base = 50 + hash(ticker) % 100
        close = pd.Series(
            base + np.cumsum(self._rng.normal(drift, noise_scale, n)), index=idx
        ).clip(lower=1.0)
        open_ = close.shift(1).fillna(close.iloc[0])
        high = pd.concat([open_, close], axis=1).max(axis=1) + self._rng.uniform(0.2, 1.0)
        low = pd.concat([open_, close], axis=1).min(axis=1) - self._rng.uniform(0.2, 1.0)
        volume = pd.Series(self._rng.uniform(500_000, 5_000_000, n), index=idx)
        return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "adj_close": close, "volume": volume})

    def get_info(self, ticker: str) -> TickerInfo:
        sectors = ["Technology", "Healthcare", "Financial Services", "Energy", "Consumer Cyclical"]
        return TickerInfo(
            ticker=ticker,
            sector=sectors[hash(ticker) % len(sectors)],
            industry="Synthetic Industry",
            market_cap=float(5_000_000_000 + hash(ticker) % 50_000_000_000),
        )

    def get_earnings_dates(self, ticker: str):
        return []

    def get_dividends(self, ticker: str) -> pd.Series:
        return pd.Series(dtype=float)

    def get_splits(self, ticker: str) -> pd.Series:
        return pd.Series(dtype=float)


def run_dry_run(config: AppConfig) -> ScanRun:
    provider = SyntheticDataProvider()
    tiny_universe = ["SYNA", "SYNB", "SYNC", "SYND", "SYNE", "SYNF", "SYNG", "SYNH"]
    return run_scan(provider, config, universe=tiny_universe, max_workers=4)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Swing-trade scanner")
    parser.add_argument("--config", type=str, default=None, help="Path to config.yaml (default: config.yaml or config/config.example.yaml)")
    parser.add_argument("--preset", type=str, default=None, choices=["CONSERVATIVE", "BALANCED", "AGGRESSIVE"], help="Override universe.preset")
    parser.add_argument("--min-score", type=float, default=60.0, help="Only print setups scoring at or above this threshold")
    parser.add_argument("--dashboard", type=str, default="dashboard.html", help="Path to write the HTML dashboard")
    parser.add_argument("--json-output", type=str, default="scan_results.json", help="Path to write raw scan results as JSON")
    parser.add_argument("--dry-run", action="store_true", help="Run the full pipeline on built-in synthetic data (no network needed)")
    parser.add_argument("--max-workers", type=int, default=8, help="Parallel data-fetch workers")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    config = load_config(args.config)
    if args.preset:
        config.universe.preset = args.preset

    if args.dry_run:
        logger.info("running in --dry-run mode: synthetic data, no network required")
        scan_run = run_dry_run(config)
    else:
        cache = DiskCache(cache_dir=config.data.cache_dir, ttl_hours=config.data.cache_ttl_hours)
        provider = YFinanceProvider(cache=cache, max_retries=config.data.max_retries, retry_backoff_seconds=config.data.retry_backoff_seconds)
        scan_run = run_scan(provider, config, max_workers=args.max_workers)

    print_scan_results(scan_run.trade_plans, min_score=args.min_score)

    from ui.dashboard import build_dashboard_html, trade_plan_to_row
    from watchlist.store import WatchlistStore

    watchlist_entries = [
        {"ticker": e.ticker, "status": e.status, "added_date": e.added_date, "setup_detected_date": e.setup_detected_date, "notes": e.notes}
        for e in WatchlistStore().all_entries()
    ]
    html = build_dashboard_html(
        scan_rows=[trade_plan_to_row(p) for p in scan_run.trade_plans],
        market_regime={"label": scan_run.market_regime.label, "score": scan_run.market_regime.score, "factors": scan_run.market_regime.factors} if scan_run.market_regime else {},
        sector_ranked=[
            {"rank": s.rank, "etf": s.etf, "performance_1m": s.performance_1m, "performance_3m": s.performance_3m, "relative_strength_vs_spy": s.relative_strength_vs_spy, "trend": s.trend}
            for s in scan_run.sector_ranked
        ],
        watchlist_entries=watchlist_entries,
        universe_size=scan_run.universe_size,
        scan_duration_s=scan_run.scan_duration_s,
    )
    with open(args.dashboard, "w") as f:
        f.write(html)
    logger.info("dashboard written to %s", args.dashboard)

    with open(args.json_output, "w") as f:
        json.dump([trade_plan_to_row(p) for p in scan_run.trade_plans], f, indent=2)
    logger.info("raw results written to %s", args.json_output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
