"""Phase-1 audit: the swing v4 trade logic on hand-made OHLC scenarios, run through every implementation:

  engine   indicator_lab.engine.simulate        research engine (E-experiments)
  core     indicator_lab.swing4.core.simulate   swing4 research simulator
  sim2     indicator_lab.swing4.sim2.simulate   swing4 phase-2 simulator (partials)
  pine     indicator_lab.pine_sim.machine       the Pine INDICATOR's state machine (f_machine), line by line
  strat    indicator_lab.pine_sim.book          the Pine STRATEGY under TradingView's order rules

Each scenario gives the signal bar, the exit signals and constant ATR = 1, so the expected fills can be written down by
hand. No market data needed. The Pine runtime itself cannot run here: `pine`/`strat` are Python emulations of the Pine
files; parity with real TradingView output is checked with pine_parity.compare_tv on an exported chart (see report).
"""
import json

import numpy as np
import pandas as pd
import pytest

from indicator_lab import pine_sim as PS
from indicator_lab.engine import ExitRules
from indicator_lab.engine import simulate as eng_sim
from indicator_lab.swing4 import core as C
from indicator_lab.swing4 import sim2 as S2

COST = 0.001
CFG = {**PS.DEFAULT, "stats_from": "2000-01-01", "trail": 4.0, "cost_pct": 0.1}


def make(rows, entries=(0,), exits=(), atr=1.0):
    o, h, lo, c = (np.array(x, float) for x in zip(*rows))
    n = len(o)
    idx = pd.date_range("2020-01-01", periods=n, freq="B")
    df = pd.DataFrame({"open": o, "high": h, "low": lo, "close": c, "volume": 1e6}, index=idx)
    e = np.zeros(n, bool)
    e[list(entries)] = True
    x = np.zeros(n, bool)
    x[list(exits)] = True
    return df, e, x, np.full(n, atr)


def net(entry, px, k=COST):
    return px * (1 - k) / (entry * (1 + k)) - 1


def run_all(df, e, x, a, cfg=None):
    """Trades of all five implementations as (entry_date, exit_date, exit price, return)."""
    cfg = {**CFG, **(cfg or {})}
    o, h, lo, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    out = {}
    _, tr = eng_sim(df, e, x, a, ExitRules(trail_atr=4.0, stop_atr=4.0), cost=COST)
    out["engine"] = [(t["entry_date"], t["exit_date"], t["exit"], t["ret"]) for t in tr]
    _, tr = C.simulate(df, e, x, a)
    out["core"] = [(t["entry_date"], t["exit_date"], t["exit"], t["ret"]) for t in tr]
    _, tr = S2.simulate(S2.arrays(df, a, x), e)
    # sim2 keeps no single exit price (partials can fill in pieces); with one fill it follows from the return
    out["sim2"] = [(t["entry_date"], t["exit_date"], (1 + t["ret"]) * t["entry"] * (1 + COST) / (1 - COST), t["ret"])
                   for t in tr]
    m = PS.machine(df.index, o, h, lo, c, a, e, x, cfg)
    out["pine"] = [(t["entry_date"], t["exit_date"], t["exit"], t["ret"]) for t in m["trades"]]
    tr = PS.book(df.index, o, h, lo, c, a, e, x, cfg, from_time="2000-01-01")
    out["strat"] = [(t["entry_date"], t["exit_date"], t["exit"], t["ret"]) for t in tr]
    return out, m


def assert_all(out, expect):
    """expect: list of (entry bar, exit bar, exit price); every implementation must produce exactly these trades and
    the engine-formula return (the strategy uses TradingView's commission formula: within 0.01 %-pt)."""
    for name, trades in out.items():
        assert len(trades) == len(expect), (name, trades)
        for (ed, xd, px, r), (ei, xi, xpx) in zip(trades, expect):
            idx = pd.date_range("2020-01-01", periods=xi + 1, freq="B")
            assert (ed, xd) == (idx[ei], idx[xi]), (name, ed, xd)
            assert px == pytest.approx(xpx, abs=1e-9), (name, px)
            assert r == pytest.approx(net(ENTRY[0], xpx), abs=1e-4 if name == "strat" else 1e-12), (name, r)


