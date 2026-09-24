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
    reasons: list[str] = []
    score = 20.0  # neutral baseline

    if ctx.trend.iloc[-1] == "bullish":
        score = 60.0
        reasons.append("Above 20/50/200 SMA (bullish trend alignment)")
    elif ctx.trend.iloc[-1] == "bearish":
        score = 10.0
        reasons.append("Below 20/50/200 SMA (bearish trend alignment)")

    if ctx.structure == "higher_highs_higher_lows":
        score += 25
        reasons.append("Market structure: higher highs, higher lows")
    elif ctx.structure == "lower_highs_lower_lows":
        score -= 15
        reasons.append("Market structure: lower highs, lower lows")

    if ctx.adx14.iloc[-1] > 25 and ctx.plus_di.iloc[-1] > ctx.minus_di.iloc[-1]:
        score += 15
        reasons.append(f"ADX {ctx.adx14.iloc[-1]:.0f} with +DI > -DI (confirmed uptrend strength)")

    return CategoryScore("trend", _clamp(score), 0, 0, reasons)


def score_momentum(ctx: TickerContext) -> CategoryScore:
    reasons: list[str] = []
    score = 30.0

    r = ctx.rsi14.iloc[-1]
    if 50 <= r <= 70:
        score += 25
        reasons.append(f"RSI {r:.0f} — bullish momentum without being overbought")
    elif r > 70:
        score += 10
        reasons.append(f"RSI {r:.0f} — overbought, momentum extended")
    elif r < 30:
        score -= 10
        reasons.append(f"RSI {r:.0f} — oversold, momentum weak")

    if ctx.macd_hist.iloc[-1] > 0:
        score += 20
        reasons.append("MACD histogram positive")
        if len(ctx.macd_hist) > 3 and ctx.macd_hist.iloc[-1] > ctx.macd_hist.iloc[-3]:
            score += 10
            reasons.append("MACD histogram expanding")
    else:
        reasons.append("MACD histogram negative")

    roc20 = roc(ctx.close, 20).iloc[-1]
    if pd.notna(roc20) and roc20 > 0:
        score += 10
        reasons.append(f"20-day ROC positive ({roc20:.1f}%)")

    if ctx.bullish_rsi_divergence:
        score += 10
        reasons.append("Bullish RSI divergence")
    if ctx.bearish_rsi_divergence:
        score -= 10
        reasons.append("Bearish RSI divergence")

    return CategoryScore("momentum", _clamp(score), 0, 0, reasons)


def score_volume(ctx: TickerContext) -> CategoryScore:
    reasons: list[str] = []
    score = 40.0

    rvol = ctx.rvol.iloc[-1]
    if pd.notna(rvol):
        if rvol >= 1.5:
            score += 30
            reasons.append(f"Relative volume {rvol:.1f}x — strong participation")
        elif rvol >= 1.0:
            score += 10
            reasons.append(f"Relative volume {rvol:.1f}x — average participation")
        else:
            score -= 10
            reasons.append(f"Relative volume {rvol:.1f}x — below average")

    if len(ctx.obv) > 10:
        obv_rising = ctx.obv.iloc[-1] > ctx.obv.iloc[-10]
        if obv_rising:
            score += 15
            reasons.append("OBV trending up (accumulation)")
        else:
            reasons.append("OBV trending down (distribution)")

    if len(ctx.ad_line) > 10:
        ad_rising = ctx.ad_line.iloc[-1] > ctx.ad_line.iloc[-10]
        if ad_rising:
            score += 15
            reasons.append("Accumulation/Distribution line rising")

    return CategoryScore("volume", _clamp(score), 0, 0, reasons)


