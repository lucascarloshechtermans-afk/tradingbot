"""Run the full-universe screener backtest with per-trade feature capture
enabled, and dump the result (trade outcomes + the feature vector at entry
for each one) to a pickle for offline analysis by feature_importance.py.

    python -m research.capture_trades --period 5y --out /path/to/trades.pkl

Kept separate from backtest_screener.py's own CLI: this is a research tool,
not something the live scanner or its default validation workflow depends
on, and pickling ~9k dataclass Trade objects + feature dicts has no place in
the production reporting path.
"""

from __future__ import annotations

import argparse
import logging
import pickle
import sys
import time

from backtest_screener import run_universe_backtest
from config.schema import load_config
from data.cache import DiskCache
from data.provider import DataProvider
from data.universe import DEFAULT_UNIVERSE
from data.yfinance_provider import YFinanceProvider

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("capture_trades")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--period", type=str, default="5y")
    parser.add_argument("--tickers", type=str, default=None)
    parser.add_argument("--config", type=str, default=None)
    parser.add_argument("--out", type=str, required=True)
    args = parser.parse_args(argv)

    config = load_config(args.config)
    cache = DiskCache(cache_dir=config.data.cache_dir, ttl_hours=config.data.cache_ttl_hours)
    provider: DataProvider = YFinanceProvider(cache=cache, max_retries=config.data.max_retries, retry_backoff_seconds=config.data.retry_backoff_seconds)
    tickers = args.tickers.split(",") if args.tickers else DEFAULT_UNIVERSE

    started = time.time()
    (
        all_trades, all_trade_strategies, all_trade_scores, all_trade_regimes, all_trade_rrs,
        all_trade_overexts, per_ticker_summaries, errors, all_trade_features,
    ) = run_universe_backtest(provider, config, tickers, args.period, min_score=None, capture_features=True)
    logger.info("done in %.1fs — %d trades, %d errors", time.time() - started, len(all_trades), len(errors))

    payload = {
        "trades": all_trades,
        "strategies": all_trade_strategies,
        "scores": all_trade_scores,
        "regimes": all_trade_regimes,
        "rrs": all_trade_rrs,
        "overexts": all_trade_overexts,
        "features": all_trade_features,
        "per_ticker_summaries": per_ticker_summaries,
        "errors": errors,
        "period": args.period,
    }
    with open(args.out, "wb") as f:
        pickle.dump(payload, f)
    logger.info("wrote %s", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
