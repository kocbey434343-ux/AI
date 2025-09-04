import pytest
from src.api.binance_api import BinanceAPI

class DummyClient:
    def __init__(self, spot=True):
        self.spot = spot
        self._exchange_info = {
            'symbols': [
                {
                    'symbol': 'BTCUSDT',
                    'filters': [
                        {'filterType': 'LOT_SIZE', 'stepSize': '0.001', 'minQty': '0.001'},
                        {'filterType': 'PRICE_FILTER', 'tickSize': '0.10', 'minPrice': '1.00'},
                        {'filterType': 'MIN_NOTIONAL', 'minNotional': '10.0'},
                    ]
                }
            ]
        }

    # Spot
    def get_symbol_info(self, symbol):
        if symbol == 'BTCUSDT':
            return self._exchange_info['symbols'][0]
        return None

    # Futures
    def futures_exchange_info(self):
        if self.spot:
            return {}
        return {
            'symbols': [
                {
                    'symbol': 'BTCUSDT',
                    'filters': [
                        {'filterType': 'LOT_SIZE', 'stepSize': '0.001', 'minQty': '0.001'},
                        {'filterType': 'PRICE_FILTER', 'tickSize': '0.10', 'minPrice': '1.00'},
                        {'filterType': 'NOTIONAL', 'minNotional': '5.0'},
                    ]
                }
            ]
        }


def _make_api_spot():
    api = BinanceAPI(mode='spot')
    # monkeypatch client
    api.client = DummyClient(spot=True)
    return api


def _make_api_futures():
    api = BinanceAPI(mode='futures')
    api.client = DummyClient(spot=False)
    return api


def test_spot_quantize_enforces_lot_price_and_min_notional():
    api = _make_api_spot()
    # quantity below minQty -> qty 0
    qty, px = api.quantize('BTCUSDT', 0.0005, 100.0)
    assert qty == pytest.approx(0.0, rel=1e-12)
    # quantity ok but notional below 10 -> qty 0
    qty, px = api.quantize('BTCUSDT', 0.001, 5.0)
    assert qty == pytest.approx(0.0, rel=1e-12)
    # valid: step rounds down and price ticks, and notional >= 10
    qty, px = api.quantize('BTCUSDT', 0.10234, 123.45)
    assert qty == pytest.approx(0.102, rel=1e-9)  # step 0.001
    assert px == pytest.approx(123.4, rel=1e-9)   # tick 0.10


def test_futures_quantize_enforces_notional_and_lot():
    api = _make_api_futures()
    # notional below NOTIONAL.minNotional -> qty 0
    qty, px = api.quantize('BTCUSDT', 0.001, 1.0)
    assert qty == pytest.approx(0.0, rel=1e-12)
    # valid: rounds quantity, price unchanged when None
    qty, px = api.quantize('BTCUSDT', 0.00234, None)
    assert qty == pytest.approx(0.002, rel=1e-9)
    assert px is None
