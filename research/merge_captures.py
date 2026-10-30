"""Merge several research.capture_trades pickles (e.g. one per ticker-batch)
into one combined payload, in the same shape capture_trades.py itself writes
-- so feature_importance.py/exit_sweep.py/stop_comparison.py can consume the
merged file exactly as if it came from one big run.

Batching the capture into smaller chunks (see run_batched_capture.sh) bounds
peak memory and gives a natural checkpoint: a crash mid-batch only costs that
batch's progress, not the whole universe.

    python -m research.merge_captures --out merged.pkl batch1.pkl batch2.pkl batch3.pkl
"""

from __future__ import annotations

import argparse
import pickle
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=str, required=True)
    parser.add_argument("batches", nargs="+")
    args = parser.parse_args(argv)

    merged = {
        "trades": [], "strategies": [], "scores": [], "regimes": [], "rrs": [], "overexts": [],
        "features": [], "per_ticker_summaries": [], "errors": [], "period": None,
    }
    for path in args.batches:
        with open(path, "rb") as f:
            payload = pickle.load(f)
        for key in ["trades", "strategies", "scores", "regimes", "rrs", "overexts", "features", "per_ticker_summaries", "errors"]:
            merged[key].extend(payload.get(key, []))
        merged["period"] = payload.get("period", merged["period"])
        print(f"{path}: {len(payload.get('trades', []))} trades")

    with open(args.out, "wb") as f:
        pickle.dump(merged, f)
    print(f"merged {len(merged['trades'])} total trades -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
