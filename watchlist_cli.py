"""Watchlist management CLI.

    python watchlist_cli.py add AAPL --notes "Watching for a pullback to the 50MA"
    python watchlist_cli.py remove AAPL
    python watchlist_cli.py list
"""

from __future__ import annotations

import argparse
import sys

from watchlist.status import VALID_STATUSES
from watchlist.store import WatchlistStore


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage the swing-scanner watchlist")
    parser.add_argument("--file", type=str, default="watchlist_data.json")
    sub = parser.add_subparsers(dest="command", required=True)

    add_p = sub.add_parser("add", help="Add a ticker to the watchlist")
    add_p.add_argument("ticker")
    add_p.add_argument("--notes", type=str, default="")

    remove_p = sub.add_parser("remove", help="Remove a ticker from the watchlist")
    remove_p.add_argument("ticker")

    sub.add_parser("list", help="List all watchlist entries")

    status_p = sub.add_parser("status", help="Manually set a ticker's status")
    status_p.add_argument("ticker")
    status_p.add_argument("new_status", choices=list(VALID_STATUSES))

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    store = WatchlistStore(path=args.file)

    if args.command == "add":
        entry = store.add(args.ticker.upper(), notes=args.notes)
        print(f"Added {entry.ticker} (status: {entry.status})")
    elif args.command == "remove":
        store.remove(args.ticker.upper())
        print(f"Removed {args.ticker.upper()}")
    elif args.command == "status":
        entry = store.update_status(args.ticker.upper(), args.new_status)
        if entry is None:
            print(f"{args.ticker.upper()} is not on the watchlist", file=sys.stderr)
            return 1
        print(f"{entry.ticker} -> {entry.status}")
    elif args.command == "list":
        entries = store.all_entries()
        if not entries:
            print("Watchlist is empty.")
        for entry in entries:
            print(f"{entry.ticker:<8}{entry.status:<16}added {entry.added_date}  {entry.notes}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
