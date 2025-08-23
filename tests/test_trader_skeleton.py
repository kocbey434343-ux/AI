import importlib

def test_trader_import_and_basic_api():
    mod = importlib.import_module('src.trader')
    Trader = mod.Trader
    t = Trader()
    assert t.get_open_positions() == {}
    assert t.execute_trade({'symbol':'BTCUSDT','signal':'AL'}) is False
    t.process_price_update('BTCUSDT', 50000.0)  # no crash
    assert t.close_position('BTCUSDT') is False
    assert t.close_all_positions() == 0
    assert t.recompute_weighted_pnl() == 0
    assert t.start() is True
    assert t.stop() is True
