import math
from src.trader import Trader
from src.api.binance_api import BinanceAPI
from src.utils.structured_log import clear_slog_events, get_slog_events

MIN_QTY = 0.05
STEP = 0.001


def test_cr0030_quantize_below_min_qty(monkeypatch):
    api = BinanceAPI()
    def fake_filters(_):
        return {
            'LOT_SIZE': {'stepSize': f'{STEP}', 'minQty': f'{MIN_QTY}'},
            'PRICE_FILTER': {'tickSize': '0.01', 'minPrice': '0.01'}
        }
    monkeypatch.setattr(api, '_get_filters', fake_filters)
    qty, _ = api.quantize('EDGEUSDT', MIN_QTY * 0.4, 10.0)
    assert qty == 0.0
    qty2, _ = api.quantize('EDGEUSDT', MIN_QTY * 1.37, 10.0)
    # clamp down to step, ensure >= minQty
    assert qty2 >= MIN_QTY
    rem = (qty2 - MIN_QTY) % STEP
    assert math.isclose(rem, 0.0, abs_tol=1e-12)


def test_cr0030_partial_exit_interaction(monkeypatch, tmp_path):
    # isolate db
    monkeypatch.setattr('config.settings.Settings.OFFLINE_MODE', True, raising=False)
    import os
    os.environ['TRADES_DB_PATH'] = str(tmp_path / 'quant_partial.db')
    clear_slog_events()
    t = Trader()
    t.risk_manager.max_positions = 100
    # Force partial config single level 0.5R 50%
    t.partial_enabled = True
    t.tp_levels = [(0.5, 0.5)]

    def _quantize(_s, q, p):
        return q, p
    def _order(*_, **kw):
        q = kw.get('quantity')
        return {'price': 100.0, 'fills': [{'price':100.0,'qty':q}], 'orderId':11}
    monkeypatch.setattr(t.api,'quantize',_quantize)
    monkeypatch.setattr(t.api,'place_order',_order)

    signal = {
        'symbol':'QPUSDT','indicators':{'ATR':1.0},'total_score':60,'signal':'AL','close_price':100.0,'volume_24h':1_000_000,'prev_close':100.0
    }
    assert t.execute_trade(signal)
    pos = t.positions['QPUSDT']
    pos['stop_loss'] = pos['entry_price'] - 10.0  # risk=10
    size_before = pos['remaining_size']
    # 0.5R: entry + 5
    t.process_price_update('QPUSDT', pos['entry_price'] + 5.0)  # 0.5R => partial
    size_after = pos['remaining_size']
    assert size_after < size_before
    events = [e for e in get_slog_events() if e['event']=='partial_exit']
    assert events
    # BE stop loss update beklenir (price > entry) -> stop_loss == entry
    assert math.isclose(pos['stop_loss'], pos['entry_price'])
