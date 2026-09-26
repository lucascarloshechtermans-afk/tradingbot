"""Pull a flat, walk-forward-safe feature vector out of a `TickerContext` for
research purposes (feature-importance / redundancy / interaction analysis) —
never used by the live scanner or the scoring engine itself, only by the
analysis scripts under `research/`.

Every value here is read from data already known as of the signal bar (the
same `history_so_far` the screener's own `signal_fn` sees) — no field here
looks past `ctx.history.index[-1]`, so a feature captured at bar i can be
correlated with the bar i+1 trade outcome without look-ahead leakage.
"""

from __future__ import annotations

import pandas as pd

from liquidity.liquidity import average_dollar_volume, corwin_schultz_spread_estimate
from strategies.context import TickerContext

REGIME_ORDINAL = {"BULLISH": 1.0, "NEUTRAL": 0.0, "HIGH_VOLATILITY": -0.5, "BEARISH": -1.0}
STRUCTURE_ORDINAL = {
    "higher_highs_higher_lows": 1.0,
    "lower_highs_lower_lows": -1.0,
}


def _last(series: pd.Series) -> float | None:
    if series is None or len(series) == 0:
        return None
    v = series.iloc[-1]
    return float(v) if pd.notna(v) else None


def _bool_to_int(v: bool | None) -> float | None:
    if v is None:
        return None
    return 1.0 if v else 0.0


def extract_features(
    ctx: TickerContext, *, rs_percentile: float | None = None, regime_label: str | None = None,
    trade_levels=None,
) -> dict[str, float | None]:
    """One row of features for the bar `ctx` was built from (the signal bar,
    i.e. `history_so_far` in backtest_screener's `signal_fn`)."""
    ema8, ema21, ema50 = _last(ctx.ema8), _last(ctx.ema21), _last(ctx.ema50)
    ema_alignment = None
    if ema8 is not None and ema21 is not None and ema50 is not None:
        ema_alignment = 1.0 if ema8 > ema21 > ema50 else (-1.0 if ema8 < ema21 < ema50 else 0.0)

    vwap = _last(ctx.anchored_vwap)
    vwap_distance_pct = None
    if vwap is not None and vwap > 0:
        vwap_distance_pct = (ctx.last_close - vwap) / vwap * 100

    plus_di, minus_di = _last(ctx.plus_di), _last(ctx.minus_di)
    di_diff = (plus_di - minus_di) if plus_di is not None and minus_di is not None else None

    obv_rising = None
    if len(ctx.obv) > 10:
        obv_rising = _bool_to_int(ctx.obv.iloc[-1] > ctx.obv.iloc[-10])
    ad_rising = None
    if len(ctx.ad_line) > 10:
        ad_rising = _bool_to_int(ctx.ad_line.iloc[-1] > ctx.ad_line.iloc[-10])

    rel = ctx.relative_strength
    rel_1m = rel.relative.get("1M") if rel is not None else None
    rel_3m = rel.relative.get("3M") if rel is not None else None
    rel_1m = float(rel_1m) if rel_1m is not None and pd.notna(rel_1m) else None
    rel_3m = float(rel_3m) if rel_3m is not None and pd.notna(rel_3m) else None

    dollar_vol = average_dollar_volume(ctx.history)
    spread_series = corwin_schultz_spread_estimate(ctx.high, ctx.low)
    spread_pct = _last(spread_series)

    sector_rank = ctx.sector_strength.rank if ctx.sector_strength is not None else None

    swing_low_mask = None
    recent_swing_low = None
    try:
        from indicators.trend import confirmed_swing_lows

        swing_low_mask = confirmed_swing_lows(ctx.low, order=3)
        if swing_low_mask.any():
            recent_swing_low = float(ctx.low[swing_low_mask].iloc[-1])
    except Exception:
        pass

    atr_value = _last(ctx.atr14)
    stop_atr = stop_structure = stop_final = target1 = target2 = None
    stop_method = None
    if trade_levels is not None:
        stop_atr = trade_levels.stop_levels.atr_stop
        stop_structure = trade_levels.stop_levels.structure_stop
        stop_final = trade_levels.stop_levels.final_stop
        stop_method = trade_levels.stop_levels.final_stop_method
        target1 = trade_levels.target1
        target2 = trade_levels.target2

    return {
        # raw price levels, kept alongside the ratio-features above so a
        # research script can reconstruct/compare ALTERNATIVE stop structures
        # (EMA21, VWAP, swing-low, ATR, structure) against what actually
        # happened, entirely offline from already-known OHLCV -- see
        # research/stop_comparison.py.
        "raw_entry_atr14": atr_value,
        "raw_ema21_price": ema21,
        "raw_vwap_price": vwap,
        "raw_swing_low_price": recent_swing_low,
        "raw_stop_atr": stop_atr,
        "raw_stop_structure": stop_structure,
        "raw_stop_final": stop_final,
        "raw_stop_method": 1.0 if stop_method == "structure" else (0.0 if stop_method == "atr" else None),
        "raw_target1": target1,
        "raw_target2": target2,
        "ema8_21_spread_pct": _last(ctx.ema8_21_spread_pct),
        "ema21_50_spread_pct": _last(ctx.ema21_50_spread_pct),
        "ema8_slope": _last(ctx.ema8_slope),
        "ema21_slope": _last(ctx.ema21_slope),
        "ema50_slope": _last(ctx.ema50_slope),
        "ema_alignment": ema_alignment,
        "rsi14": _last(ctx.rsi14),
        "rsi7": _last(ctx.rsi7),
        "rsi_bullish_divergence": _bool_to_int(ctx.bullish_rsi_divergence),
        "rsi_bearish_divergence": _bool_to_int(ctx.bearish_rsi_divergence),
        "rsi_hidden_bullish_divergence": _bool_to_int(ctx.hidden_bullish_rsi_divergence),
        "macd_hist": _last(ctx.macd_hist),
        "macd_above_zero": _bool_to_int(ctx.macd_above_zero),
        "macd_histogram_accelerating": _bool_to_int(ctx.macd_histogram_accelerating),
        "adx14": _last(ctx.adx14),
        "adx_slope": _last(ctx.adx_slope),
        "di_diff": di_diff,
        "rvol": _last(ctx.rvol),
        "obv_rising": obv_rising,
        "ad_rising": ad_rising,
        "obv_bullish_divergence": _bool_to_int(ctx.obv_bullish_divergence),
        "obv_bearish_divergence": _bool_to_int(ctx.obv_bearish_divergence),
        "vwap_distance_pct": vwap_distance_pct,
        "vwap_slope": _last(ctx.vwap_slope),
        "atr_pct": _last(ctx.atr_pct),
        "bb_width": _last(ctx.bb_width),
        "squeeze": _bool_to_int(bool(ctx.squeeze.iloc[-1])) if len(ctx.squeeze) and pd.notna(ctx.squeeze.iloc[-1]) else None,
        "bb_expanding": _bool_to_int(ctx.bb_expanding),
        "relative_strength_1m": rel_1m,
        "relative_strength_3m": rel_3m,
        "rs_percentile_vs_universe": rs_percentile,
        "is_idiosyncratic": _bool_to_int(ctx.correlation.is_idiosyncratic) if ctx.correlation is not None else None,
        "structure_ordinal": STRUCTURE_ORDINAL.get(ctx.structure, 0.0),
        "structure_break_bullish": _bool_to_int(ctx.structure_break in ("bullish_bos", "bullish_choch")),
        "structure_break_bearish": _bool_to_int(ctx.structure_break in ("bearish_bos", "bearish_choch")),
        "liquidity_sweep_bullish": _bool_to_int(ctx.liquidity_sweep == "bullish_sweep"),
        "distance_to_resistance_atr": ctx.distance_to_resistance_atr,
        "confluence_count": float(ctx.confluence_count),
        "extension_atr": ctx.extension_atr if pd.notna(ctx.extension_atr) else None,
        "stretched_reference_count": float(ctx.overextension.stretched_reference_count) if ctx.overextension is not None else None,
        "sector_rank": float(sector_rank) if sector_rank is not None else None,
        "market_regime_ordinal": REGIME_ORDINAL.get(regime_label) if regime_label else None,
        "avg_dollar_volume_millions": (dollar_vol / 1_000_000) if dollar_vol is not None else None,
        "spread_pct_estimate": spread_pct,
    }


