import os
import sqlite3
from pathlib import Path

from src.trader import Trader
from config.settings import Settings


def _db_conn_path(path: Path):
    return sqlite3.connect(str(path))


def make_trader(tmp_path):
    os.environ['TRADES_DB_PATH'] = str(tmp_path / 'scaleout.db')
    os.environ['ENABLE_POSITION_RELOAD'] = '1'  # Enable position reload for restart test
    Settings.OFFLINE_MODE = True  # type: ignore[attr-defined]
    return Trader()


def test_cr0013_scale_out_single_execution_and_persistence(tmp_path, monkeypatch):
    """CR-0013 AC1-AC4: Duplicate scale_out onleme ve persist dogrulama.
    AC1: Ilk partial exit sonrasi executions tablosunda tek scale_out satiri.
    AC2: Restart sonrasi scaled_out listesi ayni qty.
    AC3: Weighted PnL duplicate olmadan beklenen.
    AC4: Ayni R tekrar guncellemesinde yeni kayit yok (idempotent).
    """
    monkeypatch.setattr('config.settings.Settings.OFFLINE_MODE', True, raising=False)

    def _quantize(_s, q, p):
        return q, p

    def _place_order_entry(*_, **kwargs):
        quantity = kwargs.get('quantity')
        return {'price': 100.0, 'fills': [{'price': 100.0, 'qty': quantity}], 'orderId': 11}

    t = make_trader(tmp_path)
    t.risk_manager.max_positions = 100
    # Partial exit config (tek seviye)
    t.partial_enabled = True
    t.tp_levels = [(0.5, 0.5)]  # 0.5R'de %50 cikis
    monkeypatch.setattr(t.api, 'quantize', _quantize)
    monkeypatch.setattr(t.api, 'place_order', _place_order_entry)

    signal = {
        'symbol': 'SOUSDT',
        'indicators': {'ATR': 1.0},
        'total_score': 50,
        'signal': 'AL',
        'close_price': 100.0,
        'volume_24h': 1_000_000,
        'prev_close': 100.0,
    }
    opened = t.execute_trade(signal)
    assert opened
    pos = t.positions['SOUSDT']
    entry = pos['entry_price']
    pos['stop_loss'] = entry - 10.0  # risk=10

    target_price = entry + 5.0  # 0.5R
    t.process_price_update('SOUSDT', target_price)

    # AC1: Sadece bu trade'in execution kayitlarini say
    with _db_conn_path(t.trade_store.db_path) as c:  # type: ignore[attr-defined]
        cur = c.cursor()
        row = cur.execute(
            "SELECT COUNT(*) FROM executions WHERE exec_type='scale_out' AND trade_id=?",
            (pos['trade_id'],)
        ).fetchone()
        scale_out_count = row[0]
    assert scale_out_count == 1, f"Beklenen 1 scale_out kaydi, bulundu {scale_out_count} (duplicate sorunu)"

    # AC4: Aynı fiyat tekrar gelirse yeni kayit olmamali
    t.process_price_update('SOUSDT', target_price)
    with _db_conn_path(t.trade_store.db_path) as c:  # type: ignore[attr-defined]
        cur = c.cursor()
        again = cur.execute(
            "SELECT COUNT(*) FROM executions WHERE exec_type='scale_out' AND trade_id=?",
            (pos['trade_id'],)
        ).fetchone()[0]
        assert again == 1

    # AC2: Restart sonrası scaled_out korunur
    t2 = Trader()
    new_pos = t2.positions['SOUSDT']
    assert len(new_pos['scaled_out']) == 1
    level, _qty = new_pos['scaled_out'][0]
    assert abs(level - 0.5) < 1e-9
    assert abs(new_pos['remaining_size'] - pos['remaining_size']) < 1e-9

    # AC3: Kapanış sonrası weighted PnL
    def _place_order_exit(*_, **kwargs):
        quantity = kwargs.get('quantity')
        return {'price': 102.0, 'fills': [{'price': 102.0, 'qty': quantity}], 'orderId': 22}

    monkeypatch.setattr(t2.api, 'place_order', _place_order_exit)
    assert t2.close_position('SOUSDT')

    expected_pct = 3.5  # 0.5 *5% + 0.5 *2% = 3.5%
    with _db_conn_path(t2.trade_store.db_path) as c:  # type: ignore[attr-defined]
        cur = c.cursor()
        pnl_row = cur.execute(
            "SELECT pnl_pct FROM trades WHERE symbol='SOUSDT' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        pnl_pct = pnl_row[0]
    assert abs(pnl_pct - expected_pct) < 1e-6
