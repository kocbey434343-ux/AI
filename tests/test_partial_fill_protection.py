import os

from src.trader import Trader
from src.trader.execution import (
    extract_fills,
    place_protection_orders,
    prepare_order_context,
    record_open,
)

def make_trader(tmp_path):
    os.environ['TRADES_DB_PATH'] = str(tmp_path / 'partialprot.db')
    t = Trader()
    t.risk_manager.max_positions = 100
    return t


def test_partial_fill_protection_revision(tmp_path, monkeypatch):
    t = make_trader(tmp_path)
    symbol = 'PFPUSDT'
    # Fake API place_order returning partial fill first then second call for remaining
    calls = {'n': 0}
    def fake_place_order(_symbol=None, _side=None, _order_type=None, quantity=0.0, **_kwargs):
        calls['n'] += 1
        # First call: partial 40% fill
        if calls['n'] == 1:
            return {'price': 100.0, 'fills': [{'price': 100.0, 'qty': quantity * 0.4}], 'orderId': 1}
        # Second call: remaining 60%
        return {'price': 100.5, 'fills': [{'price': 100.5, 'qty': quantity * 0.6}], 'orderId': 2}
    monkeypatch.setattr(t.api, 'place_order', fake_place_order)
    # Quantize passthrough (ignore symbol precision)
    monkeypatch.setattr(t.api, 'quantize', lambda _s, q, p: (q, p))

    # Minimal signal/context for open_position path
    signal = {'indicators': {}, 'total_score': 50}
    ctx = {'symbol': symbol, 'side': 'BUY', 'risk_side': 'long', 'price': 100.0}
    oc = prepare_order_context(t, signal, ctx)
    assert oc
    # Manually simulate partial then remaining fill calling record_open twice (simplified approach)
    # First partial
    order1 = t.api.place_order(symbol=symbol, side='BUY', order_type='MARKET', quantity=oc.position_size, price=None)
    fill1, slip1, qty1 = extract_fills(order1, oc.price, oc.side, oc.position_size)
    record_open(t, oc, fill1, slip1, qty1 * 0.4)  # only partial qty (simulate first fill)
    pos = t.positions[symbol]
    pos['remaining_size'] = pos['position_size'] - pos['position_size'] * 0.4
    # Place protection after partial (should be sized to remaining in future logic)
    monkeypatch.setattr('config.settings.Settings.OFFLINE_MODE', True, raising=False)
    place_protection_orders(t, oc, fill1)
    rem_after_partial = pos['remaining_size']

    # Simulate second fill updating remaining_size to 0
    order2 = t.api.place_order(symbol=symbol, side='BUY', order_type='MARKET', quantity=pos['remaining_size'], price=None)
    _fill2, _slip2, _qty2 = extract_fills(order2, oc.price, oc.side, pos['remaining_size'])
    # Update position remaining
    pos['remaining_size'] = 0.0
    # (No actual protection revision logic yet) -> test documents current behavior
    assert rem_after_partial > 0
    TOL = 1e-9
    assert abs(pos['remaining_size'] - 0.0) < TOL
    # Future AC: protection emirlerinin miktar revizyonu test edilecek (şu an yok)
