from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from config.schema import ScoringConfig
from indicators.momentum import roc
from market_regime.regime import MarketRegime
from strategies.base import StrategySignal
from strategies.context import TickerContext


@dataclass
class CategoryScore:
    category: str
    score: float  # 0-100, this category alone
    weight: float  # from config, in percentage points
    contribution: float  # score * weight / 100
    reasons: list[str] = field(default_factory=list)


@dataclass
class ScoreResult:
    total_score: float
    label: str
    categories: list[CategoryScore]

    @property
    def all_reasons(self) -> list[str]:
        return [r for cat in self.categories for r in cat.reasons]


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def score_trend(ctx: TickerContext) -> CategoryScore:
    """Pure trend DIRECTION and STRENGTH: MA alignment, ADX/DI, EMA stack/cross,
    VWAP. Deliberately excludes market structure (HH/HL, BOS/CHOCH) — see
    `score_market_structure` — these are kept as separate categories rather than
    folded together, since a stock can be in a clean uptrend (MAs stacked, ADX
    strong) while its short-term structure is breaking down, or vice versa, and
    collapsing them into one number hides that distinction from the scanner
    output."""
    reasons: list[str] = []
    score = 20.0  # neutral baseline

    if ctx.trend.iloc[-1] == "bullish":
        score = 55.0
        reasons.append("Above 20/50/200 SMA (bullish trend alignment)")
    elif ctx.trend.iloc[-1] == "bearish":
        score = 10.0
        reasons.append("Below 20/50/200 SMA (bearish trend alignment)")

    if ctx.adx14.iloc[-1] > 25 and ctx.plus_di.iloc[-1] > ctx.minus_di.iloc[-1]:
        score += 10
        reasons.append(f"ADX {ctx.adx14.iloc[-1]:.0f} with +DI > -DI (confirmed uptrend strength)")

    adx_slope_now = ctx.adx_slope.iloc[-1]
    if pd.notna(adx_slope_now) and adx_slope_now > 0 and ctx.adx14.iloc[-1] < 40:
        score += 5
        reasons.append("ADX rising — trend strength still building, not yet exhausted")

    ema8_now, ema21_now, ema50_now = ctx.ema8.iloc[-1], ctx.ema21.iloc[-1], ctx.ema50.iloc[-1]
    if pd.notna(ema8_now) and pd.notna(ema21_now) and pd.notna(ema50_now) and ema8_now > ema21_now > ema50_now:
        score += 5
        reasons.append("EMA 8/21/50 stacked bullishly")

    if ctx.ema8_21_cross == "bullish_cross":
        score += 5
        reasons.append("EMA8 just crossed above EMA21")
    elif ctx.ema8_21_cross == "bearish_cross":
        score -= 8
        reasons.append("EMA8 just crossed below EMA21")

    vwap_now = ctx.anchored_vwap.iloc[-1]
    if pd.notna(vwap_now) and vwap_now > 0:
        if ctx.last_close > vwap_now:
            score += 5
            reasons.append("Price above anchored VWAP")
        vwap_slope_now = ctx.vwap_slope.iloc[-1]
        if pd.notna(vwap_slope_now) and vwap_slope_now > 0:
            reasons.append("Anchored VWAP sloping up")

    return CategoryScore("trend", _clamp(score), 0, 0, reasons)


def score_market_structure(ctx: TickerContext) -> CategoryScore:
    """Market STRUCTURE: the swing-point pattern (higher highs/higher lows vs.
    lower highs/lower lows) and any break of structure / change of character —
    kept separate from `score_trend` (see its docstring) so a scanner user can
    see at a glance whether a stock's structure agrees with its moving-average
    trend or is diverging from it (an early warning `score_trend` alone can't
    give, since MAs lag price by construction)."""
    reasons: list[str] = []
    score = 30.0  # neutral baseline — no structural signal yet

    if ctx.structure == "higher_highs_higher_lows":
        score += 35
        reasons.append("Market structure: higher highs, higher lows")
    elif ctx.structure == "lower_highs_lower_lows":
        score -= 20
        reasons.append("Market structure: lower highs, lower lows")

    if ctx.structure_break == "bullish_bos":
        score += 25
        reasons.append("Break of structure: close above the last swing high, confirming the uptrend")
    elif ctx.structure_break == "bullish_choch":
        score += 20
        reasons.append("Change of character: first close above the last swing high in a weak/bearish structure")
    elif ctx.structure_break == "bearish_choch":
        score -= 25
        reasons.append("Change of character: closed below the last swing low — trend may be turning")
    elif ctx.structure_break == "bearish_bos":
        score -= 30
        reasons.append("Break of structure to the downside")

    return CategoryScore("market_structure", _clamp(score), 0, 0, reasons)


