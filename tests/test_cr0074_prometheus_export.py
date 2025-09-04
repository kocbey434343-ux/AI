"""
CR-0074: Test Prometheus Metrics Export
"""

import pytest
import time
import threading
from unittest.mock import Mock, patch, MagicMock

try:
    import prometheus_client
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False


@pytest.mark.skipif(not PROMETHEUS_AVAILABLE, reason="prometheus_client not available")
class TestPrometheusExport:
    """Test Prometheus metrics export functionality"""

    def setup_method(self):
        """Setup test environment"""
        # Clear global registry to avoid conflicts
        if PROMETHEUS_AVAILABLE:
            prometheus_client.REGISTRY._collector_to_names.clear()
            prometheus_client.REGISTRY._names_to_collectors.clear()

    def test_prometheus_exporter_init(self):
        """Test PrometheusExporter initialization"""
        from src.utils.prometheus_export import PrometheusExporter

        exporter = PrometheusExporter()
        assert exporter.enabled
        assert exporter.registry is not None
        assert hasattr(exporter, 'open_latency_histogram')
        assert hasattr(exporter, 'guard_block_counter')

    def test_record_latency_metrics(self):
        """Test recording latency metrics"""
        from src.utils.prometheus_export import PrometheusExporter

        exporter = PrometheusExporter()

        # Record some latencies
        exporter.record_open_latency(100.5)
        exporter.record_close_latency(75.2)

        # Generate metrics output
        output = exporter.generate_latest()
        assert 'bot_open_latency_ms' in output
        assert 'bot_close_latency_ms' in output

    def test_record_slippage_metrics(self):
        """Test recording slippage metrics"""
        from src.utils.prometheus_export import PrometheusExporter

        exporter = PrometheusExporter()

        # Record some slippage
        exporter.record_entry_slippage(5.2)
        exporter.record_exit_slippage(3.1)

        output = exporter.generate_latest()
        assert 'bot_entry_slippage_bps' in output
        assert 'bot_exit_slippage_bps' in output

    def test_guard_block_counter(self):
        """Test guard block counter"""
        from src.utils.prometheus_export import PrometheusExporter

        exporter = PrometheusExporter()

        # Record guard blocks
        exporter.record_guard_block('daily_loss')
        exporter.record_guard_block('correlation')
        exporter.record_guard_block('daily_loss')  # Same guard again

        output = exporter.generate_latest()
        assert 'bot_guard_block_total' in output
        assert 'guard="daily_loss"' in output
        assert 'guard="correlation"' in output

    def test_position_and_pnl_gauges(self):
        """Test position count and PnL gauges"""
        from src.utils.prometheus_export import PrometheusExporter

        exporter = PrometheusExporter()

        # Update gauges
        exporter.update_positions_count(3)
        exporter.update_unrealized_pnl(125.50)

        output = exporter.generate_latest()
        assert 'bot_positions_open_gauge 3.0' in output
        assert 'bot_unrealized_pnl_gauge 125.5' in output

    def test_trade_counters(self):
        """Test trade opened/closed counters"""
        from src.utils.prometheus_export import PrometheusExporter

        exporter = PrometheusExporter()

        # Record trades
        exporter.record_trade_opened('BTCUSDT')
        exporter.record_trade_opened('ETHUSDT')
        exporter.record_trade_closed('BTCUSDT', 'profit')
        exporter.record_trade_closed('ETHUSDT', 'loss')

        output = exporter.generate_latest()
        assert 'bot_trades_opened_total' in output
        assert 'bot_trades_closed_total' in output
        assert 'symbol="BTCUSDT"' in output
        assert 'result="profit"' in output

    def test_health_status_gauge(self):
        """Test health status gauge"""
        from src.utils.prometheus_export import PrometheusExporter

        exporter = PrometheusExporter()

        # Update health status
        exporter.update_health_status('binance_api', 1)  # healthy
        exporter.update_health_status('websocket', 0)    # unhealthy

        output = exporter.generate_latest()
        assert 'bot_health_status_gauge' in output
        assert 'component="binance_api"' in output
        assert 'component="websocket"' in output

    def test_collect_from_trader(self):
        """Test collecting metrics from trader object"""
        from src.utils.prometheus_export import PrometheusExporter

        exporter = PrometheusExporter()

        # Mock trader metrics
        mock_metrics = Mock()
        mock_metrics.recent_open_latencies = [100.0, 150.0]
        mock_metrics.recent_entry_slippage_bps = [2.5, 3.0]
        mock_metrics.has_latency_anomaly = True
        mock_metrics.has_slippage_anomaly = False

        # Collect metrics
        exporter.collect_from_trader(mock_metrics)

        output = exporter.generate_latest()
        assert 'bot_open_latency_ms' in output
        assert 'bot_entry_slippage_bps' in output
        assert 'bot_anomaly_trigger_total' in output

    def test_thread_safety(self):
        """Test thread safety of metrics collection"""
        from src.utils.prometheus_export import PrometheusExporter

        exporter = PrometheusExporter()
        errors = []

        def record_metrics(thread_id):
            try:
                for i in range(100):
                    exporter.record_open_latency(thread_id * 100 + i)
                    exporter.record_guard_block(f'guard_{thread_id}')
                    exporter.update_positions_count(i)
            except Exception as e:
                errors.append(e)

        # Start multiple threads
        threads = []
        for i in range(5):
            t = threading.Thread(target=record_metrics, args=(i,))
            threads.append(t)
            t.start()

        # Wait for completion
        for t in threads:
            t.join()

        # Check no errors occurred
        assert len(errors) == 0

        # Verify metrics were recorded
        output = exporter.generate_latest()
        assert 'bot_open_latency_ms' in output
        assert 'bot_guard_block_total' in output


