import io
from contextlib import redirect_stdout

from watchlist_cli import main


def test_add_and_list(tmp_path):
    path = str(tmp_path / "wl.json")
    buf = io.StringIO()
    with redirect_stdout(buf):
        main(["--file", path, "add", "aapl", "--notes", "test note"])
    assert "Added AAPL" in buf.getvalue()

    buf2 = io.StringIO()
    with redirect_stdout(buf2):
        main(["--file", path, "list"])
    assert "AAPL" in buf2.getvalue()
    assert "test note" in buf2.getvalue()


def test_remove(tmp_path):
    path = str(tmp_path / "wl.json")
    main(["--file", path, "add", "MSFT"])
    buf = io.StringIO()
    with redirect_stdout(buf):
        main(["--file", path, "remove", "msft"])
    assert "Removed MSFT" in buf.getvalue()

    buf2 = io.StringIO()
    with redirect_stdout(buf2):
        main(["--file", path, "list"])
    assert "MSFT" not in buf2.getvalue()


def test_status_update(tmp_path):
    path = str(tmp_path / "wl.json")
    main(["--file", path, "add", "TSLA"])
    buf = io.StringIO()
    with redirect_stdout(buf):
        exit_code = main(["--file", path, "status", "tsla", "READY"])
    assert exit_code == 0
    assert "TSLA -> READY" in buf.getvalue()


def test_status_update_unknown_ticker_errors(tmp_path):
    path = str(tmp_path / "wl.json")
    exit_code = main(["--file", path, "status", "NOPE", "READY"])
    assert exit_code == 1


def test_list_empty(tmp_path):
    path = str(tmp_path / "wl.json")
    buf = io.StringIO()
    with redirect_stdout(buf):
        main(["--file", path, "list"])
    assert "empty" in buf.getvalue().lower()