def feature_names() -> list[str]:
    """The full set of feature keys `extract_features` can return (some may be
    None for a given bar depending on data availability)."""
    return [
        "ema8_21_spread_pct", "ema21_50_spread_pct", "ema8_slope", "ema21_slope", "ema50_slope",
        "ema_alignment", "rsi14", "rsi7", "rsi_bullish_divergence", "rsi_bearish_divergence",
        "rsi_hidden_bullish_divergence", "macd_hist", "macd_above_zero", "macd_histogram_accelerating",
        "adx14", "adx_slope", "di_diff", "rvol", "obv_rising", "ad_rising", "obv_bullish_divergence",
        "obv_bearish_divergence", "vwap_distance_pct", "vwap_slope", "atr_pct", "bb_width", "squeeze",
        "bb_expanding", "relative_strength_1m", "relative_strength_3m", "rs_percentile_vs_universe",
        "is_idiosyncratic", "structure_ordinal", "structure_break_bullish", "structure_break_bearish",
        "liquidity_sweep_bullish", "distance_to_resistance_atr", "confluence_count", "extension_atr",
        "stretched_reference_count", "sector_rank", "market_regime_ordinal", "avg_dollar_volume_millions",
        "spread_pct_estimate", "raw_entry_atr14", "raw_ema21_price", "raw_vwap_price", "raw_swing_low_price",
        "raw_stop_atr", "raw_stop_structure", "raw_stop_final", "raw_stop_method", "raw_target1", "raw_target2",
    ]
