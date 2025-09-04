"""Guard Events Persistence (CR-0069)

Event persistence layer for tracking guard system behavior.
Records structured data when guards are triggered.
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
from contextlib import suppress
from datetime import datetime, timezone
from typing import Any, Dict, List, NamedTuple, Optional

from src.utils.logger import get_logger

# Ensure shared cache is disabled (Windows file lock hygiene)
with suppress(Exception):
    sqlite3.enable_shared_cache(False)

LOGGER = get_logger("GuardEvents")

# Windows: context exit'te minimal gecikme ile dosya kilidi serbest birakma
if os.name == 'nt':
    try:
        _orig_connect = sqlite3.connect

        class _ConnectionProxy:
            def __init__(self, conn: sqlite3.Connection):
                object.__setattr__(self, '_c', conn)

            def __getattr__(self, name):
                return getattr(object.__getattribute__(self, '_c'), name)

            def __setattr__(self, name, value):
                if name == '_c':
                    object.__setattr__(self, name, value)
                else:
                    setattr(object.__getattribute__(self, '_c'), name, value)

            def __enter__(self):
                return object.__getattribute__(self, '_c')

            def __exit__(self, exc_type, exc, tb):
                c = object.__getattribute__(self, '_c')
                # Mirror sqlite3 Connection CM semantics (commit on success, rollback on error)
                if exc_type is None:
                    with suppress(Exception):
                        c.commit()
                else:
                    with suppress(Exception):
                        c.rollback()
                with suppress(Exception):
                    c.close()
                # Minimal pause to let Windows release file handle (300ms)
                with suppress(Exception):
                    time.sleep(0.3)
                return False

        def _patched_connect(*args, **kwargs):
            return _ConnectionProxy(_orig_connect(*args, **kwargs))

        sqlite3.connect = _patched_connect  # type: ignore[assignment]
    except Exception:
        pass


class GuardEvent(NamedTuple):
    """Guard event data structure for cleaner API."""
    guard: str
    reason: str
    symbol: Optional[str] = None
    extra_data: Optional[Dict[str, Any]] = None
    severity: str = "INFO"
    blocked: bool = True
    session_id: Optional[str] = None

# Guard events schema - supports telemetry and debugging
GUARD_EVENTS_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS guard_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,                 -- ISO timestamp
    guard TEXT NOT NULL,              -- Guard type: halt_flag, daily_loss, etc
    symbol TEXT,                      -- Symbol (if applicable)
    reason TEXT NOT NULL,             -- Human readable reason
    extra TEXT,                       -- JSON extra data (thresholds, values, etc)
    session_id TEXT,                  -- Session tracking (optional)
    severity TEXT DEFAULT 'INFO',     -- INFO, WARNING, CRITICAL
    blocked BOOLEAN DEFAULT 1,        -- Whether trade was blocked
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_guard_events_ts ON guard_events(ts);
CREATE INDEX IF NOT EXISTS idx_guard_events_guard ON guard_events(guard);
CREATE INDEX IF NOT EXISTS idx_guard_events_symbol ON guard_events(symbol);
"""

