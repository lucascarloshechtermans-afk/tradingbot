import os
import time

import pandas as pd

from data.cache import DiskCache


def _sample_df():
    return pd.DataFrame({"close": [1.0, 2.0, 3.0]})


def test_cache_roundtrip(tmp_path):
    cache = DiskCache(cache_dir=str(tmp_path), ttl_hours=1)
    cache.set("AAPL_1y_1d", _sample_df())
    result = cache.get("AAPL_1y_1d")
    assert result is not None
    pd.testing.assert_frame_equal(result, _sample_df())


def test_cache_miss_returns_none(tmp_path):
    cache = DiskCache(cache_dir=str(tmp_path), ttl_hours=1)
    assert cache.get("NONEXISTENT") is None


def test_cache_expires_after_ttl(tmp_path):
    cache = DiskCache(cache_dir=str(tmp_path), ttl_hours=1)
    cache.set("AAPL_1y_1d", _sample_df())
    path = cache._key_to_path("AAPL_1y_1d")
    old_time = time.time() - 3700  # just over 1 hour ago
    os.utime(path, (old_time, old_time))
    assert cache.get("AAPL_1y_1d") is None


def test_cache_clear_removes_all_entries(tmp_path):
    cache = DiskCache(cache_dir=str(tmp_path), ttl_hours=1)
    cache.set("A", _sample_df())
    cache.set("B", _sample_df())
    cache.clear()
    assert cache.get("A") is None
    assert cache.get("B") is None
