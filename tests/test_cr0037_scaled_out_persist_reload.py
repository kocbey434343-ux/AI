import os
from src.trader import Trader
from src.utils.structured_log import clear_slog_events


def test_cr0037_scaled_out_persist_and_reload(monkeypatch, tmp_path):
    os.environ['TRADES_DB_PATH'] = str(tmp_path / 'scaled_out_v3.db')
    os.environ['ENABLE_POSITION_RELOAD'] = '1'  # Enable position reload for restart test
    monkeypatch.setattr('config.settings.Settings.OFFLINE_MODE', True, raising=False)
    clear_slog_events()
    t = Trader()
    t.risk_manager.max_positions = 100
    t.partial_enabled = True
    # BE sonrası risk 0 olacağından çoklu seviye desteklenmediği için tek seviye yeterli
    t.tp_levels = [(0.5, 0.5)]

    def _quantize(_s,q,p): return q,p
    def _order(*_, **kw):
        q = kw.get('quantity')
        return {'price':100.0,'fills':[{'price':100.0,'qty':q}],'orderId':1}
    monkeypatch.setattr(t.api,'quantize',_quantize)
    monkeypatch.setattr(t.api,'place_order',_order)

    signal = {'symbol':'PSTUSDT','indicators':{'ATR':1.0},'total_score':60,'signal':'AL','close_price':100.0,'volume_24h':1_000_000,'prev_close':100.0}
    assert t.execute_trade(signal)
    pos = t.positions['PSTUSDT']
    pos['stop_loss'] = pos['entry_price'] - 10.0
    t.process_price_update('PSTUSDT', pos['entry_price'] + 5.0)  # 0.5R
    scaled = list(pos['scaled_out'])
    assert len(scaled) == 1
    rem_before = pos['remaining_size']
    # Restart -> persist kontrolü
    t2 = Trader()
    new_pos = t2.positions['PSTUSDT']
    assert len(new_pos['scaled_out']) == 1
    assert abs(new_pos['remaining_size'] - rem_before) < 1e-9
