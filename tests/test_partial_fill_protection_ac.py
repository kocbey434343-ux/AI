import os

from src.trader import Trader
from src.trader.execution import (
    apply_partial_fill,
    maybe_revise_protection_orders,
    prepare_order_context,
)


def make_trader(tmp_path):
    os.environ['TRADES_DB_PATH'] = str(tmp_path / 'pfpac.db')
    t = Trader()
    t.risk_manager.max_positions = 100
    return t


def test_cr0012_partial_fill_protection_acceptance(tmp_path, monkeypatch):
    """AC1-AC4: Partial fill sonrasi koruma revizyon davranisi."""
    monkeypatch.setattr('config.settings.Settings.OFFLINE_MODE', True, raising=False)
    t = make_trader(tmp_path)
    monkeypatch.setattr(t.api, 'quantize', lambda _s, q, p: (q, p))

    symbol = 'CR0012USDT'
    signal = {'indicators': {}, 'total_score': 50}
    ctx = {'symbol': symbol, 'side': 'BUY', 'risk_side': 'long', 'price': 100.0}
    oc = prepare_order_context(t, signal, ctx)
    assert oc and oc.position_size > 0

    total = oc.position_size
    part1 = round(total * 0.4, 8)
    part2 = total - part1

    # --- First partial fill (AC1) ---
    pos = apply_partial_fill(t, oc, fill_price=100.0, fill_qty=part1, slip_bps=None)
    assert pos is not None
    assert pos['position_size'] == total
    assert pos['filled_size'] == part1
    assert 0 < pos['remaining_size'] < total  # remaining < position_size

    # Protection qty revision (AC2)
    # Ilk revise: apply_partial_fill zaten protection_qty set etti -> degisim olmayabilir
    changed = maybe_revise_protection_orders(t, symbol)
    assert changed in (False, True)
    assert pos['protection_qty'] == pos['remaining_size']

    rem_after_first = pos['remaining_size']
    TOL = 1e-9
    assert abs(rem_after_first - part2) < TOL

    # --- Second partial fill completing position (AC3) ---
    pos2 = apply_partial_fill(t, oc, fill_price=100.5, fill_qty=part2, slip_bps=None)
    assert pos2 is pos
    assert pos['filled_size'] == total
    ZERO_TOL = 1e-12
    assert abs(pos['remaining_size']) < ZERO_TOL

    changed2 = maybe_revise_protection_orders(t, symbol)
    assert changed2 is True  # remaining changed to 0
    assert abs(pos['protection_qty'] - 0.0) < TOL
    assert pos.get('protection_cleared') is True

    # --- Idempotency (AC4) ---
    changed3 = maybe_revise_protection_orders(t, symbol)
    assert changed3 is False

    # VWAP entry updated between two different fill prices
    # After fills of quantities part1@100.0 and part2@100.5 average should be near 100.3
    expected_vwap = ((100.0 * part1) + (100.5 * part2)) / total
    assert abs(pos['entry_price'] - expected_vwap) < TOL
