"""
Test for Advanced Metrics Collector

Testing the enhanced performance monitoring system
"""

import pytest
import time
import threading
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from src.utils.advanced_metrics import (
    AdvancedMetricsCollector,
    get_metrics_collector,
    profile_performance,
    get_trading_metrics,
    TradingMetricsCollector,
    MetricPoint,
    PerformanceProfile
)


class TestAdvancedMetricsCollector:
    """Test AdvancedMetricsCollector functionality"""

    def test_collector_initialization(self):
        """Test metrics collector initialization"""
        collector = AdvancedMetricsCollector(history_size=500)

        assert collector.history_size == 500
        assert not collector.running
        assert len(collector.metrics_history) == 0
        assert len(collector.performance_profiles) == 0

    def test_metric_recording(self):
        """Test basic metric recording"""
        collector = AdvancedMetricsCollector()
        now = datetime.now()

        collector._record_metric('test_metric', now, 42.5, {'source': 'test'})

        assert 'test_metric' in collector.metrics_history
        points = collector.metrics_history['test_metric']
        assert len(points) == 1
        assert points[0].value == 42.5
        assert points[0].tags['source'] == 'test'

    def test_metric_summary(self):
        """Test metric summary statistics"""
        collector = AdvancedMetricsCollector()
        now = datetime.now()

        # Add test data
        values = [10.0, 20.0, 30.0, 40.0, 50.0]
        for i, value in enumerate(values):
            timestamp = now + timedelta(seconds=i)
            collector._record_metric('test_metric', timestamp, value, {})

        summary = collector.get_metric_summary('test_metric', window_minutes=5)

        assert summary['count'] == 5
        assert summary['min'] == 10.0
        assert summary['max'] == 50.0
        assert summary['avg'] == 30.0
        assert summary['latest'] == 50.0

    def test_performance_profiling(self):
        """Test function performance profiling"""
        collector = AdvancedMetricsCollector()

        @collector.profile_function("test_function")
        def slow_function():
            time.sleep(0.01)  # 10ms delay
            return "result"

        result = slow_function()

        assert result == "result"
        assert len(collector.performance_profiles) == 1

        profile = collector.performance_profiles[0]
        assert profile.function_name == "test_function"
        assert profile.execution_time_ms >= 10.0  # At least 10ms

    def test_performance_summary(self):
        """Test performance summary aggregation"""
        collector = AdvancedMetricsCollector()

        # Simulate multiple function calls
        for i in range(3):
            profile = PerformanceProfile(
                function_name="test_func",
                execution_time_ms=10.0 + i,
                memory_delta_mb=1.0,
                cpu_percent=50.0,
                call_count=1
            )
            collector.performance_profiles.append(profile)

        summary = collector.get_performance_summary()

        assert "test_func" in summary
        func_stats = summary["test_func"]
        assert func_stats['call_count'] == 3
        assert func_stats['avg_execution_ms'] == 11.0  # (10+11+12)/3
        assert func_stats['max_execution_ms'] == 12.0

    def test_anomaly_detection(self):
        """Test performance anomaly detection"""
        collector = AdvancedMetricsCollector()

        # Add high latency profile
        high_latency_profile = PerformanceProfile(
            function_name="slow_func",
            execution_time_ms=600.0,  # Above critical threshold
            memory_delta_mb=1.0,
            cpu_percent=50.0,
            call_count=1
        )
        collector.performance_profiles.append(high_latency_profile)

        anomalies = collector.detect_anomalies()

        assert len(anomalies) > 0
        latency_anomaly = next((a for a in anomalies if a['type'] == 'performance'), None)
        assert latency_anomaly is not None
        assert latency_anomaly['severity'] == 'critical'
        assert 'slow_func' in latency_anomaly['message']

    def test_collection_thread_lifecycle(self):
        """Test background collection thread"""
        collector = AdvancedMetricsCollector()

        # Start collection
        collector.start_collection(interval_seconds=0.1)
        assert collector.running
        assert collector.collection_thread is not None

        # Let it run briefly
        time.sleep(0.2)

        # Stop collection
        collector.stop_collection()
        assert not collector.running

    @patch('psutil.cpu_times')
    @patch('psutil.virtual_memory')
    def test_system_metrics_collection(self, mock_memory, mock_cpu):
        """Test system metrics collection with mocks"""
        # Mock system data
        mock_cpu.return_value = MagicMock(user=10.5, system=5.2, iowait=1.1)
        mock_memory.return_value = MagicMock(
            available=8589934592,  # 8GB
            cached=1073741824      # 1GB
        )

        collector = AdvancedMetricsCollector()
        collector._collect_system_metrics()

        # Check that metrics were recorded
        assert 'cpu_user' in collector.metrics_history
        assert 'memory_available_gb' in collector.metrics_history

        cpu_data = collector.metrics_history['cpu_user'][-1]
        assert cpu_data.value == 10.5
        assert cpu_data.tags['type'] == 'system'

    def test_export_functionality(self):
        """Test metrics export"""
        collector = AdvancedMetricsCollector()
        now = datetime.now()

        # Add some test data
        collector._record_metric('test_metric', now, 42.0, {'test': 'value'})

        export_json = collector.export_metrics(format='json')

        assert '"timestamp"' in export_json
        assert '"metrics_summary"' in export_json
        assert '"performance_summary"' in export_json
        assert '"anomalies"' in export_json


