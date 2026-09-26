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
import dataclasses
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
from relative_strength.relative_strength import compute_universe_momentum_ranks, compute_universe_rs_ranks, efficiency_ratio
from risk.gap_risk import earnings_gap_fraction
from risk.stops_targets import plan_trade_levels
from scoring.multi_timeframe import multi_timeframe_confluence, resample_weekly
from scoring.scorer import ScoreResult, score_ticker
from sector.rotation import SECTOR_ETF_MAP, SECTOR_ETFS, SectorStrength, rank_sectors, sector_strength_for
from strategies import ALL_STRATEGIES, COUNTER_TREND_STRATEGY_NAMES, best_tradeable_signal
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
    category_breakdown: list[dict] = field(default_factory=list)
    explanation: dict = field(default_factory=dict)
    # buy-limit for the next session (signal close + gates.max_entry_gap_atr
    # ATRs); None when the no-chase rule is disabled
    max_entry: float | None = None
    # composite-momentum percentile vs. the scanned universe (see
    # gates.min_momentum_percentile); None when unavailable
    momentum_percentile: float | None = None
    # trader-style chart read (analysis/chart_read.py): headlines, plan,
    # invalidation, bias and an annotated SVG chart; empty when unavailable
    chart_read: dict = field(default_factory=dict)


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
    rs_rank: float | None = None,
    earnings_gap_frac: float | None = None,
    no_trade_log: dict[str, str] | None = None,
    earnings_growth: float | None = None,
    momentum_rank: float | None = None,
) -> TradePlan | None:
    """Returns None when the setup is rejected outright by a hard gate — the
    NO-TRADE engine. A high composite score must never override one of these:
    they run BEFORE scoring even happens. When `no_trade_log` is supplied, the
    specific reason is recorded there (keyed by ticker) instead of being a
    silent None, so a scan run can report exactly why each rejected ticker was
    rejected — not just that it was."""

    def _reject(reason: str) -> None:
        if no_trade_log is not None:
            no_trade_log[ticker] = reason
        return None

    atr = ctx.atr14.iloc[-1]
    if pd.isna(atr) or atr <= 0:
        return _reject("insufficient_data: ATR unavailable")

    entry = ctx.last_close
    matched_strategies = evaluate_strategies(ctx)
    best = best_tradeable_signal(matched_strategies)

    gates = config.gates
    # Momentum-rank and efficiency gates apply to EVERY strategy (unlike the
    # RS/regime gates below): that is how they were validated -- see
    # GatesConfig and the README's scanner-comparison section.
    if gates.min_momentum_percentile is not None:
        if momentum_rank is None:
            return _reject("momentum_rank_unavailable: needs ~258 bars of history (data.period >= 2y) "
                           "and >= 10 ranked tickers")
        if momentum_rank < gates.min_momentum_percentile:
            return _reject(f"weak_momentum_rank: {momentum_rank:.0f} < {gates.min_momentum_percentile:.0f}")
    if gates.min_efficiency_ratio is not None:
        er = efficiency_ratio(ctx.close)
        if er is None or er < gates.min_efficiency_ratio:
            shown = "unavailable" if er is None else f"{er:.2f}"
            return _reject(f"choppy_price_action: efficiency ratio {shown} < {gates.min_efficiency_ratio:.2f}")

    # Mean Reversion / Support Bounce buy weakness by design, so the RS/regime
    # gates (which require the stock/market to already be STRONG) are exempted
    # for them — see Strategy.counter_trend. A ticker with no confirmed setup at
    # all still goes through the gates, matching the pre-gate behavior.
    is_counter_trend = best is not None and best.strategy in COUNTER_TREND_STRATEGY_NAMES
    if not is_counter_trend:
        if gates.regime_gate_enabled and market_regime is not None and market_regime.label in gates.blocked_regime_labels:
            return _reject(f"weak_market_regime: {market_regime.label}")
        if rs_rank is not None and rs_rank < gates.min_rs_percentile:
            return _reject(f"weak_relative_strength: RS rank {rs_rank:.0f} < {gates.min_rs_percentile:.0f}")
        if gates.block_bearish_higher_timeframe and weekly_ctx.trend.iloc[-1] == "bearish":
            return _reject("bearish_higher_timeframe: weekly trend is bearish")

    if earnings_warning is not None and earnings_warning.should_avoid:
        return _reject(f"earnings_too_close: {earnings_warning.message}")

    if (
        gates.min_earnings_growth is not None
        and earnings_growth is not None
        and earnings_growth < gates.min_earnings_growth
    ):
        return _reject(f"weak_earnings_growth: {earnings_growth:.1%} < {gates.min_earnings_growth:.1%}")

    if gates.block_extreme_overextension and ctx.overextension is not None and ctx.overextension.stretched_reference_count >= 5:
        return _reject("extreme_overextension: stretched from every reference at once")

    if (
        ctx.distance_to_resistance_atr is not None
        and ctx.distance_to_resistance_atr < gates.min_distance_to_resistance_atr
    ):
        return _reject(f"resistance_too_close: only {ctx.distance_to_resistance_atr:.2f} ATRs of room")

    max_holding_days = config.risk.holding_days_for(best.strategy if best else None)

    trade_levels = plan_trade_levels(
        entry, atr, ctx.levels, max_holding_days, direction="long", rr_multiples=(1.5, 3.0),
        target_volatility_multiplier=config.risk.target_volatility_multiplier,
        allow_tight_structure_stop=config.risk.allow_tight_structure_stop,
    )
    if trade_levels is None:
        return _reject("insufficient_data: could not compute a valid stop/target")
    stop_levels = trade_levels.stop_levels
    target1, target2, rr = trade_levels.target1, trade_levels.target2, trade_levels.risk_reward

    # Hard gate, not just a scoring input: a setup whose realistically-achievable
    # (horizon-capped) reward doesn't clear the risk by a wide enough margin gets
    # rejected outright, rather than merely scoring lower in one category among
    # ten — this is what actually makes a win rate below 50% still profitable.
    if rr < config.gates.min_risk_reward:
        return _reject(f"poor_risk_reward: {rr:.2f} < {config.gates.min_risk_reward:.2f}")

    mtf_score, mtf_reasons = multi_timeframe_confluence(ctx, weekly_ctx)

    score_result: ScoreResult = score_ticker(
        ctx,
        config.scoring,
        matched_strategies=matched_strategies,
        market_regime=market_regime,
        risk_reward_ratio=rr,
        multi_timeframe_score=mtf_score,
        multi_timeframe_reasons=mtf_reasons,
        rs_percentile=rs_rank,
    )

    max_entry = None
    if config.gates.max_entry_gap_atr is not None:
        max_entry = entry + config.gates.max_entry_gap_atr * float(atr)

    reasons = list(best.reasons) if best else []
    if momentum_rank is not None:
        reasons.append(f"Momentum-rank: top {max(1.0, 100 - momentum_rank):.0f}% van het gescande universum (3/6/12 maanden)")
    reasons.append(f"Doel is berekend om binnen ~{max_holding_days} handelsdagen haalbaar te zijn (op basis van ATR)")
    risks = list(best.risks) if best else []
    if earnings_warning and earnings_warning.message:
        risks.append(earnings_warning.message)

    # Free float / shares outstanding: RISK CONTEXT ONLY, never a bullish/bearish
    # input to the score — a low-float name can move (in either direction) more
    # violently than a large-cap on the same news/volume, which matters for a
    # multi-day hold's stop distance and slippage risk, but says nothing about
    # direction.
    if ctx.free_float_pct is not None and ctx.free_float_pct < 30:
        risks.append(f"Low free float ({ctx.free_float_pct:.0f}% of shares outstanding) — can move more erratically than a typical large-cap")
    elif ctx.shares_outstanding is not None and ctx.shares_outstanding < 50_000_000:
        risks.append(f"Small share count outstanding ({ctx.shares_outstanding / 1e6:.0f}M) — can move more erratically than a typical large-cap")
    if ctx.short_percent_of_float is not None and ctx.short_percent_of_float > 15:
        risks.append(f"Short interest ~{ctx.short_percent_of_float:.0f}% of float — added volatility risk in both directions, not a squeeze signal on its own")

    # Overnight gap risk: a ~5-trading-day hold sits through ~4 overnight
    # sessions where price can jump past a stop with no chance to exit at the
    # stop price — this is disclosure, not a hard gate (no gap frequency is
    # universally "too high" for every setup/account).
    if ctx.large_gap_frequency_pct is not None and ctx.large_gap_frequency_pct >= 10:
        direction_note = ""
        if ctx.up_gap_bias is not None and (ctx.up_gap_bias >= 0.7 or ctx.up_gap_bias <= 0.3):
            direction_note = f", historically skewed {'up' if ctx.up_gap_bias >= 0.7 else 'down'}"
        risks.append(
            f"Elevated overnight gap risk: large gaps on {ctx.large_gap_frequency_pct:.0f}% of recent sessions{direction_note} "
            f"— a stop can be jumped over intact across the ~4 overnight holds in a 5-day swing"
        )
        if earnings_gap_frac is not None and earnings_gap_frac >= 0.5:
            risks.append(f"{earnings_gap_frac * 100:.0f}% of those large gaps coincided with a known earnings date")

    # Per-category breakdown (trend, market structure, momentum, volume, ...),
    # each with its own score/weight/contribution/reasons — surfaced on the
    # TradePlan so the dashboard can show it instead of collapsing everything
    # into the single composite `score` above.
    category_breakdown = [
        {
            "category": cat.category,
            "score": round(cat.score, 1),
            "weight": cat.weight,
            "contribution": round(cat.contribution, 1),
            "reasons": cat.reasons,
        }
        for cat in score_result.categories
    ]

    # Every selected setup must be explainable: this restructures the same
    # underlying reasons/risks/category data into a fixed, always-present
    # shape, so a setup's WHY and its RISK are never a wall of undifferentiated
    # bullet points.
    category_lookup = {cat.category: cat.reasons for cat in score_result.categories}
    resistance_note = None
    if ctx.distance_to_resistance_atr is not None:
        resistance_note = f"Room to resistance: {ctx.distance_to_resistance_atr:.1f} ATRs"
    explanation = {
        "why_it_passed": reasons,
        "why_it_could_fail": risks,
        "structure": category_lookup.get("market_structure", []),
        "momentum": category_lookup.get("momentum", []),
        "volume": category_lookup.get("volume", []),
        "context": (
            category_lookup.get("market_regime", [])
            + category_lookup.get("sector", [])
            + category_lookup.get("relative_strength", [])
        ),
        "levels": [
            f"Entry: {entry:.2f}",
            *([f"Max entry (buy-limit, skip if it opens above): {max_entry:.2f}"] if max_entry is not None else []),
            f"Stop: {stop_levels.final_stop:.2f} ({stop_levels.final_stop_method}-based)",
            f"Target: {target2:.2f}",
            f"Risk/reward: {rr:.1f}:1",
            *([resistance_note] if resistance_note else []),
        ],
        "risk": [
            f"ATR: {float(ctx.atr_pct.iloc[-1]):.1f}% of price" if pd.notna(ctx.atr_pct.iloc[-1]) else "ATR: unavailable",
            f"Max holding period: {max_holding_days} trading days",
            *risks,
        ],
    }

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
        category_breakdown=category_breakdown,
        explanation=explanation,
        max_entry=round(max_entry, 2) if max_entry is not None else None,
        momentum_percentile=round(momentum_rank, 1) if momentum_rank is not None else None,
    )


