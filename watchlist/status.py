from __future__ import annotations

VALID_STATUSES = ("SETUP FORMING", "READY", "TRIGGERED", "INVALIDATED")


def determine_status(
    score: float,
    entry_triggered: bool = False,
    stop_hit: bool = False,
    ready_threshold: float = 70.0,
) -> str:
    """Pure state-transition rule for a watchlist entry.

    Precedence: an invalidated setup (stop hit before entry, or the setup no longer
    holds) always wins, then a triggered entry, then the score-based READY/FORMING
    split. Called fresh on every scan — it doesn't need the previous status because
    each of these conditions is independently derivable from today's data.
    """
    if stop_hit:
        return "INVALIDATED"
    if entry_triggered:
        return "TRIGGERED"
    if score >= ready_threshold:
        return "READY"
    return "SETUP FORMING"
