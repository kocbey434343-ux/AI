"""
Advanced Metrics Collector - Enhanced performance monitoring

Bu modül gelişmiş sistem metriklerini toplar:
- Deep performance profiling
- Memory leak detection
- Network latency monitoring
- Database query performance
- Trading strategy metrics
"""

import gc
import json
import logging
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import psutil

logger = logging.getLogger(__name__)

# Constants
MAX_PERFORMANCE_PROFILES = 100


@dataclass
class MetricPoint:
    """Single metric data point"""
    timestamp: datetime
    value: float
    tags: Dict[str, str]


@dataclass
class PerformanceProfile:
    """Performance profiling result"""
    function_name: str
    execution_time_ms: float
    memory_delta_mb: float
    cpu_percent: float
    call_count: int


class AdvancedMetricsCollector:
    """Advanced system ve application metrics collector"""

    def __init__(self, history_size: int = 1000):
        self.history_size = history_size
        self.metrics_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=history_size))
        self.performance_profiles: List[PerformanceProfile] = []
        self.memory_baselines: Dict[str, float] = {}
        self.running = False
        self.collection_thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()

        # Alert thresholds
        self.thresholds = {
            'cpu_critical': 90.0,
            'memory_critical': 90.0,
            'latency_warning_ms': 100.0,
            'latency_critical_ms': 500.0,
            'memory_leak_mb': 50.0
        }

    def start_collection(self, interval_seconds: float = 1.0):
        """Start background metric collection"""
        if self.running:
            return

        self.running = True
        self.collection_thread = threading.Thread(
            target=self._collection_loop,
            args=(interval_seconds,),
            daemon=True
        )
        self.collection_thread.start()
        logger.info(f"Advanced metrics collection started (interval: {interval_seconds}s)")

    def stop_collection(self):
        """Stop background collection"""
        self.running = False
        if self.collection_thread:
            self.collection_thread.join(timeout=2.0)
        logger.info("Advanced metrics collection stopped")

    def _collection_loop(self, interval: float):
        """Background collection loop"""
        while self.running:
            try:
                # System metrics
                self._collect_system_metrics()

                # Memory analysis
                self._collect_memory_metrics()

                # Performance counters
                self._collect_performance_counters()

                time.sleep(interval)

            except Exception as e:
                logger.error(f"Metrics collection error: {e}")
                time.sleep(interval)

    def _collect_system_metrics(self):
        """Collect advanced system metrics"""
        now = datetime.now()

        # CPU detailed
        cpu_times = psutil.cpu_times()
        self._record_metric('cpu_user', now, cpu_times.user, {'type': 'system'})
        self._record_metric('cpu_system', now, cpu_times.system, {'type': 'system'})
        self._record_metric('cpu_iowait', now, getattr(cpu_times, 'iowait', 0), {'type': 'system'})

        # Memory detailed
        memory = psutil.virtual_memory()
        self._record_metric('memory_available_gb', now, memory.available / (1024**3), {'type': 'system'})
        self._record_metric('memory_cached_gb', now, getattr(memory, 'cached', 0) / (1024**3), {'type': 'system'})

        # Disk I/O
        try:
            disk_io = psutil.disk_io_counters()
            if disk_io:
                self._record_metric('disk_read_mb', now, disk_io.read_bytes / (1024**2), {'type': 'io'})
                self._record_metric('disk_write_mb', now, disk_io.write_bytes / (1024**2), {'type': 'io'})
        except Exception:
            pass

        # Network I/O
        try:
            net_io = psutil.net_io_counters()
            if net_io:
                self._record_metric('net_sent_mb', now, net_io.bytes_sent / (1024**2), {'type': 'network'})
                self._record_metric('net_recv_mb', now, net_io.bytes_recv / (1024**2), {'type': 'network'})
        except Exception:
            pass

    def _collect_memory_metrics(self):
        """Collect memory-specific metrics"""
        now = datetime.now()

        # Python memory
        import tracemalloc
        if tracemalloc.is_tracing():
            current, peak = tracemalloc.get_traced_memory()
            self._record_metric('python_memory_current_mb', now, current / (1024**2), {'type': 'python'})
            self._record_metric('python_memory_peak_mb', now, peak / (1024**2), {'type': 'python'})

        # Garbage collection
        gc_counts = gc.get_count()
        for i, count in enumerate(gc_counts):
            self._record_metric(f'gc_objects_gen{i}', now, count, {'type': 'gc'})

        # Object counts
        self._record_metric('python_objects_total', now, len(gc.get_objects()), {'type': 'python'})

    def _collect_performance_counters(self):
        """Collect application performance counters"""
        now = datetime.now()

        # Thread count
        self._record_metric('active_threads', now, threading.active_count(), {'type': 'threading'})

        # Python performance
        import sys
        self._record_metric('python_modules_loaded', now, len(sys.modules), {'type': 'python'})

    def _record_metric(self, name: str, timestamp: datetime, value: float, tags: Dict[str, str]):
        """Record a single metric point"""
        with self.lock:
            point = MetricPoint(timestamp, value, tags)
            self.metrics_history[name].append(point)

    def profile_function(self, func_name: str):
        """Decorator for function performance profiling"""
        def decorator(func):
            def wrapper(*args, **kwargs):
                # Memory baseline
                memory_before = psutil.Process().memory_info().rss / (1024**2)
                cpu_before = psutil.cpu_percent()
                start_time = time.perf_counter()

                try:
                    return func(*args, **kwargs)
                finally:
                    # Performance measurement
                    end_time = time.perf_counter()
                    execution_time = (end_time - start_time) * 1000  # ms

                    memory_after = psutil.Process().memory_info().rss / (1024**2)
                    memory_delta = memory_after - memory_before
                    cpu_after = psutil.cpu_percent()

                    # Store profile
                    profile = PerformanceProfile(
                        function_name=func_name,
                        execution_time_ms=execution_time,
                        memory_delta_mb=memory_delta,
                        cpu_percent=(cpu_before + cpu_after) / 2,
                        call_count=1
                    )

                    with self.lock:
                        self.performance_profiles.append(profile)
                        # Keep only last 100 profiles
                        if len(self.performance_profiles) > MAX_PERFORMANCE_PROFILES:
                            self.performance_profiles = self.performance_profiles[-MAX_PERFORMANCE_PROFILES:]

            return wrapper
        return decorator

    def get_metric_summary(self, metric_name: str, window_minutes: int = 5) -> Dict:
        """Get statistical summary for a metric"""
        with self.lock:
            return self._get_metric_summary_internal(metric_name, window_minutes)

    def _get_metric_summary_internal(self, metric_name: str, window_minutes: int = 5) -> Dict:
        """Internal version without lock for use within locked sections"""
        if metric_name not in self.metrics_history:
            return {}

        cutoff_time = datetime.now() - timedelta(minutes=window_minutes)
        recent_points = [
            p for p in self.metrics_history[metric_name]
            if p.timestamp >= cutoff_time
        ]

        if not recent_points:
            return {}

        values = [p.value for p in recent_points]
        return {
            'count': len(values),
            'min': min(values),
            'max': max(values),
            'avg': sum(values) / len(values),
            'latest': values[-1] if values else None,
            'window_minutes': window_minutes
        }

    def get_performance_summary(self) -> Dict:
        """Get function performance summary"""
        with self.lock:
            return self._get_performance_summary_internal()

    def _get_performance_summary_internal(self) -> Dict:
        """Internal version without lock for use within locked sections"""
        if not self.performance_profiles:
            return {}

        # Aggregate by function name
        by_function = defaultdict(list)
        for profile in self.performance_profiles:
            by_function[profile.function_name].append(profile)

        summary = {}
        for func_name, profiles in by_function.items():
            execution_times = [p.execution_time_ms for p in profiles]
            memory_deltas = [p.memory_delta_mb for p in profiles]

            summary[func_name] = {
                'call_count': len(profiles),
                'avg_execution_ms': sum(execution_times) / len(execution_times),
                'max_execution_ms': max(execution_times),
                'avg_memory_delta_mb': sum(memory_deltas) / len(memory_deltas),
                'total_memory_delta_mb': sum(memory_deltas)
            }

        return summary

    def detect_anomalies(self) -> List[Dict]:
        """Detect performance anomalies and potential issues"""
        with self.lock:
            return self._detect_anomalies_internal()

    def _detect_anomalies_internal(self) -> List[Dict]:
        """Internal version without lock for use within locked sections"""
        anomalies = []

        # High latency functions
        performance_summary = self._get_performance_summary_internal()
        for func_name, stats in performance_summary.items():
            if stats['max_execution_ms'] > self.thresholds['latency_critical_ms']:
                anomalies.append({
                    'type': 'performance',
                    'severity': 'critical',
                    'message': f"Function {func_name} has critical latency: {stats['max_execution_ms']:.1f}ms",
                    'metric': 'execution_time',
                    'value': stats['max_execution_ms']
                })
            elif stats['avg_execution_ms'] > self.thresholds['latency_warning_ms']:
                anomalies.append({
                    'type': 'performance',
                    'severity': 'warning',
                    'message': f"Function {func_name} has high avg latency: {stats['avg_execution_ms']:.1f}ms",
                    'metric': 'execution_time',
                    'value': stats['avg_execution_ms']
                })

        # Memory leaks
        for func_name, stats in performance_summary.items():
            if stats['total_memory_delta_mb'] > self.thresholds['memory_leak_mb']:
                anomalies.append({
                    'type': 'memory',
                    'severity': 'warning',
                    'message': f"Potential memory leak in {func_name}: +{stats['total_memory_delta_mb']:.1f}MB",
                    'metric': 'memory_delta',
                    'value': stats['total_memory_delta_mb']
                })

        # System resource alerts
        cpu_summary = self._get_metric_summary_internal('cpu_user', window_minutes=2)
        if cpu_summary and cpu_summary['avg'] > self.thresholds['cpu_critical']:
            anomalies.append({
                'type': 'system',
                'severity': 'critical',
                'message': f"Critical CPU usage: {cpu_summary['avg']:.1f}%",
                'metric': 'cpu_usage',
                'value': cpu_summary['avg']
            })

        memory_summary = self._get_metric_summary_internal('memory_available_gb', window_minutes=2)
        if memory_summary and memory_summary['latest'] < 1.0:  # Less than 1GB available
            anomalies.append({
                'type': 'system',
                'severity': 'critical',
                'message': f"Critical low memory: {memory_summary['latest']:.1f}GB available",
                'metric': 'memory_available',
                'value': memory_summary['latest']
            })

        return anomalies

    def export_metrics(self, format: str = 'json') -> str:
        """Export collected metrics"""
        with self.lock:
            if format == 'json':
                # Collect summaries while holding the lock
                metrics_summaries = {}
                for name in self.metrics_history:
                    metrics_summaries[name] = self._get_metric_summary_internal(name)

                performance_summary = self._get_performance_summary_internal()
                anomalies = self._detect_anomalies_internal()

                export_data = {
                    'timestamp': datetime.now().isoformat(),
                    'metrics_summary': metrics_summaries,
                    'performance_summary': performance_summary,
                    'anomalies': anomalies
                }
                return json.dumps(export_data, indent=2, default=str)

            return "Unsupported format"


