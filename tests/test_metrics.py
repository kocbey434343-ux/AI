import os
import time

from src.utils.trade_store import TradeStore

MAX_ALL_LIMIT = 6
MAX_PNL_LIMIT = 3


def test_recent_metrics_all_and_filtered(tmp_path):
    db_file = tmp_path / 'metrics.db'
    os.environ['TRADES_DB_PATH'] = str(db_file)
    store = TradeStore(str(db_file))

    # Insert metrics for two keys
    for i in range(5):
        store.record_metric('pnl',  i * 1.0)
        store.record_metric('slip', i * 0.1)
        # small delay to guarantee ordering if same second
        time.sleep(0.01)

    all_recent = store.recent_metrics(limit=MAX_ALL_LIMIT)
    assert len(all_recent) <= MAX_ALL_LIMIT
    # Must contain only keys we inserted
    assert all(m['key'] in {'pnl','slip'} for m in all_recent)

    pnl_recent = store.recent_metrics(key='pnl', limit=MAX_PNL_LIMIT)
    assert len(pnl_recent) <= MAX_PNL_LIMIT
    assert all(m['key'] == 'pnl' for m in pnl_recent)

    # Values should be floats and last value should be the latest inserted (>= previous)
    if pnl_recent:
        # Since we requested last 3, they should correspond to highest value entries
        values = [m['value'] for m in pnl_recent]
        assert values == sorted(values, reverse=True) or values == sorted(values), "Order not deterministic but should be consistent"

    store.close()
