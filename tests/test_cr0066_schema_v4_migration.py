import sqlite3
import os
from datetime import datetime, timezone
from src.utils.trade_store import TradeStore

def test_schema_v4_migration():
    """Test CR-0066: Schema versioning v4 migration"""
    # Create a temporary test database
    test_db = "test_schema_v4.db"

    # Clean up if exists
    if os.path.exists(test_db):
        os.remove(test_db)

    try:
        # Create old schema (v3) manually
        conn = sqlite3.connect(test_db)
        cur = conn.cursor()

        # Create v3 schema (without v4 fields)
        cur.execute("""
        CREATE TABLE trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            entry_price REAL NOT NULL,
            exit_price REAL,
            size REAL NOT NULL,
            pnl_pct REAL,
            opened_at TEXT NOT NULL,
            closed_at TEXT,
            strategy_tag TEXT,
            stop_loss REAL,
            take_profit REAL,
            param_set_id TEXT,
            entry_slippage_bps REAL,
            exit_slippage_bps REAL,
            raw JSON,
            scaled_out_json JSON
        );
        """)

        # Insert test data
        cur.execute(
            "INSERT INTO trades(symbol, side, entry_price, size, opened_at) VALUES (?, ?, ?, ?, ?)",
            ("TESTUSDT", "BUY", 100.0, 10.0, "2024-01-01T00:00:00Z")
        )

        # Set user_version to 3
        cur.execute("PRAGMA user_version=3")
        conn.commit()
        conn.close()

        print("✅ Created v3 schema with test data")

        # Now use TradeStore to trigger migration
        os.environ['TRADES_DB_PATH'] = test_db
        store = TradeStore()

        # Check if migration worked
        conn = sqlite3.connect(test_db)
        cur = conn.cursor()

        # Check schema version
        version = cur.execute("PRAGMA user_version").fetchone()[0]
        print(f"✅ Schema version after migration: {version}")

        # Check columns exist
        cols = {r[1] for r in cur.execute("PRAGMA table_info(trades)").fetchall()}
        expected_v4_cols = {'schema_version', 'created_ts', 'updated_ts'}

        if expected_v4_cols.issubset(cols):
            print("✅ All v4 columns present")
        else:
            missing = expected_v4_cols - cols
            print(f"❌ Missing v4 columns: {missing}")

        # Check backfilled data
        row = cur.execute("SELECT schema_version, created_ts, updated_ts FROM trades WHERE symbol='TESTUSDT'").fetchone()
        if row:
            schema_ver, created_ts, updated_ts = row
            print(f"✅ Backfilled data - schema_version: {schema_ver}, created_ts: {created_ts}, updated_ts: {updated_ts}")

            if schema_ver == 4:
                print("✅ Schema version correctly backfilled")
            else:
                print(f"❌ Wrong schema version: {schema_ver}")
        else:
            print("❌ No test data found")

        conn.close()

        # Test new insert
        trade_id = store.insert_open("NEWTEST", "SELL", 200.0, 5.0, datetime.now(timezone.utc).isoformat())
        print(f"✅ New trade inserted with ID: {trade_id}")

        # Verify new trade has v4 fields
        conn = sqlite3.connect(test_db)
        cur = conn.cursor()
        row = cur.execute("SELECT schema_version, created_ts, updated_ts FROM trades WHERE id=?", (trade_id,)).fetchone()
        if row and row[0] == 4 and row[1] and row[2]:
            print("✅ New trade has correct v4 fields")
        else:
            print(f"❌ New trade missing v4 fields: {row}")
        conn.close()

    except Exception as e:
        print(f"❌ Migration test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        if os.path.exists(test_db):
            os.remove(test_db)
        # Reset env
        if 'TRADES_DB_PATH' in os.environ:
            del os.environ['TRADES_DB_PATH']

if __name__ == "__main__":
    test_schema_v4_migration()
