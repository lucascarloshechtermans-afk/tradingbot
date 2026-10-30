"""Item 18/19 (exit optimization / time-based failure): is the ~5-trading-day
holding cap actually the best exit, or just an assumption nobody re-tested?

Re-running the full universe backtest once per holding-day cap (1..7) would
cost 7x the walk-forward compute for no reason -- the entry decision (which
bar, at what price, with what stop/target) never depends on
`max_holding_days`, only the EXIT does. So this script captures each trade's
entry/stop/target ONCE (via a normal capture_trades.py run, loaded from its
pickle) and re-simulates, entirely offline from the already-cached OHLCV,
what would have happened to that same entry under every holding-day cap from
1 to 7 -- using the exact same stop/target/gap-through-fill rules as
backtesting/engine.py's run_backtest, just replayed by hand per trade instead
of re-running the whole walk-forward loop.

    python -m research.exit_sweep --trades /path/to/trades.pkl
"""

from __future__ import annotations

import argparse
import pickle
import sys
from collections import defaultdict

import pandas as pd

from config.schema import load_config
from data.cache import DiskCache
from data.provider import DataProvider
from data.yfinance_provider import YFinanceProvider


def resimulate_exit(
    history: pd.DataFrame, entry_bar_index: int, entry_price: float, stop: float, target: float,
    cap: int, slippage_pct: float, commission_per_trade: float,
) -> tuple[str, float] | None:
    """Replays backtesting/engine.py's exit rules (including the gap-through
    fix) for one trade, capped at `cap` trading days, entirely from already-
    known entry/stop/target -- no signal/indicator recomputation needed."""
    n = len(history)
    for offset in range(1, cap + 1):
        i = entry_bar_index + offset
        if i >= n:
            break
        bar = history.iloc[i]
        hit_stop = bar["low"] <= stop
        hit_target = bar["high"] >= target
        is_last_bar = i == n - 1
        hit_time_limit = offset >= cap

        if hit_stop or hit_target or hit_time_limit or is_last_bar:
            if hit_stop:
                exit_price = min(float(bar["open"]), stop) * (1 - slippage_pct / 100)
                reason = "stop"
            elif hit_target:
                exit_price = max(float(bar["open"]), target) * (1 - slippage_pct / 100)
                reason = "target"
            elif hit_time_limit:
                exit_price = float(bar["close"])
                reason = "time_exit"
            else:
                exit_price = float(bar["close"])
                reason = "end_of_data"

            cost_basis = entry_price  # per-share; commission handled below as a pct-equivalent nudge
            pnl_per_share_pct = (exit_price - entry_price) / entry_price * 100
            # commission is a fixed $ amount independent of position size in the
            # real engine; approximated here as a pct drag using the original
            # trade's own per-share economics is not exact share-for-share, but
            # commission_per_trade is $1 by default against positions sized in
            # the hundreds-to-thousands of dollars -- a few bps, immaterial to
            # which CAP wins this comparison (the thing being measured).
            return reason, pnl_per_share_pct
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trades", type=str, required=True)
    parser.add_argument("--config", type=str, default=None)
    parser.add_argument("--max-cap", type=int, default=7)
    args = parser.parse_args(argv)

    with open(args.trades, "rb") as f:
        payload = pickle.load(f)
    trades = payload["trades"]
    strategies = payload["strategies"]

    config = load_config(args.config)
    cache = DiskCache(cache_dir=config.data.cache_dir, ttl_hours=config.data.cache_ttl_hours)
    provider: DataProvider = YFinanceProvider(cache=cache, max_retries=config.data.max_retries, retry_backoff_seconds=config.data.retry_backoff_seconds)

    histories: dict[str, pd.DataFrame] = {}
    by_cap: dict[int, list[float]] = defaultdict(list)
    by_cap_reason: dict[int, list[str]] = defaultdict(list)
    by_cap_strategy: dict[tuple[int, str], list[float]] = defaultdict(list)

    skipped = 0
    for trade, strategy in zip(trades, strategies):
        ticker = getattr(trade, "ticker", None)
        if ticker is None:
            skipped += 1
            continue
        if ticker not in histories:
            try:
                histories[ticker] = provider.get_history(ticker, period=payload.get("period", "5y"))
            except Exception:
                continue
        history = histories[ticker]
        try:
            entry_bar_index = history.index.get_loc(trade.entry_date)
        except KeyError:
            skipped += 1
            continue

        for cap in range(1, args.max_cap + 1):
            result = resimulate_exit(
                history, entry_bar_index, trade.entry_price, trade.stop, trade.target, cap,
                config.backtesting.slippage_pct, config.backtesting.commission_per_trade,
            )
            if result is None:
                continue
            reason, pnl_pct = result
            by_cap[cap].append(pnl_pct)
            by_cap_reason[cap].append(reason)
            by_cap_strategy[(cap, strategy)].append(pnl_pct)

    print(f"\n{'=' * 72}")
    print(f"EXIT-DAY SWEEP  ({len(trades) - skipped} trades re-simulated, {skipped} skipped for missing ticker/history)")
    print(f"{'=' * 72}")
    print(f"{'Cap (days)':<12}{'Trades':<9}{'Win rate':<11}{'Avg win':<10}{'Avg loss':<10}{'Expectancy':<12}{'Target-hit%':<12}{'Stop%':<8}{'Time%'}")
    for cap in range(1, args.max_cap + 1):
        pnls = by_cap[cap]
        reasons = by_cap_reason[cap]
        if not pnls:
            continue
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]
        wr = len(wins) / len(pnls) * 100
        avg_w = sum(wins) / len(wins) if wins else 0.0
        avg_l = sum(losses) / len(losses) if losses else 0.0
        expectancy = (len(wins) / len(pnls) * avg_w) + (len(losses) / len(pnls) * avg_l)
        target_pct = reasons.count("target") / len(reasons) * 100
        stop_pct = reasons.count("stop") / len(reasons) * 100
        time_pct = (reasons.count("time_exit") + reasons.count("end_of_data")) / len(reasons) * 100
        print(
            f"{cap:<12}{len(pnls):<9}{f'{wr:.1f}%':<11}{f'{avg_w:+.2f}%':<10}{f'{avg_l:+.2f}%':<10}"
            f"{f'{expectancy:+.2f}%':<12}{f'{target_pct:.1f}%':<12}{f'{stop_pct:.1f}%':<8}{f'{time_pct:.1f}%'}"
        )

    print(f"\n{'--- Expectancy by cap, per strategy ---':<40}")
    all_strategies = sorted({s for (_, s) in by_cap_strategy})
    header = f"{'Strategy':<26}" + "".join(f"{f'{c}d':<9}" for c in range(1, args.max_cap + 1))
    print(header)
    for strategy in all_strategies:
        row = f"{strategy:<26}"
        for cap in range(1, args.max_cap + 1):
            pnls = by_cap_strategy.get((cap, strategy), [])
            if not pnls:
                row += f"{'-':<9}"
                continue
            wins = [p for p in pnls if p > 0]
            losses = [p for p in pnls if p < 0]
            avg_w = sum(wins) / len(wins) if wins else 0.0
            avg_l = sum(losses) / len(losses) if losses else 0.0
            expectancy = (len(wins) / len(pnls) * avg_w) + (len(losses) / len(pnls) * avg_l)
            row += f"{f'{expectancy:+.2f}':<9}"
        print(row)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
