from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from indicators.momentum import macd, rsi, rsi_bearish_divergence, rsi_bullish_divergence
from indicators.trend import ema, market_structure, sma, trend_alignment
from indicators.trend_strength import adx
from indicators.volatility import atr, atr_percent, bollinger_bands, bollinger_band_width, is_squeeze
from indicators.volume import accumulation_distribution, on_balance_volume, relative_volume
from price_action.candlesticks import detect_all as detect_candlesticks
from price_action.levels import Level, find_levels
from relative_strength.relative_strength import RelativeStrength, compute_relative_strength
from sector.rotation import SectorStrength


@dataclass
class TickerContext:
    """All precomputed indicators/analysis for one ticker, built once per scan and
    shared by every strategy plus the scorer — avoids recomputing the same moving
    averages, RSI, etc. seven times per ticker.
    """

    ticker: str
    history: pd.DataFrame

    sma20: pd.Series
    sma50: pd.Series
    sma100: pd.Series
    sma200: pd.Series
    ema9: pd.Series
    ema21: pd.Series
    ema50: pd.Series

    rsi14: pd.Series
    rsi7: pd.Series
    macd_line: pd.Series
    macd_signal: pd.Series
    macd_hist: pd.Series

    atr14: pd.Series
    atr_pct: pd.Series
    bb_upper: pd.Series
    bb_mid: pd.Series
    bb_lower: pd.Series
    bb_width: pd.Series
    squeeze: pd.Series

    rvol: pd.Series
    obv: pd.Series
    ad_line: pd.Series

    adx14: pd.Series
    plus_di: pd.Series
    minus_di: pd.Series

    levels: list[Level]
    structure: str
    trend: pd.Series
    candlestick_patterns: list[str]
    bullish_rsi_divergence: bool
    bearish_rsi_divergence: bool

    relative_strength: RelativeStrength | None = None
    sector_strength: SectorStrength | None = None
    market_cap: float | None = None
    sector_name: str | None = None

    @property
    def close(self) -> pd.Series:
        return self.history["close"]

    @property
    def open(self) -> pd.Series:
        return self.history["open"]

    @property
    def high(self) -> pd.Series:
        return self.history["high"]

    @property
    def low(self) -> pd.Series:
        return self.history["low"]

    @property
    def volume(self) -> pd.Series:
        return self.history["volume"]

    @property
    def last_close(self) -> float:
        return float(self.close.iloc[-1])


def build_context(
    ticker: str,
    history: pd.DataFrame,
    benchmark_close: pd.Series | None = None,
    sector_strength: SectorStrength | None = None,
    market_cap: float | None = None,
    sector_name: str | None = None,
    swing_order: int = 3,
) -> TickerContext:
    close, open_, high, low, volume = (
        history["close"], history["open"], history["high"], history["low"], history["volume"],
    )

    macd_line, macd_signal, macd_hist = macd(close)
    bb_upper, bb_mid, bb_lower = bollinger_bands(close)

    rsi14 = rsi(close, 14)
    adx14, plus_di, minus_di = adx(high, low, close, window=14)
    levels = find_levels(high, low, order=swing_order)

    relative_strength = compute_relative_strength(close, benchmark_close) if benchmark_close is not None else None

    return TickerContext(
        ticker=ticker,
        history=history,
        sma20=sma(close, 20),
        sma50=sma(close, 50),
        sma100=sma(close, 100),
        sma200=sma(close, 200),
        ema9=ema(close, 9),
        ema21=ema(close, 21),
        ema50=ema(close, 50),
        rsi14=rsi14,
        rsi7=rsi(close, 7),
        macd_line=macd_line,
        macd_signal=macd_signal,
        macd_hist=macd_hist,
        atr14=atr(high, low, close, 14),
        atr_pct=atr_percent(high, low, close, 14),
        bb_upper=bb_upper,
        bb_mid=bb_mid,
        bb_lower=bb_lower,
        bb_width=bollinger_band_width(close),
        squeeze=is_squeeze(close),
        rvol=relative_volume(volume),
        obv=on_balance_volume(close, volume),
        ad_line=accumulation_distribution(high, low, close, volume),
        adx14=adx14,
        plus_di=plus_di,
        minus_di=minus_di,
        levels=levels,
        structure=market_structure(high, low, order=swing_order),
        trend=trend_alignment(close, sma(close, 20), sma(close, 50), sma(close, 200)),
        candlestick_patterns=detect_candlesticks(open_, high, low, close),
        bullish_rsi_divergence=rsi_bullish_divergence(low, rsi14, order=swing_order),
        bearish_rsi_divergence=rsi_bearish_divergence(high, rsi14, order=swing_order),
        relative_strength=relative_strength,
        sector_strength=sector_strength,
        market_cap=market_cap,
        sector_name=sector_name,
    )