def score_momentum(ctx: TickerContext) -> CategoryScore:
    reasons: list[str] = []
    risk_notes: list[str] = []
    score = 30.0

    # RSI, MACD and 20-day ROC are all derived from the same underlying signal —
    # recent price change — so they move together far more often than not. Adding
    # a full independent bonus for each would let one real "price is going up"
    # fact get counted three times as if it were three separate pieces of
    # evidence (the "indicator redundancy" problem: correlated inputs inflating a
    # composite score without adding real information). Instead, each of the
    # three casts one vote and the combined "core momentum" bonus is capped,
    # regardless of how many of the three agree.
    core_votes = 0
    r = ctx.rsi14.iloc[-1]
    if 50 <= r <= 70:
        core_votes += 1
        reasons.append(f"RSI {r:.0f} — bullish momentum without being overbought")
    elif r > 70:
        reasons.append(f"RSI {r:.0f} — overbought, momentum extended")
    elif r < 30:
        core_votes -= 1
        reasons.append(f"RSI {r:.0f} — oversold, momentum weak")

    if ctx.macd_hist.iloc[-1] > 0:
        core_votes += 1
        reasons.append("MACD histogram positive")
        if ctx.macd_histogram_accelerating:
            reasons.append("MACD histogram accelerating (momentum building, not fading)")
    else:
        reasons.append("MACD histogram negative")

    roc20 = roc(ctx.close, 20).iloc[-1]
    if pd.notna(roc20):
        if roc20 > 0:
            core_votes += 1
            reasons.append(f"20-day ROC positive ({roc20:.1f}%)")
        elif roc20 < 0:
            core_votes -= 1

    # capped at +/-24 total regardless of vote count (was up to +55 additively
    # across RSI/MACD-hist/MACD-accel/ROC before this fix)
    score += max(-24.0, min(24.0, core_votes * 12.0))

    if ctx.macd_above_zero:
        score += 5
        reasons.append("MACD above the zero line")

    if ctx.macd_cross_state == "bullish_cross":
        score += 8
        reasons.append("MACD just crossed above its signal line")
    elif ctx.macd_cross_state == "bearish_cross":
        score -= 8
        reasons.append("MACD just crossed below its signal line")

    if ctx.bullish_rsi_divergence:
        score += 8
        reasons.append("Bullish RSI divergence")
    if ctx.bearish_rsi_divergence:
        score -= 10
        reasons.append("Bearish RSI divergence")
    if ctx.hidden_bullish_rsi_divergence:
        score += 6
        reasons.append("Hidden bullish RSI divergence (trend-continuation signal)")
    if ctx.hidden_bearish_rsi_divergence:
        score -= 6
        reasons.append("Hidden bearish RSI divergence (downtrend-continuation signal)")

    # "Is the setup already too extended?" — distance of price above its own
    # EMA21, in ATR units. A stretched move is more likely to mean-revert before
    # a swing target is reached than to run further.
    extension = ctx.extension_atr
    if pd.notna(extension):
        if extension > 4:
            score -= 15
            risk_notes.append(f"Price is {extension:.1f} ATRs above EMA21 — already extended, chase risk")
        elif extension > 2.5:
            score -= 5
            risk_notes.append(f"Price is {extension:.1f} ATRs above EMA21 — somewhat extended")

    # Broader than the single EMA21 check above: agreement across MULTIPLE
    # independent references (EMA8/21/50, VWAP, recent swing low) is a much
    # stronger overextension signal than any one distance alone — a stock can
    # look calm relative to EMA21 while still being wildly stretched from its
    # most recent swing low. Only penalized further when several agree.
    overext = ctx.overextension
    if overext is not None and overext.is_severely_overextended:
        score -= 15
        risk_notes.append(
            f"Overextended from {overext.stretched_reference_count} independent references at once "
            "— a fresh entry here chases a stretched price rather than a fresh setup"
        )

    cat = CategoryScore("momentum", _clamp(score), 0, 0, reasons)
    cat.reasons.extend(risk_notes)
    return cat