ENTRY = [100.0]
FLAT = (100, 100.5, 99.5, 100)


def test_normal_buy_and_sell_on_the_m_day_low_fills_at_the_next_open():
    # signal bar 0, fill bar 1 at 100; exit signal on bar 4's close -> sold at bar 5's open (101)
    rows = [FLAT, (100, 101, 99.5, 100.5), (100.5, 102, 100, 101.5), (101.5, 102.5, 101, 102), (102, 102, 100.5, 101),
            (101, 101.5, 100, 100.5), FLAT]
    df, e, x, a = make(rows, exits=(4,))
    ENTRY[0] = 100.0
    out, m = run_all(df, e, x, a)
    assert_all(out, [(1, 5, 101.0)])
    assert m["buy"][0] and m["sell"][4] and np.isnan(m["sell_px"][4])   # label: "next open", no price


def test_gap_up_at_entry_fills_at_the_gapped_open_and_the_initial_stop_uses_that_fill():
    # signal close 100, fill bar opens at 105: stop = 105 - 4 = 101; bar 2 trades down to 100.5 -> stopped at 101
    rows = [FLAT, (105, 106, 104, 105), (104, 104, 100.5, 101), FLAT]
    df, e, x, a = make(rows)
    ENTRY[0] = 105.0
    out, m = run_all(df, e, x, a)
    # fill bar high 106 -> trail 106 - 4 = 102 from bar 2 on (above the initial stop 101): stopped at 102
    assert_all(out, [(1, 2, 102.0)])
    assert m["sell_px"][2] == 102.0


def test_stop_on_the_entry_day():
    # fill at 100, the same bar falls to 95: the protective stop 100 - 4 x ATR(signal bar) = 96 fills on the fill bar
    rows = [FLAT, (100, 100.2, 95, 96.5), FLAT]
    df, e, x, a = make(rows)
    ENTRY[0] = 100.0
    out, m = run_all(df, e, x, a)
    assert_all(out, [(1, 1, 96.0)])
    assert m["trades"][0]["kind"] == "initial stop"


def test_no_look_ahead_the_fill_bars_high_only_moves_the_stop_from_the_next_bar():
    # fill bar: high 110, low 103. The trail from that high (106) is NOT applied on the fill bar itself (only the
    # initial stop 96 is), although the low 103 is below 106. Bar 2 then touches 106 -> stopped at 106.
    rows = [FLAT, (100, 110, 103, 108), (107, 107.5, 105, 106), FLAT]
    df, e, x, a = make(rows)
    ENTRY[0] = 100.0
    out, _ = run_all(df, e, x, a)
    assert_all(out, [(1, 2, 106.0)])


def test_trailing_stop_after_several_bars():
    # highs rise 101..105; trail = highest high - 4 = 101 after bar 5; bar 6 dips to 100.9 -> stopped at 101
    rows = [FLAT, (100, 101, 99.5, 100.5), (100.5, 102, 100, 101.5), (101.5, 103, 101, 102.5),
            (102.5, 104, 102, 103.5), (103.5, 105, 103, 104), (104, 104.2, 100.9, 101.5), FLAT]
    df, e, x, a = make(rows)
    ENTRY[0] = 100.0
    out, m = run_all(df, e, x, a)
    assert_all(out, [(1, 6, 101.0)])
    assert m["trades"][0]["kind"] == "trail stop"


def test_gap_through_the_stop_fills_at_the_open():
    rows = [FLAT, (100, 101, 99.5, 100.5), (93, 94, 92, 93.5), FLAT]
    df, e, x, a = make(rows)
    ENTRY[0] = 100.0
    out, m = run_all(df, e, x, a)
    assert_all(out, [(1, 2, 93.0)])
    assert m["sell_px"][2] == 93.0      # the label shows the real fill (the open), not the stop level