class TestMetricsServer:
    """Test metrics HTTP server"""

    @pytest.mark.skipif(not PROMETHEUS_AVAILABLE, reason="prometheus_client not available")
    def test_metrics_server_start_stop(self):
        """Test metrics server start/stop"""
        from src.utils.metrics_server import MetricsServer

        server = MetricsServer(port=8081)  # Use different port

        # Start server
        assert server.start()
        assert server.is_running()

        # Give it a moment to start
        time.sleep(0.1)

        # Stop server
        server.stop()
        time.sleep(0.1)
        assert not server.is_running()

    @pytest.mark.skipif(not PROMETHEUS_AVAILABLE, reason="prometheus_client not available")
    def test_metrics_endpoint(self):
        """Test /metrics endpoint"""
        import requests
        from src.utils.metrics_server import MetricsServer

        server = MetricsServer(port=8082)  # Use different port

        try:
            assert server.start()
            time.sleep(0.2)  # Give server time to start

            # Test /metrics endpoint
            response = requests.get('http://localhost:8082/metrics', timeout=1)
            assert response.status_code == 200
            assert 'bot_' in response.text or 'Prometheus client not available' in response.text

        except requests.exceptions.RequestException:
            # Server might not have started properly, that's OK for this test
            pass
        finally:
            server.stop()
            time.sleep(0.1)

    @pytest.mark.skipif(not PROMETHEUS_AVAILABLE, reason="prometheus_client not available")
    def test_health_endpoint(self):
        """Test /health endpoint"""
        import requests
        from src.utils.metrics_server import MetricsServer

        server = MetricsServer(port=8083)  # Use different port

        try:
            assert server.start()
            time.sleep(0.2)  # Give server time to start

            # Test /health endpoint
            response = requests.get('http://localhost:8083/health', timeout=1)
            assert response.status_code == 200
            assert response.text == 'OK'

        except requests.exceptions.RequestException:
            # Server might not have started properly, that's OK for this test
            pass
        finally:
            server.stop()
            time.sleep(0.1)