def scan_ticker(
    ticker: str,
    provider: DataProvider,
    config: AppConfig,
    spy_close: pd.Series,
    sector_ranked: list[SectorStrength],
    market_regime: MarketRegime | None,
    rs_rank: float | None,
    qqq_close: pd.Series | None = None,
    sector_histories: dict[str, pd.DataFrame] | None = None,
    no_trade_log: dict[str, str] | None = None,
    momentum_rank: float | None = None,
) -> TradePlan | None:
    try:
        history = provider.get_history(ticker, period=config.data.period)
        info = provider.get_info(ticker)
    except DataUnavailable as exc:
        logger.warning("skipping %s: %s", ticker, exc)
        if no_trade_log is not None:
            no_trade_log[ticker] = f"insufficient_data: {exc}"
        return None

    if len(history) < 60:
        logger.info("skipping %s: insufficient history (%d bars)", ticker, len(history))
        if no_trade_log is not None:
            no_trade_log[ticker] = f"insufficient_data: only {len(history)} bars of history"
        return None

    # RS/regime gates are applied inside build_trade_plan, AFTER strategies are
    # evaluated — Mean Reversion / Support Bounce setups are exempt from them
    # (see Strategy.counter_trend), so the decision needs to know which strategy
    # matched, which isn't known yet at this point.

    sector_strength = sector_strength_for(info.sector, sector_ranked)
    sector_etf = SECTOR_ETF_MAP.get(info.sector) if info.sector else None
    sector_close = (
        sector_histories[sector_etf]["close"]
        if sector_histories and sector_etf and sector_etf in sector_histories
        else None
    )
    ctx = build_context(
        ticker, history, benchmark_close=spy_close, sector_strength=sector_strength,
        market_cap=info.market_cap, sector_name=info.sector,
        shares_outstanding=info.shares_outstanding, float_shares=info.float_shares,
        short_percent_of_float=info.short_percent_of_float,
        qqq_close=qqq_close, sector_close=sector_close,
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
    # Live-scan-only enrichment: which fraction of this ticker's recent large
    # overnight gaps coincided with a KNOWN earnings date. Not computed in the
    # backtest — see risk/gap_risk.py's docstring for why (avoiding a subtle
    # look-ahead bug around when an earnings date was actually first known).
    earnings_gap_frac = earnings_gap_fraction(history, earnings_dates)
    earnings_growth = info.fundamentals.get("earnings_growth")

    return build_trade_plan(
        ticker, ctx, weekly_ctx, config, market_regime, earnings_warning, rs_rank, earnings_gap_frac, no_trade_log,
        earnings_growth=earnings_growth, momentum_rank=momentum_rank,
    )


def build_chart_read(provider: DataProvider, ticker: str, period: str) -> dict:
    """Daily + 4h chart read for one setup (see analysis/chart_read.py). Only
    run for the few tickers that produced a setup: it needs an extra 1h
    history download per ticker."""
    from analysis.chart_read import read_chart
    from ui.chart_svg import render_chart_svg

    try:
        daily = provider.get_history(ticker, period=period)
    except DataUnavailable:
        return {}
    try:
        hourly = provider.get_history(ticker, period="730d", interval="1h")
    except DataUnavailable:
        hourly = None
    try:
        read = read_chart(ticker, daily, hourly)
        svg = render_chart_svg(daily, read)
    except Exception as exc:  # noqa: BLE001 - a chart read must never break the scan
        logger.warning("chart read failed for %s: %s", ticker, exc)
        return {}
    return {"headlines": read.headlines, "plan": read.plan, "invalidation": read.invalidation,
            "bias": read.bias, "ema200_4h": read.ema200_4h, "svg": svg}


def find_validated_leader_dips(provider: DataProvider, histories: dict[str, pd.DataFrame],
                               benchmarks: dict[str, pd.DataFrame]) -> tuple[list, dict, list]:
    """The validated primary setup (analysis/leader_dip.py) and the leaders
    closest to triggering it, each with its chart read. Momentum is ranked
    against every fetched candidate."""
    from analysis.chart_read import read_chart
    from analysis.leader_dip import dip_alerts, find_leader_dips, market_state

    spy, vix = benchmarks.get("spy"), benchmarks.get("vix")
    try:
        dips = find_leader_dips(histories, spy, vix)
    except Exception as exc:  # noqa: BLE001 - must never break the scan
        logger.warning("leader-dip search failed: %s", exc)
        return [], {}, []

    def with_read(items: list) -> list:
        res = []
        for d in items:
            try:
                hourly = provider.get_history(d.ticker, period="730d", interval="1h")
            except DataUnavailable:
                hourly = None
            res.append((d, read_chart(d.ticker, d.daily, hourly)))
        return res

    alerts = dip_alerts(histories, top=10)
    return with_read(dips), market_state(spy, vix), with_read(alerts)


def find_pattern_setups(provider: DataProvider, histories: dict[str, pd.DataFrame], top: int = 15) -> list:
    """'Ready to boom' chart-pattern setups over every fetched candidate (see
    analysis/setup_finder.py), each with its chart read for the dashboard."""
    from analysis.chart_read import read_chart, resample_to_4h
    from analysis.setup_finder import find_setups
    from indicators.trend import ema as ema_fn

    hourly_cache: dict[str, pd.DataFrame | None] = {}

    def hourly(ticker: str) -> pd.DataFrame | None:
        if ticker not in hourly_cache:
            try:
                hourly_cache[ticker] = provider.get_history(ticker, period="730d", interval="1h")
            except DataUnavailable:
                hourly_cache[ticker] = None
        return hourly_cache[ticker]

    def ema200_4h(ticker: str) -> float | None:
        h = hourly(ticker)
        if h is None:
            return None
        h4 = resample_to_4h(h)
        return float(ema_fn(h4["close"], 200).iloc[-1]) if len(h4) >= 200 else None

    try:
        setups = find_setups(histories, ema200_4h_fn=ema200_4h)[:top]
        return [(s, read_chart(s.ticker, s.daily, hourly(s.ticker))) for s in setups]
    except Exception as exc:  # noqa: BLE001 - the pattern list must never break the scan
        logger.warning("pattern setup search failed: %s", exc)
        return []


@dataclass
class ScanRun:
    trade_plans: list[TradePlan]
    market_regime: MarketRegime | None
    sector_ranked: list[SectorStrength]
    universe_size: int
    scan_duration_s: float
    no_trade: dict[str, str] = field(default_factory=dict)
    # [(analysis.setup_finder.Setup, ChartRead)] -- the 'ready to boom' list
    pattern_setups: list = field(default_factory=list)
    # [(analysis.leader_dip.LeaderDip, ChartRead)] -- the validated primary setup
    leader_dips: list = field(default_factory=list)
    market_state: dict = field(default_factory=dict)
    # [(analysis.leader_dip.DipAlert, ChartRead)] -- leaders closest to a dip trigger
    dip_alerts: list = field(default_factory=list)
    sector_by_ticker: dict = field(default_factory=dict)
    # round-6 portfolio plan (price-only): analysis.momentum_portfolio.MomentumBook,
    # [analysis.index_rsi2.IndexSignal], and the universe closes for sparklines
    momentum_book: object | None = None
    index_signals: list = field(default_factory=list)
    momentum_closes: pd.DataFrame | None = None


def _naive_close(df: pd.DataFrame) -> pd.Series:
    """Close series with a tz-naive New York calendar-date index."""
    c = df["close"].copy()
    if c.index.tz is not None:
        c.index = c.index.tz_convert("America/New_York").tz_localize(None).normalize()
    return c


def find_index_signals(provider: DataProvider) -> list:
    """INDEX RSI(2) state for SPY/QQQ/IWM/DIA (analysis/index_rsi2.py)."""
    from analysis.index_rsi2 import ETFS, index_signals

    hist = {}
    for etf in ETFS:
        try:
            hist[etf] = provider.get_history(etf, period="2y")
        except DataUnavailable as exc:
            logger.warning("index RSI(2): no data for %s: %s", etf, exc)
    try:
        return index_signals(hist)
    except Exception as exc:  # noqa: BLE001 - must never break the scan
        logger.warning("index RSI(2) failed: %s", exc)
        return []


def find_momentum_book(provider: DataProvider, config: AppConfig, spy: pd.DataFrame | None,
                       extra_sectors: dict[str, str | None] | None = None):
    """MOMENTUM TOP 20 over the S&P 500 + 400 plus the scanner's own universe
    -- the same 966-name universe the research backtest ranked
    (analysis/momentum_portfolio.py). Returns (book, closes) or (None, None)."""
    if config.portfolio.momentum_pct <= 0 or spy is None or spy.empty:
        return None, None
    from analysis.momentum_portfolio import build_book, load_universe

    try:
        sectors = load_universe()
        for t in DEFAULT_UNIVERSE:
            sectors.setdefault(t, (extra_sectors or {}).get(t))
        spy_close = _naive_close(spy)
        closes, volumes = provider.get_universe_closes(sorted(sectors), latest_session=spy_close.index[-1])
        if closes.empty:
            return None, None
        book = build_book(closes, volumes, spy_close, sectors, top_n=config.portfolio.momentum_top_n)
        return book, closes
    except NotImplementedError:
        logger.info("momentum book skipped: this data provider has no bulk universe download")
        return None, None
    except Exception as exc:  # noqa: BLE001 - must never break the scan
        logger.warning("momentum book failed: %s", exc)
        return None, None


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
    qqq_close = benchmarks["qqq"]["close"] if "qqq" in benchmarks else None

    # RS rank vs. the rest of the SCANNED universe (not vs. SPY) — a hard
    # pre-filter (see GatesConfig) modeled on the IBD/Minervini RS Rating: only
    # tickers that are themselves leaders relative to their peers pass through.
    rs_ranks = compute_universe_rs_ranks(
        {t: candidates[t][1]["close"] for t in filter_result.included if t in candidates},
        window=config.gates.rs_window,
    )
    logger.info("computed RS rank for %d/%d tickers (min_rs_percentile=%.0f)", len(rs_ranks), len(filter_result.included), config.gates.min_rs_percentile)

    # Composite-momentum rank vs. EVERY fetched candidate, not just the
    # universe-filter survivors: the backtest that validated this gate ranked
    # against the full universe list (it has no market-cap/ATR filter).
    momentum_ranks: dict[str, float] = {}
    if config.gates.min_momentum_percentile is not None:
        momentum_ranks = compute_universe_momentum_ranks({t: c[1]["close"] for t, c in candidates.items()})
        logger.info("computed momentum rank for %d/%d tickers (min_momentum_percentile=%.0f)",
                    len(momentum_ranks), len(candidates), config.gates.min_momentum_percentile)
        if not momentum_ranks:
            logger.warning("no momentum ranks: the momentum gate needs >= 10 tickers with ~258 bars each "
                           "(data.period is %r; use 2y or more) -- every setup will be rejected", config.data.period)

    # The NO-TRADE engine: every ticker that build_trade_plan/scan_ticker rejects
    # gets a specific, named reason recorded here instead of silently vanishing —
    # see ScanRun.no_trade and print_no_trade_summary. A single dict written by
    # multiple worker threads is safe here because each thread only ever writes
    # its own ticker's key (CPython dict.__setitem__ is atomic per-call).
    no_trade_log: dict[str, str] = {}
    for ticker, reason in filter_result.excluded.items():
        no_trade_log[ticker] = f"universe_filter: {reason}"

    trade_plans: list[TradePlan] = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(
                scan_ticker, ticker, provider, config, spy_close, sector_ranked, market_regime, rs_ranks.get(ticker),
                qqq_close, sector_histories, no_trade_log, momentum_ranks.get(ticker),
            ): ticker
            for ticker in filter_result.included
        }
        for future in as_completed(futures):
            ticker = futures[future]
            try:
                plan = future.result()
            except Exception as exc:  # noqa: BLE001 - a single ticker failure must not kill the scan
                logger.warning("error scanning %s: %s", ticker, exc)
                no_trade_log[ticker] = f"error: {exc}"
                plan = None
            if plan is not None:
                trade_plans.append(plan)
                no_trade_log.pop(ticker, None)

    # With the momentum gate on, list the strongest momentum first: in the
    # comparison backtest, picking ~4 setups/week by momentum rank gave
    # +0.14R/trade vs +0.06R picking by composite score.
    if config.gates.min_momentum_percentile is not None:
        # (a ticker with no confirmed setup is never a trade, keep it below real setups)
        trade_plans.sort(
            key=lambda p: (p.setup != "No confirmed setup", p.momentum_percentile or 0.0, p.score), reverse=True
        )
    else:
        trade_plans.sort(key=lambda p: p.score, reverse=True)

    for plan in trade_plans:
        if plan.setup != "No confirmed setup":
            plan.chart_read = build_chart_read(provider, plan.ticker, config.data.period)
    duration = time.time() - started
    logger.info("scan complete: %d tickers scanned, %d setups found in %.1fs", len(filter_result.included), len(trade_plans), duration)

    pattern_setups = find_pattern_setups(provider, {t: c[1] for t, c in candidates.items()})
    leader_dips, mstate, alerts = find_validated_leader_dips(provider, {t: c[1] for t, c in candidates.items()}, benchmarks)
    logger.info("building the portfolio plan: index RSI(2) + momentum top %d", config.portfolio.momentum_top_n)
    signals = find_index_signals(provider)
    book, mom_closes = find_momentum_book(provider, config, benchmarks.get("spy"),
                                          {t: c[0].sector for t, c in candidates.items()})
    return ScanRun(
        trade_plans=trade_plans, market_regime=market_regime, sector_ranked=sector_ranked,
        universe_size=len(filter_result.included), scan_duration_s=duration, no_trade=no_trade_log,
        pattern_setups=pattern_setups, leader_dips=leader_dips, market_state=mstate, dip_alerts=alerts,
        sector_by_ticker={t: c[0].sector for t, c in candidates.items()},
        momentum_book=book, index_signals=signals, momentum_closes=mom_closes,
    )


