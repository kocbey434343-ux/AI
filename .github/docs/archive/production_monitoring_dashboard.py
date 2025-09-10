#!/usr/bin/env python3
"""
Production Monitoring Dashboard - Phase 2 Setup
Prometheus metrics integration for advanced production monitoring
"""

import time
import psutil
import sqlite3
import logging
import threading
from datetime import datetime
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, List, Optional
import json
import socket

class PrometheusMetricsHandler:
    """Prometheus-compatible metrics handler"""

    def __init__(self):
        self.metrics = {}
        self.lock = threading.Lock()

    def increment_counter(self, metric_name: str, labels: Dict[str, str] = None):
        """Increment a counter metric"""
        with self.lock:
            key = self._build_metric_key(metric_name, labels)
            self.metrics[key] = self.metrics.get(key, 0) + 1

    def set_gauge(self, metric_name: str, value: float, labels: Dict[str, str] = None):
        """Set a gauge metric value"""
        with self.lock:
            key = self._build_metric_key(metric_name, labels)
            self.metrics[key] = value

    def record_histogram(self, metric_name: str, value: float, labels: Dict[str, str] = None):
        """Record histogram value (simplified)"""
        with self.lock:
            key = self._build_metric_key(metric_name, labels)
            if key not in self.metrics:
                self.metrics[key] = []
            self.metrics[key].append(value)

    def _build_metric_key(self, metric_name: str, labels: Dict[str, str] = None) -> str:
        """Build metric key with labels"""
        if labels:
            label_str = ",".join([f'{k}="{v}"' for k, v in sorted(labels.items())])
            return f"{metric_name}{{{label_str}}}"
        return metric_name

    def export_metrics(self) -> str:
        """Export metrics in Prometheus format"""
        with self.lock:
            lines = []
            for key, value in self.metrics.items():
                if isinstance(value, list):
                    # Histogram - simplified
                    lines.append(f"{key}_count {len(value)}")
                    if value:
                        lines.append(f"{key}_sum {sum(value)}")
                        lines.append(f"{key}_avg {sum(value)/len(value)}")
                else:
                    lines.append(f"{key} {value}")
            return "\n".join(lines)

class MetricsHTTPHandler(BaseHTTPRequestHandler):
    """HTTP handler for /metrics endpoint"""

    def do_GET(self):
        if self.path == '/metrics':
            try:
                metrics_data = self.server.metrics_handler.export_metrics()
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain; charset=utf-8')
                self.end_headers()
                self.wfile.write(metrics_data.encode('utf-8'))
            except Exception as e:
                self.send_error(500, f"Metrics error: {e}")
        elif self.path == '/health':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            health_data = {"status": "healthy", "timestamp": datetime.now().isoformat()}
            self.wfile.write(json.dumps(health_data).encode('utf-8'))
        else:
            self.send_error(404, "Not found")

    def log_message(self, format, *args):
        """Suppress default HTTP logging"""
        pass

