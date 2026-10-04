import numpy as np
import pandas as pd
import pytest

from config.schema import ConfigError, TechnicalConfig, load_config
from data.provider import DataUnavailable
from ta.engine import analyze
from ta.evaluate import _work, forward, split_of, summarize
from ta.regime import classify_regime
from tests.ta_helpers import frame, uptrend


def test_forward_enters_next_open_and_signs_by_direction():
    closes = [100.0] * 30 + [100, 102, 104, 106, 108, 110] + [110.0] * 50
    df = frame(closes, spread=0.0)
    t = 29                                   # signal on the close of bar 29
    up = forward(df, t, 1, atr=2.0)
    entry = df["open"].iloc[t + 1]
    assert up["ret5"] == pytest.approx((df["close"].iloc[t + 5] / entry - 1) * 100)
    dn = forward(df, t, -1, atr=2.0)
    assert dn["ret5"] == pytest.approx(-up["ret5"])
    assert up["mfe"] > 0 and up["mae"] <= 0 and dn["mfe"] == pytest.approx(-up["mae"])
    assert np.isnan(forward(df, len(df) - 10, 1, 2.0)["ret40"])   # horizon past the data -> NaN, never padded
    assert forward(df, len(df) - 1, 1, 2.0) is None                 # no next open -> no trade


def test_chronological_splits():
    assert split_of(pd.Timestamp("2014-09-30")) == "train"
    assert split_of(pd.Timestamp("2014-12-15")) == "purged"     # 40-session outcome would land in 2015
    assert split_of(pd.Timestamp("2015-01-02")) == "validation"
    assert split_of(pd.Timestamp("2019-09-30")) == "validation"
    assert split_of(pd.Timestamp("2019-12-31")) == "purged"
    assert split_of(pd.Timestamp("2020-01-02")) == "oos"


def _sample_inputs(n=720):
    df = frame(uptrend(n, seed=3), spread=0.006)
    spy = frame(uptrend(n, seed=4), spread=0.004)
    dates = [df.index[400], df.index[560]]
    regimes = {d: classify_regime(spy[spy.index <= d]) for d in dates}
    return df, spy, dates, regimes


def test_engine_receives_no_bar_after_the_signal_date(monkeypatch):
    import ta.engine as eng

    seen = []
    real = eng.analyze

    def spy_analyze(ticker, daily, hourly=None, benchmarks=None, regime=None, **kw):
        seen.append((daily.index[-1], max(s.index[-1] for s in (benchmarks or {}).values())))
        return real(ticker, daily, hourly, benchmarks, regime, **kw)

    monkeypatch.setattr(eng, "analyze", spy_analyze)
    df, spy, dates, regimes = _sample_inputs()
    _work(("X", df, "Tech", spy["close"], regimes, dates))
    assert [s[0] for s in seen] == dates and all(b <= d for d, b in seen)


def test_outcomes_unknown_at_the_end_are_nan_not_partial():
    df = frame(list(np.linspace(100, 120, 60)), spread=0.0)
    out = forward(df, len(df) - 3, 1, 1.0)
    assert np.isnan(out["ret20"]) and np.isnan(out["mfe"]) and np.isnan(out["mae"])


def test_evaluation_signals_use_only_data_up_to_the_signal_date():
    df, spy, dates, regimes = _sample_inputs()
    full = pd.DataFrame(_work(("X", df, "Tech", spy["close"], regimes, dates)))
    # the same study on data that ends 41 bars after the last sample date (all later bars removed)
    cut = df.iloc[:df.index.get_loc(dates[-1]) + 42]
    short = pd.DataFrame(_work(("X", cut, "Tech", spy["close"], regimes, dates)))
    cols = ["date", "kind", "status", "direction", "score", "ret5", "ret20", "ret40", "mfe", "mae"]
    assert len(full) and full[cols].equals(short[cols])
    assert {"_all", "_primary"} <= set(full.kind)


