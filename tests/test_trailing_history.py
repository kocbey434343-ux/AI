import os
import sqlite3

from src.trader import Trader
from config.settings import Settings


def _mk(tmp_path):
    db_path = str(tmp_path / 'trailhist.db')
    # Dogrudan Settings attribute override (env degisimi yeterli degil import sonrasi)
    Settings.TRADES_DB_PATH = db_path  # type: ignore[attr-defined]
    if os.path.exists(db_path):
        os.remove(db_path)
    Settings.OFFLINE_MODE = True  # type: ignore
    t = Trader()
    t.risk_manager.max_positions = 50
    return t


def test_cr0016_trailing_persistence_and_history(tmp_path, monkeypatch):
    t = _mk(tmp_path)
    monkeypatch.setattr(t.api, 'quantize', lambda s,q,p: (q,p))
    monkeypatch.setattr(t.api, 'place_order', lambda **k: {'price':100.0,'fills':[{'price':100.0,'qty':k['quantity']}], 'orderId':7})
    sig = {'symbol':'TRAIL1','signal':'AL','close_price':100.0,'indicators':{'ATR':1.0},'total_score':50,'volume_24h':1_000_000,'prev_close':100.0}
    assert t.execute_trade(sig)
    pos = t.positions['TRAIL1']
    # Disable partial exits to isolate trailing behaviour
    t.partial_enabled = False  # type: ignore[attr-defined]
    # Lower activation threshold if needed (keep default? raise price to meet default 1.2R)
    t.trailing_activate_r = 1.0  # type: ignore[attr-defined]
    # force initial stop to 95 to create risk=5 so 1R at 105
    pos['stop_loss'] = 95.0
    # First update at 105 (1R) now activates trailing (threshold set to 1.0)
    t.process_price_update('TRAIL1', 105.0)
    first_sl = pos['stop_loss']
    assert first_sl > 95.0  # should be entry + (5 * 0.25) = 101.25
    trade_id = pos['trade_id']
    # DB updated (trade-specific)
    with sqlite3.connect(Settings.TRADES_DB_PATH) as c:
        cur = c.cursor()
        db_sl = cur.execute("SELECT stop_loss FROM trades WHERE id=?", (trade_id,)).fetchone()[0]
    assert abs(db_sl - first_sl) < 1e-9
    # One trailing_update execution row
    with sqlite3.connect(Settings.TRADES_DB_PATH) as c:
        cur = c.cursor()
        cnt = cur.execute("SELECT COUNT(*) FROM executions WHERE trade_id=? AND exec_type='trailing_update'", (trade_id,)).fetchone()[0]
    assert cnt == 1
    # Second update higher price -> second trailing record (gain=10 -> step=2.5 -> target=102.5)
    t.process_price_update('TRAIL1', 110.0)
    second_sl = pos['stop_loss']
    assert second_sl > first_sl
    with sqlite3.connect(Settings.TRADES_DB_PATH) as c:
        cur = c.cursor()
        cnt2 = cur.execute("SELECT COUNT(*) FROM executions WHERE trade_id=? AND exec_type='trailing_update'", (trade_id,)).fetchone()[0]
        db_sl2 = cur.execute("SELECT stop_loss FROM trades WHERE id=?", (trade_id,)).fetchone()[0]
    assert cnt2 == 2
    assert abs(db_sl2 - second_sl) < 1e-9
    # Restart persistence (reload)
    # Restart with same DB path
    t2 = Trader()
    new_pos = t2.positions['TRAIL1']
    assert abs(new_pos['stop_loss'] - second_sl) < 1e-9
