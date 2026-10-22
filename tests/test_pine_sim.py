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
    cfg = {"features": "step1", "model": "oos", "na_block": True}
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
