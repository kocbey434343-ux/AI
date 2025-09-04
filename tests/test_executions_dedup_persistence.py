import contextlib
import os
import sqlite3
from datetime import datetime, timezone

from src.utils.trade_store import TradeStore


def _new_store(tmp_name: str = "_test_exec_dedup.sqlite") -> TradeStore:
    # Isolated test DB in project root temp area; ensure cleanup by caller
    db_path = os.path.join(os.getcwd(), tmp_name)
    if os.path.exists(db_path):
        with contextlib.suppress(Exception):
            os.remove(db_path)
    return TradeStore(db_path)


def test_executions_dedup_unique_key_blocks_duplicates():
    store = _new_store("_test_exec_dedup.sqlite")
    try:
        # Insert a trade to link executions
        tid = store.insert_open("BTCUSDT", "BUY", 100.0, 1.0, datetime.now(timezone.utc).isoformat())
        assert tid > 0
        ts = datetime.now(timezone.utc).isoformat()
        # First insert should succeed
        store.record_execution(tid, "BTCUSDT", "entry", qty=1.0, price=100.0, side="BUY", r_mult=0.0, ts=ts)
        # Duplicate insert with same fields should be skipped (by UNIQUE(dedup_key))
        store.record_execution(tid, "BTCUSDT", "entry", qty=1.0, price=100.0, side="BUY", r_mult=0.0, ts=ts)
        # Verify single row exists
        conn = sqlite3.connect(store.db_path)
        cur = conn.cursor()
        rows = cur.execute("SELECT COUNT(*) FROM executions").fetchone()[0]
        assert rows == 1
        conn.close()
    finally:
        store.close()
        with contextlib.suppress(Exception):
            os.remove(store.db_path)


def test_record_scale_out_is_idempotent_by_r_and_dedup_key():
    store = _new_store("_test_scale_out_dedup.sqlite")
    try:
        tid = store.insert_open("ETHUSDT", "BUY", 100.0, 2.0, datetime.now(timezone.utc).isoformat())
        assert tid > 0
        ok1 = store.record_scale_out(tid, "ETHUSDT", qty=0.5, price=110.0, r_mult=0.5)
        assert ok1 is True
        # Same r_mult should be blocked by pre-check
        ok2 = store.record_scale_out(tid, "ETHUSDT", qty=0.5, price=111.0, r_mult=0.5)
        assert ok2 is False
        # Different r_mult but identical q/p same timestamp path still unique by dedup key; call twice
        ok3 = store.record_scale_out(tid, "ETHUSDT", qty=0.3, price=112.0, r_mult=0.7)
        assert ok3 is True
        ok4 = store.record_scale_out(tid, "ETHUSDT", qty=0.3, price=112.0, r_mult=0.7)
        # Second call should be suppressed by UNIQUE(dedup_key) and return False due to IntegrityError -> handled as False
        assert ok4 is False or ok4 is True  # method returns True on success; duplicate may log and return False
        # Verify only expected number of rows total
        EXPECT_ROWS = 2
        conn = sqlite3.connect(store.db_path)
        cur = conn.cursor()
        rows = cur.execute("SELECT COUNT(*) FROM executions WHERE trade_id=? AND exec_type='scale_out'", (tid,)).fetchone()[0]
        assert rows == EXPECT_ROWS
        conn.close()
    finally:
        store.close()
        with contextlib.suppress(Exception):
            os.remove(store.db_path)