class GuardEventRecorder:
    """Centralized guard event recording system.

    Thread-safe, minimal performance impact, structured data storage.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_schema()

    def _close_safely(self, conn: sqlite3.Connection) -> None:
        """Platform-dostu kapatma: Windows'ta handle serbest birakma icin kisa gecikme."""
        with suppress(Exception):
            conn.close()
        if os.name == 'nt':
            with suppress(Exception):
                # Performans için mikro bekleme (gerektiğinde ~1ms)
                time.sleep(0.001)

    def _post_close_pause(self) -> None:
        """Windows dosya kilidi serbest birakma icin ek bekleme."""
        if os.name == 'nt':
            with suppress(Exception):
                # Varsayilan olarak bekleme yok (performans)
                # time.sleep(0) NOP
                time.sleep(0)

    def _connect(self) -> sqlite3.Connection:
        """Create a SQLite connection with Windows-friendly settings.

        - Force journal_mode=DELETE to avoid WAL side files that keep locks on Windows.
        - Keep synchronous at NORMAL for reasonable durability without extra I/O.
        """
        conn = sqlite3.connect(self.db_path, timeout=1.0)
        # Test ortaminda (Windows) dosya kilitlerini azaltmak icin MEMORY journaling
        if os.name == 'nt' and os.getenv('PYTEST_CURRENT_TEST'):
            with suppress(Exception):
                conn.execute("PRAGMA journal_mode=MEMORY;")
            with suppress(Exception):
                conn.execute("PRAGMA synchronous=OFF;")
            with suppress(Exception):
                conn.execute("PRAGMA temp_store=MEMORY;")
        else:
            with suppress(Exception):
                conn.execute("PRAGMA journal_mode=DELETE;")
        return conn

    def _init_schema(self) -> None:
        """Initialize guard_events table if not exists."""
        with suppress(Exception):
            conn = self._connect()
            try:
                conn.executescript(GUARD_EVENTS_SCHEMA_SQL)
                conn.commit()
            finally:
                self._close_safely(conn)
                self._post_close_pause()

    def record_guard_event(self, event: GuardEvent) -> None:
        """Record a guard event with structured data.

        Args:
            event: GuardEvent instance with all event data
        """
        try:
            ts = datetime.now(timezone.utc).isoformat()
            extra_json = json.dumps(event.extra_data) if event.extra_data else None

            conn = self._connect()
            try:
                conn.execute("""
                    INSERT INTO guard_events
                    (ts, guard, symbol, reason, extra, session_id, severity, blocked)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (ts, event.guard, event.symbol, event.reason, extra_json,
                     event.session_id, event.severity, event.blocked))
                conn.commit()
            finally:
                self._close_safely(conn)
                self._post_close_pause()
        except Exception as e:
            LOGGER.warning(f"Failed to record guard event: {e}")

    def record_guard_event_simple(
        self, guard: str, reason: str, symbol: Optional[str] = None
    ) -> None:
        """Simplified guard event recording for common cases.

        Args:
            guard: Guard identifier
            reason: Human readable reason
            symbol: Symbol if applicable
        """
        event = GuardEvent(guard=guard, reason=reason, symbol=symbol)
        self.record_guard_event(event)

    def get_guard_events(
        self,
        guard: Optional[str] = None,
        symbol: Optional[str] = None,
        hours_back: int = 24,
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """Query guard events with filters.

        Args:
            guard: Filter by guard type
            symbol: Filter by symbol
            hours_back: Hours to look back from now
            limit: Max results

        Returns:
            List of guard event records
        """
        try:
            conn = self._connect()
            try:
                conn.row_factory = sqlite3.Row

                where_clauses = []
                params = []

                # Time filter
                where_clauses.append("datetime(ts) >= datetime('now', '-{} hours')".format(hours_back))

                if guard:
                    where_clauses.append("guard = ?")
                    params.append(guard)

                if symbol:
                    where_clauses.append("symbol = ?")
                    params.append(symbol)

                where_clause = " AND ".join(where_clauses)
                params.append(limit)

                cursor = conn.execute(f"""
                    SELECT * FROM guard_events
                    WHERE {where_clause}
                    ORDER BY ts DESC
                    LIMIT ?
                """, params)
                rows = cursor.fetchall()
                result: list[dict[str, Any]] = []
                for row in rows:
                    # sqlite3.Row supports keys(); get a static list of column names
                    try:
                        keys = list(row.keys())
                        result.append({k: row[k] for k in keys})
                    except Exception:
                        # Fallback: assume tuple-like row with cursor.description
                        desc = cursor.description or []
                        keys = [d[0] for d in desc]
                        result.append(dict(zip(keys, row)))
                return result
            finally:
                self._close_safely(conn)
                self._post_close_pause()
        except Exception as e:
            LOGGER.warning(f"Failed to query guard events: {e}")
            return []

    def get_guard_stats(self, hours_back: int = 24) -> Dict[str, Any]:
        """Get guard statistics for monitoring.

        Args:
            hours_back: Hours to analyze

        Returns:
            Statistics dict with counts, rates, top symbols etc
        """
        try:
            conn = self._connect()
            try:
                conn.row_factory = sqlite3.Row

                # Guard type counts
                cursor = conn.execute("""
                    SELECT guard, COUNT(*) as count
                    FROM guard_events
                    WHERE datetime(ts) >= datetime('now', '-{} hours')
                    GROUP BY guard
                    ORDER BY count DESC
                """.format(hours_back))
                guard_counts = {}
                for row in cursor.fetchall():
                    try:
                        guard_counts[row["guard"]] = row["count"]
                    except Exception:
                        guard_counts[row[0]] = row[1]

                # Symbol counts (top blocked symbols)
                cursor = conn.execute("""
                    SELECT symbol, COUNT(*) as count
                    FROM guard_events
                    WHERE datetime(ts) >= datetime('now', '-{} hours')
                      AND symbol IS NOT NULL
                      AND blocked = 1
                    GROUP BY symbol
                    ORDER BY count DESC
                    LIMIT 10
                """.format(hours_back))
                top_symbols = {}
                for row in cursor.fetchall():
                    try:
                        top_symbols[row["symbol"]] = row["count"]
                    except Exception:
                        top_symbols[row[0]] = row[1]

                # Total events
                cursor = conn.execute("""
                    SELECT COUNT(*) as total
                    FROM guard_events
                    WHERE datetime(ts) >= datetime('now', '-{} hours')
                """.format(hours_back))
                total_row = cursor.fetchone()
                total = total_row["total"] if isinstance(total_row, sqlite3.Row) else total_row[0]

                return {
                    "total_events": total,
                    "guard_counts": guard_counts,
                    "top_blocked_symbols": top_symbols,
                    "hours_analyzed": hours_back
                }
            finally:
                self._close_safely(conn)
                self._post_close_pause()
        except Exception as e:
            LOGGER.warning(f"Failed to get guard stats: {e}")
            return {"error": str(e)}

    def cleanup_old_events(self, days_to_keep: int = 30) -> int:
        """Clean up old guard events to prevent DB bloat.

        Args:
            days_to_keep: Number of days to retain

        Returns:
            Number of deleted records
        """
        try:
            conn = self._connect()
            try:
                cursor = conn.execute(
                    """
                    DELETE FROM guard_events
                    WHERE datetime(ts) < datetime('now', '-{} days')
                    """.format(days_to_keep)
                )
                with suppress(Exception):
                    conn.commit()
                deleted = cursor.rowcount
                LOGGER.info(f"Cleaned up {deleted} old guard events (kept {days_to_keep} days)")
                return deleted
            finally:
                self._close_safely(conn)
                self._post_close_pause()
        except Exception as e:
            LOGGER.warning(f"Failed to cleanup guard events: {e}")
            return 0
