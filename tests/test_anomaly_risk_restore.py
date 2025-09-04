import os

from config.settings import Settings
from src.trader import Trader
from src.trader.metrics import maybe_check_anomalies


def make_trader(tmp_path):
    os.environ['TRADES_DB_PATH'] = str(tmp_path / 'anomaly.db')
    t = Trader()
    # Hizli test icin esikleri dusur (latency/slippage)
    Settings.LATENCY_ANOMALY_MS = 100  # ms
    Settings.SLIPPAGE_ANOMALY_BPS = 10  # bps
    Settings.ANOMALY_RISK_MULT = 0.5
    return t


def feed_latency(self, values):
    self.recent_open_latencies.extend(values)


def feed_slippage(self, values):
    self.recent_entry_slippage_bps.extend(values)


def test_anomaly_risk_reduction_and_restore(tmp_path):
    t = make_trader(tmp_path)
    base_risk = t.risk_manager.risk_percent

    # 1) Latency anomaly tetikleme
    feed_latency(t, [200, 220, 250])  # ort > 100
    maybe_check_anomalies(t)
    assert t.risk_manager.risk_percent == base_risk * Settings.ANOMALY_RISK_MULT, 'Latency anomaly risk reduce fail'

    # 2) Latency recovery (alt banda düşür)
    t.recent_open_latencies = [50, 60, 70]  # ort ~60 < 0.8*100=80
    maybe_check_anomalies(t)
    # Henüz restore olmaz çünkü slip anomaly tetikleneceğini test edeceğiz

    # 3) Slippage anomaly bagimsiz tetikle
    feed_slippage(t, [15, 20, 18])  # ort > 10
    maybe_check_anomalies(t)
    assert t.risk_manager.risk_percent == base_risk * Settings.ANOMALY_RISK_MULT, 'Slippage anomaly risk reduce missing or overwritten'

    # 4) Slippage recovery + her iki flag false iken restore
    t.recent_entry_slippage_bps = [2, 3, 4]  # ort < 0.8*10=8
    maybe_check_anomalies(t)
    assert t.risk_manager.risk_percent == base_risk, 'Risk percent not restored after both anomalies cleared'
    # Internal flag temizlenmis olmali
    assert getattr(t, '_original_risk_percent', None) is None
