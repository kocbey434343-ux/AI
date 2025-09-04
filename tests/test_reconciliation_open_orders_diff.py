import os; from config.settings import Settings; from src.trader import Trader  # noqa: E401,E702


def test_cr0018_reconciliation_open_orders_diff(tmp_path):
    """AC1-AC4: orphan exchange order, orphan local position, idempotent, disappearance when reconciled."""
    os.environ['TRADES_DB_PATH'] = str(tmp_path / 'recon.db')
    Settings.OFFLINE_MODE = True  # type: ignore
    t = Trader()

    # Stage 1: Only an exchange open order exists (no local position) -> orphan_exchange_order
    t.api.get_open_orders = lambda: [  # type: ignore
        {'symbol': 'LTCUSDT', 'orderId': 1}
    ]
    t.api.get_positions = lambda: []  # type: ignore
    summary1 = t._reconcile_open_orders()
    assert 'LTCUSDT' in summary1['orphan_exchange_order'], 'AC1 failed: orphan exchange order not detected'
    assert 'LTCUSDT' not in summary1['orphan_exchange_position']
    assert 'LTCUSDT' not in summary1['orphan_local_position']

    # Stage 2: Repeat call same state -> idempotent (no duplicates)
    summary2 = t._reconcile_open_orders()
    assert summary2['orphan_exchange_order'].count('LTCUSDT') == 1, 'AC3 failed: duplicate symbol detected'

    # Stage 3: Add local position (still no exchange position)
    t.positions['LTCUSDT'] = {
        'side': 'BUY', 'entry_price': 100.0, 'position_size': 1.0, 'remaining_size': 1.0,
        'stop_loss': 95.0, 'take_profit': 110.0, 'atr': None, 'trade_id': 7, 'scaled_out': []
    }
    summary3 = t._reconcile_open_orders()
    assert 'LTCUSDT' not in summary3['orphan_exchange_order'], 'AC4 failed: symbol should disappear after local tracking'
    assert 'LTCUSDT' in summary3['orphan_local_position'], 'AC2/AC4 failed: local orphan position expected without exchange position'

    # Stage 4: Provide matching exchange position -> orphan_local_position cleared
    t.api.get_positions = lambda: [  # type: ignore
        {'symbol': 'LTCUSDT', 'side': 'BUY', 'size': 1.0, 'entry_price': 100.0}
    ]
    summary4 = t._reconcile_open_orders()
    assert 'LTCUSDT' not in summary4['orphan_local_position'], 'AC4 failed: should be reconciled when exchange position exists'
    assert 'LTCUSDT' not in summary4['orphan_exchange_order'], 'AC4 failed: should remain absent from orphan_exchange_order'
