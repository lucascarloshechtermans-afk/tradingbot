import pandas as pd

from indicator_lab import gex_levels as G


def test_walls_and_zero_gamma_on_a_synthetic_chain():
    spot = 100.0
    rows = [("call", 105, 50_000), ("call", 110, 10_000), ("call", 100, 5_000),
            ("put", 95, 60_000), ("put", 90, 10_000), ("put", 100, 5_000)]
    d = pd.DataFrame([{"kind": k, "strike": float(s), "oi": float(oi), "iv": 0.2, "t": 20 / 365} for k, s, oi in rows])
    _, cw, pw, zg, others, _ = G.levels(data=(spot, d))
    assert cw == 105 and pw == 95
    # puts below and calls above with similar size: the total GEX flips sign between the two walls
    assert 95 < zg < 105
    assert set(others) <= {90.0, 100.0, 110.0}
