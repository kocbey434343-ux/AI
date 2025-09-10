"""
CR-0074: Metrics Prometheus Export
Prometheus formatinda metrics export sistemi
"""

import contextlib
import threading
from datetime import datetime, timezone

from src.utils.logger import get_logger

try:
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        Counter,
        Gauge,
        Histogram,
        Info,
        generate_latest as _prom_generate_latest,
    )
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    # Mock classes for when prometheus_client is not available
    CONTENT_TYPE_LATEST = 'text/plain'
    class MockCounter:
        def __init__(self, *args, **kwargs):
            # no-op mock
            pass
        def inc(self, *args, **kwargs):
            # no-op mock
            pass
        def labels(self, **_):
            # return self to allow chained calls in disabled mode
            return self
    class MockHistogram:
        def __init__(self, *args, **kwargs):
            # no-op mock
            pass
        def observe(self, *args, **kwargs):
            # no-op mock
            pass
    class MockGauge:
        def __init__(self, *args, **kwargs):
            # no-op mock
            pass
        def set(self, *args, **kwargs):
            # no-op mock
            pass
        def labels(self, **_):
            # return self to allow chained calls in disabled mode
            return self
    class MockInfo:
        def __init__(self, *args, **kwargs):
            # no-op mock
            pass
        def info(self, *args, **kwargs):
            # no-op mock
            pass
    # Gerçek Prometheus istemcisi mevcutsa kullan, yoksa mock'lar
    if PROMETHEUS_AVAILABLE:
        # Gerçek prometheus metrikleri
        from prometheus_client import (
            Counter,
            Gauge,
            Histogram,
            Info,
            generate_latest as _prom_generate_latest,
        )
    else:
        # Mock sınıfları kullan
        Counter = MockCounter  # type: ignore
        Histogram = MockHistogram  # type: ignore
        Gauge = MockGauge  # type: ignore
        Info = MockInfo  # type: ignore
        _prom_generate_latest = None  # type: ignore

    def _mock_generate_latest(registry=None):
        # reference the parameter to avoid linter warnings
        _ = registry
        # return static content as bytes when client is unavailable
        return b"# Prometheus client not available - using mock data"

# Helper to unify generate_latest regardless of availability
def _generate_latest(registry):
    if PROMETHEUS_AVAILABLE and _prom_generate_latest is not None:
        return _prom_generate_latest(registry)
    return _mock_generate_latest(registry)  # type: ignore[name-defined]


