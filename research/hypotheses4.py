"""Signal matrices for the pre-registered hypotheses (research/HYPOTHESES.md).
Every signal uses data through the close of day t only."""

from __future__ import annotations

import numpy as np
import pandas as pd

from research.engine2 import Panel

SECTOR_ETF = {
    "Information Technology": "XLK", "Health Care": "XLV", "Financials": "XLF", "Consumer Discretionary": "XLY",
    "Communication Services": "XLC", "Industrials": "XLI", "Consumer Staples": "XLP", "Energy": "XLE",
    "Utilities": "XLU", "Real Estate": "XLRE", "Materials": "XLB",
}


def indicators(p: Panel) -> dict[str, pd.DataFrame]:
    C, O, H, L, V, A = (p.df(x) for x in (p.c, p.o, p.h, p.l, p.v, p.atr))
    elig = p.df(p.eligible)
    mom = sum((C.shift(5) / C.shift(5 + h) - 1) for h in (63, 126, 252)) / 3
    mom_rank = mom.where(elig).rank(axis=1, pct=True) * 100
    d = C.diff()
    up = d.clip(lower=0).ewm(alpha=1 / 2, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / 2, adjust=False).mean()
    rsi2 = 100 - 100 / (1 + up / dn.replace(0, np.nan))
    ma20 = C.rolling(20).mean()
    bbw = 4 * C.rolling(20).std() / ma20
    return {
        "C": C, "O": O, "H": H, "L": L, "V": V, "A": A, "mom_rank": mom_rank,
        "sma200": C.rolling(200).mean(), "sma50": C.rolling(50).mean(), "ema21": C.ewm(span=21, adjust=False).mean(),
        "ret5_atr": (C - C.shift(5)) / A, "ret1_atr": (C - C.shift(1)) / A,
        "ibs": (C - L) / (H - L).replace(0, np.nan), "rsi2": rsi2,
        "vol20": V.rolling(20).mean().shift(1), "hi20c": C.rolling(20).max().shift(1),
        "hi252c": C.rolling(252).max().shift(1), "hi63": H.rolling(63).max(),
        "bbw_pct": bbw.shift(1).rolling(120).rank(pct=True),
    }


def signals(p: Panel, ind: dict[str, pd.DataFrame] | None = None) -> dict[str, np.ndarray]:
    I = ind or indicators(p)  # noqa: E741
    C, O, H, L, V, A = I["C"], I["O"], I["H"], I["L"], I["V"], I["A"]
    up200 = C > I["sma200"]
    mr = I["mom_rank"]
    spy = p.bench["SPY"]["close"].reindex(p.dates)
    rs_ratio = C.div(spy, axis=0)
    down = C < C.shift(1)
    down_vol10 = V.where(down, 0).rolling(10).max().shift(1)
    rng = H - L
    nr7 = rng <= rng.rolling(7).min()
    inside = (H < H.shift(1)) & (L > L.shift(1))
    month_end = pd.Series(p.dates.month, index=p.dates) != pd.Series(p.dates.month, index=p.dates).shift(-1)
    every5 = pd.Series(np.arange(len(p.dates)) % 5 == 0, index=p.dates)

    # sector leadership: stock's sector ETF in the top 3 of 1-month return
    etf_ret = pd.DataFrame({e: p.bench[e]["close"].reindex(p.dates).pct_change(21) for e in SECTOR_ETF.values() if e in p.bench})
    etf_rank = etf_ret.rank(axis=1, ascending=False)
    sec_top3 = pd.DataFrame(False, index=p.dates, columns=p.tickers)
    for col, sec in zip(p.tickers, p.sector):
        e = SECTOR_ETF.get(sec or "")
        if e in etf_rank:
            sec_top3[col] = etf_rank[e] <= 3

    S = {
        "H01 LEADER_DIP": (mr >= 80) & (I["ret5_atr"] <= -1),
        "H02 LEADER_DIP_DEEP": (mr >= 80) & (I["ret5_atr"] <= -1) & (C <= I["ema21"] - A),
        "H03 IBS_UPTREND": up200 & (I["ibs"] < 0.15),
        "H04 RSI2_UPTREND": up200 & (I["rsi2"] < 10),
        "H05 DOWN3_UPTREND": up200 & down & down.shift(1).fillna(False).astype(bool) & down.shift(2).fillna(False).astype(bool),
        "H06 GAPDOWN_REVERSAL": (O < L.shift(1) - 0.5 * A) & (C > O) & up200,
        "H07 HIGH_52W": C >= I["hi252c"],
        "H08 BREAKOUT_20D_VOL": (C >= I["hi20c"]) & (V > 1.5 * I["vol20"]),
        "H09 MOMENTUM_TOP_DECILE": (mr >= 90) & every5.to_numpy()[:, None],
        "H10 POCKET_PIVOT": (C > C.shift(1)) & (V > down_vol10) & (C > I["sma50"]),
        "H11 SQUEEZE_BREAKOUT": (I["bbw_pct"] <= 0.10) & (C > I["hi20c"]),
        "H12 NR7_INSIDE_UPTREND": nr7 & inside & (C > I["sma50"]),
        "H13 RS_LEADS_PRICE": (rs_ratio >= rs_ratio.rolling(63).max()) & (C <= I["hi63"] - A),
        "H14 SECTOR_LEADER_DIP": sec_top3 & (I["ret5_atr"] <= -1),
        "H15 CAPITULATION": (I["ret5_atr"] <= -3) & (V >= 2 * I["vol20"]),
        "H16 LEADER_PANIC_DAY": (mr >= 80) & (I["ret1_atr"] <= -2),
        "H17 TURN_OF_MONTH_LEADERS": (mr >= 80) & month_end.to_numpy()[:, None],
        "H18 GAP_UP_DRIFT": (O - C.shift(1) > 2 * A) & (V >= 3 * I["vol20"]) & ((C - L) / rng.replace(0, np.nan) >= 0.75),
        "H19 BASELINE": pd.DataFrame(every5.to_numpy()[:, None].repeat(len(p.tickers), 1), index=p.dates, columns=p.tickers),
    }
    return {k: np.asarray(v.fillna(False) if isinstance(v, pd.DataFrame) else v, dtype=bool) for k, v in S.items()}