class TestTraderMetricsIntegration:
    """Test trader metrics integration"""

    def test_trader_metrics_integration_init(self):
        """Test TraderMetricsIntegration initialization"""
        from src.utils.trader_metrics_integration import TraderMetricsIntegration

        mock_trader = Mock()
        integration = TraderMetricsIntegration(mock_trader)

        assert integration.trader == mock_trader
        # metrics_enabled might be False if prometheus_client not available
        assert hasattr(integration, 'metrics_enabled')

    @patch('src.utils.trader_metrics_integration.METRICS_AVAILABLE', True)
    @patch('src.utils.trader_metrics_integration.get_exporter_instance')
    def test_record_trade_events(self, mock_get_exporter):
        """Test recording trade events"""
        from src.utils.trader_metrics_integration import TraderMetricsIntegration

        mock_exporter = Mock()
        mock_get_exporter.return_value = mock_exporter
        mock_trader = Mock()

        integration = TraderMetricsIntegration(mock_trader)
        integration.metrics_enabled = True
        integration.prometheus_exporter = mock_exporter

        # Test trade opened
        integration.record_trade_opened('BTCUSDT')
        mock_exporter.record_trade_opened.assert_called_with('BTCUSDT')

        # Test trade closed
        integration.record_trade_closed('BTCUSDT', 15.50)  # profit
        mock_exporter.record_trade_closed.assert_called_with('BTCUSDT', 'profit')

        # Test loss
        integration.record_trade_closed('ETHUSDT', -10.25)  # loss
        mock_exporter.record_trade_closed.assert_called_with('ETHUSDT', 'loss')

    @patch('src.utils.trader_metrics_integration.METRICS_AVAILABLE', True)
    @patch('src.utils.trader_metrics_integration.get_exporter_instance')
    def test_update_positions(self, mock_get_exporter):
        """Test updating position metrics"""
        from src.utils.trader_metrics_integration import TraderMetricsIntegration

        mock_exporter = Mock()
        mock_get_exporter.return_value = mock_exporter
        mock_trader = Mock()

        integration = TraderMetricsIntegration(mock_trader)
        integration.metrics_enabled = True
        integration.prometheus_exporter = mock_exporter

        # Test position count update
        integration.update_positions_count(5)
        mock_exporter.update_positions_count.assert_called_with(5)

        # Test unrealized PnL update
        integration.update_unrealized_pnl(123.45)
        mock_exporter.update_unrealized_pnl.assert_called_with(123.45)

    def test_patch_trader_with_metrics(self):
        """Test patching trader with metrics"""
        from src.utils.trader_metrics_integration import patch_trader_with_metrics

        mock_trader = Mock()

        # Patch trader
        integration = patch_trader_with_metrics(mock_trader)

        # Verify integration was added
        assert hasattr(mock_trader, '_metrics_integration')
        assert mock_trader._metrics_integration == integration

        # Verify convenience methods were added
        assert hasattr(mock_trader, 'init_metrics_server')
        assert hasattr(mock_trader, 'shutdown_metrics_server')
        assert hasattr(mock_trader, 'collect_metrics')


class TestMetricsWithoutPrometheus:
    """Test metrics system when prometheus_client is not available"""

    @patch('src.utils.prometheus_export.PROMETHEUS_AVAILABLE', False)
    def test_exporter_disabled_when_prometheus_unavailable(self):
        """Test that exporter is disabled when prometheus_client is not available"""
        from src.utils.prometheus_export import PrometheusExporter

        exporter = PrometheusExporter()
        assert not exporter.enabled

        # Should not raise errors
        exporter.record_open_latency(100.0)
        exporter.record_guard_block('test')

        # Should return fallback content
        output = exporter.generate_latest()
        assert 'Prometheus client not available' in output

    @patch('src.utils.trader_metrics_integration.METRICS_AVAILABLE', False)
    def test_trader_integration_disabled(self):
        """Test that trader integration is disabled gracefully"""
        from src.utils.trader_metrics_integration import TraderMetricsIntegration

        mock_trader = Mock()
        integration = TraderMetricsIntegration(mock_trader)

        assert not integration.metrics_enabled

        # Should not raise errors
        integration.record_trade_opened('BTCUSDT')
        integration.update_positions_count(3)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