def print_scan_results(trade_plans: list[TradePlan], min_score: float = 65.0) -> None:
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
    for i, plan in enumerate(shown, start=1):
        cr = plan.chart_read
        if not cr:
            continue
        print(f"{i}. {plan.ticker} chart read ({cr['bias'].upper()}):")
        for h in cr["headlines"]:
            print(f"     {h}")
        if cr.get("plan"):
            print(f"     PLAN: {cr['plan']}")
        if cr.get("invalidation"):
            print(f"     INVALID: {cr['invalidation']}")
        print()


def print_leader_dips(leader_dips: list, market: dict, risk_pct: float = 0.5) -> None:
    vix, weak, bear = market.get("vix"), market.get("spy_below_50"), market.get("spy_below_200")
    print()
    print("=== LEADER DIP -- disciplined dip entry (buy next open, stop 2.5 ATR, exit after 10 sessions) ===")
    print("    research round 4: no setup beat a random stock bought the same day (2008-2026) -- the grade is a")
    print(f"    RISK DIAL: N = normal size ({risk_pct:.2f}% of the account at risk), H = half ({risk_pct / 2:.2f}%) while SPY < 200d")
    if vix is not None:
        print(f"    market: VIX {vix:.1f}, SPY {'BELOW' if weak else 'above'} its 50-day"
              f"{'' if bear is None else (', BELOW its 200-day' if bear else ', above its 200-day')}")
    if not leader_dips:
        print("    NO TRADE: no leader dip today.")
    for d, read in leader_dips:
        tag = {"N": "TRADE", "H": "HALF"}.get(d.grade, "watch")
        print(f"  [{d.grade}] {d.ticker:<6} {tag:<6} close {d.close:.2f}  stop~{d.stop_estimate:.2f} ({d.risk_pct:.1f}%)  "
              f"dip {d.dip_atr:+.1f} ATR  momentum {d.momentum_rank:.0f}")
        print("        + " + "; ".join(d.reasons[2:]) if len(d.reasons) > 2 else "        + (no context notes)")
        if d.missing:
            print("        - " + "; ".join(d.missing))
    print()