# Global instance
_metrics_collector = None


def get_metrics_collector() -> AdvancedMetricsCollector:
    """Get global metrics collector instance"""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = AdvancedMetricsCollector()
    return _metrics_collector


def profile_performance(func_name: Optional[str] = None):
    """Convenience decorator for performance profiling"""
    def decorator(func):
        name = func_name or f"{func.__module__}.{func.__name__}"
        return get_metrics_collector().profile_function(name)(func)
    return decorator


# Trading-specific metrics collector
class TradingMetricsCollector:
    """Trading strategy specific metrics"""

    def __init__(self):
        self.strategy_metrics = defaultdict(list)
        self.trade_latencies = deque(maxlen=1000)
        self.order_success_rates = deque(maxlen=100)

    def record_trade_latency(self, latency_ms: float, trade_type: str):
        """Record trade execution latency"""
        self.trade_latencies.append({
            'timestamp': datetime.now(),
            'latency_ms': latency_ms,
            'trade_type': trade_type
        })

    def record_strategy_performance(self, strategy_name: str, performance_data: Dict):
        """Record strategy performance metrics"""
        self.strategy_metrics[strategy_name].append({
            'timestamp': datetime.now(),
            **performance_data
        })

    def get_trade_latency_stats(self) -> Dict:
        """Get trade latency statistics"""
        if not self.trade_latencies:
            return {}

        latencies = [entry['latency_ms'] for entry in self.trade_latencies]
        return {
            'count': len(latencies),
            'avg_ms': sum(latencies) / len(latencies),
            'min_ms': min(latencies),
            'max_ms': max(latencies),
            'p95_ms': sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0,
            'p99_ms': sorted(latencies)[int(len(latencies) * 0.99)] if latencies else 0
        }


# Global trading metrics instance
_trading_metrics = None


def get_trading_metrics() -> TradingMetricsCollector:
    """Get global trading metrics collector"""
    global _trading_metrics
    if _trading_metrics is None:
        _trading_metrics = TradingMetricsCollector()
    return _trading_metrics
