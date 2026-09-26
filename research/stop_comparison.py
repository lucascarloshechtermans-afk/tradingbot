"""Item 17 (stop-loss analysis): the live system already computes an
ATR-based AND a structure-based stop for every trade (see
risk/stops_targets.py's `compute_stop`) and picks whichever the config
prefers (structure, unless unreasonably far from entry). This re-simulates
each captured trade's ACTUAL exit under every stop alternative the feature
capture already recorded (ATR, structure, EMA21, VWAP, recent swing low),
holding entry/target/holding-cap fixed, to see whether the current
stop-selection logic is actually the best one available rather than just
the first one that seemed reasonable.

Caveat printed with the report: this holds the ORIGINAL target and R:R fixed
across all stop variants, so it measures "does a tighter/wider stop change
the outcome of the same trade", not a full re-optimized R:R-consistent
target for each stop distance -- a fair, cheap first cut, not the final
word (a real re-optimization would recompute targets per stop too).

    python -m research.stop_comparison --trades /path/to/trades.pkl
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
from research.exit_sweep import resimulate_exit

STOP_BUFFER_PCT = 0.3


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trades", type=str, required=True)
    parser.add_argument("--config", type=str, default=None)
    args = parser.parse_args(argv)

    with open(args.trades, "rb") as f:
        payload = pickle.load(f)
    trades = payload["trades"]
    features = payload["features"]

    config = load_config(args.config)
    cap = config.risk.max_holding_days or 5
    cache = DiskCache(cache_dir=config.data.cache_dir, ttl_hours=config.data.cache_ttl_hours)
    provider: DataProvider = YFinanceProvider(cache=cache, max_retries=config.data.max_retries, retry_backoff_seconds=config.data.retry_backoff_seconds)

    histories: dict[str, pd.DataFrame] = {}
    by_variant: dict[str, list[float]] = defaultdict(list)
    by_variant_reason: dict[str, list[str]] = defaultdict(list)
    skipped = 0

    for trade, feat in zip(trades, features):
        ticker = getattr(trade, "ticker", None)
        if ticker is None or feat is None:
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

        entry = trade.entry_price
        target = feat.get("raw_target2") or trade.target
        candidates = {
            "actual (hybrid)": feat.get("raw_stop_final"),
            "atr_only": feat.get("raw_stop_atr"),
            "structure_only": feat.get("raw_stop_structure"),
        }
        ema21 = feat.get("raw_ema21_price")
        if ema21 is not None and ema21 < entry:
            candidates["ema21"] = ema21 * (1 - STOP_BUFFER_PCT / 100)
        vwap = feat.get("raw_vwap_price")
        if vwap is not None and vwap < entry:
            candidates["vwap"] = vwap * (1 - STOP_BUFFER_PCT / 100)
        swing_low = feat.get("raw_swing_low_price")
        if swing_low is not None and swing_low < entry:
            candidates["swing_low"] = swing_low * (1 - STOP_BUFFER_PCT / 100)

        for variant, stop in candidates.items():
            if stop is None or target is None or stop >= entry:
                continue
            result = resimulate_exit(
                history, entry_bar_index, entry, stop, target, cap,
                config.backtesting.slippage_pct, config.backtesting.commission_per_trade,
            )
            if result is None:
                continue
            reason, pnl_pct = result
            by_variant[variant].append(pnl_pct)
            by_variant_reason[variant].append(reason)

    print(f"\n{'=' * 78}")
    print(f"STOP-STRUCTURE COMPARISON  (cap={cap} trading days, target held at original target2)")
    print(f"{'=' * 78}")
    print(
        "NOTE: target and R:R are held fixed across variants -- this isolates the stop's\n"
        "own effect, it is not a full re-optimization (see module docstring).\n"
    )
    print(f"{'Stop type':<18}{'Trades':<9}{'Win rate':<11}{'Avg win':<10}{'Avg loss':<10}{'Expectancy':<12}{'Stop-hit%':<10}{'Target-hit%'}")
    for variant, pnls in sorted(by_variant.items(), key=lambda kv: -len(kv[1])):
        reasons = by_variant_reason[variant]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]
        wr = len(wins) / len(pnls) * 100
        avg_w = sum(wins) / len(wins) if wins else 0.0
        avg_l = sum(losses) / len(losses) if losses else 0.0
        expectancy = (len(wins) / len(pnls) * avg_w) + (len(losses) / len(pnls) * avg_l)
        stop_pct = reasons.count("stop") / len(reasons) * 100
        target_pct = reasons.count("target") / len(reasons) * 100
        print(
            f"{variant:<18}{len(pnls):<9}{f'{wr:.1f}%':<11}{f'{avg_w:+.2f}%':<10}{f'{avg_l:+.2f}%':<10}"
            f"{f'{expectancy:+.2f}%':<12}{f'{stop_pct:.1f}%':<10}{f'{target_pct:.1f}%'}"
        )
    print(f"\n(skipped {skipped} trades missing ticker/history/feature data)\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