def print_portfolio_plan(scan_run: ScanRun, config: AppConfig) -> None:
    """Terminal version of the dashboard's 'Vandaag te doen' + Portefeuille tab."""
    from ui.portfolio import allocation_rows

    pc = config.portfolio
    bear = scan_run.market_state.get("spy_below_200")
    print()
    print(f"=== PORTFOLIO PLAN {pc.momentum_pct:.0f}/{pc.dip_pct:.0f}/{pc.index_rsi2_pct:.0f} (momentum / dip / index RSI2) -- price data only ===")
    for name, pct, amount, rule in allocation_rows(pc, config.risk.account_size, bear):
        print(f"  {name:<22}{pct:>5}  {amount:>10}  {rule}")
    book = scan_run.momentum_book
    if pc.momentum_pct > 0:
        print()
        if book is None or book.as_of is None:
            print("--- MOMENTUM TOP 20: not available (no universe data)")
        else:
            state = "INVESTED" if book.invested else "CASH (SPY closed below its 200-day at month-end)"
            print(f"--- MOMENTUM TOP {len(book.picks)}: month-end list of {book.as_of.date()} -- {state}; "
                  f"next rebalance at the close of {book.next_rebalance.date() if book.next_rebalance is not None else '?'}")
            for p in book.picks:
                print(f"  {p.rank:>2}. {p.ticker:<6} {p.status:<7} 12-1m {p.mom_12_1:+6.0f}%  last month {p.ret_1m:+6.1f}%  month-end close {p.close:>9.2f}  {p.sector or ''}")
            if book.exits:
                print(f"  sell (left the list): {', '.join(book.exits)}")
            if book.preview:
                print(f"  preview if the month ended today ({book.preview_date.date()}): in {', '.join(book.preview_in) or '-'}; "
                      f"out {', '.join(book.preview_out) or '-'}")
    if pc.index_rsi2_pct > 0 and scan_run.index_signals:
        print()
        print("--- INDEX RSI(2): buy next open after close > SMA200 and RSI(2) < 10; sell next open after close > SMA5")
        for sig in scan_run.index_signals:
            trig = (f"sell if close > {sig.sell_above:.2f}" if sig.sell_above is not None else
                    f"buy if close <= {sig.buy_below:.2f}" if sig.buy_below is not None and sig.above_200 else "below 200d: no trade")
            print(f"  {sig.etf:<4} {sig.state:<8} close {sig.close:>8.2f}  RSI2 {sig.rsi2:5.1f}  SMA5 {sig.sma5:>8.2f}  "
                  f"SMA200 {sig.sma200:>8.2f}  tomorrow: {trig}")
    print()


