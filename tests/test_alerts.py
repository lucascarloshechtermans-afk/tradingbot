from datetime import datetime

from alerts.dispatcher import AlertDispatcher
from alerts.rules import Alert, evaluate_scan_alerts, evaluate_trade_alert
from config.schema import AlertsConfig
from events.earnings import EarningsWarning
from scoring.scorer import CategoryScore, ScoreResult
from strategies.base import StrategySignal
from tests.helpers import breakout_history, context_from


def _score_result(total=80.0, label="Strong setup"):
    return ScoreResult(total_score=total, label=label, categories=[CategoryScore("trend", 80, 15, 12, [])])


def test_breakout_alert_fires_when_strategy_matched():
    ctx = context_from(breakout_history())
    config = AlertsConfig()
    signals = [StrategySignal(strategy="Bullish Breakout", matched=True, confidence=80.0)]
    alerts = evaluate_scan_alerts("AAPL", ctx, signals, _score_result(), None, config)
    assert any(a.alert_type == "breakout" for a in alerts)


def test_volume_spike_alert_fires_on_high_rvol():
    ctx = context_from(breakout_history())  # has a volume spike on the last bar
    config = AlertsConfig()
    alerts = evaluate_scan_alerts("AAPL", ctx, [], _score_result(total=10, label="Ignore"), None, config)
    assert any(a.alert_type == "volume_spike" for a in alerts)


def test_score_threshold_alert_fires_above_threshold():
    ctx = context_from(breakout_history())
    config = AlertsConfig(score_threshold=75.0)
    alerts = evaluate_scan_alerts("AAPL", ctx, [], _score_result(total=80.0), None, config)
    assert any(a.alert_type == "score_threshold" for a in alerts)


def test_score_threshold_alert_silent_below_threshold():
    ctx = context_from(breakout_history())
    config = AlertsConfig(score_threshold=90.0, triggers={k: False for k in AlertsConfig().triggers})
    alerts = evaluate_scan_alerts("AAPL", ctx, [], _score_result(total=50.0), None, config)
    assert not any(a.alert_type == "score_threshold" for a in alerts)


def test_earnings_approaching_alert_fires_within_window():
    ctx = context_from(breakout_history())
    config = AlertsConfig()
    warning = EarningsWarning(has_upcoming_earnings=True, days_until_earnings=3, should_avoid=True, message="Earnings in 3 days")
    alerts = evaluate_scan_alerts("AAPL", ctx, [], _score_result(total=10, label="Ignore"), warning, config)
    assert any(a.alert_type == "earnings_approaching" for a in alerts)


def test_disabled_config_produces_no_alerts():
    ctx = context_from(breakout_history())
    config = AlertsConfig(enabled=False)
    alerts = evaluate_scan_alerts("AAPL", ctx, [], _score_result(total=99.0), None, config)
    assert alerts == []


def test_disabled_trigger_suppresses_that_alert_type():
    ctx = context_from(breakout_history())
    config = AlertsConfig(triggers={**AlertsConfig().triggers, "volume_spike": False})
    alerts = evaluate_scan_alerts("AAPL", ctx, [], _score_result(total=10, label="Ignore"), None, config)
    assert not any(a.alert_type == "volume_spike" for a in alerts)


def test_evaluate_trade_alert_entry_triggered():
    config = AlertsConfig()
    alert = evaluate_trade_alert("AAPL", "entry_triggered", config, detail="filled at 105.00")
    assert alert is not None
    assert alert.alert_type == "entry_triggered"
    assert "105.00" in alert.message


def test_evaluate_trade_alert_disabled_returns_none():
    config = AlertsConfig(enabled=False)
    assert evaluate_trade_alert("AAPL", "stop_hit", config) is None


def test_dispatcher_writes_and_appends_log(tmp_path):
    log_path = tmp_path / "alerts_log.json"
    dispatcher = AlertDispatcher(log_path=log_path, print_to_console=False)
    alert1 = Alert(ticker="AAPL", alert_type="breakout", message="AAPL: breakout", timestamp=datetime.now().isoformat())
    dispatcher.dispatch([alert1])
    assert log_path.exists()

    alert2 = Alert(ticker="MSFT", alert_type="volume_spike", message="MSFT: spike", timestamp=datetime.now().isoformat())
    dispatcher.dispatch([alert2])

    import json

    logged = json.loads(log_path.read_text())
    assert len(logged) == 2


def test_dispatcher_handles_empty_alerts_list(tmp_path):
    log_path = tmp_path / "alerts_log.json"
    dispatcher = AlertDispatcher(log_path=log_path, print_to_console=False)
    dispatcher.dispatch([])
    assert not log_path.exists()


def test_dispatcher_recovers_from_corrupt_log(tmp_path):
    log_path = tmp_path / "alerts_log.json"
    log_path.write_text("{not valid json")
    dispatcher = AlertDispatcher(log_path=log_path, print_to_console=False)
    alert = Alert(ticker="AAPL", alert_type="breakout", message="AAPL: breakout", timestamp=datetime.now().isoformat())
    dispatcher.dispatch([alert])
    import json

    logged = json.loads(log_path.read_text())
    assert len(logged) == 1
