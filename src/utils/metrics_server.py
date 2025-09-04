"""
CR-0074: HTTP Metrics Endpoint
Simple HTTP server for Prometheus metrics endpoint
"""

import contextlib
import http.server
import socket
import socketserver
import threading
from typing import Optional

from src.utils.logger import get_logger

try:
    from src.utils.prometheus_export import get_exporter_instance as _get_exporter_instance_real
    PROMETHEUS_EXPORT_AVAILABLE = True
except ImportError:
    # Fallback if prometheus_export is not available
    PROMETHEUS_EXPORT_AVAILABLE = False
    _get_exporter_instance_real = None  # type: ignore


def _safe_get_exporter_instance():
    """Get exporter instance if available, else None (safe for import-time failures)."""
    try:
        if PROMETHEUS_EXPORT_AVAILABLE and _get_exporter_instance_real is not None:
            return _get_exporter_instance_real()
    except Exception:
        return None
    return None


class MetricsHandler(http.server.BaseHTTPRequestHandler):
    """HTTP handler for /metrics endpoint"""
    protocol_version = "HTTP/1.1"

    def __init__(self, *args, exporter=None, **kwargs):
        self.exporter = exporter or _safe_get_exporter_instance()
        super().__init__(*args, **kwargs)

    def do_GET(self):
        """Handle GET requests"""
        if self.path == '/metrics':
            self._handle_metrics()
        elif self.path == '/health':
            self._handle_health()
        else:
            self.send_error(404, "Endpoint not found")

    def _handle_metrics(self):
        """Handle /metrics endpoint"""
        try:
            if not self.exporter:
                self.send_error(503, "Metrics exporter not available")
                return

            metrics_data = self.exporter.generate_latest()
            content_type = self.exporter.get_content_type()
            body = metrics_data.encode('utf-8')

            self.send_response(200)
            self.send_header('Content-type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Connection', 'close')
            self.end_headers()
            self.wfile.write(body)
            with contextlib.suppress(Exception):
                self.wfile.flush()
            self.close_connection = True

        except Exception as e:
            self.send_error(500, f"Error generating metrics: {e}")

    def _handle_health(self):
        """Handle /health endpoint"""
        try:
            body = b"OK"
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Connection', 'close')
            self.end_headers()
            self.wfile.write(body)
            with contextlib.suppress(Exception):
                self.wfile.flush()
            self.close_connection = True

        except Exception as e:
            self.send_error(500, f"Health check failed: {e}")

    def log_message(self, format, *args):
        """Override to use our logger instead of stderr"""
        logger = get_logger(__name__)
        logger.info(f"HTTP {self.address_string()} - {format % args}")

    def address_string(self):
        """Avoid reverse DNS lookup which can block on some systems (e.g., Windows)."""
        return self.client_address[0]


class ThreadingTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True
    # Reduce request handling blocking time
    timeout = 0.5


class DualStackServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    """A Threading TCPServer that prefers IPv6 and enables dual-stack if possible."""
    address_family = socket.AF_INET6
    allow_reuse_address = True
    daemon_threads = True
    timeout = 0.5

    def server_bind(self):
        if self.address_family == socket.AF_INET6:
            with contextlib.suppress(Exception):
                self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        return super().server_bind()


class MetricsServer:
    """Simple HTTP server for Prometheus metrics"""

    def __init__(self, port: int = 8080, host: str = "localhost"):
        self.port = port
        self.host = host
        self.server: Optional[socketserver.TCPServer] = None
        self.server_thread: Optional[threading.Thread] = None
        self.exporter = _safe_get_exporter_instance()
        self.logger = get_logger(__name__)

    def start(self):
        """Start the metrics server"""
        try:
            # Create handler class with bound exporter
            def handler_factory(*args, **kwargs):
                return MetricsHandler(*args, exporter=self.exporter, **kwargs)

            # Prefer dual-stack IPv6 server to handle localhost resolving to ::1
            try:
                bind_addr = ("::", self.port) if self.host in ("localhost", "127.0.0.1") else (self.host, self.port)
                self.server = DualStackServer(bind_addr, handler_factory)
            except Exception:
                # Fallback to IPv4
                self.server = ThreadingTCPServer((self.host, self.port), handler_factory)
            # Use smaller poll interval to be more responsive in tests
            def _serve():
                # self.server is set above
                self.server.serve_forever(poll_interval=0.1)  # type: ignore[attr-defined]

            self.server_thread = threading.Thread(target=_serve, daemon=True)
            self.server_thread.start()

            self.logger.info(f"Metrics server started at http://{self.host}:{self.port}/metrics")
            return True

        except Exception as e:
            self.logger.error(f"Failed to start metrics server: {e}")
            return False

    def stop(self):
        """Stop the metrics server"""
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.logger.info("Metrics server stopped")
            if self.server_thread and self.server_thread.is_alive():
                # Join with a small timeout to prevent test hangs
                self.server_thread.join(timeout=1.0)
            self.server_thread = None
            self.server = None

    def is_running(self) -> bool:
        """Check if server is running"""
        return self.server is not None and self.server_thread is not None and self.server_thread.is_alive()


class MetricsServerManager:
    """Singleton manager for metrics server"""
    _instance = None
    _lock = threading.RLock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance.server = None
        return cls._instance

    def start_server(self, port: int = 8080, host: str = "localhost") -> bool:
        """Start metrics server"""
        with self._lock:
            if self.server and self.server.is_running():
                get_logger(__name__).warning("Metrics server already running")
                return True

            self.server = MetricsServer(port=port, host=host)
            return self.server.start()

    def stop_server(self):
        """Stop metrics server"""
        with self._lock:
            if self.server:
                self.server.stop()
                self.server = None

    def is_running(self) -> bool:
        """Check if server is running"""
        return self.server is not None and self.server.is_running()

    def get_server(self) -> Optional[MetricsServer]:
        """Get server instance"""
        return self.server


def start_metrics_server(port: int = 8080, host: str = "localhost") -> bool:
    """Start metrics server"""
    manager = MetricsServerManager()
    return manager.start_server(port=port, host=host)


def stop_metrics_server():
    """Stop metrics server"""
    manager = MetricsServerManager()
    manager.stop_server()


def is_metrics_server_running() -> bool:
    """Check if metrics server is running"""
    manager = MetricsServerManager()
    return manager.is_running()


def get_metrics_server() -> Optional[MetricsServer]:
    """Get metrics server instance"""
    manager = MetricsServerManager()
    return manager.get_server()