def score_volume(ctx: TickerContext) -> CategoryScore:
    reasons: list[str] = []
    score = 40.0

    rvol = ctx.rvol.iloc[-1]
    if pd.notna(rvol):
        if rvol >= 1.5:
            score += 25
            reasons.append(f"Relative volume {rvol:.1f}x — strong participation")
        elif rvol >= 1.0:
            score += 8
            reasons.append(f"Relative volume {rvol:.1f}x — average participation")
        else:
            score -= 10
            reasons.append(f"Relative volume {rvol:.1f}x — below average")

    # OBV and the A/D line are both cumulative volume-flow measures built from the
    # same daily price/volume bars, so they usually agree — sum their bonuses
    # independently and "two confirmations" is really one fact double-counted.
    # Cap the combined contribution the same way score_momentum caps its votes.
    flow_votes = 0
    if len(ctx.obv) > 10:
        obv_rising = ctx.obv.iloc[-1] > ctx.obv.iloc[-10]
        if obv_rising:
            flow_votes += 1
            reasons.append("OBV trending up (accumulation)")
        else:
            flow_votes -= 1
            reasons.append("OBV trending down (distribution)")

    if len(ctx.ad_line) > 10:
        ad_rising = ctx.ad_line.iloc[-1] > ctx.ad_line.iloc[-10]
        if ad_rising:
            flow_votes += 1
            reasons.append("Accumulation/Distribution line rising")
        else:
            flow_votes -= 1

    score += max(-12.0, min(12.0, flow_votes * 6.0))

    if ctx.obv_bullish_divergence:
        score += 10
        reasons.append("Bullish OBV divergence (volume strengthening while price dipped)")
    if ctx.obv_bearish_divergence:
        score -= 10
        reasons.append("Bearish OBV divergence (volume weakening while price rose)")

    return CategoryScore("volume", _clamp(score), 0, 0, reasons)


def score_price_action(ctx: TickerContext, matched_strategies: list[StrategySignal]) -> CategoryScore:
    from strategies import best_tradeable_signal

    reasons: list[str] = []
    matched = [s for s in matched_strategies if s.matched]
    best = best_tradeable_signal(matched_strategies)

    if best is None:
        score = 20.0
        reasons.append("No specific tradeable price-action setup confirmed")
    else:
        score = best.confidence
        reasons.append(f"{best.strategy} setup confirmed")
        reasons.extend(best.reasons[:3])

        other_matched = [s for s in matched if s.strategy != best.strategy]
        if other_matched:
            score += min(len(other_matched) * 8, 20)
            other_names = ", ".join(s.strategy for s in other_matched)
            reasons.append(f"Additional confirming setups: {other_names}")

    supportive_candles = {"bullish_engulfing", "hammer", "morning_star"}
    present_candles = supportive_candles & set(ctx.candlestick_patterns)
    if present_candles:
        score += 8
        reasons.append(f"Supporting candlestick pattern: {', '.join(present_candles)}")

    if ctx.liquidity_sweep == "bullish_sweep":
        score += 10
        reasons.append("Bullish liquidity sweep: support was pierced then reclaimed on the same bar")
    elif ctx.liquidity_sweep == "bearish_sweep":
        score -= 10
        reasons.append("Bearish liquidity sweep: resistance was pierced then rejected")

    if ctx.confluence_count >= 2:
        score += 10
        reasons.append(f"Price sits at a confluence zone: {', '.join(ctx.confluence_sources)}")

    if ctx.gap_classification:
        if "breakaway" in ctx.gap_classification and "up" in ctx.gap_classification:
            score += 8
            reasons.append("Breakaway gap up from a consolidation")
        elif "exhaustion" in ctx.gap_classification and "up" in ctx.gap_classification:
            score -= 8
            reasons.append("Gap up after an already-extended move — possible exhaustion gap")

    return CategoryScore("price_action", _clamp(score), 0, 0, reasons)


def score_volatility(ctx: TickerContext) -> CategoryScore:
    reasons: list[str] = []
    atr_pct = ctx.atr_pct.iloc[-1]

    if pd.isna(atr_pct):
        return CategoryScore("volatility", 40.0, 0, 0, ["Insufficient history for ATR%"])

    if 1.5 <= atr_pct <= 6.0:
        score = 65.0
        reasons.append(f"ATR {atr_pct:.1f}% of price — healthy range for a multi-day swing")
    elif atr_pct < 1.5:
        score = 40.0
        reasons.append(f"ATR {atr_pct:.1f}% of price — quiet, limited swing potential")
    else:
        score = 35.0
        reasons.append(f"ATR {atr_pct:.1f}% of price — high volatility, wider stops needed")

    is_squeezing = bool(ctx.squeeze.iloc[-1]) if pd.notna(ctx.squeeze.iloc[-1]) else False
    if is_squeezing:
        if ctx.bb_expanding:
            score += 20
            reasons.append("Squeeze already expanding — the move may be starting now, not just possible later")
        else:
            score += 10
            reasons.append("Volatility squeeze — potential energy building for a move")

    return CategoryScore("volatility", _clamp(score), 0, 0, reasons)


