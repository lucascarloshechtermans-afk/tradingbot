import pytest

from watchlist.status import determine_status
from watchlist.store import WatchlistStore


def test_determine_status_invalidated_beats_everything():
    assert determine_status(score=90, entry_triggered=True, stop_hit=True) == "INVALIDATED"


def test_determine_status_triggered_when_entry_fires():
    assert determine_status(score=90, entry_triggered=True, stop_hit=False) == "TRIGGERED"


def test_determine_status_ready_above_threshold():
    assert determine_status(score=75, ready_threshold=70) == "READY"


def test_determine_status_forming_below_threshold():
    assert determine_status(score=50, ready_threshold=70) == "SETUP FORMING"


def test_store_add_and_load(tmp_path):
    store = WatchlistStore(path=tmp_path / "watchlist.json")
    store.add("AAPL", status="SETUP FORMING", notes="testing")
    entries = store.load()
    assert "AAPL" in entries
    assert entries["AAPL"].status == "SETUP FORMING"
    assert entries["AAPL"].notes == "testing"


def test_store_add_is_idempotent(tmp_path):
    store = WatchlistStore(path=tmp_path / "watchlist.json")
    store.add("AAPL")
    store.add("AAPL", status="READY")  # should NOT overwrite existing entry
    entries = store.load()
    assert entries["AAPL"].status == "SETUP FORMING"


def test_store_update_status_sets_detected_date(tmp_path):
    store = WatchlistStore(path=tmp_path / "watchlist.json")
    store.add("AAPL")
    assert store.load()["AAPL"].setup_detected_date is None
    store.update_status("AAPL", "READY")
    entry = store.load()["AAPL"]
    assert entry.status == "READY"
    assert entry.setup_detected_date is not None


def test_store_update_status_unknown_ticker_returns_none(tmp_path):
    store = WatchlistStore(path=tmp_path / "watchlist.json")
    result = store.update_status("NOPE", "READY")
    assert result is None


def test_store_remove(tmp_path):
    store = WatchlistStore(path=tmp_path / "watchlist.json")
    store.add("AAPL")
    store.remove("AAPL")
    assert "AAPL" not in store.load()


def test_store_rejects_invalid_status(tmp_path):
    store = WatchlistStore(path=tmp_path / "watchlist.json")
    with pytest.raises(ValueError):
        store.add("AAPL", status="NOT_A_REAL_STATUS")


def test_store_handles_corrupt_file_gracefully(tmp_path):
    path = tmp_path / "watchlist.json"
    path.write_text("{not valid json")
    store = WatchlistStore(path=path)
    assert store.load() == {}


def test_store_all_entries(tmp_path):
    store = WatchlistStore(path=tmp_path / "watchlist.json")
    store.add("AAPL")
    store.add("MSFT")
    tickers = {e.ticker for e in store.all_entries()}
    assert tickers == {"AAPL", "MSFT"}
