from __future__ import annotations

import json
import logging
from dataclasses import asdict
from pathlib import Path

from alerts.rules import Alert

logger = logging.getLogger(__name__)


class AlertDispatcher:
    """Prints alerts to the console and appends them to a JSON log file.

    Deliberately not a real OS/browser push-notification system — see the build
    plan's UI section for why: that needs a running server and a browser
    permission flow neither of which exist for a locally-run scanner script, and it
    couldn't be exercised in this sandbox anyway. Any future UI can poll this log.
    """

    def __init__(self, log_path: str | Path = "alerts_log.json", print_to_console: bool = True):
        self.log_path = Path(log_path)
        self.print_to_console = print_to_console

    def _load_existing(self) -> list[dict]:
        if not self.log_path.exists():
            return []
        try:
            return json.loads(self.log_path.read_text())
        except json.JSONDecodeError:
            logger.warning("alert log %s is corrupt, starting a fresh log", self.log_path)
            return []

    def dispatch(self, alerts: list[Alert]) -> None:
        if not alerts:
            return
        existing = self._load_existing()
        for alert in alerts:
            if self.print_to_console:
                print(f"[ALERT] {alert.message}")
            existing.append(asdict(alert))
        self.log_path.write_text(json.dumps(existing, indent=2))
