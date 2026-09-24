from __future__ import annotations

import hashlib
import logging
import time
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


class DiskCache:
    """Simple on-disk cache for OHLCV frames, keyed by ticker/period/interval.

    Freshness is TTL-based (file mtime), not calendar-aware — a `cache_ttl_hours`
    below ~20 is recommended for daily bars so a new trading day's close is picked
    up promptly.
    """

    def __init__(self, cache_dir: str = ".cache", ttl_hours: float = 20.0):
        self.cache_dir = Path(cache_dir)
        self.ttl_seconds = ttl_hours * 3600
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _key_to_path(self, key: str) -> Path:
        digest = hashlib.sha1(key.encode()).hexdigest()[:16]
        safe_prefix = "".join(c for c in key if c.isalnum())[:40]
        return self.cache_dir / f"{safe_prefix}_{digest}.pkl"

    def get(self, key: str) -> pd.DataFrame | None:
        path = self._key_to_path(key)
        if not path.exists():
            return None
        age = time.time() - path.stat().st_mtime
        if age > self.ttl_seconds:
            logger.debug("cache stale for %s (age=%.0fs)", key, age)
            return None
        try:
            return pd.read_pickle(path)
        except Exception as exc:
            logger.warning("cache read failed for %s: %s", key, exc)
            return None

    def set(self, key: str, df: pd.DataFrame) -> None:
        path = self._key_to_path(key)
        try:
            df.to_pickle(path)
        except Exception as exc:
            logger.warning("cache write failed for %s: %s", key, exc)

    def clear(self) -> None:
        for f in self.cache_dir.glob("*.pkl"):
            f.unlink(missing_ok=True)
