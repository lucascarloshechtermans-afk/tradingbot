from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import pandas as pd

from config.schema import AlertsConfig
from events.earnings import EarningsWarning
from scoring.scorer import ScoreResult
from strategies.base import StrategySignal
from strategies.context import TickerContext


@dataclass
class Alert:
    ticker: str
    alert_type: str
    message: str
    timestamp: str


def evaluate_scan_alerts(
    ticker: str,
    ctx: TickerContext,
    matched_strategies: list[StrategySignal],
    score_result: ScoreResult,
    earnings_warning: EarningsWarning | None,
    config: AlertsConfig,
    volume_spike_threshold: float = 2.0,
) -> list[Alert]:
    """Alerts derivable from a single scan snapshot (as opposed to trade-lifecycle
    alerts like entry/stop/target, which come from `evaluate_trade_alert` once a
    position is actually being tracked)."""
    if not config.enabled:
        return []

    alerts: list[Alert] = []
    ts = datetime.now(timezone.utc).isoformat()

    def add(alert_type: str, message: str) -> None:
        alerts.append(Alert(ticker=ticker, alert_type=alert_type, message=message, timestamp=ts))

    if config.triggers.get("breakout", True):
        if any(s.matched and s.strategy == "Bullish Breakout" for s in matched_strategies):
            add("breakout", f"{ticker}: breakout setup confirmed")

    if config.triggers.get("volume_spike", True):
        rvol = ctx.rvol.iloc[-1]
        if pd.notna(rvol) and rvol >= volume_spike_threshold:
            add("volume_spike", f"{ticker}: relative volume {rvol:.1f}x")

    if config.triggers.get("rsi_condition", True):
        r = ctx.rsi14.iloc[-1]
        if pd.notna(r):
            if r >= 70:
                add("rsi_condition", f"{ticker}: RSI overbought at {r:.0f}")
            elif r <= 30:
                add("rsi_condition", f"{ticker}: RSI oversold at {r:.0f}")

    if config.triggers.get("ma_cross", True) and len(ctx.close) > 1 and pd.notna(ctx.sma50.iloc[-2]):
        crossed_above = ctx.close.iloc[-2] <= ctx.sma50.iloc[-2] and ctx.close.iloc[-1] > ctx.sma50.iloc[-1]
        crossed_below = ctx.close.iloc[-2] >= ctx.sma50.iloc[-2] and ctx.close.iloc[-1] < ctx.sma50.iloc[-1]
        if crossed_above:
            add("ma_cross", f"{ticker}: price crossed above the 50-day SMA")
        elif crossed_below:
            add("ma_cross", f"{ticker}: price crossed below the 50-day SMA")

    if score_result.total_score >= config.score_threshold:
        add(
            "score_threshold",
            f"{ticker}: score {score_result.total_score:.0f} >= threshold {config.score_threshold:.0f} ({score_result.label})",
        )

    if (
        config.triggers.get("earnings_approaching", True)
        and earnings_warning is not None
        and earnings_warning.has_upcoming_earnings
        and earnings_warning.days_until_earnings is not None
        and earnings_warning.days_until_earnings <= 7
    ):
        add("earnings_approaching", f"{ticker}: earnings in {earnings_warning.days_until_earnings} days")

    return alerts


def evaluate_trade_alert(ticker: str, event: str, config: AlertsConfig, detail: str = "") -> Alert | None:
    """Trade-lifecycle alerts: `event` is one of 'entry_triggered', 'stop_hit',
    'target_hit'. Only fires if that trigger is enabled in config."""
    if not config.enabled or not config.triggers.get(event, True):
        return None
    labels = {
        "entry_triggered": "entry triggered",
        "stop_hit": "stop hit",
        "target_hit": "target hit",
    }
    label = labels.get(event, event)
    message = f"{ticker}: {label}" + (f" — {detail}" if detail else "")
    return Alert(ticker=ticker, alert_type=event, message=message, timestamp=datetime.now(timezone.utc).isoformat())
