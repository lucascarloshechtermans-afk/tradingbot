"""Technical-analysis engine (price, volume and volatility only).

Modules are small and independently testable; `ta.engine.analyze()` combines
them into one explainable `TechnicalReport` per ticker. No module here does
risk management, position sizing or portfolio logic.

Look-ahead rule used everywhere: a function given a frame uses only the rows
in that frame, and a swing point only counts from the bar on which it became
knowable (`Swing.known_at`), never from the bar it occurred on.
"""

LABEL_NL = {
    "strong_bullish": "sterk bullish", "bullish": "bullish", "neutral": "neutraal", "bearish": "bearish",
    "strong_bearish": "sterk bearish", "accelerating": "versnelt", "improving": "verbetert", "decelerating": "vertraagt",
    "worsening": "verslechtert", "flat": "vlak", "early": "vroeg", "established": "gevestigd", "mature": "volwassen",
    "n/a": "n.v.t.", "high": "hoog", "medium": "gemiddeld", "low": "laag", "confirmed": "bevestigd", "failed": "mislukt",
    "pending": "nog niet bevestigd", "strong": "sterke", "weak": "zwakke", "triggered": "getriggerd", "developing": "in ontwikkeling", "none": "geen setup",
}


def nl(code: str) -> str:
    """Dutch display text for an internal code (unknown codes are shown as-is)."""
    return LABEL_NL.get(code, code)