def test_no_re_entry_on_the_exit_bar():
    # stopped on bar 2; a new BUY condition on bar 2 itself is ignored; the one on bar 3 is taken
    rows = [FLAT, (100, 101, 99.5, 100.5), (100, 100, 96, 99), (99, 100, 98.5, 99.5), (99.5, 100, 99, 99.5),
            (99.5, 99.6, 94, 95), FLAT]
    df, e, x, a = make(rows, entries=(0, 2, 3))
    ENTRY[0] = 100.0
    out, _ = run_all(df, e, x, a)
    for name, tr in out.items():
        assert [t[0] for t in tr] == [df.index[1], df.index[4]], name


def test_open_position_at_the_end_is_not_a_closed_trade():
    rows = [FLAT, (100, 101, 99.5, 100.5), (100.5, 102, 100, 101.5)]
    df, e, x, a = make(rows)
    out, m = run_all(df, e, x, a)
    assert all(tr == [] for tr in out.values())
    assert m["open_position"] and m["in_trade"][-1]


def test_costs_engine_formula_and_tradingview_commission():
    rows = [FLAT, (100, 101, 99.5, 100.5), (100.5, 110, 100.5, 109), (109, 109.5, 108, 108.5), (110, 111, 109, 110)]
    df, e, x, a = make(rows, exits=(3,))
    out, _ = run_all(df, e, x, a)
    assert out["engine"][0][3] == pytest.approx(110 * 0.999 / (100 * 1.001) - 1, abs=1e-15)
    # TradingView: commission 0.1% of the traded value on both sides
    assert out["strat"][0][3] == pytest.approx((110 - 100) / 100 - 0.001 * (1 + 110 / 100), abs=1e-15)
    assert abs(out["engine"][0][3] - out["strat"][0][3]) < 1e-4


def test_stop_wins_when_stop_and_half_profit_target_touch_the_same_bar():
    # half-profit target +4 ATR = 104 (pine tp_mult 4; sim2 partial at +1R with R = 4 ATR). Fill bar high 101 -> trail
    # 97 from bar 2. Bar 2 touches 104 AND 96.5: the stop wins, no half is booked, everything exits at 97.
    rows = [FLAT, (100, 101, 99.5, 100.5), (100, 104.5, 96.5, 100), FLAT]
    df, e, x, a = make(rows)
    o, h, lo, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    m = PS.machine(df.index, o, h, lo, c, a, e, x, {**CFG, "tp_mult": 4.0, "half_book": True})
    _, tr = S2.simulate(S2.arrays(df, a, x), e, S2.Policy(partial=((1.0, 0.5),)))
    assert m["trades"][0]["exit"] == 97.0 and not m["trades"][0]["half"]
    assert m["trades"][0]["ret"] == pytest.approx(net(100, 97), abs=1e-12)
    assert tr[0]["parts_hit"] == 0 and tr[0]["ret"] == pytest.approx(net(100, 97), abs=1e-12)


def test_half_profit_then_exit_books_fifty_fifty():
    # half at +4 ATR = 104 on bar 2 (not a gap: open 101), the rest leaves at bar 5's open 106 after an exit signal
    rows = [FLAT, (100, 101, 99.5, 100.5), (101, 104.5, 100.8, 104), (104, 106, 103.5, 105.5), (105.5, 106.5, 105, 106),
            (106, 106.2, 105.5, 106), FLAT]
    df, e, x, a = make(rows, exits=(4,))
    o, h, lo, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    m = PS.machine(df.index, o, h, lo, c, a, e, x, {**CFG, "tp_mult": 4.0, "half_book": True})
    _, tr = S2.simulate(S2.arrays(df, a, x), e, S2.Policy(partial=((1.0, 0.5),)))
    expect = 0.5 * net(100, 104) + 0.5 * net(100, 106)
    assert m["trades"][0]["half"] and m["trades"][0]["ret"] == pytest.approx(expect, abs=1e-12)
    assert tr[0]["ret"] == pytest.approx(expect, abs=1e-12)