def test_summary_reports_every_split_and_group():
    df, spy, dates, regimes = _sample_inputs()
    rows = _work(("X", df, "Tech", spy["close"], regimes, dates))
    res = pd.DataFrame(rows)
    res = pd.concat([res.assign(date=pd.Timestamp(y), ticker=f"T{y}") for y in ("2010-06-01", "2017-06-01", "2023-06-01")])
    unknown = res.iloc[:3].assign(ret20=np.nan, date=pd.Timestamp("2023-06-01"), ticker="T2023-06-01")
    out = summarize(pd.concat([res, unknown]), stride=160)
    assert "SETUPS" in out and "Frequentie" in out and "MFE/MAE" in out
    for split in ("train", "validation", "oos"):
        assert split in out
    assert "3 aandelen" in out    # header counts only rows with a known 20-session outcome


def test_technical_config_parsing_and_weights_reach_the_score():
    cfg = TechnicalConfig.from_dict({"weights": {"volume": 0, "trend": 40}, "hourly_top_n": 5})
    assert cfg.hourly_top_n == 5 and cfg.weights == {"volume": 0.0, "trend": 40.0}
    with pytest.raises(ConfigError):
        TechnicalConfig.from_dict({"weights": {"fundamentals": 5}})
    with pytest.raises(ConfigError):
        TechnicalConfig.from_dict({"weights": {"trend": -1}})
    assert load_config().technical.enabled
    rep = analyze("X", frame(uptrend(400)), weights=cfg.weights)
    by = {c.family: c for c in rep.score.contributions}
    assert by["volume"].points == 0
    assert by["trend"].weight > analyze("X", frame(uptrend(400))).score.contributions[0].weight


class _FakeProvider:
    def __init__(self):
        self.hourly_calls = []

    def get_history(self, ticker, period="1y", interval="1d"):
        if interval != "1d":
            self.hourly_calls.append(ticker)
            raise DataUnavailable("no intraday in this test")
        if ticker == "BAD":
            raise DataUnavailable("missing")
        return frame(uptrend(500, seed=len(ticker)), spread=0.005)


def test_scanner_two_pass_analysis_and_name_order():
    from scanner import run_technical_analysis, technical_names

    class P:
        def __init__(self, t, setup="Breakout"):
            self.ticker, self.setup = t, setup

    class Book:
        picks = [P("AAA"), P("BBB")]
        preview_in = ["CCC", "AAA"]

    names = technical_names(Book(), [], [], [P("DDD"), P("EEE", "No confirmed setup")], [], max_names=10)
    assert names == ["AAA", "BBB", "CCC", "DDD"]
    cfg = load_config()
    cfg.technical.hourly_top_n = 2
    prov = _FakeProvider()
    reports, regime = run_technical_analysis(prov, cfg, ["AAA", "BAD", "CCC", "DDD"], {"AAA": "Information Technology"})
    assert [r.ticker for r in reports] == ["AAA", "CCC", "DDD"]       # a failing name is skipped, order kept
    assert prov.hourly_calls == ["AAA", "CCC"]                         # 4H/1H pass only for the first N
    assert regime is not None and all(0 <= r.score.total <= 100 for r in reports)
    assert {x.benchmark for x in reports[0].rs.results} >= {"SPY", "QQQ", "XLK"}        # sector ETF benchmark from the GICS sector
    cfg.technical.enabled = False
    assert run_technical_analysis(prov, cfg, ["AAA"], {}) == ([], None)


def test_dashboard_has_the_technical_tab():
    from ui.dashboard import build_dashboard_html
    from ui.ta_report import ta_card_line

    rep = analyze("AAA", frame(uptrend(400)))
    html = build_dashboard_html([], {}, [], [], 0, 0.0, technical=([rep], None))
    assert 'data-tab="ta"' in html and "id='ta-AAA'" in html and "function openTa" in html
    assert "openTa('AAA')" in ta_card_line(rep)
    assert "Geen technische analyse" in build_dashboard_html([], {}, [], [], 0, 0.0)


def test_terminal_summary_skips_reports_without_a_daily_analysis(capsys):
    from scanner import print_technical_summary
    good = analyze("AAA", frame(uptrend(400)))
    short = analyze("NEW", frame(uptrend(60)))
    assert not short.daily.ok
    print_technical_summary([short, good], None)
    out = capsys.readouterr().out
    assert "AAA" in out and "NEW" not in out
