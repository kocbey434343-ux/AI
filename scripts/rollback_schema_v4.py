#!/usr/bin/env python3
"""
CR-0066 Schema v4 Rollback Script
Rollback from v4 to v3 by dropping v4-specific columns
CAUTION: This will lose v4 data (schema_version, created_ts, updated_ts)
"""

import sqlite3
import sys
from pathlib import Path

def rollback_v4_to_v3(db_path: str, dry_run: bool = True):
    """Rollback schema from v4 to v3"""
    if not Path(db_path).exists():
        print(f"❌ Database not found: {db_path}")
        return False

    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        # Check current version
        version = cur.execute("PRAGMA user_version").fetchone()[0]
        print(f"📊 Current schema version: {version}")

        if version != 4:
            print(f"⚠️  Database is not v4 (current: {version}). Rollback not needed.")
            return True

        # Check if v4 columns exist
        cols = {r[1] for r in cur.execute("PRAGMA table_info(trades)").fetchall()}
        v4_cols = {'schema_version', 'created_ts', 'updated_ts'}
        missing = v4_cols - cols

        if missing:
            print(f"⚠️  v4 columns already missing: {missing}")

        if dry_run:
            print("🔍 DRY RUN - Changes that would be made:")
            for col in v4_cols & cols:
                print(f"  - DROP COLUMN {col}")
            print("  - SET user_version = 3")
            return True

        print("⚠️  EXECUTING ROLLBACK - This will lose v4 data!")

        # Create new table without v4 columns
        cur.execute("""
        CREATE TABLE trades_v3_temp (
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

        # Copy data (excluding v4 columns)
        cur.execute("""
        INSERT INTO trades_v3_temp
        SELECT id, symbol, side, entry_price, exit_price, size, pnl_pct, opened_at, closed_at,
               strategy_tag, stop_loss, take_profit, param_set_id, entry_slippage_bps,
               exit_slippage_bps, raw, scaled_out_json
        FROM trades;
        """)

        # Drop old table and rename
        cur.execute("DROP TABLE trades")
        cur.execute("ALTER TABLE trades_v3_temp RENAME TO trades")

        # Recreate indexes
        cur.execute("CREATE INDEX IF NOT EXISTS idx_trades_symbol_time ON trades(symbol, opened_at)")

        # Set version to 3
        cur.execute("PRAGMA user_version=3")

        conn.commit()
        conn.close()

        print("✅ Rollback completed successfully")
        print("📊 Schema version set to 3")
        print("⚠️  v4 timestamp data has been lost")

        return True

    except Exception as e:
        print(f"❌ Rollback failed: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python rollback_v4.py <db_path> [--execute]")
        print("By default runs in dry-run mode. Use --execute to actually rollback.")
        sys.exit(1)

    db_path = sys.argv[1]
    dry_run = "--execute" not in sys.argv

    if dry_run:
        print("🔍 Running in DRY-RUN mode")
    else:
        print("⚠️  EXECUTE mode - changes will be permanent!")

    success = rollback_v4_to_v3(db_path, dry_run)
    sys.exit(0 if success else 1)
