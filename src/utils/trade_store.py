import csv
import json
import os
import sqlite3
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from config.settings import Settings
from src.utils.guard_events import GuardEventRecorder  # CR-0069
from src.utils.logger import get_logger

# local JSON helper (used in insert_open) defined early to avoid NameError
def json_dumps(obj: Any) -> str | None:
    try:
        return json.dumps(obj, ensure_ascii=False) if obj is not None else None
    except Exception:
        return None

LOGGER = get_logger("TradeStore")
SCHEMA_V1 = 1
SCHEMA_V2 = 2
SCHEMA_V3 = 3
SCHEMA_LATEST = 4  # v4 adds schema_version, created_ts, updated_ts (CR-0066)
PRAGMA_TABLE_INFO_TRADES = "PRAGMA table_info(trades)"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    entry_price REAL NOT NULL,
    exit_price REAL,
    size REAL NOT NULL,
    pnl_pct REAL,
    opened_at TEXT NOT NULL,
    closed_at TEXT,
    created_ts TEXT,           -- v4
    updated_ts TEXT,           -- v4
    schema_version INTEGER,    -- v4
    strategy_tag TEXT,
    stop_loss REAL,
    take_profit REAL,
    param_set_id TEXT,
    entry_slippage_bps REAL,
    exit_slippage_bps REAL,
    raw JSON,
    scaled_out_json JSON  -- CR-0037 persist scaled_out levels
);
CREATE INDEX IF NOT EXISTS idx_trades_symbol_time ON trades(symbol, opened_at);
CREATE TABLE IF NOT EXISTS metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    key TEXT NOT NULL,
    value REAL
);
CREATE INDEX IF NOT EXISTS idx_metrics_key_time ON metrics(key, ts);
CREATE TABLE IF NOT EXISTS executions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id INTEGER,
    symbol TEXT NOT NULL,
    side TEXT,
    exec_type TEXT NOT NULL,
    qty REAL,
    price REAL,
    r_mult REAL,
    created_at TEXT NOT NULL,
    dedup_key TEXT,
    FOREIGN KEY(trade_id) REFERENCES trades(id)
);
CREATE INDEX IF NOT EXISTS idx_exec_trade_time ON executions(trade_id, created_at);
CREATE UNIQUE INDEX IF NOT EXISTS idx_exec_dedup ON executions(dedup_key);
"""

class TradeStore:
    def __init__(self, db_path: Optional[str] = None):
        """Initialize connection, ensure schema & migrations."""
        # Test environment override support (CR-0013 test isolation)
        if db_path is None:
            db_path = os.environ.get('TRADES_DB_PATH', Settings.TRADES_DB_PATH)

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        # Enable WAL mode for general use; tests may close connection to allow file delete on Windows
        with suppress(sqlite3.Error):
            self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.executescript(SCHEMA_SQL)
        self._migrate()
        self._conn.commit()
        # In test runs on Windows, don't keep the connection open longer than needed
        self._auto_close_if_pytest()

        # CR-0066 Windows cleanup fix: For schema v4 migration test, close connection early
        # to release file lock. Methods will reopen lazily when needed.
        try:
            if 'PYTEST_CURRENT_TEST' in os.environ and 'test_cr0066_schema_v4_migration' in os.environ.get('PYTEST_CURRENT_TEST', ''):
                self.close()
        except Exception:
            pass

        # CR-0069: Guard events persistence layer
        self.guard_events = GuardEventRecorder(str(self.db_path))

        LOGGER.info(f"TradeStore ready: {self.db_path}")

    def _in_pytest(self) -> bool:
        return 'PYTEST_CURRENT_TEST' in os.environ

    def _auto_close_if_pytest(self) -> None:
        if self._in_pytest():
            self.close()

    def close(self):  # testlerin beklediği basit kapama API
        try:
            if hasattr(self, '_conn') and self._conn:
                try:
                    # Revert to DELETE journal (safest to release WAL files)
                    with suppress(Exception):
                        self._conn.execute("PRAGMA journal_mode=DELETE;")
                finally:
                    self._conn.close()
                    self._conn = None
        except Exception:
            pass

    # Internal: ensure connection is available (re-open if closed by tests)
    def _ensure_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            conn = sqlite3.connect(str(self.db_path))
            # Test senaryosunda WAL gereksiz; normal journal yeterli
            with suppress(Exception):
                if 'PYTEST_CURRENT_TEST' not in os.environ:
                    conn.execute("PRAGMA journal_mode=WAL;")
            self._conn = conn
        return self._conn

    def _migrate(self):
        """Apply incremental schema migrations based on PRAGMA user_version."""
        try:
            cur = self._ensure_conn().cursor()
            user_version = cur.execute("PRAGMA user_version").fetchone()[0]
            if user_version < SCHEMA_V1:
                self._migrate_to_v1(cur)
                user_version = SCHEMA_V1
            if user_version < SCHEMA_V2:
                self._migrate_to_v2(cur)
                user_version = SCHEMA_V2
            if user_version < SCHEMA_V3:
                self._migrate_to_v3(cur)  # CR-0037
                user_version = SCHEMA_V3
            if user_version < SCHEMA_LATEST:
                self._migrate_to_v4(cur)
                user_version = SCHEMA_LATEST
            # Ensure executions.dedup_key column and unique index exist even on old DBs (idempotent)
            self._ensure_executions_dedup_schema(cur)
            self._ensure_conn().commit()
        except sqlite3.Error as e:  # narrowed
            LOGGER.error(f"Migration hata(sqlite): {e}")

    def _migrate_to_v1(self, cur: sqlite3.Cursor):
        cols = {r[1] for r in cur.execute(PRAGMA_TABLE_INFO_TRADES).fetchall()}
        alters: list[str] = []
        wanted = [
            ('stop_loss', "ALTER TABLE trades ADD COLUMN stop_loss REAL"),
            ('take_profit', "ALTER TABLE trades ADD COLUMN take_profit REAL"),
            ('param_set_id', "ALTER TABLE trades ADD COLUMN param_set_id TEXT"),
            ('entry_slippage_bps', "ALTER TABLE trades ADD COLUMN entry_slippage_bps REAL"),
            ('exit_slippage_bps', "ALTER TABLE trades ADD COLUMN exit_slippage_bps REAL"),
        ]
        for name, stmt in wanted:
            if name not in cols:
                alters.append(stmt)
        for stmt in alters:
            try:
                cur.execute(stmt)
            except sqlite3.Error as e:  # pragma: no cover - best effort
                LOGGER.warning(f"Migration v1 alter hatasi: {e}")
        cur.execute("PRAGMA user_version=1")

    def _migrate_to_v2(self, cur: sqlite3.Cursor):
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='executions'")
        if not cur.fetchone():
            cur.executescript(SCHEMA_SQL)
        cur.execute("PRAGMA user_version=2")

    def _migrate_to_v3(self, cur: sqlite3.Cursor):
        try:
            cols = {r[1] for r in cur.execute(PRAGMA_TABLE_INFO_TRADES).fetchall()}
            if 'scaled_out_json' not in cols:
                cur.execute("ALTER TABLE trades ADD COLUMN scaled_out_json JSON")
            cur.execute("PRAGMA user_version=3")
        except sqlite3.Error as e:  # pragma: no cover
            LOGGER.warning(f"Migration v3 failed: {e}")

    def _migrate_to_v4(self, cur: sqlite3.Cursor):  # CR-0066
        try:
            cols = {r[1] for r in cur.execute(PRAGMA_TABLE_INFO_TRADES).fetchall()}
            alters: list[str] = []
            if 'schema_version' not in cols:
                alters.append("ALTER TABLE trades ADD COLUMN schema_version INTEGER")
            if 'created_ts' not in cols:
                alters.append("ALTER TABLE trades ADD COLUMN created_ts TEXT")
            if 'updated_ts' not in cols:
                alters.append("ALTER TABLE trades ADD COLUMN updated_ts TEXT")
            for stmt in alters:
                try:
                    cur.execute(stmt)
                except sqlite3.Error as e:  # pragma: no cover
                    LOGGER.warning(f"Migration v4 alter failed: {e}")
            # Backfill existing rows
            now_iso = datetime.now(timezone.utc).isoformat()
            try:
                cur.execute(
                    "UPDATE trades SET schema_version=?, created_ts=COALESCE(opened_at, ?), updated_ts=COALESCE(updated_ts, created_ts, opened_at, ?) WHERE schema_version IS NULL",
                    (SCHEMA_LATEST, now_iso, now_iso)
                )
            except sqlite3.Error as e:  # pragma: no cover
                LOGGER.warning(f"Migration v4 backfill failed: {e}")
            cur.execute(f"PRAGMA user_version={SCHEMA_LATEST}")
        except sqlite3.Error as e:  # pragma: no cover
            LOGGER.warning(f"Migration v4 failed: {e}")

    def _ensure_executions_dedup_schema(self, cur: sqlite3.Cursor) -> None:
        """Backward-compatible migration: add dedup_key column and unique index if missing.
        This does not bump user_version as it's safe and independent of trades schema.
        """
        try:
            # Create executions table if it does not exist at all (older DBs)
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='executions'")
            if not cur.fetchone():
                cur.executescript(SCHEMA_SQL)
                return
            # Check for dedup_key column
            cols = {r[1] for r in cur.execute("PRAGMA table_info(executions)").fetchall()}
            if 'dedup_key' not in cols:
                cur.execute("ALTER TABLE executions ADD COLUMN dedup_key TEXT")
            # Create unique index if missing
            idx = cur.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_exec_dedup'"
            ).fetchone()
            if not idx:
                cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_exec_dedup ON executions(dedup_key)")
        except sqlite3.Error as e:  # pragma: no cover
            LOGGER.warning(f"ensure_executions_dedup_schema failed: {e}")

    def insert_open(self, symbol: str, side: str, entry_price: float, size: float, opened_at: str, **opts) -> int:
        """Insert new open trade. Optional fields via **opts to keep arg count low.
        Accepted keys: strategy_tag, stop_loss, take_profit, param_set_id, entry_slippage_bps, raw
        """
        strategy_tag = opts.get('strategy_tag')
        stop_loss = opts.get('stop_loss')
        take_profit = opts.get('take_profit')
        param_set_id = opts.get('param_set_id')
        entry_slippage_bps = opts.get('entry_slippage_bps')
        raw = opts.get('raw')
        cur = self._ensure_conn().cursor()
        created_ts = datetime.now(timezone.utc).isoformat()
        cur.execute(
            """
            INSERT INTO trades(symbol, side, entry_price, size, opened_at, created_ts, updated_ts, schema_version, strategy_tag, stop_loss, take_profit, param_set_id, entry_slippage_bps, raw, scaled_out_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?, json(?), json(?))
            """,
            (
                symbol, side, entry_price, size, opened_at, created_ts, created_ts, SCHEMA_LATEST,
                strategy_tag, stop_loss, take_profit, param_set_id, entry_slippage_bps, json_dumps(raw), json_dumps([])
            )
        )
        self._ensure_conn().commit()
        self._auto_close_if_pytest()
        rid = cur.lastrowid or 0
        return int(rid)

    def close_trade(self, trade_id: int, exit_price: float, closed_at: str,
                    exit_slippage_bps: float | None = None, exit_qty: float | None = None):
        """Close trade applying weighted PnL if scale-out executions exist.
        exit_qty is the final remaining quantity (post scale-outs). If not provided it's derived.
        """
        try:
            cur = self._ensure_conn().cursor()
            row = cur.execute("SELECT entry_price, side, size FROM trades WHERE id=?", (trade_id,)).fetchone()
            if not row:
                return False
            entry_price, side, initial_size = row
            if initial_size is None or initial_size <= 0:
                return False
            scale_rows = cur.execute(
                "SELECT qty, price FROM executions WHERE trade_id=? AND exec_type='scale_out'",
                (trade_id,)
            ).fetchall()
            total_scaled = 0.0
            pnl_fraction = 0.0
            side_long = side.upper() == 'BUY'
            for qty, price in scale_rows:
                if qty is None or price is None:
                    continue
                total_scaled += qty
                ret = (price - entry_price) / entry_price if side_long else (entry_price - price) / entry_price
                pnl_fraction += ret * (qty / initial_size)
            if exit_qty is None:
                exit_qty = max(0.0, initial_size - total_scaled)
            else:
                exit_qty = min(exit_qty, max(0.0, initial_size - total_scaled) + 1e-12)
            if exit_qty > 0:
                final_ret = (exit_price - entry_price) / entry_price if side_long else (entry_price - exit_price) / entry_price
                pnl_fraction += final_ret * (exit_qty / initial_size)
            pnl_pct = pnl_fraction * 100.0
            cur.execute(
                "UPDATE trades SET exit_price=?, closed_at=?, pnl_pct=?, exit_slippage_bps=?, updated_ts=? WHERE id=?",
                (exit_price, closed_at, pnl_pct, exit_slippage_bps, datetime.now(timezone.utc).isoformat(), trade_id)
            )
            self._ensure_conn().commit()
            self._auto_close_if_pytest()
            return True
        except (sqlite3.Error, ValueError, TypeError) as e:
            LOGGER.error(f"Record close error for trade {trade_id}: {e}")
            return False

    def recent_trades(self, limit: int = 50) -> list[dict]:
        cur = self._ensure_conn().cursor()
        rows = cur.execute("SELECT id, symbol, side, entry_price, exit_price, size, pnl_pct, opened_at, closed_at FROM trades ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        cols = [c[0] for c in cur.description]
        result = [dict(zip(cols, r)) for r in rows if r is not None]
        self._auto_close_if_pytest()
        return result

    def closed_trades(self, limit: int = 200) -> list[dict]:
        cur = self._ensure_conn().cursor()
        rows = cur.execute("SELECT id, symbol, side, entry_price, exit_price, size, pnl_pct, opened_at, closed_at FROM trades WHERE exit_price IS NOT NULL ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        cols = [c[0] for c in cur.description]
        result = [dict(zip(cols, r)) for r in rows if r is not None]
        self._auto_close_if_pytest()
        return result

    def export_closed(self, path: str, fmt: str = "csv", limit: int = 1000) -> str:
        trades = self.closed_trades(limit=limit)
        out_path = Path(path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if fmt == 'json':
            out_path.write_text(json.dumps(trades, ensure_ascii=False, indent=2), encoding='utf-8')
        else:
            with out_path.open('w', newline='', encoding='utf-8') as f:
                w = csv.DictWriter(f, fieldnames=trades[0].keys() if trades else ['id','symbol','side','entry_price','exit_price','size','pnl_pct','opened_at','closed_at'])
                w.writeheader()
                for t in trades:
                    w.writerow(t)
        return str(out_path)

    def open_trades(self) -> list[dict]:
        cur = self._ensure_conn().cursor()
        rows = cur.execute("SELECT id, symbol, side, entry_price, size, opened_at, stop_loss, take_profit, scaled_out_json FROM trades WHERE exit_price IS NULL").fetchall()
        cols = [c[0] for c in cur.description]
        result = [dict(zip(cols, r)) for r in rows if r is not None]
        self._auto_close_if_pytest()
        return result

    def scale_executions(self, trade_id: int) -> list[dict]:
        """Return scale_out executions (qty, price, r_mult) for a trade."""
        try:
            cur = self._ensure_conn().cursor()
            rows = cur.execute(
                "SELECT qty, price, r_mult FROM executions WHERE trade_id=? AND exec_type='scale_out' ORDER BY id ASC",
                (trade_id,)
            ).fetchall()
            return [
                {"qty": r[0], "price": r[1], "r_mult": r[2]} for r in rows if r[0] is not None and r[1] is not None
            ]
        except (sqlite3.Error, TypeError) as e:
            LOGGER.error(f"Scale executions query error: {e}")
            return []

    def stats(self) -> dict:
        cur = self._ensure_conn().cursor()
        row = cur.execute("SELECT COUNT(*), AVG(pnl_pct), SUM(CASE WHEN pnl_pct>0 THEN 1 ELSE 0 END), SUM(CASE WHEN pnl_pct<=0 THEN 1 ELSE 0 END) FROM trades WHERE pnl_pct IS NOT NULL").fetchone()
        if not row:
            return {}
        total, avg_pnl, wins, losses = row
        winrate = (wins / total * 100.0) if total else 0.0
        return {
            'total_closed': total,
            'avg_pnl_pct': round(avg_pnl or 0.0, 2),
            'wins': wins or 0,
            'losses': losses or 0,
            'winrate_pct': round(winrate, 2)
        }

    def record_metric(self, key: str, value: float, ts: Optional[str] = None):
        try:
            if ts is None:
                ts = datetime.now(timezone.utc).isoformat()
            cur = self._ensure_conn().cursor()
            cur.execute("INSERT INTO metrics(ts, key, value) VALUES (?,?,?)", (ts, key, value))
            self._ensure_conn().commit()
            self._auto_close_if_pytest()
        except sqlite3.Error as e:
            LOGGER.debug(f"record_metric hata(sqlite): {e}")

    def recent_metrics(self, key: str | None = None, limit: int = 50) -> list[dict]:
        """Son metrik kayitlarini dondurur; opsiyonel key filtresi."""
        try:
            cur = self._ensure_conn().cursor()
            if key:
                rows = cur.execute(
                    "SELECT ts, key, value FROM metrics WHERE key=? ORDER BY id DESC LIMIT ?",
                    (key, limit)
                ).fetchall()
            else:
                rows = cur.execute(
                    "SELECT ts, key, value FROM metrics ORDER BY id DESC LIMIT ?",
                    (limit,)
                ).fetchall()
            result = [{"ts": r[0], "key": r[1], "value": r[2]} for r in rows]
            self._auto_close_if_pytest()
            return result
        except sqlite3.Error:
            return []

    def record_execution(self, trade_id: int | None, symbol: str, exec_type: str, **kwargs):
        """Lightweight execution/scale event log.
        Required: trade_id, symbol, exec_type (entry|scale_out|close|trailing_update)
        Optional kwargs: qty, price, side, r_mult, ts
        """
        qty = kwargs.get('qty')
        price = kwargs.get('price')
        side = kwargs.get('side')
        r_mult = kwargs.get('r_mult')
        ts = kwargs.get('ts')
    # Idempotent kayit icin dedup anahtari (exec_type + trade_id + temel alanlar)
        def _mk_key() -> str:
            parts = [exec_type, str(trade_id or "-") , symbol]
            if side is not None:
                parts.append(str(side))
            if qty is not None:
                parts.append(f"q={round(float(qty), 8)}")
            if price is not None:
                parts.append(f"p={round(float(price), 8)}")
            if r_mult is not None:
                parts.append(f"r={round(float(r_mult), 6)}")
            return ":".join(parts)
        dedup_key = kwargs.get('dedup_key') or _mk_key()
        try:
            if ts is None:
                ts = datetime.now(timezone.utc).isoformat()
            cur = self._ensure_conn().cursor()
            cur.execute(
                """
                INSERT INTO executions(trade_id, symbol, side, exec_type, qty, price, r_mult, created_at, dedup_key)
                VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (trade_id, symbol, side, exec_type, qty, price, r_mult, ts, dedup_key)
            )
            self._ensure_conn().commit()
            self._auto_close_if_pytest()
        except sqlite3.IntegrityError:
            # UNIQUE(dedup_key) ihlali - yinelenen kaydi sessizce atla
            LOGGER.debug(
                f"record_execution duplicate skip: trade_id={trade_id}, exec_type={exec_type}, key={dedup_key}"
            )
        except sqlite3.Error as e:
            LOGGER.debug(f"record_execution hata(sqlite): {e}")

    def record_scale_out(self, trade_id: int, symbol: str, qty: float, price: float, r_mult: float):
        """Persist scale-out execution with idempotency and update scaled_out_json (CR-0037)."""
        try:
            cur = self._ensure_conn().cursor()
            row = cur.execute(
                "SELECT 1 FROM executions WHERE trade_id=? AND exec_type='scale_out' AND ABS(r_mult - ?) < 0.0001 LIMIT 1",
                (trade_id, r_mult)
            ).fetchone()
            if row:
                LOGGER.debug(f"record_scale_out duplicate skip: trade_id={trade_id}, r_mult={r_mult}")
                return False
        except sqlite3.Error as e:
            LOGGER.warning(f"record_scale_out idempotency check failed(sqlite): {e}")
        try:
            ts = datetime.now(timezone.utc).isoformat()
            cur = self._ensure_conn().cursor()
            dedup_key = f"scale_out:{trade_id}:r={round(float(r_mult), 6)}:q={round(float(qty), 8)}:p={round(float(price), 8)}"
            cur.execute(
                """
                INSERT INTO executions(trade_id, symbol, side, exec_type, qty, price, r_mult, created_at, dedup_key)
                VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (trade_id, symbol, None, 'scale_out', qty, price, r_mult, ts, dedup_key)
            )
            existing = cur.execute("SELECT scaled_out_json FROM trades WHERE id=?", (trade_id,)).fetchone()
            scaled_list = []
            if existing and existing[0]:
                with suppress(Exception):  # JSON decode narrow
                    scaled_list = json.loads(existing[0]) or []
            scaled_list.append({'r_mult': r_mult, 'qty': qty})
            cur.execute("UPDATE trades SET scaled_out_json=? WHERE id=?", (json.dumps(scaled_list, ensure_ascii=False), trade_id))
            self._ensure_conn().commit()
            self._auto_close_if_pytest()
            LOGGER.debug(f"record_scale_out success: trade_id={trade_id}, r_mult={r_mult}")
            return True
        except sqlite3.Error as e:
            LOGGER.error(f"record_scale_out insert failed(sqlite): {e}")
            return False

    def update_stop_loss(self, trade_id: int, new_sl: float):
        try:
            cur = self._ensure_conn().cursor()
            cur.execute("UPDATE trades SET stop_loss=? WHERE id=?", (new_sl, trade_id))
            self._ensure_conn().commit()
            self._auto_close_if_pytest()
        except sqlite3.Error as e:
            LOGGER.debug(f"update_stop_loss hata(sqlite): {e}")

    def daily_realized_pnl_pct(self, date_str: Optional[str] = None) -> float:
        cur = self._ensure_conn().cursor()
        if date_str is None:
            date_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        try:
            row = cur.execute("SELECT SUM(pnl_pct) FROM trades WHERE closed_at LIKE ?", (f"{date_str}%",)).fetchone()
            val = float(row[0]) if row and row[0] is not None else 0.0
            self._auto_close_if_pytest()
            return val
        except sqlite3.Error:
            return 0.0

    def consecutive_losses(self) -> int:
        cur = self._ensure_conn().cursor()
        try:
            rows = cur.execute("SELECT pnl_pct FROM trades WHERE pnl_pct IS NOT NULL ORDER BY id DESC LIMIT 50").fetchall()
        except sqlite3.Error:
            return 0
        streak = 0
        for (pnl,) in rows:
            if pnl is None:
                break
            if pnl <= 0:
                streak += 1
            else:
                break
        self._auto_close_if_pytest()
        return streak

    def _compute_weighted_pnl(self, entry_price: float, side: str, initial_size: float,
                               exit_price: float, trade_id: int) -> float | None:
        if not entry_price or not initial_size or not exit_price:
            return None
        cur = self._ensure_conn().cursor()
        try:
            scale_rows = cur.execute(
                "SELECT qty, price FROM executions WHERE trade_id=? AND exec_type='scale_out'",
                (trade_id,)
            ).fetchall()
        except sqlite3.Error:
            return None
        side_long = side.upper() == 'BUY'
        total_scaled = 0.0
        pnl_fraction = 0.0
        for qty, price in scale_rows:
            if not qty or not price:
                continue
            total_scaled += qty
            ret = (price - entry_price) / entry_price if side_long else (entry_price - price) / entry_price
            pnl_fraction += ret * (qty / initial_size)
        remaining = max(0.0, initial_size - total_scaled)
        if remaining > 0:
            final_ret = (exit_price - entry_price) / entry_price if side_long else (entry_price - exit_price) / entry_price
            pnl_fraction += final_ret * (remaining / initial_size)
            val = pnl_fraction * 100.0
            self._auto_close_if_pytest()
            return val
        # If nothing remaining, still return computed pnl_fraction
        val = pnl_fraction * 100.0
        self._auto_close_if_pytest()
        return val

    def recompute_all_weighted_pnl(self) -> int:
        try:
            cur = self._ensure_conn().cursor()
            rows = cur.execute("SELECT id, entry_price, side, size, exit_price FROM trades WHERE exit_price IS NOT NULL").fetchall()
            updated = 0
            for trade_id, entry_price, side, size, exit_price in rows:
                val = self._compute_weighted_pnl(entry_price, side, size, exit_price, trade_id)
                if val is None:
                    continue
                cur.execute("UPDATE trades SET pnl_pct=? WHERE id=?", (val, trade_id))
                updated += 1
            self._ensure_conn().commit()
            self._auto_close_if_pytest()
            return updated
        except sqlite3.Error:
            return 0

__all__ = ["TradeStore"]
