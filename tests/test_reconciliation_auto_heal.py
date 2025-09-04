from src.trader import Trader
from config.settings import Settings

def test_cr0015_reconciliation_auto_heal(monkeypatch, tmp_path):
    # Setup isolated DB
    import os
    os.environ['TRADES_DB_PATH'] = str(tmp_path / 'heal.db')
    Settings.OFFLINE_MODE = True  # type: ignore
    t = Trader()
    # Inject a fake open position lacking protection orders
    t.positions['HEALSYM'] = {
        'side': 'BUY',
        'entry_price': 100.0,
        'position_size': 10.0,
        'remaining_size': 10.0,
        'stop_loss': 95.0,
        'take_profit': 110.0,
        'atr': None,
        'trade_id': 999,
        'scaled_out': []
    }
    summary = t._reconcile_open_orders()
    assert 'HEALSYM' in summary['missing_stop_tp']
    # heal flag set
    assert t.positions['HEALSYM'].get('heal_attempted_HEALSYM') is True
    # Second call idempotent (flag remains True, no duplication)
    summary2 = t._reconcile_open_orders()
    assert 'HEALSYM' in summary2['missing_stop_tp']
    # still single attempt marker
    assert t.positions['HEALSYM'].get('heal_attempted_HEALSYM') is True
