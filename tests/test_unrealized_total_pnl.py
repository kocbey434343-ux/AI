import os

from src.trader import Trader
from config.settings import Settings

EPS = 1e-9

def _mk(env_db):
    os.environ['TRADES_DB_PATH'] = env_db
    Settings.OFFLINE_MODE = True  # type: ignore
    return Trader()


def test_cr0014_unrealized_total_pnl_empty(tmp_path, monkeypatch):
    t = _mk(str(tmp_path/ 'unreal1.db'))
    assert abs(t.unrealized_total_pnl_pct() - 0.0) < EPS


def test_cr0014_unrealized_single_long(tmp_path, monkeypatch):
    t = _mk(str(tmp_path/ 'unreal2.db'))
    t.risk_manager.max_positions = 100
    # stubs
    monkeypatch.setattr(t.api, 'quantize', lambda s,q,p: (q,p))
    monkeypatch.setattr(t.api, 'place_order', lambda **k: {'price':100.0,'fills':[{'price':100.0,'qty':k['quantity']}], 'orderId':1})
    sig = {'symbol':'UL1','signal':'AL','close_price':100.0,'indicators':{'ATR':1.0},'total_score':50,'volume_24h':1_000_000,'prev_close':100.0}
    assert t.execute_trade(sig) is True
    # price up 2%
    t.process_price_update('UL1', 102.0)
    pnl = t.unrealized_total_pnl_pct()
    assert abs(pnl - 2.0) < EPS


def test_cr0014_unrealized_partial_weight(tmp_path, monkeypatch):
    t = _mk(str(tmp_path/ 'unreal3.db'))
    t.risk_manager.max_positions = 100
    monkeypatch.setattr(t.api, 'quantize', lambda s,q,p: (q,p))
    monkeypatch.setattr(t.api, 'place_order', lambda **k: {'price':100.0,'fills':[{'price':100.0,'qty':k['quantity']}], 'orderId':2})
    sig = {'symbol':'UL2','signal':'AL','close_price':100.0,'indicators':{'ATR':1.0},'total_score':50,'volume_24h':1_000_000,'prev_close':100.0}
    assert t.execute_trade(sig)
    pos = t.positions['UL2']
    # force stop to set risk
    pos['stop_loss'] = 90.0
    # set partial plan single level 1R=10 move 50%
    t.tp_levels = [(1.0,0.5)]  # type: ignore
    # price reaches 1R -> triggers partial exit
    t.process_price_update('UL2', 110.0)
    # remaining now 50%; raise price to +2R (120)
    t.process_price_update('UL2', 120.0)
    pnl = t.unrealized_total_pnl_pct()
    # remaining half gains (120-100)/100 = 20% * 0.5 weight = 10%
    assert abs(pnl - 10.0) < EPS


def test_cr0014_unrealized_long_short_aggregate(tmp_path, monkeypatch):
    t = _mk(str(tmp_path/ 'unreal4.db'))
    t.risk_manager.max_positions = 100
    # Partial exits kapat (agirliklar bozulmasin)
    t.partial_enabled = False  # type: ignore[attr-defined]
    monkeypatch.setattr(t.api, 'quantize', lambda s,q,p: (q,p))
    # long open
    monkeypatch.setattr(t.api, 'place_order', lambda **k: {'price':100.0,'fills':[{'price':100.0,'qty':k['quantity']}], 'orderId':3})
    sig_long = {'symbol':'UL3','signal':'AL','close_price':100.0,'indicators':{'ATR':1.0},'total_score':50,'volume_24h':1_000_000,'prev_close':100.0}
    assert t.execute_trade(sig_long)
    # short open (simulate SELL signal) -> need map; we stub guard pipeline by calling directly
    monkeypatch.setattr(t.api, 'place_order', lambda **k: {'price':200.0,'fills':[{'price':200.0,'qty':k['quantity']}], 'orderId':4})
    sig_short = {'symbol':'US3','signal':'SAT','close_price':200.0,'indicators':{'ATR':2.0},'total_score':50,'volume_24h':1_000_000,'prev_close':200.0}
    assert t.execute_trade(sig_short)
    # move prices: long +5% (105), short profitable when price declines -> drop to 190 (-5%)
    t.process_price_update('UL3', 105.0)
    t.process_price_update('US3', 190.0)
    pnl = t.unrealized_total_pnl_pct()
    # each side weight 1; long +5% + short +5% = 10%
    assert abs(pnl - 10.0) < EPS
