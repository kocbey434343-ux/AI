from src.trader import Trader
from src.utils.structured_log import clear_slog_events, get_slog_events
import os
import math

# CR-0028: Structured logging entegrasyon testi
# Senaryo: Offline trader -> pozisyon aç -> fiyat artışı ile partial exit + (mümkünse) trailing -> pozisyonu kapat.
# Beklenen minimum structured events: trade_open, partial_exit (>=1), trade_close. Trailing_update opsiyonel (koşullara bağlı).

def _prep_trader(monkeypatch, tmp_path):
    os.environ['TRADES_DB_PATH'] = str(tmp_path / 'cr0028_struct.db')
    monkeypatch.setattr('config.settings.Settings.OFFLINE_MODE', True, raising=False)
    monkeypatch.setattr('config.settings.Settings.STRUCTURED_LOG_ENABLED', True, raising=False)
    # Partial & trailing paramlarını agresif yap ki kolay tetiklensin
    monkeypatch.setattr('config.settings.Settings.ENABLE_PARTIAL_EXITS', True, raising=False)
    monkeypatch.setattr('config.settings.Settings.PARTIAL_TP1_R_MULT', 0.2, raising=False)
    monkeypatch.setattr('config.settings.Settings.PARTIAL_TP1_PCT', 25.0, raising=False)
    monkeypatch.setattr('config.settings.Settings.PARTIAL_TP2_R_MULT', 0.4, raising=False)
    monkeypatch.setattr('config.settings.Settings.PARTIAL_TP2_PCT', 35.0, raising=False)
    monkeypatch.setattr('config.settings.Settings.TRAILING_ACTIVATE_R_MULT', 0.2, raising=False)
    monkeypatch.setattr('config.settings.Settings.TRAILING_STEP_PCT', 10.0, raising=False)
    monkeypatch.setattr('config.settings.Settings.ATR_TRAILING_ENABLED', True, raising=False)

    t = Trader()
    def _quantize(sym, q, p):
        return (min(q, 1.0), p)
    def _place_order(**kw):
        q = kw.get('quantity', 0.0)
        price = 100.0
        return {'price': price, 'fills': [{'price': price, 'qty': q}], 'orderId': 1}
    monkeypatch.setattr(t.api, 'quantize', _quantize)
    monkeypatch.setattr(t.api, 'place_order', _place_order)
    return t


def test_cr0028_structured_log_end_to_end(monkeypatch, tmp_path):
    clear_slog_events()
    t = _prep_trader(monkeypatch, tmp_path)

    sig = {
        'symbol': 'SLOGX',
        'indicators': {'ATR': 2.0},
        'total_score': 75,
        'signal': 'AL',
        'close_price': 100.0,
        'volume_24h': 1_000_000,
        'prev_close': 100.0
    }
    assert t.execute_trade(sig), 'Pozisyon açılmadı'
    pos = t.positions['SLOGX']

    # Entry = 100, stop = 80 -> risk = 20
    entry = pos['entry_price']
    pos['stop_loss'] = entry - 20.0

    # 0.25R (trailing activate ve partial1 tetik) -> price = entry + 5
    t.process_price_update('SLOGX', entry + 5.0)
    # 0.5R (ikinci partial) -> price = entry + 10
    t.process_price_update('SLOGX', entry + 10.0)
    # 1.0R -> price = entry + 20 (kesin trailing tetiklemesi)
    t.process_price_update('SLOGX', entry + 20.0)

    assert t.close_position('SLOGX')

    events = get_slog_events()
    ev_types = {e['event'] for e in events}
    assert 'trade_open' in ev_types, ev_types
    assert 'partial_exit' in ev_types, ev_types
    assert 'trade_close' in ev_types, ev_types
    # trailing_update opsiyonel; yoksa sorun yapma

    # Kapsamlı alan kontrolleri
    open_ev = next(e for e in events if e['event'] == 'trade_open')
    assert open_ev.get('symbol') == 'SLOGX'
    pe = next(e for e in events if e['event'] == 'partial_exit')
    assert pe.get('remaining') is not None
    tc = next(e for e in events if e['event'] == 'trade_close')
    assert 'fill' in tc

    # Eğer trailing_update oluştuysa new_stop numeric olmalı
    trailing_events = [e for e in events if e['event'] == 'trailing_update']
    if trailing_events:
        for te in trailing_events:
            ns = te.get('new_stop')
            assert ns is None or isinstance(ns, (int, float))
            if isinstance(ns, (int, float)):
                assert not math.isnan(ns)