def score_relative_strength(ctx: TickerContext, rs_percentile: float | None = None) -> CategoryScore:
    if ctx.relative_strength is None:
        return CategoryScore("relative_strength", 40.0, 0, 0, ["No benchmark data supplied"])

    reasons: list[str] = []
    rel_1m = ctx.relative_strength.relative.get("1M", float("nan"))
    rel_3m = ctx.relative_strength.relative.get("3M", float("nan"))
    score = 40.0

    if pd.notna(rel_1m):
        if rel_1m > 0:
            score += 30
            reasons.append(f"Outperforming benchmark over 1M ({rel_1m:+.1f}%)")
        else:
            score -= 15
            reasons.append(f"Underperforming benchmark over 1M ({rel_1m:+.1f}%)")

    if pd.notna(rel_3m) and rel_3m > 0:
        score += 20
        reasons.append(f"Outperforming benchmark over 3M ({rel_3m:+.1f}%)")

    # Outperformance that's ALSO low-correlation to the broad market is a
    # stronger "genuine strength" signal than outperformance during a rally
    # everything is having — the latter could just be beta, not the stock
    # standing out on its own. Only rewarded alongside real outperformance
    # above, never as a bonus for low correlation by itself (being
    # uncorrelated says nothing about direction).
    corr = ctx.correlation
    if corr is not None and corr.is_idiosyncratic and pd.notna(rel_1m) and rel_1m > 0:
        score += 10
        reasons.append("Outperformance looks idiosyncratic (low correlation to SPY/QQQ/sector), not just riding the market")

    # The RS-vs-universe percentile already gates entry (GatesConfig.
    # min_rs_percentile) as a pass/fail check, but doesn't otherwise
    # differentiate a ticker that BARELY cleared the gate from one leading the
    # whole scanned universe -- Minervini's own guidance is to prefer RS
    # "80s/90s", not just "above the minimum." New, unvalidated.
    if rs_percentile is not None:
        if rs_percentile >= 90:
            score += 20
            reasons.append(f"RS percentile {rs_percentile:.0f} — top decile vs. scanned universe")
        elif rs_percentile >= 80:
            score += 10
            reasons.append(f"RS percentile {rs_percentile:.0f} — top quintile vs. scanned universe")

    return CategoryScore("relative_strength", _clamp(score), 0, 0, reasons)


def score_market_regime(regime: MarketRegime | None) -> CategoryScore:
    if regime is None:
        return CategoryScore("market_regime", 50.0, 0, 0, ["No market regime data supplied"])

    mapping = {"BULLISH": 90.0, "NEUTRAL": 55.0, "BEARISH": 20.0, "HIGH_VOLATILITY": 25.0}
    score = mapping.get(regime.label, 50.0)
    reasons = [f"Market regime: {regime.label} (score {regime.score:+.0f})"]
    return CategoryScore("market_regime", score, 0, 0, reasons)


def score_sector(ctx: TickerContext) -> CategoryScore:
    if ctx.sector_strength is None:
        return CategoryScore("sector", 50.0, 0, 0, ["No sector data supplied"])

    reasons: list[str] = []
    s = ctx.sector_strength
    if s.rank <= 3:
        score = 85.0
        reasons.append(f"{s.etf} ranked #{s.rank} of 11 sectors by relative strength")
    elif s.rank <= 6:
        score = 60.0
        reasons.append(f"{s.etf} ranked #{s.rank} of 11 sectors (mid-pack)")
    else:
        score = 30.0
        reasons.append(f"{s.etf} ranked #{s.rank} of 11 sectors (weak)")

    if s.trend == "improving":
        score += 10
        reasons.append("Sector relative strength improving")
    elif s.trend == "deteriorating":
        score -= 10
        reasons.append("Sector relative strength deteriorating")

    return CategoryScore("sector", _clamp(score), 0, 0, reasons)


