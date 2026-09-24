from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path

from watchlist.status import VALID_STATUSES

logger = logging.getLogger(__name__)


@dataclass
class WatchlistEntry:
    ticker: str
    added_date: str
    status: str
    setup_detected_date: str | None = None
    notes: str = ""
    last_updated: str | None = None


class WatchlistStore:
    """JSON-backed watchlist persistence. One file, read-modify-write on every
    call — simple and sufficient for a single-user local scanner."""

    def __init__(self, path: str | Path = "watchlist_data.json"):
        self.path = Path(path)

    def load(self) -> dict[str, WatchlistEntry]:
        if not self.path.exists():
            return {}
        try:
            raw = json.loads(self.path.read_text())
        except json.JSONDecodeError as exc:
            logger.warning("watchlist file %s is corrupt, treating as empty: %s", self.path, exc)
            return {}
        return {ticker: WatchlistEntry(**data) for ticker, data in raw.items()}

    def save(self, entries: dict[str, WatchlistEntry]) -> None:
        raw = {ticker: asdict(entry) for ticker, entry in entries.items()}
        self.path.write_text(json.dumps(raw, indent=2))

    def add(self, ticker: str, status: str = "SETUP FORMING", notes: str = "") -> WatchlistEntry:
        if status not in VALID_STATUSES:
            raise ValueError(f"Invalid status '{status}', must be one of {VALID_STATUSES}")
        entries = self.load()
        if ticker not in entries:
            entries[ticker] = WatchlistEntry(
                ticker=ticker,
                added_date=date.today().isoformat(),
                status=status,
                setup_detected_date=date.today().isoformat() if status != "SETUP FORMING" else None,
                notes=notes,
                last_updated=datetime.now().isoformat(),
            )
            self.save(entries)
        return entries[ticker]

    def remove(self, ticker: str) -> None:
        entries = self.load()
        if ticker in entries:
            del entries[ticker]
            self.save(entries)

    def update_status(self, ticker: str, new_status: str) -> WatchlistEntry | None:
        if new_status not in VALID_STATUSES:
            raise ValueError(f"Invalid status '{new_status}', must be one of {VALID_STATUSES}")
        entries = self.load()
        entry = entries.get(ticker)
        if entry is None:
            return None
        if entry.setup_detected_date is None and new_status != "SETUP FORMING":
            entry.setup_detected_date = date.today().isoformat()
        entry.status = new_status
        entry.last_updated = datetime.now().isoformat()
        self.save(entries)
        return entry

    def all_entries(self) -> list[WatchlistEntry]:
        return list(self.load().values())
