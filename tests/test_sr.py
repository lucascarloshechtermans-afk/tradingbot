"""Support / resistance module: point in time (no look-ahead) and sane levels on a known pattern."""
import numpy as np
import pandas as pd

from indicator_lab import sr


def _walk(n=600, seed=1):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2018-01-01", periods=n)
    c = 50 * np.exp(np.cumsum(rng.normal(0, 0.02, n)))
    o = c * (1 + rng.normal(0, 0.005, n))
    h = np.maximum(o, c) * (1 + rng.uniform(0, 0.02, n))
    lo = np.minimum(o, c) * (1 - rng.uniform(0, 0.02, n))
    v = rng.uniform(1e6, 3e6, n)
    return pd.DataFrame({"open": o, "high": h, "low": lo, "close": c, "volume": v}, index=idx)


def test_point_in_time():
    df = _walk()
    full = sr.levels(df)
    for t in (300, 401, 555):
        part = sr.levels(df.iloc[:t + 1])
        a, b = full.iloc[t], part.iloc[t]
        for k in ("sup", "sup_lo", "sup_str", "res", "res_str", "res_strong", "flip", "room_pct"):
            assert (pd.isna(a[k]) and pd.isna(b[k])) or a[k] == b[k], (t, k)


def test_support_below_resistance_above():
    df = _walk()
    lv = sr.levels(df).iloc[300:]
    c = df["close"].iloc[300:]
    ok = lv["sup"].notna() & lv["res"].notna()
    assert ok.mean() > 0.95
    assert (lv.loc[ok, "sup"] <= c[ok]).all() and (lv.loc[ok, "res"] > c[ok]).all()
    assert (lv.loc[ok, "sup_lo"] <= lv.loc[ok, "sup"] + 1e-9).all()


def test_double_top_becomes_strong_resistance():
    # flat range 90-100 with repeated highs at 100: the 100 zone must be found as resistance with >= 2 touches
    n = 300
    idx = pd.bdate_range("2020-01-01", periods=n)
    base = 95 + 5 * np.sin(np.arange(n) / 6.0)
    df = pd.DataFrame({"open": base, "high": base + 0.5, "low": base - 0.5, "close": base, "volume": 1e6}, index=idx)
    lv = sr.levels(df)
    t = n - 1 - int(np.argmax(df["close"].to_numpy()[::-1] < 93))   # a bar near the bottom of the range
    assert 99 <= lv["res"].iloc[t] <= 101 or 99 <= lv["res_strong"].iloc[t] <= 101
    assert lv["res_str"].iloc[t] >= 1.0
