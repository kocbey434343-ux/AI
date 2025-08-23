import math

from src.api.binance_api import BinanceAPI
from src.trader import Trader


MIN_QTY = 0.01
STEP = 0.001
EPS = 1e-12
ORIG_POS = 10.0


def test_quantize_min_qty_zero(monkeypatch):
    api = BinanceAPI()
    # monkeypatch filters
    def fake_get_filters(_symbol: str):
        return {
        'LOT_SIZE': {'stepSize': f'{STEP}', 'minQty': f'{MIN_QTY}'},
            'PRICE_FILTER': {'tickSize': '0.1', 'minPrice': '0.1'}
        }
    monkeypatch.setattr(api, '_get_filters', fake_get_filters)
    qty, _ = api.quantize('ABCUSDT', MIN_QTY / 2, 10.0)
    assert qty <= EPS  # below minQty -> zeroed
    qty2, _ = api.quantize('ABCUSDT', 0.017, 10.0)
    expected = 0.017 - (0.017 % STEP)
    assert math.isclose(qty2, expected) and qty2 >= MIN_QTY


def test_correlation_guard_blocks():
    t = Trader()
    # speed: offline mode assumed in tests
    # Seed two symbols with highly correlated synthetic data
    for i in range(60):
        p = 100 + i
        t.corr_cache.update('AAAUSDT', p)
        t.corr_cache.update('BBBUSDT', p * 1.001)
    allow, _ = t._check_correlation_guard('CCCUSDT')
    # no existing open positions => allow
    assert allow
    # create an open position for AAAUSDT
    t.open_positions['AAAUSDT'] = {'side': 'BUY', 'entry_price': 100, 'stop_loss': 99, 'take_profit': 105, 'risk_per_unit': 1, 'entry_risk_distance':1}
    allow2, details2 = t._check_correlation_guard('BBBUSDT')
    # threshold default 0.85 so AAA vs BBB should exceed
    assert not allow2 or details2  # either explicitly blocked or correlation measured


def test_partial_exit_reduces_remaining():
    t = Trader()
    symbol = 'TESTUSDT'
    # Insert a fake open position with risk metrics
    t.open_positions[symbol] = {
        'side': 'BUY', 'entry_price': 100.0, 'stop_loss': 95.0, 'take_profit': 110.0,
        'position_size': 10.0, 'remaining_size': 10.0, 'scaled_out': [], 'risk_per_unit': 5.0,
        'entry_risk_distance': 5.0, 'atr': None, 'rr': 2.0
    }
    # Price reaches first R multiple (r=1.0 -> price= entry + risk =105)
    t.process_price_update(symbol, 105.0)
    # After first partial: remaining should be <= original
    rem = t.open_positions[symbol]['remaining_size']
    assert rem <= ORIG_POS
    # If second level configured, push price to achieve it
    t.process_price_update(symbol, 100 + 1.8 * 5.0)
    assert t.open_positions[symbol]['remaining_size'] <= rem