def score_risk_reward(risk_reward_ratio: float | None, distance_to_resistance_atr: float | None = None) -> CategoryScore:
    if risk_reward_ratio is None:
        return CategoryScore("risk_reward", 40.0, 0, 0, ["No risk/reward computed"])

    score = _clamp(risk_reward_ratio / 3.0 * 100.0)
    reasons = [f"Risk/reward ratio {risk_reward_ratio:.1f}:1"]

    if distance_to_resistance_atr is not None:
        if distance_to_resistance_atr < 1.0:
            score -= 15
            reasons.append(f"Resistance is only {distance_to_resistance_atr:.1f} ATRs away — little room to run")
        elif distance_to_resistance_atr > 3.0:
            score += 10
            reasons.append(f"Resistance is {distance_to_resistance_atr:.1f} ATRs away — plenty of room")

    return CategoryScore("risk_reward", _clamp(score), 0, 0, reasons)


def score_multi_timeframe(mtf_score: float | None, mtf_reasons: list[str] | None) -> CategoryScore:
    if mtf_score is None:
        return CategoryScore("multi_timeframe", 40.0, 0, 0, ["No multi-timeframe data supplied"])
    return CategoryScore("multi_timeframe", _clamp(mtf_score), 0, 0, list(mtf_reasons or []))


CONFLUENCE_STRONG_THRESHOLD = 75.0
CONFLUENCE_BONUS_PER_CATEGORY = 1.5
CONFLUENCE_MAX_BONUS = 12.0


def _confluence_bonus(categories: list[CategoryScore]) -> float:
    """A pure weighted average can't distinguish a setup where ONE category
    dominates from one where MANY independent signal families (trend,
    momentum, volume, price action, ...) are all strong at once — but the
    second is a materially higher-conviction setup, which is exactly what
    "confluence" means in discretionary trading. This structural blind spot is
    why the composite score never reached 80 even once across 8958 backtested
    trades after fixing the scoring data-completeness bug (see
    backtest_screener.py's score_ticker call) — reaching 80+ on a pure average
    needs nearly every one of 11 categories near-maxed simultaneously, which
    essentially never happens by chance. Only categories the config actually
    weights (weight > 0) count, so zeroing out a category via config also
    removes it from confluence credit."""
    n_strong = sum(
        1 for cat in categories if cat.weight > 0 and cat.score >= CONFLUENCE_STRONG_THRESHOLD
    )
    return min(n_strong * CONFLUENCE_BONUS_PER_CATEGORY, CONFLUENCE_MAX_BONUS)


def score_ticker(
    ctx: TickerContext,
    config: ScoringConfig,
    matched_strategies: list[StrategySignal],
    market_regime: MarketRegime | None = None,
    risk_reward_ratio: float | None = None,
    multi_timeframe_score: float | None = None,
    multi_timeframe_reasons: list[str] | None = None,
    rs_percentile: float | None = None,
) -> ScoreResult:
    raw_categories = {
        "trend": score_trend(ctx),
        "market_structure": score_market_structure(ctx),
        "momentum": score_momentum(ctx),
        "volume": score_volume(ctx),
        "price_action": score_price_action(ctx, matched_strategies),
        "volatility": score_volatility(ctx),
        "relative_strength": score_relative_strength(ctx, rs_percentile),
        "market_regime": score_market_regime(market_regime),
        "sector": score_sector(ctx),
        "risk_reward": score_risk_reward(risk_reward_ratio, ctx.distance_to_resistance_atr),
        "multi_timeframe": score_multi_timeframe(multi_timeframe_score, multi_timeframe_reasons),
    }

    categories: list[CategoryScore] = []
    total = 0.0
    for name, cat in raw_categories.items():
        weight = config.weights.get(name, 0.0)
        contribution = cat.score * weight / 100.0
        categories.append(CategoryScore(cat.category, cat.score, weight, contribution, cat.reasons))
        total += contribution

    total = _clamp(total + _confluence_bonus(categories))

    thresholds = config.thresholds
    if total >= thresholds["exceptional"]:
        label = "Exceptional setup"
    elif total >= thresholds["strong"]:
        label = "Strong setup"
    elif total >= thresholds["interesting"]:
        label = "Interesting setup"
    elif total >= thresholds["watchlist"]:
        label = "Watchlist"
    else:
        label = "Ignore"

    return ScoreResult(total_score=round(total, 1), label=label, categories=categories)
