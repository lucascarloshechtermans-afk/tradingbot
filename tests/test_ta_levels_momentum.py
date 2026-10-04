import numpy as np

from ta.core import compute_indicators
from ta.levels import find_zones
from ta.momentum import assess_momentum, find_divergences
from ta.structure import structure_events
from ta.swings import find_swings
from tests.ta_helpers import frame, zigzag


def _zones(closes):
    df = frame(closes)
    ind = compute_indicators(df)
    ev, _ = structure_events(df, find_swings(df, 3))
    return df, find_zones(df, ind["atr"], ev, ind["rvol"])


def test_repeated_bounces_make_a_strong_support_zone():
    # price keeps returning to ~100 and bouncing 10 points
    closes = zigzag(110, [-10, 10, -10, 10, -10, 10, -10, 10, -10, 12], 8) + [121] * 3
    df, zones = _zones(closes)
    z = min(zones, key=lambda z: abs(z.mid - 100))
    assert z.low <= 100.5 and z.high >= 98.5
    assert z.support_reactions >= 3 and z.role == "support"
    assert z.strength == "strong" and z.score >= 60


def test_broken_resistance_turns_support():
    # rejected twice at 110, breaks out, comes back to 110 and holds
    closes = zigzag(100, [10, -8, 8, -8, 8, 12, -9, 12], 8)
    df, zones = _zones(closes)
    z = next(z for z in zones if z.low <= 111.1 <= z.high)
    assert z.role == "flip_support", [(x.low, x.high, x.role, x.resistance_reactions) for x in zones]


def test_regular_bullish_divergence_on_confirmed_swings():
    # deep drop, bounce, then a slow drift to a slightly lower low: RSI makes a higher low
    closes = list(np.linspace(150, 100, 25)) + list(np.linspace(100, 115, 10)) + list(np.linspace(115, 98, 30)) + \
        list(np.linspace(98, 108, 8))
    df = frame(closes, spread=0.002)
    ind = compute_indicators(df)
    sw = find_swings(df, 3)
    divs = find_divergences(ind, sw, len(df) - 1)
    assert any(d.kind == "regular_bull" and d.oscillator == "rsi14" for d in divs)
    # the same frame cut before the second low is confirmed has no such divergence
    low_i = int(np.argmin(closes[40:])) + 40
    cut = low_i + 2
    sw_cut = find_swings(df.iloc[:cut + 1], 3)
    assert not any(d.kind == "regular_bull" for d in find_divergences(compute_indicators(df.iloc[:cut + 1]), sw_cut, cut))


def test_overbought_in_uptrend_is_not_called_bearish():
    closes = list(np.linspace(100, 200, 120))
    df = frame(closes, spread=0.002)
    ind = compute_indicators(df)
    m = assess_momentum(ind, find_swings(df, 3), len(df) - 1, trend_direction=1)
    assert m.state in ("bullish", "strong_bullish")
    assert any("geen verkoopsignaal" in n for n in m.notes)
