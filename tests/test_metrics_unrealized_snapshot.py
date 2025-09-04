import os

from src.trader import Trader
from config.settings import Settings


def test_cr0017_metrics_snapshot_unrealized_zero(tmp_path):
    Settings.OFFLINE_MODE = True  # type: ignore
    os.environ['TRADES_DB_PATH'] = str(tmp_path / 'mrunr.db')
    t = Trader()
    from src.trader.metrics import metrics_snapshot
    snap = metrics_snapshot(t)
    assert 'unrealized_total_pnl_pct' in snap
    assert abs(snap['unrealized_total_pnl_pct'] - 0.0) < 1e-9


def test_cr0017_metrics_snapshot_unrealized_positive(tmp_path, monkeypatch):
    Settings.OFFLINE_MODE = True  # type: ignore
    os.environ['TRADES_DB_PATH'] = str(tmp_path / 'mrunr2.db')
    t = Trader()
    monkeypatch.setattr(t.api, 'quantize', lambda s,q,p: (q,p))
    monkeypatch.setattr(t.api, 'place_order', lambda **k: {'price':100.0,'fills':[{'price':100.0,'qty':k['quantity']}], 'orderId':55})
    sig = {'symbol':'MUNR','signal':'AL','close_price':100.0,'indicators':{'ATR':1.0},'total_score':50,'volume_24h':1_000_000,'prev_close':100.0}
    t.risk_manager.max_positions = 50
    assert t.execute_trade(sig)
    t.process_price_update('MUNR', 102.0)
    from src.trader.metrics import metrics_snapshot
    snap = metrics_snapshot(t)
    assert snap['unrealized_total_pnl_pct'] > 0.0