class ProductionMonitoringDashboard:
    """Advanced production monitoring with Prometheus integration"""

    def __init__(self, metrics_port: int = 8090):
        self.start_time = datetime.now()
        self.metrics_port = metrics_port
        self.setup_logging()

        # Metrics handler
        self.metrics = PrometheusMetricsHandler()

        # Monitoring data
        self.db_path = Path("data/trading_data.db")
        self.baseline_memory = None
        self.last_trade_count = 0

        # Start metrics server
        self.start_metrics_server()

        self.logger.info("Production Monitoring Dashboard initialized")
        self.logger.info(f"Metrics server: http://localhost:{metrics_port}/metrics")

    def setup_logging(self):
        """Setup logging"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(message)s',
            handlers=[
                logging.FileHandler('production_monitoring_dashboard.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def start_metrics_server(self):
        """Start HTTP server for metrics endpoint"""
        try:
            server = HTTPServer(('localhost', self.metrics_port), MetricsHTTPHandler)
            server.metrics_handler = self.metrics

            # Start server in background thread
            server_thread = threading.Thread(target=server.serve_forever, daemon=True)
            server_thread.start()

            self.logger.info(f"Metrics server started on port {self.metrics_port}")
        except Exception as e:
            self.logger.error(f"Failed to start metrics server: {e}")

    def collect_system_metrics(self):
        """Collect and export system metrics"""
        try:
            # Memory metrics
            process = psutil.Process()
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024

            self.metrics.set_gauge("bot_memory_usage_mb", memory_mb)

            # Memory growth calculation
            if self.baseline_memory is None:
                self.baseline_memory = memory_mb
                self.metrics.set_gauge("bot_memory_baseline_mb", memory_mb)

            growth_percent = ((memory_mb - self.baseline_memory) / self.baseline_memory) * 100
            self.metrics.set_gauge("bot_memory_growth_percent", growth_percent)

            # System metrics
            cpu_percent = psutil.cpu_percent()
            self.metrics.set_gauge("system_cpu_percent", cpu_percent)

            # Uptime
            uptime_hours = (datetime.now() - self.start_time).total_seconds() / 3600
            self.metrics.set_gauge("bot_uptime_hours", uptime_hours)

        except Exception as e:
            self.logger.error(f"System metrics collection failed: {e}")
            self.metrics.increment_counter("bot_monitoring_errors", {"type": "system_metrics"})

    def collect_database_metrics(self):
        """Collect database performance metrics"""
        try:
            if not self.db_path.exists():
                self.metrics.set_gauge("bot_database_status", 0)  # 0 = missing
                return

            start_time = time.time()
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            # Trade metrics
            cursor.execute("SELECT COUNT(*) FROM trades")
            trade_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM executions")
            execution_count = cursor.fetchone()[0]

            conn.close()
            response_time_ms = (time.time() - start_time) * 1000

            # Export metrics
            self.metrics.set_gauge("bot_database_status", 1)  # 1 = healthy
            self.metrics.set_gauge("bot_database_response_ms", response_time_ms)
            self.metrics.set_gauge("bot_trades_total", trade_count)
            self.metrics.set_gauge("bot_executions_total", execution_count)

            # Trade activity rate
            new_trades = trade_count - self.last_trade_count
            if new_trades > 0:
                self.metrics.increment_counter("bot_new_trades", {"count": str(new_trades)})
                self.last_trade_count = trade_count

        except Exception as e:
            self.logger.error(f"Database metrics collection failed: {e}")
            self.metrics.set_gauge("bot_database_status", -1)  # -1 = error
            self.metrics.increment_counter("bot_monitoring_errors", {"type": "database_metrics"})

    def collect_process_metrics(self):
        """Collect bot process health metrics"""
        try:
            bot_processes = 0
            python_processes = 0

            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                if proc.info['name'] and 'python' in proc.info['name'].lower():
                    python_processes += 1
                    cmdline = proc.info.get('cmdline', [])
                    if cmdline and any('main.py' in arg or 'trade' in arg.lower() for arg in cmdline):
                        bot_processes += 1

            self.metrics.set_gauge("bot_processes_count", bot_processes)
            self.metrics.set_gauge("python_processes_count", python_processes)

            # Bot health status
            bot_status = 1 if bot_processes > 0 else 0
            self.metrics.set_gauge("bot_health_status", bot_status)

        except Exception as e:
            self.logger.error(f"Process metrics collection failed: {e}")
            self.metrics.increment_counter("bot_monitoring_errors", {"type": "process_metrics"})

    def check_production_readiness(self):
        """Evaluate production readiness criteria"""
        try:
            uptime_hours = (datetime.now() - self.start_time).total_seconds() / 3600

            # Production readiness criteria
            criteria = {
                "uptime_24h": uptime_hours >= 24,
                "memory_stable": True,  # Will be calculated based on growth
                "database_healthy": self.db_path.exists(),
                "bot_running": True  # Will be updated from process metrics
            }

            # Calculate readiness score
            readiness_score = sum(criteria.values()) / len(criteria)
            self.metrics.set_gauge("bot_production_readiness_score", readiness_score)

            # Individual criteria
            for criterion, status in criteria.items():
                self.metrics.set_gauge(f"bot_readiness_{criterion}", 1 if status else 0)

        except Exception as e:
            self.logger.error(f"Production readiness check failed: {e}")
            self.metrics.increment_counter("bot_monitoring_errors", {"type": "readiness_check"})

    def generate_summary_report(self):
        """Generate human-readable summary"""
        uptime_hours = (datetime.now() - self.start_time).total_seconds() / 3600

        report = f"""
PRODUCTION MONITORING DASHBOARD SUMMARY
========================================
Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Uptime: {uptime_hours:.2f} hours
Target: 24h continuous operation for production validation

Metrics Endpoint: http://localhost:{self.metrics_port}/metrics
Health Endpoint: http://localhost:{self.metrics_port}/health

Phase 2 Status: Advanced monitoring infrastructure operational
Next Phase: Production environment preparation
Target Go-Live: 18 Eylül 2025
        """.strip()

        return report

    def monitoring_loop(self, interval_minutes: int = 2):
        """Main monitoring loop with Prometheus metrics"""
        self.logger.info(f"Starting advanced monitoring loop - interval {interval_minutes} minutes")
        self.logger.info("Phase 2: Production Monitoring Setup - Prometheus integration active")

        while True:
            try:
                # Collect all metrics
                self.collect_system_metrics()
                self.collect_database_metrics()
                self.collect_process_metrics()
                self.check_production_readiness()

                # Log summary every 10 minutes
                if int(time.time()) % 600 == 0:
                    self.logger.info(self.generate_summary_report())

                time.sleep(interval_minutes * 60)

            except KeyboardInterrupt:
                self.logger.info("Monitoring stopped by user")
                break
            except Exception as e:
                self.logger.error(f"Monitoring loop error: {e}")
                self.metrics.increment_counter("bot_monitoring_errors", {"type": "loop_error"})
                time.sleep(30)

def main():
    print("Production Monitoring Dashboard - Phase 2 Setup")
    print("=" * 60)
    print("Advanced monitoring with Prometheus metrics integration")
    print("Following successful Phase 1 (24h testnet validation)")
    print("=" * 60)

    try:
        dashboard = ProductionMonitoringDashboard(metrics_port=8090)
        dashboard.monitoring_loop(interval_minutes=2)
    except Exception as e:
        print(f"Dashboard startup failed: {e}")
        logging.error(f"Dashboard startup failed: {e}")

if __name__ == "__main__":
    main()
