from math import isclose
from src.execution.smart_execution import execute_sliced_market


class DummyAPI:
    def __init__(self):
        self.placed = []

    def quantize(self, _symbol, qty, price):
        return float(round(qty, 6)), price

    def place_order(self, symbol, side, order_type, quantity, price=None):
        self.placed.append((symbol, side, order_type, quantity))
        # Simulate exchange response
        return {
            'orderId': len(self.placed),
            'price': price,
            'fills': [{'price': price or 100.0, 'qty': quantity}],
        }


def test_execute_sliced_market_basic(monkeypatch):
    monkeypatch.setenv('SMART_EXECUTION_ENABLED', 'true')
    monkeypatch.setenv('TWAP_SLICES', '3')
    monkeypatch.setenv('TWAP_INTERVAL_SEC', '0')  # no sleep in tests
    monkeypatch.setenv('SMART_EXECUTION_SLEEP_SEC', '0')

    # Re-import Settings to apply env overrides for the test process
    from importlib import reload
    import config.settings as cfg
    reload(cfg)
    assert cfg.Settings.SMART_EXECUTION_ENABLED is True

    api = DummyAPI()
    last_order, executed = execute_sliced_market(api, 'BTCUSDT', 'BUY', 0.9, 100.0, sleep_fn=lambda _s: None)

    # 3 slices -> approx equal quantities (quantized)
    assert executed > 0
    MAX_SLICES = 3
    assert len(api.placed) <= MAX_SLICES
    assert last_order is not None


def test_execute_sliced_market_min_notional(monkeypatch):
    monkeypatch.setenv('SMART_EXECUTION_ENABLED', 'true')
    monkeypatch.setenv('TWAP_SLICES', '5')
    monkeypatch.setenv('MIN_SLICE_NOTIONAL_USDT', '50')
    monkeypatch.setenv('SMART_EXECUTION_SLEEP_SEC', '0')

    from importlib import reload
    import config.settings as cfg
    reload(cfg)

    api = DummyAPI()
    # price=10, qty per slice ~0.2 -> notional 2 < 50 => skip almost all slices
    last_order, executed = execute_sliced_market(api, 'ETHUSDT', 'BUY', 1.0, 10.0, sleep_fn=lambda _s: None)
    assert isclose(executed, 0.0, abs_tol=1e-12)
    assert last_order is None
