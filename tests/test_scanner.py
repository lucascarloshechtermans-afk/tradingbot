import io
from contextlib import redirect_stdout

import pandas as pd

from config.schema import AppConfig
from market_regime.regime import MarketRegime
from scanner import (
    SyntheticDataProvider,
    build_trade_plan,
    compute_breadth_pct_above_50ma,
    print_scan_results,
    run_dry_run,
    run_scan,
    scan_ticker,
)
from scoring.multi_timeframe import resample_weekly
from tests.helpers import breakout_history, context_from, flat_history


def test_compute_breadth_above_50ma():
    above_df = breakout_history()  # clearly trending up, above its own 50MA
    flat_df = flat_history()
    histories = {"UP": above_df, "FLAT": flat_df}
    breadth = compute_breadth_pct_above_50ma(histories)
    assert breadth is not None
    assert 0 <= breadth <= 100


def test_compute_breadth_none_when_insufficient_history():
    short_df = breakout_history()[:10]
    breadth = compute_breadth_pct_above_50ma({"SHORT": short_df})
    assert breadth is None


def test_build_trade_plan_produces_valid_plan():
    history = breakout_history()
    ctx = context_from(history, ticker="TEST")
    weekly_ctx = context_from(resample_weekly(history), ticker="TEST_weekly")
    config = AppConfig()
    regime = MarketRegime(label="BULLISH", score=50, factors={"spy_trend": "bullish"})

    plan = build_trade_plan("TEST", ctx, weekly_ctx, config, regime, earnings_warning=None)

    assert plan is not None
    assert plan.ticker == "TEST"
    assert plan.stop < plan.entry  # long setup: stop below entry
    assert plan.target2 > plan.entry
    assert plan.risk_reward > 0
    assert 0 <= plan.score <= 100
    assert plan.market_regime == "BULLISH"
    assert len(plan.recent_closes) > 0


def test_build_trade_plan_none_when_atr_unavailable():
    # too little history for ATR(14) to ever produce a value
    idx = pd.date_range("2024-01-01", periods=5, freq="D")
    close = pd.Series([100, 101, 102, 101, 103], index=idx)
    history = pd.DataFrame({"open": close, "high": close + 1, "low": close - 1, "close": close, "volume": 1_000_000.0})
    ctx = context_from(history, ticker="SHORT")
    config = AppConfig()
    plan = build_trade_plan("SHORT", ctx, ctx, config, None, None)
    assert plan is None


def test_scan_ticker_with_synthetic_provider():
    provider = SyntheticDataProvider(seed=1)
    config = AppConfig()
    spy_close = provider.get_history("SPY")["close"]
    plan = scan_ticker("SYNTEST", provider, config, spy_close, sector_ranked=[], market_regime=None)
    assert plan is not None
    assert plan.ticker == "SYNTEST"


def test_run_dry_run_produces_ranked_results():
    config = AppConfig()
    scan_run = run_dry_run(config)
    assert scan_run.universe_size > 0
    assert len(scan_run.trade_plans) > 0
    scores = [p.score for p in scan_run.trade_plans]
    assert scores == sorted(scores, reverse=True)  # ranked descending


def test_run_scan_skips_tickers_with_data_errors():
    class FlakyProvider(SyntheticDataProvider):
        def get_history(self, ticker, period="1y", interval="1d"):
            if ticker == "BADTICKER":
                from data.provider import DataUnavailable

                raise DataUnavailable("simulated failure")
            return super().get_history(ticker, period, interval)

    provider = FlakyProvider(seed=2)
    config = AppConfig()
    scan_run = run_scan(provider, config, universe=["GOODTICKER", "BADTICKER"], max_workers=2)
    tickers = {p.ticker for p in scan_run.trade_plans}
    assert "BADTICKER" not in tickers


def test_print_scan_results_matches_requested_format():
    config = AppConfig()
    scan_run = run_dry_run(config)
    buf = io.StringIO()
    with redirect_stdout(buf):
        print_scan_results(scan_run.trade_plans, min_score=0)
    output = buf.getvalue()
    assert " — Score " in output
    assert "RANK" in output and "TICKER" in output and "SETUP" in output


def test_print_scan_results_respects_min_score_filter():
    config = AppConfig()
    scan_run = run_dry_run(config)
    buf = io.StringIO()
    with redirect_stdout(buf):
        print_scan_results(scan_run.trade_plans, min_score=200)  # nothing qualifies
    assert "No setups scored above" in buf.getvalue()
