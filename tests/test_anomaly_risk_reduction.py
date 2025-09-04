import os
from src.trader import Trader
from config.settings import Settings
from src.trader.metrics import maybe_check_anomalies


def test_anomaly_risk_reduction_latency_and_recovery(tmp_path):
    os.environ['TRADES_DB_PATH'] = str(tmp_path / 'anomaly.db')
    t = Trader()
    base = t.risk_manager.risk_percent
    # Simulate high latency samples above threshold
    with t.metrics_lock:
        t.recent_open_latencies.extend([Settings.LATENCY_ANOMALY_MS + 200] * 5)
    # Trigger anomaly check
    maybe_check_anomalies(t)
    assert t.risk_manager.risk_percent == base * Settings.ANOMALY_RISK_MULT
    # Now simulate recovery (latency drops)
    with t.metrics_lock:
        # Recovery: replace with low latencies so ortalama dusuk olsun
        t.recent_open_latencies = [Settings.LATENCY_ANOMALY_MS * 0.5] * 10
    maybe_check_anomalies(t)
    assert t.risk_manager.risk_percent == base


def test_anomaly_risk_reduction_slippage(tmp_path):
    os.environ['TRADES_DB_PATH'] = str(tmp_path / 'anomaly2.db')
    t = Trader()
    base = t.risk_manager.risk_percent
    # Simulate slippage anomaly
    with t.metrics_lock:
        t.recent_entry_slippage_bps.extend([Settings.SLIPPAGE_ANOMALY_BPS + 10] * 4)
    maybe_check_anomalies(t)
    assert t.risk_manager.risk_percent == base * Settings.ANOMALY_RISK_MULT
    # Keep anomaly active (no recovery) ensure not multiplied again
    maybe_check_anomalies(t)
    assert t.risk_manager.risk_percent == base * Settings.ANOMALY_RISK_MULT
