from __future__ import annotations

import io
from contextlib import redirect_stdout
from dataclasses import dataclass

from backtest_screener import print_losing_trade_analysis, print_regime_performance_report


@dataclass
class _FakeTrade:
    pnl: float | None
    pnl_pct: float
    exit_reason: str


def test_print_regime_performance_report_buckets_by_regime():
    trades = [
        _FakeTrade(pnl=1.0, pnl_pct=2.0, exit_reason="target"),
        _FakeTrade(pnl=-1.0, pnl_pct=-1.5, exit_reason="stop"),
        _FakeTrade(pnl=2.0, pnl_pct=3.0, exit_reason="target"),
    ]
    regimes = ["BULLISH", "BULLISH", "NEUTRAL"]
    buf = io.StringIO()
    with redirect_stdout(buf):
        print_regime_performance_report(trades, regimes)
    output = buf.getvalue()
    assert "BULLISH" in output
    assert "NEUTRAL" in output


def test_print_regime_performance_report_handles_missing_regime():
    trades = [_FakeTrade(pnl=1.0, pnl_pct=2.0, exit_reason="target")]
    regimes = [None]
    buf = io.StringIO()
    with redirect_stdout(buf):
        print_regime_performance_report(trades, regimes)
    assert "unknown" in buf.getvalue()


def test_print_losing_trade_analysis_reports_loser_breakdown():
    trades = [
        _FakeTrade(pnl=1.0, pnl_pct=2.0, exit_reason="target"),
        _FakeTrade(pnl=-1.0, pnl_pct=-1.5, exit_reason="stop"),
        _FakeTrade(pnl=-2.0, pnl_pct=-2.5, exit_reason="time_exit"),
    ]
    strategies = ["Bullish Breakout", "Bullish Breakout", "Mean Reversion"]
    scores = [70.0, 40.0, 45.0]
    regimes = ["BULLISH", "BULLISH", "NEUTRAL"]
    rrs = [2.0, 1.5, 1.3]
    buf = io.StringIO()
    with redirect_stdout(buf):
        print_losing_trade_analysis(trades, strategies, scores, regimes, rrs)
    output = buf.getvalue()
    assert "LOSING-TRADE ANALYSIS" in output
    assert "2 losers of 3" in output
    assert "stop" in output
    assert "time_exit" in output


def test_print_losing_trade_analysis_handles_no_losers():
    trades = [_FakeTrade(pnl=1.0, pnl_pct=2.0, exit_reason="target")]
    buf = io.StringIO()
    with redirect_stdout(buf):
        print_losing_trade_analysis(trades, ["Bullish Breakout"], [70.0], ["BULLISH"], [2.0])
    assert "LOSING-TRADE ANALYSIS" in buf.getvalue()


def test_print_losing_trade_analysis_handles_empty_input():
    buf = io.StringIO()
    with redirect_stdout(buf):
        print_losing_trade_analysis([], [], [], [], [])
    assert buf.getvalue() == ""
