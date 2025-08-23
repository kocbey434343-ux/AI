import csv
import json
import sqlite3
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from config.settings import Settings
from src.utils.logger import get_logger

LOGGER = get_logger("TradeStore")
SCHEMA_LATEST = 2

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
    strategy_tag TEXT,
    stop_loss REAL,
    take_profit REAL,
    param_set_id TEXT,
    entry_slippage_bps REAL,
    exit_slippage_bps REAL,
    raw JSON
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
    FOREIGN KEY(trade_id) REFERENCES trades(id)
);
CREATE INDEX IF NOT EXISTS idx_exec_trade_time ON executions(trade_id, created_at);
"""

class TradeStore:
    def __init__(self, db_path: Optional[str] = None):
        """Initialize connection, ensure schema & migrations."""
        self.db_path = Path(db_path or Settings.TRADES_DB_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.executescript(SCHEMA_SQL)
        self._migrate()
        self._conn.commit()
        LOGGER.info(f"TradeStore hazir: {self.db_path}")

    def _migrate(self):
        """Apply incremental schema migrations based on PRAGMA user_version."""
        try:
            cur = self._conn.cursor()
            user_version = cur.execute("PRAGMA user_version").fetchone()[0]
            if user_version < 1:
                self._migrate_to_v1(cur)
                user_version = 1
            if user_version < SCHEMA_LATEST:
                self._migrate_to_v2(cur)
                user_version = SCHEMA_LATEST
            self._conn.commit()
        except Exception as e:
            LOGGER.error(f"Migration hata: {e}")

    def _migrate_to_v1(self, cur: sqlite3.Cursor):
        cols = {r[1] for r in cur.execute("PRAGMA table_info(trades)").fetchall()}
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
            except Exception as e:  # pragma: no cover - best effort
                LOGGER.warning(f"Migration v1 alter hatasi: {e}")
        cur.execute("PRAGMA user_version=1")

    def _migrate_to_v2(self, cur: sqlite3.Cursor):
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='executions'")
        if not cur.fetchone():
            cur.executescript(SCHEMA_SQL)
        cur.execute("PRAGMA user_version=2")

    # Context manager helpers
    def __enter__(self):  # pragma: no cover - convenience
        return self

    def __exit__(self, exc_type, exc, tb):  # pragma: no cover - convenience
        self.close()

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
        cur = self._conn.cursor()
        cur.execute(
            """
            INSERT INTO trades(symbol, side, entry_price, size, opened_at, strategy_tag, stop_loss, take_profit, param_set_id, entry_slippage_bps, raw)
            VALUES (?,?,?,?,?,?,?,?,?,?, json(?))
            """,
            (
                symbol, side, entry_price, size, opened_at, strategy_tag, stop_loss, take_profit,
                param_set_id, entry_slippage_bps, json_dumps(raw)
            )
        )
        self._conn.commit()
        rid = cur.lastrowid or 0
        return int(rid)

    def close_trade(self, trade_id: int, exit_price: float, closed_at: str,
                    exit_slippage_bps: float | None = None, exit_qty: float | None = None):
        """Close trade applying weighted PnL if scale-out executions exist.
        exit_qty is the final remaining quantity (post scale-outs). If not provided it's derived.
        """
        try:
            cur = self._conn.cursor()
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
                "UPDATE trades SET exit_price=?, closed_at=?, pnl_pct=?, exit_slippage_bps=? WHERE id=?",
                (exit_price, closed_at, pnl_pct, exit_slippage_bps, trade_id)
            )
            self._conn.commit()
            return True
        except Exception:
            return False

    def recent_trades(self, limit: int = 50) -> list[dict]:
        cur = self._conn.cursor()
        rows = cur.execute("SELECT id, symbol, side, entry_price, exit_price, size, pnl_pct, opened_at, closed_at FROM trades ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, r)) for r in rows]

    def closed_trades(self, limit: int = 200) -> list[dict]:
        cur = self._conn.cursor()
        rows = cur.execute("SELECT id, symbol, side, entry_price, exit_price, size, pnl_pct, opened_at, closed_at FROM trades WHERE exit_price IS NOT NULL ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, r)) for r in rows]

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
        cur = self._conn.cursor()
        rows = cur.execute("SELECT id, symbol, side, entry_price, size, opened_at, stop_loss, take_profit FROM trades WHERE exit_price IS NULL").fetchall()
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, r)) for r in rows]

    def scale_executions(self, trade_id: int) -> list[dict]:
        """Return scale_out executions (qty, price, r_mult) for a trade."""
        try:
            cur = self._conn.cursor()
            rows = cur.execute(
                "SELECT qty, price, r_mult FROM executions WHERE trade_id=? AND exec_type='scale_out' ORDER BY id ASC",
                (trade_id,)
            ).fetchall()
            return [
                {"qty": r[0], "price": r[1], "r_mult": r[2]} for r in rows if r[0] is not None and r[1] is not None
            ]
        except Exception:
            return []

    def stats(self) -> dict:
        cur = self._conn.cursor()
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
            cur = self._conn.cursor()
            cur.execute("INSERT INTO metrics(ts, key, value) VALUES (?,?,?)", (ts, key, value))
            self._conn.commit()
        except Exception as e:
            LOGGER.debug(f"record_metric hata: {e}")

    def recent_metrics(self, key: str | None = None, limit: int = 50) -> list[dict]:
        """Son metrik kayitlarini dondurur; opsiyonel key filtresi."""
        try:
            cur = self._conn.cursor()
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
            return [
                {"ts": r[0], "key": r[1], "value": r[2]} for r in rows
            ]
        except Exception:
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
        try:
            if ts is None:
                ts = datetime.now(timezone.utc).isoformat()
            cur = self._conn.cursor()
            cur.execute(
                """
                INSERT INTO executions(trade_id, symbol, side, exec_type, qty, price, r_mult, created_at)
                VALUES (?,?,?,?,?,?,?,?)
                """,
                (trade_id, symbol, side, exec_type, qty, price, r_mult, ts)
            )
            self._conn.commit()
        except Exception as e:
            LOGGER.debug(f"record_execution hata: {e}")

    def update_stop_loss(self, trade_id: int, new_sl: float):
        try:
            cur = self._conn.cursor()
            cur.execute("UPDATE trades SET stop_loss=? WHERE id=?", (new_sl, trade_id))
            self._conn.commit()
        except Exception as e:
            LOGGER.debug(f"update_stop_loss hata: {e}")

    def daily_realized_pnl_pct(self, date_str: Optional[str] = None) -> float:
        cur = self._conn.cursor()
        if date_str is None:
            # YYYY-MM-DD prefix match (UTC date)
            date_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        row = cur.execute("SELECT SUM(pnl_pct) FROM trades WHERE closed_at LIKE ?", (f"{date_str}%",)).fetchone()
        return float(row[0]) if row and row[0] is not None else 0.0

    def consecutive_losses(self) -> int:
        cur = self._conn.cursor()
        # Count from latest backwards until a win encountered
        rows = cur.execute("SELECT pnl_pct FROM trades WHERE pnl_pct IS NOT NULL ORDER BY id DESC LIMIT 50").fetchall()
        streak = 0
        for (pnl,) in rows:
            if pnl is None:
                break
            if pnl <= 0:
                streak += 1
            else:
                break
        return streak

    def close(self):
        with suppress(Exception):
            self._conn.close()

    # ------------ Recompute / Backfill Utilities ------------
    def _compute_weighted_pnl(self, entry_price: float, side: str, initial_size: float,
                               exit_price: float, trade_id: int) -> float | None:
        if not entry_price or not initial_size or not exit_price:
            return None
        cur = self._conn.cursor()
        scale_rows = cur.execute(
            "SELECT qty, price FROM executions WHERE trade_id=? AND exec_type='scale_out'",
            (trade_id,)
        ).fetchall()
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
        return pnl_fraction * 100.0

    def recompute_all_weighted_pnl(self) -> int:
        """Recompute weighted pnl_pct for already closed trades.
        Returns: number of updated rows.
        """
        try:
            cur = self._conn.cursor()
            rows = cur.execute("SELECT id, entry_price, side, size, exit_price FROM trades WHERE exit_price IS NOT NULL").fetchall()
            updated = 0
            for trade_id, entry_price, side, size, exit_price in rows:
                val = self._compute_weighted_pnl(entry_price, side, size, exit_price, trade_id)
                if val is None:
                    continue
                cur.execute("UPDATE trades SET pnl_pct=? WHERE id=?", (val, trade_id))
                updated += 1
            self._conn.commit()
            return updated
        except Exception:
            return 0

def json_dumps(obj: Any) -> str | None:
    try:
        return json.dumps(obj, ensure_ascii=False) if obj is not None else None
    except Exception:
        return None

__all__ = ["TradeStore"]
