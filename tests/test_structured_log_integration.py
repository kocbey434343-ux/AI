from src.trader import Trader
from src.utils.structured_log import clear_slog_events, get_slog_events
import os


def _isolate_db(tmp_path):
    os.environ['TRADES_DB_PATH'] = str(tmp_path / 'slog.db')


def test_cr0028_structured_log_core_events(monkeypatch, tmp_path):
    _isolate_db(tmp_path)
    monkeypatch.setattr('config.settings.Settings.OFFLINE_MODE', True, raising=False)
    clear_slog_events()
    t = Trader()
    t._risk_reset_date = '1900-01-01'
    t._maybe_daily_risk_reset()
    monkeypatch.setattr(t.api, 'get_open_orders', lambda: [])
    monkeypatch.setattr(t.api, 'get_positions', lambda: [])
    t._reconcile_open_orders()
    events = {e['event'] for e in get_slog_events()}
    assert 'daily_risk_reset' in events
    assert 'reconciliation' in events


def test_cr0028_structured_log_trade_lifecycle(monkeypatch, tmp_path):
    _isolate_db(tmp_path)
    monkeypatch.setattr('config.settings.Settings.OFFLINE_MODE', True, raising=False)
    clear_slog_events()
    t = Trader()
    t.risk_manager.max_positions = 100  # guard engelini kaldır

    def _quantize(_s, q, p):
        return q, p

    def _place_order_entry(*_, **kwargs):
        quantity = kwargs.get('quantity')
        return {'price': 100.0, 'fills': [{'price': 100.0, 'qty': quantity}], 'orderId': 11}

    def _place_order_exit(*_, **kwargs):
        quantity = kwargs.get('quantity')
        return {'price': 102.0, 'fills': [{'price': 102.0, 'qty': quantity}], 'orderId': 22}

    monkeypatch.setattr(t.api, 'quantize', _quantize)
    monkeypatch.setattr(t.api, 'place_order', _place_order_entry)

    signal = {
        'symbol': 'AAAUSDT',
        'indicators': {'ATR': 1.0},
        'total_score': 55,
        'signal': 'AL',
        'close_price': 100.0,
        'volume_24h': 1_000_000,
        'prev_close': 100.0,
    }
    assert t.execute_trade(signal)
    pos = t.positions['AAAUSDT']
    pos['stop_loss'] = pos['entry_price'] - 10.0
    t.partial_enabled = True
    t.tp_levels = [(0.5, 0.5)]
    t.process_price_update('AAAUSDT', pos['entry_price'] + 5.0)
    monkeypatch.setattr(t.api, 'place_order', _place_order_exit)
    assert t.close_position('AAAUSDT')
    events = {e['event'] for e in get_slog_events()}
    assert {'trade_open', 'partial_exit', 'trade_close'}.issubset(events)


def test_cr0028_anomaly_events(monkeypatch, tmp_path):
    _isolate_db(tmp_path)
    monkeypatch.setattr('config.settings.Settings.OFFLINE_MODE', True, raising=False)
    clear_slog_events()
    t = Trader()
    t.recent_open_latencies = [2000]*40
    t.recent_entry_slippage_bps = [100]*40
    from src.trader.metrics import maybe_check_anomalies
    maybe_check_anomalies(t)
    events = {e['event'] for e in get_slog_events()}
    assert 'anomaly_latency' in events
    assert 'anomaly_slippage' in events
