"""
Performance Monitor Panel test
Phase 4: Performance Optimization & Advanced Features test
"""

import sys
import time
import pytest
from unittest.mock import MagicMock, patch

# PyQt5 import attempt
try:
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtCore import QTimer
    HAS_PYQT5 = True
except ImportError:
    HAS_PYQT5 = False

# Test sadece PyQt5 varsa çalışır
pytestmark = pytest.mark.skipif(not HAS_PYQT5, reason="PyQt5 not available")

from src.ui.performance_monitor_panel import PerformanceMonitorPanel, PerformanceMetricsCollector


class TestPerformanceMonitorPanel:
    """Performance Monitor Panel test suite"""

    @pytest.fixture
    def app(self):
        """QApplication fixture"""
        if not QApplication.instance():
            app = QApplication(sys.argv)
        else:
            app = QApplication.instance()
        yield app
        # Cleanup handled by pytest

    @pytest.fixture
    def panel(self, app):
        """Performance Monitor Panel fixture"""
        panel = PerformanceMonitorPanel()
        yield panel
        panel.stop_monitoring()
        panel.close()

    def test_panel_initialization(self, panel):
        """Panel başlatma testı"""
        assert panel is not None
        assert hasattr(panel, 'metrics_collector')
        assert hasattr(panel, 'is_monitoring')
        assert panel.objectName() == "PerformanceMonitorPanel"

    def test_metrics_collector_initialization(self, app):
        """Metrics collector başlatma testı"""
        collector = PerformanceMetricsCollector()
        assert collector is not None
        assert collector.collection_interval == 1.0
        assert not collector.running

    def test_system_metrics_collection(self, app):
        """Sistem metrikleri toplama testı"""
        collector = PerformanceMetricsCollector()
        metrics = collector.collect_system_metrics()

        assert 'cpu_percent' in metrics
        assert 'memory_percent' in metrics
        assert 'memory_used_mb' in metrics
        assert 'memory_total_mb' in metrics

        # CPU percentage should be valid
        assert 0 <= metrics['cpu_percent'] <= 100

        # Memory percentage should be valid
        assert 0 <= metrics['memory_percent'] <= 100

    def test_mock_a32_metrics(self, app):
        """A32 mock metrics testı"""
        collector = PerformanceMetricsCollector()
        metrics = collector.mock_a32_metrics()

        assert 'edge_health_latency_ms' in metrics
        assert 'cost_calc_latency_ms' in metrics
        assert 'microstructure_latency_ms' in metrics
        assert 'edge_status' in metrics
        assert 'total_trades' in metrics

        # Latency values should be reasonable
        assert 0 < metrics['edge_health_latency_ms'] < 100
        assert 0 < metrics['cost_calc_latency_ms'] < 100

        # Edge status should be valid
        assert metrics['edge_status'] in ['HOT', 'WARM', 'COLD']

    def test_latency_measurement(self, app):
        """Latency ölçüm testı"""
        collector = PerformanceMetricsCollector()

        # Test function with known delay
        def test_func():
            time.sleep(0.01)  # 10ms

        latency = collector.measure_call_latency(test_func)

        # Should be around 10ms (+/- tolerance)
        assert 8 < latency < 20

    def test_alert_generation(self, app):
        """Alert üretimi testı"""
        collector = PerformanceMetricsCollector()

        # Mock high CPU usage
        with patch.object(collector, 'collect_system_metrics') as mock_system:
            mock_system.return_value = {
                'cpu_percent': 90,  # High CPU
                'memory_percent': 50,
                'memory_used_mb': 1000,
                'memory_total_mb': 2000
            }

            alerts = collector.collect_alert_metrics()

            # Should generate CPU alert
            cpu_alerts = [a for a in alerts if 'CPU' in a['message']]
            assert len(cpu_alerts) > 0
            assert cpu_alerts[0]['level'] == 'warning'

    def test_monitoring_start_stop(self, panel):
        """Monitoring başlatma/durdurma testı"""
        # Initially should be running (auto-start)
        assert panel.is_monitoring

        # Stop monitoring
        panel.stop_monitoring()
        assert not panel.is_monitoring

        # Restart monitoring
        panel.start_monitoring()
        assert panel.is_monitoring

    def test_metrics_display_update(self, panel):
        """Metrics display güncelleme testı"""
        # Mock metrics data
        mock_metrics = {
            'system': {
                'cpu_percent': 45.2,
                'memory_percent': 65.8,
                'memory_used_mb': 1024,
                'memory_total_mb': 2048
            },
            'a32': {
                'edge_health_latency_ms': 25.5,
                'cost_calc_latency_ms': 12.3,
                'microstructure_latency_ms': 18.7,
                'edge_status': 'HOT',
                'total_trades': 150
            },
            'api_latency': {
                'avg_api_latency_ms': 42.1,
                'max_api_latency_ms': 120.5
            },
            'alerts': [],
            'timestamp': time.time()
        }

        # Update display
        panel.update_metrics_display(mock_metrics)

        # Check that labels are updated
        assert "45.2%" in panel.cpu_label.text()
        assert "65.8%" in panel.memory_label.text()
        assert "HOT" in panel.edge_status_label.text()

    def test_table_updates(self, panel):
        """Tablo güncelleme testı"""
        initial_row_count = panel.realtime_table.rowCount()

        # Add some mock data
        mock_metrics = {
            'system': {'cpu_percent': 30, 'memory_percent': 40},
            'a32': {'edge_health_latency_ms': 20, 'edge_status': 'WARM'},
            'api_latency': {'avg_api_latency_ms': 35},
            'alerts': [],
            'timestamp': time.time()
        }

        panel.add_realtime_table_row(mock_metrics)

        # Should have added one row
        assert panel.realtime_table.rowCount() == initial_row_count + 1

    def test_clear_metrics(self, panel):
        """Metrics temizleme testı"""
        # Add some data first
        panel.metrics_history = [{'test': 'data'}]
        panel.realtime_table.insertRow(0)

        # Clear metrics
        panel.clear_metrics()

        # Should be empty
        assert len(panel.metrics_history) == 0
        assert panel.realtime_table.rowCount() == 0

    def test_log_message(self, panel):
        """Log mesajı testı"""
        initial_content = panel.logs_text.toPlainText()

        panel.log_message("Test log message")

        new_content = panel.logs_text.toPlainText()
        assert "Test log message" in new_content
        assert len(new_content) > len(initial_content)


class TestPerformanceMetricsCollectorIntegration:
    """Integration tests for metrics collector"""

    def test_full_metrics_collection(self):
        """Tam metrics collection integration testı"""
        collector = PerformanceMetricsCollector()

        metrics = collector.collect_all_metrics()

        # Should have all required sections
        assert 'system' in metrics
        assert 'a32' in metrics
        assert 'api_latency' in metrics
        assert 'alerts' in metrics
        assert 'timestamp' in metrics

        # Timestamp should be recent
        import datetime
        timestamp = metrics['timestamp']
        now = datetime.datetime.now()

        # Should be within last few seconds
        assert abs((now - timestamp).total_seconds()) < 10


if __name__ == "__main__":
    """Standalone test runner"""
    pytest.main([__file__, "-v"])
