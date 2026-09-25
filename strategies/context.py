from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from indicators.momentum import (
    macd,
    macd_above_zero,
    macd_cross,
    macd_histogram_accelerating,
    rsi,
    rsi_bearish_divergence,
    rsi_bullish_divergence,
    rsi_hidden_bearish_divergence,
    rsi_hidden_bullish_divergence,
)
from indicators.trend import crossover, ema, ema_spread_pct, ma_slope, market_structure, sma, trend_alignment
from indicators.trend_strength import adx, adx_slope
from indicators.volatility import (
    atr,
    atr_percent,
    bollinger_bands,
    bollinger_band_width,
    distance_in_atr,
    is_expanding,
    is_squeeze,
)
from indicators.volume import (
    accumulation_distribution,
    is_volume_drying_up,
    obv_bearish_divergence,
    obv_bullish_divergence,
    on_balance_volume,
    relative_volume,
)
from indicators.vwap import anchored_vwap, default_vwap_anchor_index, vwap_slope
from price_action.candlesticks import detect_all as detect_candlesticks
from price_action.fibonacci import fibonacci_retracement_levels
from price_action.historical_context import HistoricalContext, compute_historical_context
from price_action.levels import Level, confluence_score, find_levels, nearest_level
from price_action.patterns import classify_gap
from price_action.structure import classify_structure_break, detect_liquidity_sweep
from relative_strength.relative_strength import RelativeStrength, compute_relative_strength
from risk.gap_risk import analyze_gap_risk
from sector.rotation import SectorStrength

