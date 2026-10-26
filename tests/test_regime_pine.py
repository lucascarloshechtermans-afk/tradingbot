"""Bar-by-bar emulation of indicator_lab/pine/market_regime_sma200.pine (Pine semantics: `var` state, x[k] history,
nz()) must equal the research simulation in indicator_lab/timing/regime.py, so the chart table shows what was tested."""
import os

import numpy as np
import pandas as pd
import pytest

from indicator_lab.timing import regime as R


def pine_regime(close: np.ndarray, length=200, band=0.0, cost=0.1):
    n = len(close)
    sma = pd.Series(close).rolling(length).mean().to_numpy()
    state = np.zeros(n)
    eq = np.full(n, np.nan)
    s, e = 0.0, 1.0
    for i in range(n):
        if not np.isnan(sma[i]):
            if s == 0.0 and close[i] > sma[i] * (1 + band / 100):
                s = 1.0
            elif s == 1.0 and close[i] < sma[i] * (1 - band / 100):
                s = 0.0
        state[i] = s
        if i >= 2 and not np.isnan(sma[i - 2]):                     # started = not na(sma[2])
            w_eff = state[i - 2]
            dw = abs(w_eff - (state[i - 3] if i >= 3 else 0.0))   # nz(state[3])
            e *= 1 + w_eff * (close[i] / close[i - 1] - 1) - dw * cost / 100
            eq[i] = e
    return state, eq


@pytest.mark.skipif(not os.path.exists(os.path.join(R.LONG, "SPY.csv.gz")), reason="long SPY cache not present")
@pytest.mark.parametrize("band,key", [(0.0, "T1 SMA200"), (2.0, "T2 SMA200 met 2%-band")])
def test_pine_equals_research(band, key):
    c = R.load("SPY")
    state, eq = pine_regime(c.to_numpy(), band=band)
    rf = pd.Series(0.0, index=c.index)
    w = R.weights(c, rf)[key]
    on = ~np.isnan(eq)
    if band == 0.0:   # research T1 is close > SMA (no memory); identical unless a close equals its SMA exactly
        assert (state[on] == w[on]).mean() > 0.999
    else:
        assert (state[on] == w[on]).all()
    r = R.simulate(c, rf, state).to_numpy()
    first = int(np.argmax(on))
    research = np.cumprod(1 + r[first:])
    assert np.allclose(eq[first:] / eq[first] * (1 + r[first]), research, rtol=1e-9)
