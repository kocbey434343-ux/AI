import os, sqlite3
from config.settings import Settings
from src.trader import Trader

def _make_trader(tmp_path):
    db_path = str(tmp_path / 'scaleout.db')
    Settings.TRADES_DB_PATH = db_path  # type: ignore[attr-defined]
    os.environ['TRADES_DB_PATH'] = db_path
    Settings.OFFLINE_MODE = True  # type: ignore
    if os.path.exists(db_path):
        os.remove(db_path)
    t = Trader()
    t.risk_manager.max_positions = 50
    return t


def test_scaleout_persist_and_reload(tmp_path, monkeypatch):
    t = _make_trader(tmp_path)
    # Basit order taklitleri
    monkeypatch.setattr(t.api, 'quantize', lambda s,q,p: (q,p))
    monkeypatch.setattr(t.api, 'place_order', lambda **k: {'price':100.0,'fills':[{'price':100.0,'qty':k['quantity']}], 'orderId':11})
    sig = {'symbol':'SOUT1','signal':'AL','close_price':100.0,'indicators':{'ATR':1.0},'total_score':70,'volume_24h':1_000_000,'prev_close':100.0}
    assert t.execute_trade(sig)
    pos = t.positions['SOUT1']
    trade_id = pos['trade_id']
    # Risk mesafesini manuel ayarla (1R tetiklemek icin)
    pos['stop_loss'] = 95.0  # risk=5
    # Fiyat 105 -> r=1.0 (PARTIAL_TP1_R_MULT varsayilan 1.0)
    t.process_price_update('SOUT1', 105.0)
    # Partial exit gerceklesti mi
    assert pos.get('scaled_out'), 'Partial exit tetiklenmedi'
    first_scale = pos['scaled_out'][0]
    assert abs(first_scale[0] - 1.0) < 1e-9, 'R seviyesi beklenen degil'
    # DB'de scaled_out_json dolu mu
    with sqlite3.connect(Settings.TRADES_DB_PATH) as c:
        cur = c.cursor()
        row = cur.execute('SELECT scaled_out_json,size FROM trades WHERE id=?', (trade_id,)).fetchone()
        assert row is not None
        so_json, size = row
        assert so_json and '"r_mult": 1.0' in so_json
    remaining_after = pos['remaining_size']
    # Restart (reload)
    t2 = Trader()
    pos2 = t2.positions['SOUT1']
    assert pos2.get('scaled_out'), 'Reload scaled_out bos'
    # Remaining dogru mu
    total_scaled_qty = sum(q for _,q in pos2['scaled_out'])
    assert abs(pos2['remaining_size'] - (pos2['position_size'] - total_scaled_qty)) < 1e-9
    assert abs(pos2['remaining_size'] - remaining_after) < 1e-9