FIB_LOOKBACK_BARS = 60


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
    ema8: pd.Series
    ema21: pd.Series
    ema50: pd.Series
    ema8_slope: pd.Series
    ema21_slope: pd.Series
    ema50_slope: pd.Series
    ema8_21_spread_pct: pd.Series
    ema21_50_spread_pct: pd.Series
    ema8_21_cross: str

    rsi14: pd.Series
    rsi7: pd.Series
    macd_line: pd.Series
    macd_signal: pd.Series
    macd_hist: pd.Series
    macd_cross_state: str
    macd_above_zero: bool
    macd_histogram_accelerating: bool

    atr14: pd.Series
    atr_pct: pd.Series
    bb_upper: pd.Series
    bb_mid: pd.Series
    bb_lower: pd.Series
    bb_width: pd.Series
    squeeze: pd.Series
    bb_expanding: bool

    rvol: pd.Series
    obv: pd.Series
    ad_line: pd.Series
    volume_drying_up: bool

    adx14: pd.Series
    plus_di: pd.Series
    minus_di: pd.Series
    adx_slope: pd.Series

    levels: list[Level]
    structure: str
    structure_break: str  # 'bullish_bos' | 'bearish_bos' | 'bullish_choch' | 'bearish_choch' | 'none'
    liquidity_sweep: str | None  # 'bullish_sweep' | 'bearish_sweep' | None
    trend: pd.Series
    candlestick_patterns: list[str]
    bullish_rsi_divergence: bool
    bearish_rsi_divergence: bool
    hidden_bullish_rsi_divergence: bool
    hidden_bearish_rsi_divergence: bool
    obv_bullish_divergence: bool
    obv_bearish_divergence: bool

    anchored_vwap: pd.Series
    vwap_slope: pd.Series

    extension_atr: float  # distance of price above/below EMA21, in ATRs — how "stretched" the move already is
    distance_to_resistance_atr: float | None
    confluence_count: int
    confluence_sources: list[str] = field(default_factory=list)
    gap_classification: str | None = None

    relative_strength: RelativeStrength | None = None
    sector_strength: SectorStrength | None = None
    market_cap: float | None = None
    sector_name: str | None = None
    shares_outstanding: float | None = None
    float_shares: float | None = None
    short_percent_of_float: float | None = None  # point-in-time snapshot only, no historical series available

    avg_gap_pct: float | None = None
    avg_abs_gap_pct: float | None = None
    large_gap_frequency_pct: float | None = None
    up_gap_bias: float | None = None

    historical_context: HistoricalContext | None = None

    @property
    def free_float_pct(self) -> float | None:
        if self.float_shares is None or self.shares_outstanding is None or self.shares_outstanding <= 0:
            return None
        return self.float_shares / self.shares_outstanding * 100

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
    shares_outstanding: float | None = None,
    float_shares: float | None = None,
    short_percent_of_float: float | None = None,
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

    ema8 = ema(close, 8)
    ema21 = ema(close, 21)
    ema50 = ema(close, 50)
    atr14 = atr(high, low, close, 14)
    last_atr = atr14.iloc[-1] if len(atr14) else float("nan")

    obv = on_balance_volume(close, volume)

    sma50 = sma(close, 50)
    sma200 = sma(close, 200)

    structure = market_structure(high, low, order=swing_order)
    last_close = float(close.iloc[-1])

    resistance = nearest_level(levels, last_close, kind="resistance")
    distance_to_resistance = (
        distance_in_atr(resistance.price, last_close, last_atr) if resistance is not None else None
    )
    if distance_to_resistance is not None and distance_to_resistance != distance_to_resistance:  # NaN
        distance_to_resistance = None

    extension = distance_in_atr(last_close, ema21.iloc[-1], last_atr) if len(ema21) else float("nan")

    anchor_index = default_vwap_anchor_index(low, order=swing_order)
    vwap_series = anchored_vwap(high, low, close, volume, anchor_index)

    fib_window_high = high.tail(FIB_LOOKBACK_BARS).max()
    fib_window_low = low.tail(FIB_LOOKBACK_BARS).min()
    fib_levels = (
        fibonacci_retracement_levels(fib_window_high, fib_window_low)
        if pd.notna(fib_window_high) and pd.notna(fib_window_low) and fib_window_high > fib_window_low
        else None
    )
    last_vwap = vwap_series.iloc[-1] if len(vwap_series) else float("nan")
    confluence_count, confluence_sources = confluence_score(
        last_close, levels, vwap_value=last_vwap if pd.notna(last_vwap) else None, fib_levels=fib_levels,
    )

    relative_strength = compute_relative_strength(close, benchmark_close) if benchmark_close is not None else None
    gap_risk = analyze_gap_risk(history)
    historical_context = compute_historical_context(close, last_close, levels)

    return TickerContext(
        ticker=ticker,
        history=history,
        sma20=sma(close, 20),
        sma50=sma50,
        sma100=sma(close, 100),
        sma200=sma200,
        ema8=ema8,
        ema21=ema21,
        ema50=ema50,
        ema8_slope=ma_slope(ema8, lookback=5),
        ema21_slope=ma_slope(ema21, lookback=5),
        ema50_slope=ma_slope(ema50, lookback=5),
        ema8_21_spread_pct=ema_spread_pct(ema8, ema21),
        ema21_50_spread_pct=ema_spread_pct(ema21, ema50),
        ema8_21_cross=crossover(ema8, ema21),
        rsi14=rsi14,
        rsi7=rsi(close, 7),
        macd_line=macd_line,
        macd_signal=macd_signal,
        macd_hist=macd_hist,
        macd_cross_state=macd_cross(macd_line, macd_signal),
        macd_above_zero=macd_above_zero(macd_line),
        macd_histogram_accelerating=macd_histogram_accelerating(macd_hist),
        atr14=atr14,
        atr_pct=atr_percent(high, low, close, 14),
        bb_upper=bb_upper,
        bb_mid=bb_mid,
        bb_lower=bb_lower,
        bb_width=bollinger_band_width(close),
        squeeze=is_squeeze(close),
        bb_expanding=bool(is_expanding(close).iloc[-1]) if len(close) else False,
        rvol=relative_volume(volume),
        obv=obv,
        ad_line=accumulation_distribution(high, low, close, volume),
        volume_drying_up=is_volume_drying_up(volume),
        adx14=adx14,
        plus_di=plus_di,
        minus_di=minus_di,
        adx_slope=adx_slope(adx14),
        levels=levels,
        structure=structure,
        structure_break=classify_structure_break(high, low, close, order=swing_order),
        liquidity_sweep=detect_liquidity_sweep(high, low, close, levels),
        trend=trend_alignment(close, sma(close, 20), sma50, sma200),
        candlestick_patterns=detect_candlesticks(open_, high, low, close),
        bullish_rsi_divergence=rsi_bullish_divergence(low, rsi14, order=swing_order),
        bearish_rsi_divergence=rsi_bearish_divergence(high, rsi14, order=swing_order),
        hidden_bullish_rsi_divergence=rsi_hidden_bullish_divergence(low, rsi14, order=swing_order),
        hidden_bearish_rsi_divergence=rsi_hidden_bearish_divergence(high, rsi14, order=swing_order),
        obv_bullish_divergence=obv_bullish_divergence(low, obv, order=swing_order),
        obv_bearish_divergence=obv_bearish_divergence(high, obv, order=swing_order),
        anchored_vwap=vwap_series,
        vwap_slope=vwap_slope(vwap_series),
        extension_atr=extension,
        distance_to_resistance_atr=distance_to_resistance,
        confluence_count=confluence_count,
        confluence_sources=confluence_sources,
        gap_classification=classify_gap(open_, high, low, close, sma50, last_atr),
        relative_strength=relative_strength,
        sector_strength=sector_strength,
        market_cap=market_cap,
        sector_name=sector_name,
        shares_outstanding=shares_outstanding,
        float_shares=float_shares,
        short_percent_of_float=short_percent_of_float,
        avg_gap_pct=gap_risk.avg_gap_pct,
        avg_abs_gap_pct=gap_risk.avg_abs_gap_pct,
        large_gap_frequency_pct=gap_risk.large_gap_frequency_pct,
        up_gap_bias=gap_risk.up_gap_bias,
        historical_context=historical_context,
    )