class PrometheusExporter:
    """
    Trading bot metrics'lerini Prometheus formatinda export eden sinif
    """

    def __init__(self, registry=None):
        self.logger = get_logger(__name__)
        self.lock = threading.RLock()

        if not PROMETHEUS_AVAILABLE:
            self.logger.warning("prometheus_client not available - metrics export disabled")
            self.enabled = False
            return

        self.enabled = True
        # Ensure a concrete registry only when client is available
        if registry is not None:
            self.registry = registry
        elif PROMETHEUS_AVAILABLE:
            # Lazy import to avoid name binding/type checker issues when unavailable
            from prometheus_client import CollectorRegistry as _CollectorRegistry  # type: ignore
            self.registry = _CollectorRegistry()
        else:
            self.registry = None

        # Initialize metrics
        self._init_metrics()

    def _init_metrics(self):
        """Initialize Prometheus metric definitions"""

        # Latency metrics
        self.open_latency_histogram = Histogram(
            'bot_open_latency_ms',
            'Trade acilis latency milliseconds',
            buckets=[50, 100, 200, 500, 1000, 2000, 5000],
            registry=self.registry,
        )

        self.close_latency_histogram = Histogram(
            'bot_close_latency_ms',
            'Trade kapanis latency milliseconds',
            buckets=[50, 100, 200, 500, 1000, 2000, 5000],
            registry=self.registry,
        )

        # Slippage metrics
        self.entry_slippage_histogram = Histogram(
            'bot_entry_slippage_bps',
            'Entry slippage basis points',
            buckets=[1, 5, 10, 20, 50, 100, 200],
            registry=self.registry,
        )

        self.exit_slippage_histogram = Histogram(
            'bot_exit_slippage_bps',
            'Exit slippage basis points',
            buckets=[1, 5, 10, 20, 50, 100, 200],
            registry=self.registry,
        )

        # Guard block counters
        self.guard_block_counter = Counter(
            'bot_guard_block_total',
            'Guard tarafindan bloke edilen trade sayisi',
            ['guard'],
            registry=self.registry,
        )

        # Position metrics
        self.positions_open_gauge = Gauge(
            'bot_positions_open_gauge',
            'Acik pozisyon sayisi',
            registry=self.registry,
        )

        self.unrealized_pnl_gauge = Gauge(
            'bot_unrealized_pnl_gauge',
            'Unrealized PnL',
            registry=self.registry,
        )

        # Reconciliation metrics
        self.reconciliation_orphans_counter = Counter(
            'bot_reconciliation_orphans_total',
            'Reconciliation orphan sayisi',
            ['type'],
            registry=self.registry,
        )

        # Anomaly metrics
        self.anomaly_counter = Counter(
            'bot_anomaly_trigger_total',
            'Anomaly tetik sayisi',
            ['type'],
            registry=self.registry,
        )

        # Health status
        self.health_status_gauge = Gauge(
            'bot_health_status_gauge',
            'Bot saglik durumu',
            ['component'],
            registry=self.registry,
        )

        # Trade counters
        self.trades_opened_counter = Counter(
            'bot_trades_opened_total',
            'Acilan trade sayisi',
            ['symbol'],
            registry=self.registry,
        )

        self.trades_closed_counter = Counter(
            'bot_trades_closed_total',
            'Kapanan trade sayisi',
            ['symbol', 'result'],
            registry=self.registry,
        )

        # Clock skew metrics (A29 P0)
        self.clock_skew_gauge = Gauge(
            'bot_clock_skew_ms_gauge',
            'Exchange server saati ile lokal saat arasindaki fark (ms)',
            registry=self.registry,
        )

        self.clock_skew_alerts_counter = Counter(
            'bot_clock_skew_alerts_total',
            'Clock skew guard uyarilari',
            registry=self.registry,
        )

        # Rate limit & backoff telemetry (A29 P0 - CR-0084)
        self.rate_limit_hits_counter = Counter(
            'bot_rate_limit_hits_total',
            'Rate limit hit count (HTTP 429/418)',
            ['code'],
            registry=self.registry,
        )

        self.backoff_seconds_histogram = Histogram(
            'bot_backoff_seconds',
            'Backoff sleep durations in seconds',
            buckets=[0.01, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 30, 60],
            registry=self.registry,
        )

        self.used_weight_gauge = Gauge(
            'bot_used_weight_gauge',
            'Binance X-MBX-USED-WEIGHT-1m header (approximate request weight over 1 minute)',
            registry=self.registry,
        )

        # Order submit retries (A29 P0 - CR-0083)
        self.order_submit_retries_counter = Counter(
            'bot_order_submit_retries_total',
            'Order submit retry attempts by reason',
            ['reason'],
            registry=self.registry,
        )

        # Bot info
        self.bot_info = Info(
            'bot_info',
            'Bot version ve config bilgisi',
            registry=self.registry
        )

        # Set bot info
        self._update_bot_info()

    # ---- Helper updaters ----
    def record_clock_skew_ms(self, skew_ms: float) -> None:
        """Record current clock skew in milliseconds (safe if disabled)."""
        if not getattr(self, 'enabled', False):
            return
        with contextlib.suppress(Exception):
            self.clock_skew_gauge.set(float(skew_ms))

    def inc_clock_skew_alert(self) -> None:
        """Increment clock skew alert counter (safe if disabled)."""
        if not getattr(self, 'enabled', False):
            return
        with contextlib.suppress(Exception):
            self.clock_skew_alerts_counter.inc()

    def record_rate_limit_hit(self, code: str | int) -> None:
        """Record a rate limit hit event (429/418)."""
        if not getattr(self, 'enabled', False):
            return
        with contextlib.suppress(Exception):
            self.rate_limit_hits_counter.labels(code=str(code)).inc()

    def observe_backoff_seconds(self, seconds: float) -> None:
        """Observe a backoff sleep duration in seconds."""
        if not getattr(self, 'enabled', False):
            return
        with contextlib.suppress(Exception):
            self.backoff_seconds_histogram.observe(float(seconds))

    def set_used_weight(self, weight: float) -> None:
        """Update the X-MBX-USED-WEIGHT-1m gauge if provided."""
        if not getattr(self, 'enabled', False):
            return
        with contextlib.suppress(Exception):
            self.used_weight_gauge.set(float(weight))

    def record_order_submit_retry(self, reason: str) -> None:
        """Increment order submit retry counter with a reason label."""
        if not getattr(self, 'enabled', False):
            return
        with contextlib.suppress(Exception):
            self.order_submit_retries_counter.labels(reason=str(reason)).inc()

    def _update_bot_info(self):
        """Update bot information metrics"""
        try:
            info_data = {
                'version': '1.0.0',
                'start_time': datetime.now(timezone.utc).isoformat()
            }
            self.bot_info.info(info_data)
        except Exception as e:
            self.logger.error(f"Failed to update bot info: {e}")

    def record_open_latency(self, latency_ms: float):
        """Record trade open latency"""
        if not self.enabled:
            return
        with self.lock:
            self.open_latency_histogram.observe(latency_ms)

    def record_close_latency(self, latency_ms: float):
        """Record trade close latency"""
        if not self.enabled:
            return
        with self.lock:
            self.close_latency_histogram.observe(latency_ms)

    def record_entry_slippage(self, slippage_bps: float):
        """Record entry slippage"""
        if not self.enabled:
            return
        with self.lock:
            self.entry_slippage_histogram.observe(slippage_bps)

    def record_exit_slippage(self, slippage_bps: float):
        """Record exit slippage"""
        if not self.enabled:
            return
        with self.lock:
            self.exit_slippage_histogram.observe(slippage_bps)

    def record_guard_block(self, guard_type: str):
        """Record guard block event"""
        if not self.enabled:
            return
        with self.lock:
            self.guard_block_counter.labels(guard=guard_type).inc()

    def update_positions_count(self, count: int):
        """Update open positions count"""
        if not self.enabled:
            return
        with self.lock:
            self.positions_open_gauge.set(count)

    def update_unrealized_pnl(self, pnl: float):
        """Update unrealized PnL"""
        if not self.enabled:
            return
        with self.lock:
            self.unrealized_pnl_gauge.set(pnl)

    def record_reconciliation_orphan(self, orphan_type: str):
        """Record reconciliation orphan"""
        if not self.enabled:
            return
        with self.lock:
            self.reconciliation_orphans_counter.labels(type=orphan_type).inc()

    def record_anomaly(self, anomaly_type: str):
        """Record anomaly event"""
        if not self.enabled:
            return
        with self.lock:
            self.anomaly_counter.labels(type=anomaly_type).inc()

    def update_health_status(self, component: str, status: int):
        """Update component health status (0=unhealthy, 1=healthy)"""
        if not self.enabled:
            return
        with self.lock:
            self.health_status_gauge.labels(component=component).set(status)

    def record_trade_opened(self, symbol: str):
        """Record trade opened"""
        if not self.enabled:
            return
        with self.lock:
            self.trades_opened_counter.labels(symbol=symbol).inc()

    def record_trade_closed(self, symbol: str, result: str):
        """Record trade closed with result (profit/loss)"""
        if not self.enabled:
            return
        with self.lock:
            self.trades_closed_counter.labels(symbol=symbol, result=result).inc()

    def collect_from_trader(self, trader_metrics):
        """Collect metrics from trader object"""
        if not self.enabled or not trader_metrics:
            return

        try:
            self._collect_latency_metrics(trader_metrics)
            self._collect_slippage_metrics(trader_metrics)
            self._collect_anomaly_metrics(trader_metrics)
        except Exception as e:
            self.logger.error(f"Failed to collect trader metrics: {e}")

    def _collect_latency_metrics(self, trader_metrics):
        """Helper to collect latency metrics"""
        for latency in getattr(trader_metrics, 'recent_open_latencies', []):
            self.record_open_latency(latency)
        for latency in getattr(trader_metrics, 'recent_close_latencies', []):
            self.record_close_latency(latency)

    def _collect_slippage_metrics(self, trader_metrics):
        """Helper to collect slippage metrics"""
        for slippage in getattr(trader_metrics, 'recent_entry_slippage_bps', []):
            self.record_entry_slippage(slippage)
        for slippage in getattr(trader_metrics, 'recent_exit_slippage_bps', []):
            self.record_exit_slippage(slippage)

    def _collect_anomaly_metrics(self, trader_metrics):
        """Helper to collect anomaly metrics"""
        # Check for anomaly flags
        if getattr(trader_metrics, 'has_latency_anomaly', False):
            self.record_anomaly('latency')
        if getattr(trader_metrics, 'has_slippage_anomaly', False):
            self.record_anomaly('slippage')

    def collect_from_guards(self, guard_metrics):
        """Collect metrics from guard systems"""
        if not self.enabled or not guard_metrics:
            return

        try:
            for guard_name, metrics in guard_metrics.items():
                if 'violation_count' in metrics:
                    for _ in range(metrics['violation_count']):
                        self.record_guard_block(guard_name)
        except Exception as e:
            self.logger.error(f"Failed to collect guard metrics: {e}")

    def generate_latest(self) -> str:
        """Generate Prometheus metrics output"""
        if not self.enabled:
            return "# Prometheus client not available\n"

        try:
            with self.lock:
                return _generate_latest(self.registry).decode('utf-8')
        except Exception as e:
            self.logger.error(f"Failed to generate Prometheus metrics: {e}")
            return f"# Error generating metrics: {e}\n"

    def get_content_type(self) -> str:
        """Get content type for HTTP response"""
        # CONTENT_TYPE_LATEST comes from prometheus_client when available
        if PROMETHEUS_AVAILABLE:
            return CONTENT_TYPE_LATEST
        return 'text/plain'

    def export_metrics(self) -> str:
        """Export metrics (alias for generate_latest)"""
        return self.generate_latest()


# Module-level exporter factory
def create_prometheus_exporter(registry=None) -> PrometheusExporter:
    """Create a new PrometheusExporter instance"""
    return PrometheusExporter(registry=registry)


def get_exporter_instance(registry=None) -> PrometheusExporter:
    """Get or create a PrometheusExporter instance"""
    return create_prometheus_exporter(registry=registry)


def init_prometheus_export():
    """Initialize Prometheus export system"""
    return get_exporter_instance()


def export_prometheus_metrics() -> str:
    """Export current metrics in Prometheus format"""
    exporter = get_exporter_instance()
    return exporter.export_metrics()


def get_prometheus_exporter() -> PrometheusExporter:
    """Get PrometheusExporter instance for A32 integration"""
    return get_exporter_instance()


def get_prometheus_content_type() -> str:
    """Get Prometheus content type for HTTP response"""
    exporter = get_exporter_instance()
    return exporter.get_content_type()