def test_missing_atr_blocks_the_entry_in_the_engines():
    rows = [FLAT, (100, 101, 99.5, 100.5), FLAT, FLAT]
    df, e, x, a = make(rows)
    a[0] = np.nan
    _, tr = eng_sim(df, e, x, a, ExitRules(trail_atr=4.0, stop_atr=4.0))
    _, tr2 = C.simulate(df, e, x, a)
    assert tr == [] and tr2 == []


def _fake_features(index, values: dict):
    from indicator_lab.export_pine import _load
    feats = _load()[0]["feats"]
    return pd.DataFrame({f: values.get(f, 0.0) for f in feats}, index=index)


def test_missing_model_feature_means_no_buy(monkeypatch):
    """A missing feature (volume, SPY, ...) makes quality na and blocks the BUY (no silent imputation, step R4)."""
    from indicator_lab import pine_parity as PP
    idx = pd.date_range("2020-01-01", periods=5, freq="B")
    f = _fake_features(idx, {})
    f.loc[idx[2], "rvol"] = np.nan          # e.g. no volume
    f.loc[idx[3], "spy_roc63"] = np.nan     # e.g. no SPY data
    monkeypatch.setattr(PP, "pine_features", lambda df, us=True, version="current": f)
    df = pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0}, index=idx)
    q, thr = PS.quality(df, "X", PS.V41)
    assert np.isfinite(q[[0, 1, 4]]).all() and np.isnan(q[2]) and np.isnan(q[3])
    with np.errstate(invalid="ignore"):
        assert not (q >= thr)[2] and not (q >= thr)[3]


def test_year_change_switches_to_that_years_walk_forward_fit(monkeypatch):
    from indicator_lab import pine_parity as PP
    from indicator_lab.export_pine import _load
    final, yearly = _load()
    idx = pd.DatetimeIndex(["2019-12-31", "2020-01-02"])
    vals = {k: v for k, v in zip(final["feats"], final["mu"])}   # every feature at the final fit's mean
    f = _fake_features(idx, vals)
    monkeypatch.setattr(PP, "pine_features", lambda df, us=True, version="current": f)
    df = pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0}, index=idx)
    q, thr = PS.quality(df, "X", PS.FINAL)
    fits = {fit["year"]: fit for fit in yearly["fits"]}
    X = f[final["feats"]].to_numpy(float)
    for i, y in enumerate((2019, 2020)):
        fit = fits[y]
        s = fit["b"] + ((X[i] - np.asarray(fit["mu"])) / np.asarray(fit["sd"])) @ np.asarray(fit["w"])
        assert q[i] == pytest.approx(1 / (1 + np.exp(-s)), abs=1e-12) and thr[i] == fit["thr"]
    assert thr[0] != thr[1]


def test_too_little_history_gives_no_signal():
    # 150 rising bars: the SMA200 trend filter is still na, so no breakout candidate can exist
    c = 100 * np.exp(np.cumsum(np.full(150, 0.004)))
    o, h, lo = c * 0.999, c * 1.002, c * 0.997
    entry_ok, _ = PS.signals(o, h, lo, c, {**PS.DEFAULT}, np.ones(150, bool))
    assert not entry_ok.any()


def test_indicator_and_independent_runs_share_no_state():
    """f_machine is called twice in the Pine file (OOS and in-sample quality). In Pine every call site keeps its own
    `var` state; the Python emulation mirrors that by being a pure function: a run is the same whether or not another
    run with other entries happened before it."""
    rows = [FLAT, (100, 101, 99.5, 100.5), (100.5, 102, 100, 101.5), (101.5, 101.6, 96.5, 97), FLAT, FLAT]
    df, e, x, a = make(rows)
    o, h, lo, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    first = PS.machine(df.index, o, h, lo, c, a, e, x, CFG)["trades"]
    PS.machine(df.index, o, h, lo, c, a, ~e, x, CFG)
    again = PS.machine(df.index, o, h, lo, c, a, e, x, CFG)["trades"]
    assert first == again


