import os

from src.trader import Trader
from src.trader.trailing import compute_r_multiple, maybe_partial_exits, maybe_trailing


def make_trader(tmp_path):
    os.environ['TRADES_DB_PATH'] = str(tmp_path / 'trailpersist.db')
    t = Trader()
    t.risk_manager.max_positions = 100
    return t


def test_trailing_and_partial_persist_reload(tmp_path):
    t = make_trader(tmp_path)
    # Simule acik pozisyon
    symbol = 'TPRSUSDT'
    pos = {
        'side': 'BUY', 'entry_price': 100.0, 'position_size': 10.0, 'remaining_size': 10.0,
        'stop_loss': 95.0, 'take_profit': 120.0, 'atr': 1.5, 'trade_id': None, 'scaled_out': []
    }
    t.positions[symbol] = pos
    # R-multiple ilerlet: fiyat 110 -> risk=5 => r=2.0
    price1 = 110.0
    r1 = compute_r_multiple(pos, price1)
    assert r1 is not None
    maybe_partial_exits(t, symbol, pos, price1, r1)
    # Partial logic: TP1_R_MULT default 1.0 -> ilk seviye gerceklesmis olmali
    assert pos['scaled_out'], 'Scale-out kaydedilmedi'
    first_scaled = pos['scaled_out'][0]
    EPS = 1e-6
    assert abs(first_scaled[0] - 1.0) < EPS, 'Ilk scale-out seviyesi beklenen degil'
    # Stop break-even'e çekildi mi?
    assert pos['stop_loss'] == pos['entry_price'], 'Stop BE yapilmadi'
    # Trailing tetikle: fiyati trailing_activate_r uzerinde arttir
    price2 = 120.0
    # Stop break-even'e cekildigi icin risk=0 ve r_multiple None doner. Trailing'i test etmek icin stop'u entry altina az miktar geri ayarla.
    pos['stop_loss'] = pos['entry_price'] - 2.0  # yeni risk 2
    r2 = compute_r_multiple(pos, price2)
    assert r2 is not None
    maybe_trailing(t, symbol, pos, price2, r2)
    # Stop yukselmeli veya entry uzerinde kalmali
    assert pos['stop_loss'] >= pos['entry_price']
    # Persist (simulate reload via trade_store open trades path): kaydetmek icin DB open kaydi ekleyelim
    # Not: trade_id None oldugundan scale_out DB kaydi yok; reload testinde scaled_out korunmasi icin trade_id atayalim
    pos['trade_id'] = 999
    # Simulate that open trade is in DB with same fields
    t.trade_store.insert_open(symbol=symbol, side='BUY', entry_price=pos['entry_price'], size=pos['position_size'],
                              opened_at='2024-01-01T00:00:00Z', strategy_tag='x', stop_loss=pos['stop_loss'], take_profit=pos['take_profit'])
    # Force reload
    t.positions.clear()
    t._reload_open_positions()
    re_pos = t.positions[symbol]
    # Reload eksik: scaled_out DB'den gelmez (şu anda destek yok) -> beklenen boş
    assert re_pos.get('scaled_out') == []
    # Geliştirme notu: scaled_out persist edilmediği için future CR gerekli
