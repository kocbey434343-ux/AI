"""Metrik toplama, flush ve anomaly tespiti."""
from __future__ import annotations
import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any

from config.settings import Settings
from src.utils.structured_log import slog


def init_metrics(self):
    # Thread-safe metric list mutation icin lock
    if not hasattr(self, 'metrics_lock'):
        self.metrics_lock = threading.RLock()
    # Maksimum saklanacak ornek (testlerde kullaniliyor)
    if not hasattr(self, 'MAX_RECENT_SAMPLES'):
        self.MAX_RECENT_SAMPLES = 500
    self.recent_open_latencies = []  # list[float]
    self.recent_close_latencies = []  # list[float]
    self.recent_entry_slippage_bps = []  # list[float]
    self.recent_exit_slippage_bps = []  # list[float]
    self._last_metrics_flush = time.time()
    self._anomaly_flagged = {"latency": False, "slip": False}
    # anomaly risk state
    self._original_risk_percent = None


def metrics_snapshot(self) -> Dict[str, Any]:
    unreal = 0.0
    try:
        if hasattr(self, 'unrealized_total_pnl_pct'):
            unreal = float(self.unrealized_total_pnl_pct())
    except Exception:
        unreal = 0.0
    return {
        'ts': time.time(),
        'open_lat_ms': self.recent_open_latencies[-100:],
        'close_lat_ms': self.recent_close_latencies[-100:],
        'entry_slip_bps': self.recent_entry_slippage_bps[-100:],
        'exit_slip_bps': self.recent_exit_slippage_bps[-100:],
        'guards': dict(self.guard_counters),
        'unrealized_total_pnl_pct': unreal
    }


def maybe_flush_metrics(self, force: bool = False):
    if not Settings.METRICS_FILE_ENABLED:
        return
    now = time.time()
    if not force and (now - self._last_metrics_flush) < Settings.METRICS_FLUSH_INTERVAL_SEC:
        return
    snap = metrics_snapshot(self)
    try:
        Path(Settings.METRICS_FILE_DIR).mkdir(parents=True, exist_ok=True)
        ts_min = datetime.fromtimestamp(int(now), tz=timezone.utc).strftime('%Y%m%d_%H%M')
        fname = Path(Settings.METRICS_FILE_DIR) / f"metrics_{ts_min}.jsonl"
        with fname.open('a', encoding='utf-8') as f:
            f.write(json.dumps(snap, ensure_ascii=False) + '\n')
        self._last_metrics_flush = now
        _maybe_retention_cleanup()
    except Exception:
        pass


def _maybe_retention_cleanup():  # CR-0046
    try:
        import gzip
        retain_sec = Settings.METRICS_RETENTION_HOURS * 3600
        now = time.time()
        base = Path(Settings.METRICS_FILE_DIR)
        if not base.exists():
            return
        for p in list(base.glob('metrics_*.jsonl')):
            age = now - p.stat().st_mtime
            if age > retain_sec:
                p.unlink(missing_ok=True)  # type: ignore[arg-type]
                continue
            # Compress older than half of retention if not yet .gz
            if Settings.METRICS_RETENTION_COMPRESS and p.suffix == '.jsonl' and age > retain_sec/2:
                gz = p.with_suffix(p.suffix + '.gz')
                if not gz.exists():
                    with p.open('rb') as fin, gzip.open(gz, 'wb') as fout:
                        fout.writelines(fin)
                    p.unlink(missing_ok=True)  # type: ignore[arg-type]
    except Exception:
        pass


def recent_latency_slippage_stats(self, window: int = 30) -> Dict[str, float | None]:
    def _avg(lst):
        if not lst:
            return None
        sub = lst[-window:] if len(lst) > window else lst
        return sum(sub)/len(sub) if sub else None
    return {
        'open_latency_ms': _avg(self.recent_open_latencies),
        'close_latency_ms': _avg(self.recent_close_latencies),
        'entry_slip_bps': _avg(self.recent_entry_slippage_bps),
        'exit_slip_bps': _avg(self.recent_exit_slippage_bps)
    }


def _apply_risk_reduction(self, reason: str):
    if self._original_risk_percent is None:
        self._original_risk_percent = self.risk_manager.risk_percent
        self.risk_manager.risk_percent *= Settings.ANOMALY_RISK_MULT
        self.logger.info(f"Risk percent reduced to {self.risk_manager.risk_percent:.3f} due to {reason} anomaly")


def _maybe_restore_risk(self):
    if not any(self._anomaly_flagged.values()) and self._original_risk_percent is not None:
        self.risk_manager.risk_percent = self._original_risk_percent
        self.logger.info(f"Risk percent restored to {self.risk_manager.risk_percent:.3f}")
        self._original_risk_percent = None


def _check_latency_anomaly(self, ol: float):
    if ol > Settings.LATENCY_ANOMALY_MS and not self._anomaly_flagged['latency']:
        self.logger.warning(f"Latency anomaly avg_open={ol:.1f}ms")
        slog('anomaly_latency', avg_open_ms=ol)
        self._anomaly_flagged['latency'] = True
        _apply_risk_reduction(self, 'latency')
    elif ol <= Settings.LATENCY_ANOMALY_MS * 0.8 and self._anomaly_flagged['latency']:
        self.logger.info("Latency recovered")
        slog('anomaly_latency_recovered', avg_open_ms=ol)
        self._anomaly_flagged['latency'] = False
        _maybe_restore_risk(self)


def _check_slip_anomaly(self, es: float):
    if es > Settings.SLIPPAGE_ANOMALY_BPS and not self._anomaly_flagged['slip']:
        self.logger.warning(f"Slippage anomaly avg_entry={es:.1f}bps")
        slog('anomaly_slippage', avg_entry_slip_bps=es)
        self._anomaly_flagged['slip'] = True
        _apply_risk_reduction(self, 'slippage')
    elif es <= Settings.SLIPPAGE_ANOMALY_BPS * 0.8 and self._anomaly_flagged['slip']:
        self.logger.info("Slippage recovered")
        slog('anomaly_slippage_recovered', avg_entry_slip_bps=es)
        self._anomaly_flagged['slip'] = False
        _maybe_restore_risk(self)


def maybe_check_anomalies(self):
    try:
        stats = recent_latency_slippage_stats(self, 30)
        ol = stats.get('open_latency_ms') or 0
        es = stats.get('entry_slip_bps') or 0
        _check_latency_anomaly(self, ol)
        _check_slip_anomaly(self, es)
    except Exception:
        pass


def maybe_trim_metrics(self):
    """Recent metric listlerini MAX_RECENT_SAMPLES limitine indir.

    Idempotent ve hafif bir islem; open/close append sonrasi cagrilacak.
    """
    try:
        max_n = getattr(self, 'MAX_RECENT_SAMPLES', 500)
        with self.metrics_lock:
            if len(self.recent_open_latencies) > max_n:
                self.recent_open_latencies = self.recent_open_latencies[-max_n:]
            if len(self.recent_close_latencies) > max_n:
                self.recent_close_latencies = self.recent_close_latencies[-max_n:]
            if len(self.recent_entry_slippage_bps) > max_n:
                self.recent_entry_slippage_bps = self.recent_entry_slippage_bps[-max_n:]
            if len(self.recent_exit_slippage_bps) > max_n:
                self.recent_exit_slippage_bps = self.recent_exit_slippage_bps[-max_n:]
    except Exception:
        pass
