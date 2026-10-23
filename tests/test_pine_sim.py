"""R6: the Pine strategy (emulated under TradingView's order rules), the Pine indicator's chart statistics and the
research engine must produce the same trades."""
import os

import numpy as np
import pandas as pd
import pytest

from indicator_lab import data


@pytest.mark.parametrize("ticker", ["AAPL", "JPM"])
def test_strategy_indicator_and_engine_take_the_same_trades(ticker):
    if not all(os.path.exists(os.path.join(data.CACHE_DIR, f"{t}.csv")) for t in (ticker, "SPY")):
        pytest.skip("no cached market data (e.g. CI without network)")
    from indicator_lab import evaluate as E
    from indicator_lab import pine_sim as S
    from indicator_lab.strategies import BEST
    cfg = S.FINAL
    df = E.get(ticker)
    ind = S.run(df, ticker, cfg)["trades"]
    st = S.run_strategy(df, ticker, cfg)
    _, eng = E.run_ticker(BEST[0], BEST[1], ticker)
    eng = [x for x in eng if x["entry_date"] >= pd.Timestamp("2015-01-01")]
    key = [(x["entry_date"], x["exit_date"]) for x in ind]
    assert key == [(x["entry_date"], x["exit_date"]) for x in st]
    assert key == [(x["entry_date"], x["exit_date"]) for x in eng]
    assert len(ind) >= 20
    assert abs(np.mean([x["ret"] for x in ind]) - np.mean([x["ret"] for x in st])) < 0.001   # 0.1 %-pt
    assert abs(np.mean([x["ret"] for x in ind]) - np.mean([x["ret"] for x in eng])) < 1e-9


@pytest.mark.parametrize("ticker", ["AAPL", "JPM"])
def test_v4_regime_rule_pine_strategy_and_engine_agree(ticker):
    """swing_v4.pine / swing_v4_strategy.pine (emulated) and the swing4 Python engine take the same trades."""
    if not all(os.path.exists(os.path.join(data.CACHE_DIR, f"{t}.csv")) for t in (ticker, "SPY", "^VIX")):
        pytest.skip("no cached market data (e.g. CI without network)")
    from indicator_lab import evaluate as E
    from indicator_lab import meta
    from indicator_lab import pine_sim as S
    from indicator_lab.swing4 import core as C
    df = E.get(ticker)
    ind = S.run(df, ticker, S.V4)["trades"]
    st = S.run_strategy(df, ticker, S.V4)
    s = C.signals(ticker)
    with np.errstate(invalid="ignore"):
        entry = s["entry"] & (meta.feature_frame(df)["spy_roc63"].to_numpy() <= 0.03)
    _, eng = C.simulate(df, entry, s["exit_sig"], s["atr"])
    eng = [x for x in eng if x["entry_date"] >= pd.Timestamp("2015-01-01")]
    key = [(x["entry_date"], x["exit_date"]) for x in ind]
    assert key == [(x["entry_date"], x["exit_date"]) for x in st]
    assert key == [(x["entry_date"], x["exit_date"]) for x in eng]
    assert len(ind) >= 10


@pytest.mark.parametrize("ticker", ["AAPL", "NVDA"])
def test_trade_drawdown_same_convention_in_pine_emulation_and_research_simulator(ticker):
    """Drawdown inside a trade (peak since the fill to a later low; every bar's high assumed before its low):
    pine_sim (= the Pine table) and swing4.sim2 (research) must agree trade by trade."""
    if not all(os.path.exists(os.path.join(data.CACHE_DIR, f"{t}.csv")) for t in (ticker, "SPY", "^VIX")):
        pytest.skip("no cached market data (e.g. CI without network)")
    from indicator_lab import evaluate as E
    from indicator_lab import pine_sim as S
    from indicator_lab.swing4 import core as C
    from indicator_lab.swing4 import sim2 as S2
    df = E.get(ticker)
    ind = S.run(df, ticker, S.FINAL)["trades"]
    s = C.signals(ticker)
    _, tr = S2.simulate(S2.arrays(df, s["atr"], s["exit_sig"]), s["entry"])
    res = {(x["entry_date"], x["exit_date"]): x["dd"] for x in tr}
    common = [x for x in ind if (x["entry_date"], x["exit_date"]) in res]
    # the trade sets can differ by a borderline model call after a data refresh (adjusted prices are revised);
    # this test is about the drawdown convention, so it compares the trades both take
    assert len(common) >= 10 and len(common) >= 0.9 * len(ind)
    for x in common:
        assert abs(res[(x["entry_date"], x["exit_date"])] - x["mae"]) < 1e-12