def score_price_action(ctx: TickerContext, matched_strategies: list[StrategySignal]) -> CategoryScore:
    reasons: list[str] = []
    matched = [s for s in matched_strategies if s.matched]

    if not matched:
        return CategoryScore("price_action", 20.0, 0, 0, ["No specific price-action setup confirmed"])

    best = max(matched, key=lambda s: s.confidence)
    score = best.confidence
    reasons.append(f"{best.strategy} setup confirmed")
    reasons.extend(best.reasons[:3])

    if len(matched) > 1:
        score += min((len(matched) - 1) * 8, 20)
        other_names = ", ".join(s.strategy for s in matched if s is not best)
        reasons.append(f"Additional confirming setups: {other_names}")

    supportive_candles = {"bullish_engulfing", "hammer", "morning_star"}
    if supportive_candles & set(ctx.candlestick_patterns):
        score += 10
        matched_candles = supportive_candles & set(ctx.candlestick_patterns)
        reasons.append(f"Supporting candlestick pattern: {', '.join(matched_candles)}")

    return CategoryScore("price_action", _clamp(score), 0, 0, reasons)


def score_volatility(ctx: TickerContext) -> CategoryScore:
    reasons: list[str] = []
    atr_pct = ctx.atr_pct.iloc[-1]

    if pd.isna(atr_pct):
        return CategoryScore("volatility", 40.0, 0, 0, ["Insufficient history for ATR%"])

    if 1.5 <= atr_pct <= 6.0:
        score = 70.0
        reasons.append(f"ATR {atr_pct:.1f}% of price — healthy range for a multi-day swing")
    elif atr_pct < 1.5:
        score = 40.0
        reasons.append(f"ATR {atr_pct:.1f}% of price — quiet, limited swing potential")
    else:
        score = 35.0
        reasons.append(f"ATR {atr_pct:.1f}% of price — high volatility, wider stops needed")

    if bool(ctx.squeeze.iloc[-1]) if pd.notna(ctx.squeeze.iloc[-1]) else False:
        score += 15
        reasons.append("Volatility squeeze — potential energy building for a move")

    return CategoryScore("volatility", _clamp(score), 0, 0, reasons)


def score_relative_strength(ctx: TickerContext) -> CategoryScore:
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


def score_risk_reward(risk_reward_ratio: float | None) -> CategoryScore:
    if risk_reward_ratio is None:
        return CategoryScore("risk_reward", 40.0, 0, 0, ["No risk/reward computed"])

    score = _clamp(risk_reward_ratio / 3.0 * 100.0)
    reasons = [f"Risk/reward ratio {risk_reward_ratio:.1f}:1"]
    return CategoryScore("risk_reward", score, 0, 0, reasons)


def score_multi_timeframe(mtf_score: float | None, mtf_reasons: list[str] | None) -> CategoryScore:
    if mtf_score is None:
        return CategoryScore("multi_timeframe", 40.0, 0, 0, ["No multi-timeframe data supplied"])
    return CategoryScore("multi_timeframe", _clamp(mtf_score), 0, 0, list(mtf_reasons or []))


def score_ticker(
    ctx: TickerContext,
    config: ScoringConfig,
    matched_strategies: list[StrategySignal],
    market_regime: MarketRegime | None = None,
    risk_reward_ratio: float | None = None,
    multi_timeframe_score: float | None = None,
    multi_timeframe_reasons: list[str] | None = None,
) -> ScoreResult:
    raw_categories = {
        "trend": score_trend(ctx),
        "momentum": score_momentum(ctx),
        "volume": score_volume(ctx),
        "price_action": score_price_action(ctx, matched_strategies),
        "volatility": score_volatility(ctx),
        "relative_strength": score_relative_strength(ctx),
        "market_regime": score_market_regime(market_regime),
        "sector": score_sector(ctx),
        "risk_reward": score_risk_reward(risk_reward_ratio),
        "multi_timeframe": score_multi_timeframe(multi_timeframe_score, multi_timeframe_reasons),
    }

    categories: list[CategoryScore] = []
    total = 0.0
    for name, cat in raw_categories.items():
        weight = config.weights.get(name, 0.0)
        contribution = cat.score * weight / 100.0
        categories.append(CategoryScore(cat.category, cat.score, weight, contribution, cat.reasons))
        total += contribution

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