class TestTradingMetricsCollector:
    """Test trading-specific metrics"""

    def test_trade_latency_recording(self):
        """Test trade latency recording"""
        collector = TradingMetricsCollector()

        collector.record_trade_latency(50.5, 'BUY')
        collector.record_trade_latency(75.2, 'SELL')

        assert len(collector.trade_latencies) == 2

        stats = collector.get_trade_latency_stats()
        assert stats['count'] == 2
        assert stats['avg_ms'] == (50.5 + 75.2) / 2
        assert stats['min_ms'] == 50.5
        assert stats['max_ms'] == 75.2

    def test_strategy_performance_recording(self):
        """Test strategy performance recording"""
        collector = TradingMetricsCollector()

        performance_data = {
            'pnl': 150.0,
            'trades': 5,
            'win_rate': 0.8
        }

        collector.record_strategy_performance('test_strategy', performance_data)

        assert 'test_strategy' in collector.strategy_metrics
        assert len(collector.strategy_metrics['test_strategy']) == 1

        recorded = collector.strategy_metrics['test_strategy'][0]
        assert recorded['pnl'] == 150.0
        assert recorded['trades'] == 5
        assert recorded['win_rate'] == 0.8
        assert 'timestamp' in recorded


class TestGlobalInstances:
    """Test global instance management"""

    def test_get_metrics_collector_singleton(self):
        """Test that get_metrics_collector returns same instance"""
        collector1 = get_metrics_collector()
        collector2 = get_metrics_collector()

        assert collector1 is collector2
        assert isinstance(collector1, AdvancedMetricsCollector)

    def test_get_trading_metrics_singleton(self):
        """Test that get_trading_metrics returns same instance"""
        trading1 = get_trading_metrics()
        trading2 = get_trading_metrics()

        assert trading1 is trading2
        assert isinstance(trading1, TradingMetricsCollector)

    def test_profile_performance_decorator(self):
        """Test profile_performance decorator"""
        @profile_performance("decorated_function")
        def test_function():
            time.sleep(0.01)
            return 42

        result = test_function()

        assert result == 42

        # Check that profiling was recorded
        collector = get_metrics_collector()
        assert len(collector.performance_profiles) > 0

        latest_profile = collector.performance_profiles[-1]
        assert latest_profile.function_name == "decorated_function"
        assert latest_profile.execution_time_ms >= 10.0


class TestMemoryTracking:
    """Test memory tracking functionality"""

    @patch('tracemalloc.is_tracing')
    @patch('tracemalloc.get_traced_memory')
    def test_memory_metrics_collection(self, mock_get_traced, mock_is_tracing):
        """Test memory metrics collection with mocks"""
        mock_is_tracing.return_value = True
        mock_get_traced.return_value = (1048576, 2097152)  # 1MB current, 2MB peak

        collector = AdvancedMetricsCollector()
        collector._collect_memory_metrics()

        assert 'python_memory_current_mb' in collector.metrics_history
        assert 'python_memory_peak_mb' in collector.metrics_history

        current_data = collector.metrics_history['python_memory_current_mb'][-1]
        assert abs(current_data.value - 1.0) < 0.01  # ~1MB

        peak_data = collector.metrics_history['python_memory_peak_mb'][-1]
        assert abs(peak_data.value - 2.0) < 0.01  # ~2MB


class TestPerformanceIntegration:
    """Integration tests for performance monitoring"""

    def test_end_to_end_monitoring(self):
        """Test complete monitoring workflow"""
        collector = get_metrics_collector()
        trading = get_trading_metrics()

        # Record some trading metrics
        trading.record_trade_latency(45.2, 'BUY')
        trading.record_strategy_performance('test_strat', {'pnl': 100.0})

        # Record system metrics
        now = datetime.now()
        collector._record_metric('cpu_usage', now, 65.5, {'type': 'system'})

        # Get summaries
        trading_stats = trading.get_trade_latency_stats()
        system_summary = collector.get_metric_summary('cpu_usage')

        assert trading_stats['count'] == 1
        assert trading_stats['avg_ms'] == 45.2

        assert system_summary['latest'] == 65.5

        # Export everything
        export_data = collector.export_metrics()
        assert len(export_data) > 0
        assert '"timestamp"' in export_data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
