import io
from contextlib import redirect_stdout

import pytest

from backtest import build_arg_parser, find_strategy, main


def test_find_strategy_resolves_known_slug():
    strategy = find_strategy("breakout")
    assert strategy.name == "Bullish Breakout"


def test_find_strategy_rejects_unknown_slug():
    with pytest.raises(ValueError):
        find_strategy("not_a_real_strategy")


def test_arg_parser_requires_strategy():
    parser = build_arg_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])  # --strategy is required


def test_main_dry_run_single_backtest_runs_without_error():
    buf = io.StringIO()
    with redirect_stdout(buf):
        exit_code = main(["--dry-run", "--strategy", "breakout"])
    assert exit_code == 0
    output = buf.getvalue()
    assert "Backtest:" in output
    assert "Trades:" in output
    assert "Buy & Hold return:" in output


def test_main_dry_run_walk_forward_runs_without_error():
    buf = io.StringIO()
    with redirect_stdout(buf):
        exit_code = main(["--dry-run", "--strategy", "pullback", "--walk-forward", "--train-days", "150", "--test-days", "50"])
    assert exit_code == 0
    assert "Walk-forward validation:" in buf.getvalue()


def test_main_live_mode_without_ticker_errors():
    exit_code = main(["--strategy", "breakout"])  # no --ticker, no --dry-run
    assert exit_code == 2


def test_main_dry_run_all_strategies_run_without_crashing():
    for slug in ["breakout", "pullback", "trend_continuation", "support_bounce", "momentum_continuation", "mean_reversion", "volatility_contraction"]:
        buf = io.StringIO()
        with redirect_stdout(buf):
            exit_code = main(["--dry-run", "--strategy", slug])
        assert exit_code == 0, f"strategy {slug} failed"