def print_no_trade_summary(no_trade: dict[str, str]) -> None:
    """The NO-TRADE engine's report: every rejected ticker had a specific,
    named reason — this shows the breakdown by reason category, so it's
    obvious whether the scanner is (for example) mostly filtering on weak
    liquidity vs. a bad market regime vs. poor R:R, not just how many tickers
    got rejected."""
    if not no_trade:
        return
    from collections import Counter

    categories = Counter(reason.split(":", 1)[0] for reason in no_trade.values())
    print(f"--- No-trade summary ({len(no_trade)} tickers rejected) ---")
    for category, count in categories.most_common():
        print(f"  {category:<28}{count}")
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
        shares_outstanding = float(200_000_000 + hash(ticker) % 800_000_000)
        return TickerInfo(
            ticker=ticker,
            sector=sectors[hash(ticker) % len(sectors)],
            industry="Synthetic Industry",
            market_cap=float(5_000_000_000 + hash(ticker) % 50_000_000_000),
            shares_outstanding=shares_outstanding,
            float_shares=shares_outstanding * 0.85,
            short_percent_of_float=float(2 + hash(ticker) % 10),
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
    # a cross-sectional percentile over 8 random walks means nothing (and needs
    # >= 10 tickers), so the dry run shows the pipeline without those gates
    gates = dataclasses.replace(config.gates, min_momentum_percentile=None, min_efficiency_ratio=None)
    return run_scan(provider, dataclasses.replace(config, gates=gates), universe=tiny_universe, max_workers=4)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Swing-trade scanner")
    parser.add_argument("--config", type=str, default=None, help="Path to config.yaml (default: config.yaml or config/config.example.yaml)")
    parser.add_argument("--preset", type=str, default=None, choices=["CONSERVATIVE", "BALANCED", "AGGRESSIVE"], help="Override universe.preset")
    parser.add_argument(
        "--min-score", type=float, default=65.0,
        help="Only print setups scoring at or above this threshold. Defaults to 65 "
        "(the 'Interesting' tier and above, per config.scoring.thresholds — "
        "recalibrated against the real achievable score distribution, see "
        "config/schema.py's DEFAULT_SCORE_THRESHOLDS comment) rather than 55/"
        "Watchlist — this scanner is built to surface few, high-conviction setups, "
        "not maximize signal count; pass --min-score 55 or lower to see the full "
        "Watchlist tier too.",
    )
    parser.add_argument("--dashboard", type=str, default="dashboard.html", help="Path to write the HTML dashboard")
    parser.add_argument("--json-output", type=str, default="scan_results.json", help="Path to write raw scan results as JSON")
    parser.add_argument("--dry-run", action="store_true", help="Run the full pipeline on built-in synthetic data (no network needed)")
    parser.add_argument("--max-workers", type=int, default=8, help="Parallel data-fetch workers")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    config = load_config(args.config, preset_override=args.preset)

    if args.dry_run:
        logger.info("running in --dry-run mode: synthetic data, no network required")
        scan_run = run_dry_run(config)
    else:
        cache = DiskCache(cache_dir=config.data.cache_dir, ttl_hours=config.data.cache_ttl_hours)
        provider = YFinanceProvider(cache=cache, max_retries=config.data.max_retries, retry_backoff_seconds=config.data.retry_backoff_seconds)
        scan_run = run_scan(provider, config, max_workers=args.max_workers)

    print_portfolio_plan(scan_run, config)
    print_leader_dips(scan_run.leader_dips, scan_run.market_state, config.portfolio.dip_risk_pct_of_account)
    if scan_run.dip_alerts:
        print("--- Next-session alerts: momentum leaders closest to a LEADER DIP trigger ---")
        for a, _r in scan_run.dip_alerts:
            print(f"  {a.ticker:<6} close {a.close:>9.2f}  dip trigger <= {a.alert_price:>9.2f} ({-a.distance_pct:+.1f}%)  "
                  f"deep-dip (21 EMA - 1 ATR) <= {a.deep_dip_price:>9.2f}  momentum {a.momentum_rank:.0f}  ATR {a.atr_pct:.1f}%")
        print()
    print("--- Other strategy setups (NOT validated: bought short-term strength and did worse than random")
    print("    entries in the same stocks out-of-sample -- see README 'Optimization round 3'; info only) ---")
    print_scan_results(scan_run.trade_plans, min_score=args.min_score)
    if scan_run.pattern_setups:
        print(f"--- Ready to boom: {len(scan_run.pattern_setups)} chart-pattern setups (hold up to 20 days) ---")
        for i, (s, _read) in enumerate(scan_run.pattern_setups, 1):
            print(f"  {i:<3}{s.ticker:<7}{s.score:>4.0f}  {s.status:<17}{s.names[:40]:<41}trigger {s.trigger:.2f}  stop {s.stop:.2f}  target {s.target:.2f}")
        print()
    print_no_trade_summary(scan_run.no_trade)

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
            {
                "rank": s.rank, "etf": s.etf, "performance_5d": s.performance_5d, "performance_1m": s.performance_1m,
                "performance_3m": s.performance_3m, "relative_strength_vs_spy": s.relative_strength_vs_spy,
                "volatility_pct": s.volatility_pct, "trend": s.trend,
            }
            for s in scan_run.sector_ranked
        ],
        watchlist_entries=watchlist_entries,
        universe_size=scan_run.universe_size,
        scan_duration_s=scan_run.scan_duration_s,
        pattern_setups=scan_run.pattern_setups,
        leader_dips=scan_run.leader_dips,
        market_state=scan_run.market_state,
        dip_alerts=scan_run.dip_alerts,
        sector_by_ticker=scan_run.sector_by_ticker,
        portfolio_cfg=config.portfolio,
        account_size=config.risk.account_size,
        momentum_book=scan_run.momentum_book,
        index_signals=scan_run.index_signals,
        momentum_closes=scan_run.momentum_closes,
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
