import numpy as np
import pandas as pd
import pytest

from indicators.hvn_absorption import (
    absorption,
    absorption_at_hvn,
    find_hvns,
    hvn_profile,
    hvn_touch,
    volume_profile,
)


def _bars(closes, volume=1_000_000.0, spread=0.5):
    idx = pd.date_range("2024-01-01", periods=len(closes), freq="D")
    close = pd.Series(closes, index=idx, dtype=float)
    open_ = close.shift(1).fillna(close.iloc[0])
    high = pd.concat([open_, close], axis=1).max(axis=1) + spread
    low = pd.concat([open_, close], axis=1).min(axis=1) - spread
    vol = volume if isinstance(volume, pd.Series) else pd.Series(volume, index=idx)
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close, "volume": vol})


def _two_cluster_history(seed=0):
    """Price spends long, busy stretches around 100 and 120 with a quick, thin
    transit between them -> two clear high volume nodes and a low volume gap."""
    rng = np.random.default_rng(seed)
    a = 100 + rng.normal(0, 0.4, 60)
    transit = np.linspace(100, 120, 8)
    b = 120 + rng.normal(0, 0.4, 60)
    closes = np.concatenate([a, transit, b])
    vol = pd.Series(np.concatenate([np.full(60, 2e6), np.full(8, 3e5), np.full(60, 2e6)]),
                    index=pd.date_range("2024-01-01", periods=len(closes), freq="D"))
    return _bars(closes, volume=vol)


# ---------------------------------------------------------------- profile ---

def test_volume_profile_conserves_total_volume():
    df = _two_cluster_history()
    prof = volume_profile(df["high"], df["low"], df["volume"], bins=40, smoothing=0)
    assert prof.volume.sum() == pytest.approx(df["volume"].sum())


def test_zero_range_bar_goes_into_single_bin():
    idx = pd.date_range("2024-01-01", periods=2, freq="D")
    high = pd.Series([10.0, 12.0], index=idx)
    low = pd.Series([10.0, 11.0], index=idx)
    vol = pd.Series([500.0, 100.0], index=idx)
    prof = volume_profile(high, low, vol, bins=4, smoothing=0)
    assert prof.volume.sum() == pytest.approx(600.0)
    assert prof.volume[0] == pytest.approx(500.0)


def test_poc_and_value_area_sit_in_the_busy_cluster():
    df = _two_cluster_history()
    prof = volume_profile(df["high"], df["low"], df["volume"])
    assert min(abs(prof.poc - 100), abs(prof.poc - 120)) < 1.5
    assert prof.value_area_low <= prof.poc <= prof.value_area_high


# -------------------------------------------------------------------- HVN ---

def test_find_hvns_detects_both_clusters_and_not_the_gap():
    df = _two_cluster_history()
    prof = volume_profile(df["high"], df["low"], df["volume"], bins=60, smoothing=1.5)
    nodes = find_hvns(prof)
    prices = [nd.price for nd in nodes]
    assert any(abs(p - 100) < 1.5 for p in prices)
    assert any(abs(p - 120) < 1.5 for p in prices)
    assert not any(105 < p < 115 for p in prices)
    assert sum(nd.is_poc for nd in nodes) == 1
    assert max(nd.strength for nd in nodes) == pytest.approx(100.0)
    for nd in nodes:
        assert nd.zone_low <= nd.price <= nd.zone_high


def test_multi_period_merges_same_level_across_lookbacks():
    df = _two_cluster_history()
    nodes = hvn_profile(df, lookbacks=(40, 128))
    near_120 = [nd for nd in nodes if abs(nd.price - 120) < 1.5]
    assert len(near_120) == 1
    assert sorted(near_120[0].lookbacks) == [40, 128]
    # the 100 node only exists in the long window
    near_100 = [nd for nd in nodes if abs(nd.price - 100) < 1.5]
    assert near_100 and near_100[0].lookbacks == [128]
    assert near_100[0].touches > 0


def test_hvn_touch_returns_nodes_the_bar_trades_into():
    df = _two_cluster_history()
    nodes = hvn_profile(df, lookbacks=(128,))
    assert [round(n.price) for n in hvn_touch(nodes, bar_high=121.0, bar_low=119.0)] == [120]
    assert hvn_touch(nodes, bar_high=111.0, bar_low=109.0) == []


# ------------------------------------------------------------- absorption ---

def _absorption_setup(last_open, last_high, last_low, last_close, last_volume):
    df = _bars(100 + np.sin(np.arange(40) / 3), spread=1.0)
    df.iloc[-1, df.columns.get_loc("open")] = last_open
    df.iloc[-1, df.columns.get_loc("high")] = last_high
    df.iloc[-1, df.columns.get_loc("low")] = last_low
    df.iloc[-1, df.columns.get_loc("close")] = last_close
    df.iloc[-1, df.columns.get_loc("volume")] = last_volume
    return df


def test_bullish_absorption_heavy_volume_long_lower_wick_close_high():
    df = _absorption_setup(100.0, 100.6, 99.0, 100.5, 4_000_000)
    res = absorption(df).iloc[-1]
    assert res["absorption"] and res["direction"] == 1 and res["heavy"]


def test_bearish_absorption_mirror_image():
    df = _absorption_setup(100.0, 101.0, 99.4, 99.5, 2_000_000)
    res = absorption(df).iloc[-1]
    assert res["absorption"] and res["direction"] == -1 and not res["heavy"]


def test_no_absorption_without_volume():
    df = _absorption_setup(100.0, 100.6, 99.0, 100.5, 1_000_000)
    assert not absorption(df).iloc[-1]["absorption"]


def test_no_absorption_when_heavy_volume_moved_price_a_lot():
    # big wide-range trend bar: high effort AND high result -> not absorption
    df = _absorption_setup(98.0, 104.2, 97.8, 104.0, 4_000_000)
    assert not absorption(df).iloc[-1]["absorption"]


def test_delta_decides_direction_when_given():
    df = _absorption_setup(100.0, 100.6, 99.0, 100.5, 4_000_000)
    delta = pd.Series(0.0, index=df.index)
    delta.iloc[-1] = -1_500_000  # aggressive selling, yet closed near the high
    assert absorption(df, delta=delta).iloc[-1]["direction"] == 1
    delta.iloc[-1] = +1_500_000  # aggressive BUYING closing high is just strength
    assert absorption(df, delta=delta).iloc[-1]["direction"] == 0


def test_absorption_at_hvn_flags_bars_inside_a_node():
    df = _two_cluster_history()
    nodes = hvn_profile(df, lookbacks=(128,))
    out = absorption_at_hvn(df, nodes=nodes)
    assert out["at_hvn"].iloc[-1]  # last bars sit in the 120 cluster
    assert abs(out["hvn_price"].iloc[-1] - 120) < 1.5
    assert not out["at_hvn"].iloc[64]  # mid-transit, in the volume gap
