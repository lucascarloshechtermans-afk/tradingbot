from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

DEFAULT_LIQUIDITY_WINDOW = 20
CORWIN_SCHULTZ_K = 3 - 2 * 2**0.5


def average_dollar_volume(history: pd.DataFrame, window: int = DEFAULT_LIQUIDITY_WINDOW) -> float | None:
    """Trailing average of close * volume — the standard "can I actually get in
    and out of this position" liquidity measure. `data.universe` imports this
    (rather than defining its own copy) so there is one source of truth."""
    if history is None or history.empty or len(history) < window:
        return None
    recent = history.tail(window)
    dollar_volume = (recent["close"] * recent["volume"]).mean()
    return float(dollar_volume) if pd.notna(dollar_volume) else None


def average_share_volume(history: pd.DataFrame, window: int = DEFAULT_LIQUIDITY_WINDOW) -> float | None:
    if history is None or history.empty or len(history) < window:
        return None
    value = history["volume"].tail(window).mean()
    return float(value) if pd.notna(value) else None


def corwin_schultz_spread_estimate(high: pd.Series, low: pd.Series, window: int = DEFAULT_LIQUIDITY_WINDOW) -> pd.Series:
    """Estimate the effective percentage bid-ask spread from consecutive daily
    high/low pairs, per Corwin & Schultz (2012), "A Simple Way to Estimate
    Bid-Ask Spreads from Daily High and Low Prices," The Journal of Finance,
    67(2), 719-760.

    This free data source has no tick/quote history, so a real historical
    bid-ask spread cannot be computed — this is a well-established published
    ESTIMATOR that only needs daily OHLC, not a substitute for a real quoted
    spread. Treat it as a liquidity-quality proxy (higher = less liquid, wider
    effective trading cost), not a literal number a broker would show you.

    Each day's estimate uses only that day and the day before it (never a future
    bar), so this is safe to use in a walk-forward backtest without look-ahead.
    """
    log_hl = np.log(high / low)
    beta = log_hl**2 + log_hl.shift(1) ** 2

    two_day_high = pd.concat([high, high.shift(1)], axis=1).max(axis=1)
    two_day_low = pd.concat([low, low.shift(1)], axis=1).min(axis=1)
    gamma = np.log(two_day_high / two_day_low) ** 2

    alpha = (np.sqrt(2 * beta) - np.sqrt(beta)) / CORWIN_SCHULTZ_K - np.sqrt(gamma / CORWIN_SCHULTZ_K)
    daily_spread = 2 * (np.exp(alpha) - 1) / (1 + np.exp(alpha))
    # negative two-day estimates are a known artifact of the estimator on very
    # calm days — the original paper's convention is to floor them at zero
    # rather than let them pull the rolling average negative (a spread can't be
    # negative in reality)
    daily_spread = daily_spread.clip(lower=0)

    return (daily_spread.rolling(window).mean() * 100).rename("spread_pct_estimate")


@dataclass
class LiquidityProfile:
    avg_dollar_volume: float | None
    avg_share_volume: float | None
    spread_pct_estimate: float | None
    dollar_volume_high_vol_days: float | None  # avg $ volume on the highest-ATR% days in the window
    dollar_volume_normal_days: float | None  # avg $ volume on the rest
    liquidity_holds_in_volatility: bool | None  # False = $ volume meaningfully dries up exactly when you'd need it most
    tradeable: bool
    reasons: list[str]


def evaluate_liquidity(
    history: pd.DataFrame,
    atr_pct: pd.Series,
    window: int = DEFAULT_LIQUIDITY_WINDOW,
    min_avg_dollar_volume: float = 5_000_000,
    max_spread_pct_estimate: float = 0.5,
    volatile_day_threshold_percentile: float = 0.75,
) -> LiquidityProfile:
    """The full liquidity picture for one ticker, and whether it clears the bar
    for a realistic 5-day swing trade — deliberately NOT just a volume filter:
    dollar volume alone says nothing about execution cost (a thin stock can have
    "enough" share volume at a wide spread and still be expensive to trade), so
    the spread estimate is checked as its own, separate hard condition.
    """
    reasons: list[str] = []

    dollar_vol = average_dollar_volume(history, window)
    share_vol = average_share_volume(history, window)

    spread_series = corwin_schultz_spread_estimate(history["high"], history["low"], window)
    spread_last = float(spread_series.iloc[-1]) if len(spread_series) and pd.notna(spread_series.iloc[-1]) else None

    dv_high_vol = None
    dv_normal = None
    holds_in_volatility = None
    if len(atr_pct) >= window * 2 and len(history) >= window * 2:
        recent_atr = atr_pct.tail(window * 2)
        recent_history = history.tail(window * 2)
        threshold = recent_atr.quantile(volatile_day_threshold_percentile)
        volatile_mask = recent_atr >= threshold
        dollar_vol_series = recent_history["close"] * recent_history["volume"]
        if volatile_mask.sum() >= 3 and (~volatile_mask).sum() >= 3:
            dv_high_vol = float(dollar_vol_series[volatile_mask].mean())
            dv_normal = float(dollar_vol_series[~volatile_mask].mean())
            # liquidity "holding up" means volume on volatile days isn't
            # dramatically lower than on calm days — a >40% drop is a red flag
            # that exactly when you'd most want to exit, there may not be
            # enough real interest on the other side of the trade
            holds_in_volatility = bool(dv_normal <= 0 or dv_high_vol >= dv_normal * 0.6)

    tradeable = True
    if dollar_vol is None:
        tradeable = False
        reasons.append("Insufficient history to compute average dollar volume")
    elif dollar_vol < min_avg_dollar_volume:
        tradeable = False
        reasons.append(f"Average dollar volume ${dollar_vol:,.0f} below minimum ${min_avg_dollar_volume:,.0f}")
    else:
        reasons.append(f"Average dollar volume ${dollar_vol:,.0f}")

    if spread_last is not None:
        if spread_last > max_spread_pct_estimate:
            tradeable = False
            reasons.append(
                f"Estimated spread {spread_last:.2f}% exceeds {max_spread_pct_estimate:.2f}% "
                "(Corwin-Schultz estimate — real execution cost likely too high)"
            )
        else:
            reasons.append(f"Estimated spread {spread_last:.2f}% (Corwin-Schultz estimate)")

    if holds_in_volatility is False:
        reasons.append(
            f"Liquidity thins out on volatile days (${dv_high_vol:,.0f} vs ${dv_normal:,.0f} on calm days) "
            "— exits during a fast move may see worse fills"
        )

    return LiquidityProfile(
        avg_dollar_volume=dollar_vol,
        avg_share_volume=share_vol,
        spread_pct_estimate=spread_last,
        dollar_volume_high_vol_days=dv_high_vol,
        dollar_volume_normal_days=dv_normal,
        liquidity_holds_in_volatility=holds_in_volatility,
        tradeable=tradeable,
        reasons=reasons,
    )
