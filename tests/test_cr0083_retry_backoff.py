import pytest
from dataclasses import dataclass
from typing import Any


@pytest.fixture
def fake_metrics():
    class M:
        def __init__(self):
            self.backoffs = []
            self.retries = {}

        def observe_backoff_seconds(self, seconds: float) -> None:
            self.backoffs.append(float(seconds))

        def record_order_submit_retry(self, reason: str) -> None:
            self.retries[reason] = self.retries.get(reason, 0) + 1

    return M()


@pytest.fixture
def slog_spy(monkeypatch):
    calls = []
    def _slog(event, **payload):
        calls.append((event, payload))
    monkeypatch.setattr("src.trader.execution.slog", _slog, raising=False)
    return calls


class _Logger:
    def info(self, *a, **k):
        """Test stub: no-op logger."""
        pass
    def warning(self, *a, **k):
        """Test stub: no-op logger."""
        pass
    def error(self, *a, **k):
        """Test stub: no-op logger."""
        pass
    def debug(self, *a, **k):
        """Test stub: no-op logger."""
        pass


@dataclass
class _SelfObj:
    metrics: Any
    logger: Any


def _make_self(fake_metrics):
    return _SelfObj(metrics=fake_metrics, logger=_Logger())


def _make_oc():
    from src.trader.execution import OrderContext
    return OrderContext(
        symbol="BTCUSDT",
        side="BUY",
        risk_side="long",
        price=100.0,
        stop_loss=95.0,
        take_profit=115.0,
        protected_stop=94.5,
        position_size=0.01,
        atr=None,
    )


def test_place_with_retry_succeeds_after_transient_failures(monkeypatch, fake_metrics, slog_spy):
    # Settings: 3 deneme; jitter deterministik; sleep no-op
    from config.settings import Settings
    monkeypatch.setattr(Settings, "RETRY_MAX_ATTEMPTS", 3, raising=False)
    monkeypatch.setattr(Settings, "RETRY_BACKOFF_BASE_SEC", 0.1, raising=False)
    monkeypatch.setattr(Settings, "RETRY_BACKOFF_MULT", 2.0, raising=False)

    # place_main_and_protection: ilk iki deneme None, sonra sahte order
    call_state = {"n": 0}
    ORDER_ID = 123
    FAIL_UNTIL = 2
    EXPECT_RETRIES = 2

    def fake_place(*_args, **_kwargs):
        call_state["n"] += 1
        if call_state["n"] <= FAIL_UNTIL:
            return None
        return {"orderId": ORDER_ID}

    monkeypatch.setattr("src.trader.execution.place_main_and_protection", fake_place, raising=False)
    monkeypatch.setattr("src.trader.execution.time.sleep", lambda *_args, **_kwargs: None, raising=False)
    # random module icindeki uniform'u sabitle
    monkeypatch.setattr("random.uniform", lambda *_args, **_kwargs: 1.0, raising=False)

    s = _make_self(fake_metrics)
    oc = _make_oc()
    from src.trader.execution import _place_with_retry
    order = _place_with_retry(s, oc)

    assert order and order.get("orderId") == ORDER_ID
    # 2 kez bekleme ve retry metrik kaydi olmali
    assert len(fake_metrics.backoffs) == EXPECT_RETRIES
    assert fake_metrics.retries.get("order_place_fail") == EXPECT_RETRIES
    # slog retry event sayisi
    retry_events = [e for e, _ in slog_spy if e == "order_submit_retry"]
    assert len(retry_events) == EXPECT_RETRIES


def test_place_with_retry_gives_up_after_max_attempts(monkeypatch, fake_metrics, slog_spy):
    from config.settings import Settings
    monkeypatch.setattr(Settings, "RETRY_MAX_ATTEMPTS", 3, raising=False)
    monkeypatch.setattr(Settings, "RETRY_BACKOFF_BASE_SEC", 0.05, raising=False)
    monkeypatch.setattr(Settings, "RETRY_BACKOFF_MULT", 2.0, raising=False)

    # Her deneme None dondursun
    def always_none(*_args, **_kwargs):
        return None

    monkeypatch.setattr("src.trader.execution.place_main_and_protection", always_none, raising=False)
    monkeypatch.setattr("src.trader.execution.time.sleep", lambda *_args, **_kwargs: None, raising=False)
    monkeypatch.setattr("random.uniform", lambda *_args, **_kwargs: 1.0, raising=False)

    s = _make_self(fake_metrics)
    oc = _make_oc()
    from src.trader.execution import _place_with_retry
    order = _place_with_retry(s, oc)

    assert order is None
    # max_attempts-1 kadar backoff ve retry metrik kaydi olmali
    EXPECT_RETRIES = 2
    assert len(fake_metrics.backoffs) == EXPECT_RETRIES
    assert fake_metrics.retries.get("order_place_fail") == EXPECT_RETRIES
    retry_events = [e for e, _ in slog_spy if e == "order_submit_retry"]
    assert len(retry_events) == EXPECT_RETRIES
