import numpy as np
import pandas as pd

from analysis.index_rsi2 import buy_trigger_price, evaluate, rsi2_parts


def _df(close):
    idx = pd.bdate_range("2025-01-01", periods=len(close))
    return pd.DataFrame({"close": close}, index=idx)


def _uptrend(n=260):
    rng = np.random.default_rng(1)
    return list(100 * np.exp(np.cumsum(0.002 + rng.normal(0, 0.004, n))))


def test_buy_trigger_price_is_the_rsi2_threshold():
    c = pd.Series(_uptrend())
    _, up, dn = rsi2_parts(c)
    x = buy_trigger_price(float(c.iloc[-1]), float(up.iloc[-1]), float(dn.iloc[-1]))
    below = rsi2_parts(pd.concat([c, pd.Series([x * 0.999])], ignore_index=True))[0].iloc[-1]
    above = rsi2_parts(pd.concat([c, pd.Series([x * 1.001])], ignore_index=True))[0].iloc[-1]
    assert below < 10 <= above


def _smooth(n=260):
    return list(100 * np.exp(np.arange(n) * 0.002))  # RSI(2) = 100 throughout: never in a trade


def test_state_machine_buy_hold_sell():
    base = _smooth()
    drop = base + [base[-1] * 0.95]
    s = evaluate("SPY", _df(drop))
    assert s.state == "KOOP" and s.sell_above is not None and s.buy_below is None
    held = drop + [drop[-1] * 0.995]
    assert evaluate("SPY", _df(held)).state == "HOUDEN"
    sold = held + [base[-1] * 1.01]
    s2 = evaluate("SPY", _df(sold))
    assert s2.state == "VERKOOP"
    assert evaluate("SPY", _df(sold + [sold[-1]])).state == "GEEN"


def test_sell_above_is_the_sma5_threshold():
    base = _uptrend()
    drop = base + [base[-1] * 0.98, base[-1] * 0.96]
    s = evaluate("SPY", _df(drop))
    closes = pd.Series(drop)
    for x, want in ((s.sell_above * 1.001, True), (s.sell_above * 0.999, False)):
        nxt = pd.concat([closes, pd.Series([x])], ignore_index=True)
        assert bool(nxt.iloc[-1] > nxt.rolling(5).mean().iloc[-1]) is want


def test_no_trade_below_the_200_day():
    down = list(np.linspace(200, 100, 260)) + [95, 90]
    assert evaluate("SPY", _df(down)).state == "GEEN"
