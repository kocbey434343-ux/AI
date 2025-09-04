"""Clock skew guard tests."""

# ruff: noqa: I001

import time

import pytest

from config.settings import Settings
from src.api.health_check import HealthChecker


class DummyExporter:
    def __init__(self):
        self.skew_values = []
        self.alerts = 0

    def record_clock_skew_ms(self, v):
        self.skew_values.append(v)

    def inc_clock_skew_alert(self):
        self.alerts += 1


@pytest.fixture(autouse=True)
def patch_exporter(monkeypatch):
    dummy = DummyExporter()
    monkeypatch.setattr('src.api.health_check.get_exporter_instance', lambda: dummy)
    return dummy


def test_clock_skew_normal(monkeypatch, patch_exporter):
    hc = HealthChecker()
    # serverTime ~ now (difference ~50ms)
    def _near_now():
        return {'serverTime': (time.time() * 1000.0) + 50.0}

    monkeypatch.setattr(hc.api, 'get_server_time', _near_now)
    # Force threshold high to pass easily
    monkeypatch.setattr(Settings, 'CLOCK_SKEW_WARN_MS', 500.0, raising=False)
    monkeypatch.setattr(Settings, 'CLOCK_SKEW_GUARD_ENABLED', True, raising=False)

    ok, msg = hc.check_clock_skew()
    assert ok is True
    assert 'Clock skew' in msg
    assert patch_exporter.skew_values, 'metric not recorded'
    assert patch_exporter.alerts == 0


def test_clock_skew_alert(monkeypatch, patch_exporter):
    hc = HealthChecker()
    # Create a large skew: 10_000 ms ahead of local
    monkeypatch.setattr(hc.api, 'get_server_time', lambda: {'serverTime': 10_000_000.0})
    monkeypatch.setattr(Settings, 'CLOCK_SKEW_WARN_MS', 100.0, raising=False)
    monkeypatch.setattr(Settings, 'CLOCK_SKEW_GUARD_ENABLED', True, raising=False)

    ok, msg = hc.check_clock_skew()
    assert ok is False
    assert 'Clock skew high' in msg
    assert patch_exporter.alerts >= 1
