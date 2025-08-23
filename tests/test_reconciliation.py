import contextlib
import logging
from src.trader.core import Trader


def test_reconciliation_diff():
    t = Trader()
    # Local positions: BTCUSDT (no protection), ADAUSDT (has protection) -> only BTCUSDT should flag missing_stop_tp
    t.positions['BTCUSDT'] = {
        'side': 'BUY', 'entry_price': 100.0, 'position_size': 1.0, 'remaining_size': 1.0,
        'stop_loss': 95.0, 'take_profit': 110.0, 'atr': None, 'trade_id': 1, 'scaled_out': []
    }
    t.positions['ADAUSDT'] = {
        'side': 'BUY', 'entry_price': 50.0, 'position_size': 2.0, 'remaining_size': 2.0,
        'stop_loss': 48.0, 'take_profit': 55.0, 'atr': None, 'trade_id': 2, 'scaled_out': [],
        'oco_resp': {'ids': [12345]}  # simulate protection present
    }

    # Monkeypatch API methods to return deterministic exchange state
    t.api.get_positions = lambda: [
        {'symbol': 'ETHUSDT', 'side': 'BUY', 'size': 0.5, 'entry_price': 2000.0}
    ]  # orphan exchange position ETHUSDT
    t.api.get_open_orders = lambda symbol=None: []  # noqa: ARG005 simb param gereksiz testte

    # Manuel log yakalama (caplog Trader logger'ini yakalamiyor cunku handler ekli)
    records: list[str] = []
    class _ListH(logging.Handler):
        def emit(self, record):
            with contextlib.suppress(Exception):
                msg = record.getMessage()
                if 'RECON:' in msg:
                    records.append(msg)
    logger = logging.getLogger('Trader')
    lh = _ListH()
    logger.addHandler(lh)
    try:
        summary = t._reconcile_open_orders()
    finally:
        logger.removeHandler(lh)

    # Expectations
    assert 'ETHUSDT' in summary['orphan_exchange_position']
    # Both local symbols absent on exchange -> orphan_local_position contains them
    assert 'BTCUSDT' in summary['orphan_local_position']
    assert 'ADAUSDT' in summary['orphan_local_position']
    # Missing stop/tp only for BTCUSDT (no protection)
    assert 'BTCUSDT' in summary['missing_stop_tp']
    assert 'ADAUSDT' not in summary['missing_stop_tp']

    # Log lines contain RECON prefixes
    assert records, 'RECON loglari yakalanamadi'
    assert any('RECON:missing_stop_tp:BTCUSDT' in m for m in records)
    assert any('RECON:orphan_exchange_position:ETHUSDT' in m for m in records)