def test_benchmark_rows_match_a_hand_calculation():
    rows = [FLAT, (100, 101, 99.5, 100.5), (100.5, 102, 100, 101.5), (101.5, 102.5, 101, 102), (102, 102, 100.5, 101),
            (101, 101.5, 100, 100.5), (100.5, 101, 100, 100.5), (100.5, 103, 100.5, 102.5)]
    df, e, x, a = make(rows, entries=(0, 6), exits=(4,))
    o, h, lo, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    m = PS.machine(df.index, o, h, lo, c, a, e, x, CFG)
    spy = np.linspace(400, 420, len(c))
    b = PS.bench(df.index, c, spy, m, "2000-01-01")
    assert b["system"] == pytest.approx(net(100, 101), abs=1e-12)          # one closed trade
    assert b["bh"] == pytest.approx(102.5 / 100 - 1) and b["spy"] == pytest.approx(420 / 400 - 1)
    # closed trade: fill bar 1 .. exit bar 5 = 4 bars; open trade: fill bar 7 = last bar -> 0 bars; window 8 bars
    assert b["exposure"] == pytest.approx(4 / 8)


# ------------------------------------------------------------------ real-data checks (skipped without the cache)
def _cached(*tickers):
    import os

    from indicator_lab import data
    return all(os.path.exists(os.path.join(data.CACHE_DIR, f"{t}.csv")) for t in tickers)


@pytest.mark.skipif(not _cached("ASML.AS", "SPY"), reason="no cached market data")
def test_spy_holiday_on_a_non_us_chart_uses_the_previous_spy_day():
    """P3: on a Euronext date without a SPY bar (US holiday) v4.1 uses SPY's last close before that date; v4 used the
    one before it (two SPY days old). On normal dates both use the previous SPY day."""
    from indicator_lab import pine_parity as PP
    from indicator_lab.evaluate import get
    df, spy = get("ASML.AS"), get("SPY")
    sc = spy["close"]
    roc = sc / sc.shift(63) - 1
    f4 = PP.pine_features(df, us=False, version="fixed")
    f41 = PP.pine_features(df, us=False, version="v41")
    hol = [d for d in df.index if d not in spy.index and d > spy.index[300]]
    assert len(hol) >= 50
    for d in hol[-10:]:
        prev = spy.index[spy.index < d]
        assert f41.at[d, "spy_roc63"] == pytest.approx(roc[prev[-1]], abs=1e-12)
        assert f4.at[d, "spy_roc63"] == pytest.approx(roc[prev[-2]], abs=1e-12)
    normal = [d for d in df.index[-300:] if d in spy.index]
    assert np.allclose(f41.loc[normal, "spy_roc63"], f4.loc[normal, "spy_roc63"], equal_nan=True)


@pytest.mark.skipif(not _cached("AAPL", "SPY", "^VIX"), reason="no cached market data")
def test_tradingview_export_round_trip(tmp_path):
    """compare_tv on a CSV built like a TradingView export from the Python emulation itself must report no
    difference (checks the reader and the comparison, not TradingView)."""
    from indicator_lab import pine_parity as PP
    from indicator_lab.evaluate import get
    df = get("AAPL").iloc[-1500:]
    f = PP.pine_features(df, us=True, version="v41")
    r = PS.run(df, "AAPL", PS.V41)
    _, q_raw = PP.score(f, json.load(open(PP.MODEL)))   # noqa: SIM115
    exp = pd.DataFrame({"time": (df.index - pd.Timestamp("1970-01-01")) // pd.Timedelta("1s"), "open": df["open"].values, "high": df["high"].values,
                        "low": df["low"].values, "close": df["close"].values, "Volume": df["volume"].values,
                        "Breakout quality (0-1)": q_raw.values,
                        "Status (1 BUY, -1 SELL, 2 long, 0 flat)": np.where(r["buy"], 1, np.where(r["sell"], -1, 0))})
    for k, v in PP.TV_FEATS.items():
        exp[k] = f[v].values
    p = tmp_path / "tv.csv"
    exp.to_csv(p, index=False)
    out = PP.compare_tv(str(p), us=True, version="v41")
    assert max(out["feature_max_z"].values()) < 1e-9 and out["quality_max"] < 1e-9
    assert out["buy_mismatch"] == [] and out["sell_mismatch"] == []
