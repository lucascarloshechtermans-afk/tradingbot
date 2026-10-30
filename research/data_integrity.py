"""Item 22 (data integrity check): scan every cached OHLCV series for the
concrete failure modes that would silently corrupt indicators/backtests if
they occurred: duplicate/non-monotonic dates, invalid bars (high<low, open or
close outside [low,high]), non-positive prices/volume, and single-day moves
extreme enough to suggest an unadjusted corporate action slipped through
(see the split-adjustment check already done manually for NVDA during this
audit -- this generalizes that check to the whole universe instead of one
hand-picked ticker).

Runs entirely from the already-cached data (data.cache.DiskCache) built up by
prior backtest runs -- no new network calls.

    python -m research.data_integrity --tickers ... (default: DEFAULT_UNIVERSE)
"""

from __future__ import annotations

import argparse
import sys

from config.schema import load_config
from data.cache import DiskCache
from data.provider import DataProvider, DataUnavailable
from data.universe import DEFAULT_UNIVERSE
from data.yfinance_provider import YFinanceProvider

EXTREME_MOVE_PCT = 40.0  # single-bar close-to-close move that warrants a look


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--period", type=str, default="5y")
    parser.add_argument("--tickers", type=str, default=None)
    parser.add_argument("--config", type=str, default=None)
    args = parser.parse_args(argv)

    config = load_config(args.config)
    cache = DiskCache(cache_dir=config.data.cache_dir, ttl_hours=config.data.cache_ttl_hours)
    provider: DataProvider = YFinanceProvider(cache=cache, max_retries=config.data.max_retries, retry_backoff_seconds=config.data.retry_backoff_seconds)
    tickers = args.tickers.split(",") if args.tickers else DEFAULT_UNIVERSE

    issues = []
    checked = 0
    for ticker in tickers:
        try:
            history = provider.get_history(ticker, period=args.period)
        except DataUnavailable as exc:
            issues.append((ticker, "UNAVAILABLE", str(exc)))
            continue
        checked += 1

        if history.index.duplicated().any():
            issues.append((ticker, "DUPLICATE_DATES", f"{history.index.duplicated().sum()} duplicate index entries"))
        if not history.index.is_monotonic_increasing:
            issues.append((ticker, "NON_MONOTONIC", "date index is not sorted increasing"))

        invalid_bar = history["high"] < history["low"]
        if invalid_bar.any():
            issues.append((ticker, "HIGH_LT_LOW", f"{int(invalid_bar.sum())} bars where high < low"))

        oob_open = (history["open"] > history["high"]) | (history["open"] < history["low"])
        oob_close = (history["close"] > history["high"]) | (history["close"] < history["low"])
        if oob_open.any():
            issues.append((ticker, "OPEN_OUT_OF_RANGE", f"{int(oob_open.sum())} bars where open is outside [low, high]"))
        if oob_close.any():
            issues.append((ticker, "CLOSE_OUT_OF_RANGE", f"{int(oob_close.sum())} bars where close is outside [low, high]"))

        non_positive = (history[["open", "high", "low", "close"]] <= 0).any(axis=1)
        if non_positive.any():
            issues.append((ticker, "NON_POSITIVE_PRICE", f"{int(non_positive.sum())} bars with a zero/negative price"))

        zero_volume = history["volume"] <= 0
        if zero_volume.any():
            issues.append((ticker, "ZERO_VOLUME", f"{int(zero_volume.sum())} bars with zero/negative volume"))

        pct_change = history["close"].pct_change().abs() * 100
        extreme = pct_change[pct_change > EXTREME_MOVE_PCT]
        if not extreme.empty:
            dates = ", ".join(d.date().isoformat() for d in extreme.index[:5])
            issues.append((
                ticker, "EXTREME_MOVE",
                f"{len(extreme)} single-bar move(s) > {EXTREME_MOVE_PCT:.0f}% (e.g. {dates}) -- "
                "verify this is a real event, not an unadjusted split/data glitch",
            ))

    print(f"\n{'=' * 78}")
    print(f"DATA INTEGRITY CHECK  ({checked}/{len(tickers)} tickers checked, {args.period})")
    print(f"{'=' * 78}")
    if not issues:
        print("No issues found.")
    else:
        for ticker, kind, detail in issues:
            print(f"  {ticker:<8} {kind:<22} {detail}")
    print(f"\n{len(issues)} issue(s) across {len({t for t, *_ in issues})} ticker(s)\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
