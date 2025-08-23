"""Metrik toplama, flush ve anomaly tespiti."""
from __future__ import annotations
from typing import Dict, Any
import time
import json
from pathlib import Path
from datetime import datetime, timezone
from config.settings import Settings


def init_metrics(self):
    self.recent_open_latencies = []  # list[float]
    self.recent_close_latencies = []  # list[float]
    self.recent_entry_slippage_bps = []  # list[float]
    self.recent_exit_slippage_bps = []  # list[float]
    self._last_metrics_flush = time.time()
    self._anomaly_flagged = {"latency": False, "slip": False}
    # anomaly risk state
    self._original_risk_percent = None


def metrics_snapshot(self) -> Dict[str, Any]:
    return {
        'ts': time.time(),
        'open_lat_ms': self.recent_open_latencies[-100:],
        'close_lat_ms': self.recent_close_latencies[-100:],
        'entry_slip_bps': self.recent_entry_slippage_bps[-100:],
        'exit_slip_bps': self.recent_exit_slippage_bps[-100:],
        'guards': dict(self.guard_counters)
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


def maybe_check_anomalies(self):
    try:
        stats = recent_latency_slippage_stats(self, 30)
        ol = stats.get('open_latency_ms') or 0
        es = stats.get('entry_slip_bps') or 0
        if ol > Settings.LATENCY_ANOMALY_MS and not self._anomaly_flagged['latency']:
            self.logger.warning(f"Latency anomaly avg_open={ol:.1f}ms")
            self._anomaly_flagged['latency'] = True
            if self._original_risk_percent is None:
                self._original_risk_percent = self.risk_manager.risk_percent
                self.risk_manager.risk_percent *= Settings.ANOMALY_RISK_MULT
                self.logger.info(f"Risk percent reduced to {self.risk_manager.risk_percent:.3f} due to latency anomaly")
        elif ol <= Settings.LATENCY_ANOMALY_MS * 0.8 and self._anomaly_flagged['latency']:
            self.logger.info("Latency recovered")
            self._anomaly_flagged['latency'] = False
            if not any(self._anomaly_flagged.values()) and self._original_risk_percent is not None:
                self.risk_manager.risk_percent = self._original_risk_percent
                self.logger.info(f"Risk percent restored to {self.risk_manager.risk_percent:.3f}")
        if es > Settings.SLIPPAGE_ANOMALY_BPS and not self._anomaly_flagged['slip']:
            self.logger.warning(f"Slippage anomaly avg_entry={es:.1f}bps")
            self._anomaly_flagged['slip'] = True
            if self._original_risk_percent is None:
                self._original_risk_percent = self.risk_manager.risk_percent
                self.risk_manager.risk_percent *= Settings.ANOMALY_RISK_MULT
                self.logger.info(f"Risk percent reduced to {self.risk_manager.risk_percent:.3f} due to slippage anomaly")
        elif es <= Settings.SLIPPAGE_ANOMALY_BPS * 0.8 and self._anomaly_flagged['slip']:
            self.logger.info("Slippage recovered")
            self._anomaly_flagged['slip'] = False
            if not any(self._anomaly_flagged.values()) and self._original_risk_percent is not None:
                self.risk_manager.risk_percent = self._original_risk_percent
                self.logger.info(f"Risk percent restored to {self.risk_manager.risk_percent:.3f}")
    except Exception:
        pass
