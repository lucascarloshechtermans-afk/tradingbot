"""Print the standard aggregate metrics (win rate, profit factor, expectancy)
from a research.capture_trades / research.merge_captures pickle -- for
comparing two config variants (e.g. max_holding_days 5 vs 7) captured via
separate chunked runs, without re-running a full backtest_screener.py pass
just to see the headline numbers.

    python -m research.report_from_pickle --trades merged.pkl --label "5-day cap"
"""

from __future__ import annotations

import argparse
import pickle
import sys

import pandas as pd

from backtesting.metrics import compute_metrics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trades", type=str, required=True)
    parser.add_argument("--label", type=str, default=None)
    parser.add_argument("--initial-capital", type=float, default=10_000.0)
    args = parser.parse_args(argv)

    with open(args.trades, "rb") as f:
        payload = pickle.load(f)
    trades = payload["trades"]
    strategies = payload.get("strategies", [None] * len(trades))
    closed = [t for t in trades if t.pnl is not None]

    cum_pnl = pd.Series([t.pnl for t in closed]).cumsum() + args.initial_capital
    if cum_pnl.empty:
        cum_pnl = pd.Series([args.initial_capital])
    metrics = compute_metrics(closed, cum_pnl, initial_capital=args.initial_capital)

    label = args.label or args.trades
    print(f"\n=== {label} ({len(closed)} closed trades) ===")
    print(f"Win rate:        {metrics.win_rate_pct:.1f}%")
    print(f"Profit factor:   {metrics.profit_factor}")
    print(f"Expectancy:      {metrics.expectancy:+.2f}%")
    print(f"Avg win/loss:    {metrics.avg_win_pct:.2f}% / {metrics.avg_loss_pct:.2f}%")
    print(f"Avg hold:        {metrics.avg_holding_days:.1f} days")
    print(f"Max cons losses: {metrics.max_consecutive_losses}")

    from collections import defaultdict

    by_strategy = defaultdict(list)
    for t, s in zip(closed, strategies[: len(closed)]):
        by_strategy[s].append(t)
    print(f"\n{'Strategy':<26}{'Trades':<9}{'Win rate':<11}{'Expectancy'}")
    for strategy, strat_trades in sorted(by_strategy.items(), key=lambda kv: -len(kv[1])):
        wins = [t for t in strat_trades if t.pnl > 0]
        losses = [t for t in strat_trades if t.pnl < 0]
        n = len(strat_trades)
        wr = len(wins) / n * 100 if n else 0
        avg_w = sum(t.pnl_pct for t in wins) / len(wins) if wins else 0
        avg_l = sum(t.pnl_pct for t in losses) / len(losses) if losses else 0
        expectancy = (len(wins) / n * avg_w) + (len(losses) / n * avg_l) if n else 0
        print(f"{strategy:<26}{n:<9}{f'{wr:.1f}%':<11}{expectancy:+.2f}%")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
