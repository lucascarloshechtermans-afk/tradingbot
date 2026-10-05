import pandas as pd

from data.sessions import drop_incomplete_daily, last_completed_session


def _ny(s):
    return pd.Timestamp(s, tz="America/New_York")


def test_last_completed_session_during_and_after_the_session():
    assert last_completed_session(_ny("2026-09-30 11:04")) == pd.Timestamp("2026-09-29")   # market open: yesterday
    assert last_completed_session(_ny("2026-09-30 16:20")) == pd.Timestamp("2026-09-30")   # after the close
    assert last_completed_session(_ny("2026-10-03 12:00")) == pd.Timestamp("2026-10-02")   # Saturday -> Friday
    assert last_completed_session(_ny("2026-10-05 09:00")) == pd.Timestamp("2026-10-02")   # Monday pre-open -> Friday


def test_drop_incomplete_daily_removes_todays_live_bar():
    idx = pd.DatetimeIndex(["2026-09-28", "2026-09-29", "2026-09-30"]).tz_localize("America/New_York").tz_convert("UTC")
    df = pd.DataFrame({"close": [1.0, 2.0, 3.0]}, index=idx)
    out = drop_incomplete_daily(df, now=_ny("2026-09-30 14:45"))
    assert list(out["close"]) == [1.0, 2.0]
    assert len(drop_incomplete_daily(df, now=_ny("2026-09-30 17:00"))) == 3
    naive = pd.DataFrame({"close": [1.0, 2.0, 3.0]}, index=pd.DatetimeIndex(["2026-09-28", "2026-09-29", "2026-09-30"]))
    assert len(drop_incomplete_daily(naive, now=_ny("2026-09-30 14:45"))) == 2
