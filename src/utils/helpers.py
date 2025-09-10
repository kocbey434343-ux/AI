from __future__ import annotations

import json
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, NamedTuple, Optional

import pandas as pd
from config.settings import Settings


def save_json(data, filename):
    """Veriyi JSON olarak kaydet"""
    filepath = f"{Settings.DATA_PATH}/processed/{filename}"
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2, default=str)
    return filepath

def load_json(filename):
    """JSON veriyi yükle"""
    filepath = f"{Settings.DATA_PATH}/processed/{filename}"
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return None

def save_csv(df, filename):
    """DataFrame'i CSV olarak kaydet"""
    filepath = f"{Settings.DATA_PATH}/processed/{filename}"
    df.to_csv(filepath, index=False)
    return filepath

def format_timestamp(ts):
    """Zaman damgasini formatla"""
    if isinstance(ts, pd.Timestamp):
        return ts.strftime('%Y-%m-%d %H:%M:%S')
    if isinstance(ts, str):
        return ts
    return datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')

def calculate_pnl(entry_price, exit_price, side, quantity):
    """Kar/zarar hesapla"""
    if side == "BUY":
        pnl = (exit_price - entry_price) * quantity
    else:  # SELL
        pnl = (entry_price - exit_price) * quantity
    return pnl

class Costs(NamedTuple):
    commission_pct_per_side: float
    slippage_pct_per_side: float

def calculate_net_pnl(entry_price: float, exit_price: float, side: str, quantity: float,
                      costs: Optional[Costs] = None) -> float:
    """Komisyon ve slippage dahil net PnL hesapla (USDT cinsinden).
    Parametreler yuzde cinsindedir (0.04 => %0.04).
    Round-trip maliyet modeli: her iki tarafta da (entry+exit) * (commission + slippage).
    """
    gross = calculate_pnl(entry_price, exit_price, side, quantity)
    commission_pct = (costs.commission_pct_per_side if costs is not None else Settings.COMMISSION_PCT_PER_SIDE)
    slippage_pct = (costs.slippage_pct_per_side if costs is not None else Settings.SLIPPAGE_PCT_PER_SIDE)
    traded_notional = (entry_price + exit_price) * quantity
    total_cost = traded_notional * ((commission_pct + slippage_pct) / 100.0)
    return gross - total_cost

def calculate_win_rate(trades):
    """Kazanma oranini hesapla"""
    if not trades:
        return 0

    wins = sum(1 for trade in trades if trade['pnl'] > 0)
    return wins / len(trades) * 100

def calculate_sharpe_ratio(returns, risk_free_rate=0.01):
    """Sharpe orani hesapla"""
    MIN_SAMPLES = 2
    if len(returns) < MIN_SAMPLES:
        return 0

    excess_returns = [r - risk_free_rate for r in returns]
    return (sum(excess_returns) / len(excess_returns)) / (pd.Series(excess_returns).std() * (252 ** 0.5))

def create_backup_snapshot(extra: Dict[str, Any] | None = None):  # CR-0047
    ts = time.strftime('%Y%m%d_%H%M%S')
    root = Path(Settings.BACKUP_PATH)
    try:
        root.mkdir(parents=True, exist_ok=True)
        # ensure uniqueness if called within same second
        suffix = 0
        snap_dir = root / f"snapshot_{ts}"
        while snap_dir.exists():
            suffix += 1
            snap_dir = root / f"snapshot_{ts}_{suffix}"
        snap_dir.mkdir()
        db_path = Path(Settings.TRADES_DB_PATH)
        if db_path.exists():
            shutil.copy2(db_path, snap_dir / db_path.name)
        ss_path = Path(Settings.LOG_PATH) / 'shutdown_snapshot.json'
        if ss_path.exists():
            shutil.copy2(ss_path, snap_dir / 'shutdown_snapshot.json')
        meta = { 'created': ts, 'suffix': suffix, 'db': db_path.name, 'extra': extra or {} }
        (snap_dir / 'meta.json').write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
        cleanup_old_backups(root)
        return str(snap_dir)
    except Exception:
        return None


def cleanup_old_backups(root: Path | None = None):  # CR-0047
    root = root or Path(Settings.BACKUP_PATH)
    try:
        keep = Settings.BACKUP_MAX_SNAPSHOTS
        retention_days = Settings.BACKUP_RETENTION_DAYS
        cutoff = time.time() - retention_days * 86400
        snaps = [p for p in root.glob('snapshot_*') if p.is_dir()]
        # sort newest first
        snaps.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        for p in snaps:
            if p.stat().st_mtime < cutoff or snaps.index(p) >= keep:
                shutil.rmtree(p, ignore_errors=True)
    except Exception:
        pass
