"""Item 25 (false-positive database): write every LOSING trade from a
capture_trades/merge_captures pickle to a CSV -- setup type, regime, score,
the technical conditions at entry, entry/exit, loss, and a classified failure
reason -- and print which failure modes dominate, so recurring bad-signal
patterns are visible instead of buried in an aggregate win rate.

Failure reasons (first match wins):
  gap_through_stop   stopped out, and the fill was worse than the stop itself
                     (the session opened below the stop)
  held_through_earnings  an earnings announcement fell inside the hold
                     (needs --earnings, a {ticker: [timestamps]} pickle)
  stopped_out        ordinary stop hit
  time_exit_loss     never hit stop or target, closed red at the time cap

Flags added alongside (not exclusive): tight_stop (<1 ATR), gap_up_entry
(opened >0.5 ATR above the signal close), low_rvol (<1.0), weak_regime
(not BULLISH), near_resistance (<1.5 ATR of room).

    python -m research.false_positive_log --trades merged.pkl --out losers.csv [--earnings earnings.pkl]
"""

from __future__ import annotations

import argparse
import bisect
import pickle
import sys

import pandas as pd

from config.schema import load_config
from data.cache import DiskCache
from data.yfinance_provider import YFinanceProvider


def _naive(ts) -> pd.Timestamp:
    ts = pd.Timestamp(ts)
    return ts.tz_convert("UTC").tz_localize(None) if ts.tzinfo else ts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trades", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--earnings", default=None)
    parser.add_argument("--period", default="5y")
    args = parser.parse_args(argv)

    payload = pickle.load(open(args.trades, "rb"))
    earnings = {}
    if args.earnings:
        earnings = {k: sorted(_naive(x) for x in v) for k, v in pickle.load(open(args.earnings, "rb")).items()}

    config = load_config(None)
    provider = YFinanceProvider(cache=DiskCache(cache_dir=config.data.cache_dir, ttl_hours=10_000))
    histories: dict[str, pd.DataFrame] = {}

    rows = []
    fields = zip(payload["trades"], payload["strategies"], payload["scores"], payload["regimes"], payload["features"])
    for t, strategy, score, regime, feat in fields:
        if t.pnl is None or t.pnl >= 0:
            continue
        feat = feat or {}
        ticker = getattr(t, "ticker", None)
        atr = feat.get("raw_entry_atr14")

        gap_atr = None
        if ticker and atr:
            if ticker not in histories:
                histories[ticker] = provider.get_history(ticker, period=args.period)
            h = histories[ticker]
            try:
                i = h.index.get_loc(t.entry_date)
                gap_atr = (float(h["open"].iloc[i]) - float(h["close"].iloc[i - 1])) / atr
            except (KeyError, IndexError):
                pass

        held_through = False
        events = earnings.get(ticker, [])
        if events and t.exit_date is not None:
            start = _naive(t.entry_date).normalize() + pd.Timedelta(hours=13, minutes=30)
            end = _naive(t.exit_date).normalize() + pd.Timedelta(hours=20)
            k = bisect.bisect_right(events, start)
            held_through = k < len(events) and events[k] < end

        slip = config.backtesting.slippage_pct / 100
        if t.exit_reason == "stop" and t.exit_price < t.stop * (1 - slip) - 1e-9:
            reason = "gap_through_stop"
        elif held_through:
            reason = "held_through_earnings"
        elif t.exit_reason == "stop":
            reason = "stopped_out"
        else:
            reason = "time_exit_loss"

        risk = t.shares * (t.entry_price - t.stop)
        rows.append({
            "ticker": ticker, "strategy": strategy, "entry_date": _naive(t.entry_date).date(),
            "exit_date": _naive(t.exit_date).date() if t.exit_date is not None else None,
            "regime": regime, "score": score, "entry": round(t.entry_price, 2), "stop": round(t.stop, 2),
            "target": round(t.target, 2), "exit": round(t.exit_price, 2), "exit_reason": t.exit_reason,
            "loss_pct": round(t.pnl_pct, 2), "loss_usd": round(t.pnl, 2),
            "R": round(t.pnl / risk, 3) if risk > 0 else None,
            "failure_reason": reason,
            "stop_atr": round((t.entry_price - t.stop) / atr, 2) if atr else None,
            "entry_gap_atr": round(gap_atr, 2) if gap_atr is not None else None,
            "rsi14": feat.get("rsi14"), "rvol": feat.get("rvol"), "adx14": feat.get("adx14"),
            "extension_atr": feat.get("extension_atr"),
            "distance_to_resistance_atr": feat.get("distance_to_resistance_atr"),
            "rs_percentile": feat.get("rs_percentile_vs_universe"), "sector_rank": feat.get("sector_rank"),
            "tight_stop": bool(atr and (t.entry_price - t.stop) / atr < 1.0),
            "gap_up_entry": bool(gap_atr is not None and gap_atr > 0.5),
            "low_rvol": bool(feat.get("rvol") is not None and feat["rvol"] < 1.0),
            "weak_regime": regime not in (None, "BULLISH"),
            "near_resistance": bool(feat.get("distance_to_resistance_atr") is not None and feat["distance_to_resistance_atr"] < 1.5),
            "held_through_earnings": held_through,
        })

    df = pd.DataFrame(rows)
    df.to_csv(args.out, index=False)
    total_losers = len(df)
    print(f"\n{total_losers} losing trades written to {args.out}\n")

    print(f"{'Failure reason':<24}{'Trades':>8}{'Share':>8}{'Net $':>11}{'Mean R':>9}")
    for reason, g in df.groupby("failure_reason"):
        print(f"{reason:<24}{len(g):>8}{len(g) / total_losers * 100:>7.1f}%{g.loss_usd.sum():>11,.0f}{g.R.mean():>9.2f}")

    print(f"\n{'Flag (among losers)':<24}{'Share':>8}{'Net $':>11}")
    for flag in ["tight_stop", "gap_up_entry", "low_rvol", "weak_regime", "near_resistance", "held_through_earnings"]:
        g = df[df[flag]]
        print(f"{flag:<24}{len(g) / total_losers * 100:>7.1f}%{g.loss_usd.sum():>11,.0f}")

    print(f"\n{'Worst 10 losses':<24}")
    worst = df.nsmallest(10, "loss_pct")[["ticker", "strategy", "entry_date", "loss_pct", "failure_reason", "regime", "stop_atr", "entry_gap_atr"]]
    print(worst.to_string(index=False))
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
