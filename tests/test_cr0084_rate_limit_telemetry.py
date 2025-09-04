"""
CR-0084: Rate Limit & Backoff Telemetry basic unit tests
"""
import pytest

try:
    import prometheus_client
    PROMETHEUS_AVAILABLE = True
except ImportError:  # pragma: no cover
    PROMETHEUS_AVAILABLE = False


@pytest.mark.skipif(not PROMETHEUS_AVAILABLE, reason="prometheus_client not available")
class TestRateLimitTelemetry:
    def setup_method(self):
        # Clear global registry to avoid conflicts across tests
        if PROMETHEUS_AVAILABLE:
            prometheus_client.REGISTRY._collector_to_names.clear()
            prometheus_client.REGISTRY._names_to_collectors.clear()

    def test_rate_limit_and_backoff_metrics_recorded(self):
        from src.utils.prometheus_export import PrometheusExporter

        exp = PrometheusExporter()
        # simulate 429 and 418
        exp.record_rate_limit_hit(429)
        exp.record_rate_limit_hit(418)
        # simulate backoff observations
        exp.observe_backoff_seconds(0.05)
        exp.observe_backoff_seconds(1.2)

        out = exp.generate_latest()
        assert 'bot_rate_limit_hits_total' in out
        assert 'code="429"' in out
        assert 'code="418"' in out
        assert 'bot_backoff_seconds' in out

    def test_used_weight_gauge_update(self):
        from src.utils.prometheus_export import PrometheusExporter

        exp = PrometheusExporter()
        # set used weight gauge
        exp.set_used_weight(120.0)
        out = exp.generate_latest()
        assert 'bot_used_weight_gauge 120.0' in out
