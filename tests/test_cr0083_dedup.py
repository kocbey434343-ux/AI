import types
import pytest

from src.trader import execution as exec_mod
from src.utils.order_dedup import _reset_for_tests


class DummyLogger:
    def __init__(self):
        self.logs = []
    def info(self, msg):
        self.logs.append(("INFO", msg))
    def warning(self, msg):
        self.logs.append(("WARN", msg))
    def error(self, msg):
        self.logs.append(("ERROR", msg))
    def debug(self, msg):
        self.logs.append(("DEBUG", msg))


class DummySelf:
    def __init__(self):
        self.market_mode = 'spot'
        self.logger = DummyLogger()
        self.positions = {}
        self.recent_open_latencies = []
        self.recent_entry_slippage_bps = []
        # Basit store stub
        self.trade_store = types.SimpleNamespace(insert_open=lambda **_: 1)


@pytest.fixture(autouse=True)
def _reset_singletons():
    _reset_for_tests()
    yield
    _reset_for_tests()


def _mk_order_ctx():
    return exec_mod.OrderContext(
        symbol='BTCUSDT', side='BUY', risk_side='long', price=50000.0,
        stop_loss=49000.0, take_profit=53000.0, protected_stop=48900.0,
        position_size=0.01, atr=None
    )


def test_order_dedup_should_block_second_submit(monkeypatch):
    dummy_self = DummySelf()

    # Monkeypatch heavy functions to no-op/minimal
    monkeypatch.setattr(exec_mod, 'prepare_order_context', lambda *_: _mk_order_ctx())
    monkeypatch.setattr(exec_mod, 'place_main_and_protection', lambda *_: {'price': _mk_order_ctx().price})
    monkeypatch.setattr(exec_mod, 'record_open', lambda *_: 1)
    monkeypatch.setattr(exec_mod, 'place_protection_orders', lambda *_: None)

    # 1) First call should pass (return True)
    ok1 = exec_mod.open_position(dummy_self, signal={}, ctx={})
    assert ok1 is True

    # 2) Immediate second call with same params should be skipped (return False)
    ok2 = exec_mod.open_position(dummy_self, signal={}, ctx={})
    assert ok2 is False

    # 3) After TTL expiry, it should allow again. Keep TTL small in settings or simulate time.
    # Simulate TTL by manually resetting dedup for test to avoid waiting.
    _reset_for_tests()
    ok3 = exec_mod.open_position(dummy_self, signal={}, ctx={})
    assert ok3 is True
