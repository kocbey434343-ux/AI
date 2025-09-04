from src.trader import Trader
from src.utils.structured_log import clear_slog_events, get_slog_events
import os

def _prep(monkeypatch, tmp_path, enable):
    os.environ['TRADES_DB_PATH'] = str(tmp_path / ('atrflag_on.db' if enable else 'atrflag_off.db'))
    monkeypatch.setattr('config.settings.Settings.OFFLINE_MODE', True, raising=False)
    monkeypatch.setattr('config.settings.Settings.ATR_TRAILING_ENABLED', enable, raising=False)
    # Risk escalation'ı devre dışı bırak
    monkeypatch.setattr('config.settings.Settings.RISK_ESCALATION_ENABLED', False, raising=False)
    clear_slog_events()
    t = Trader()
    t.risk_manager.max_positions = 100
    def _q(_s,q,p): return q,p
    def _order(*_, **kw):
        q = kw.get('quantity')
        return {'price': 100.0, 'fills': [{'price':100.0,'qty':q}], 'orderId':1}
    monkeypatch.setattr(t.api,'quantize',_q)
    monkeypatch.setattr(t.api,'place_order',_order)
    sig = {'symbol':'ATRTEST' + ('1' if enable else '0'),'indicators':{'ATR':2.0},'total_score':60,'signal':'AL','close_price':100.0,'volume_24h':1_000_000,'prev_close':100.0}
    assert t.execute_trade(sig)
    pos = t.positions[sig['symbol']]
    pos['stop_loss'] = 95.0
    pos['atr'] = 2.0
    t.partial_enabled = False
    return t, sig['symbol']


def test_cr0029_atr_trailing_disabled(monkeypatch, tmp_path):
    t, sym = _prep(monkeypatch, tmp_path, False)
    t.process_price_update(sym, 112.0)
    t.process_price_update(sym, 118.0)
    events = [e for e in get_slog_events() if e['event']=='trailing_update']
    assert events, 'classic trailing yok'
    assert all(e.get('mode')!='atr' for e in events)


def test_cr0029_atr_trailing_enabled(monkeypatch, tmp_path):
    t, sym = _prep(monkeypatch, tmp_path, True)
    t.process_price_update(sym, 112.0)
    t.process_price_update(sym, 118.0)
    events = [e for e in get_slog_events() if e['event']=='trailing_update']
    assert any(e.get('mode')=='atr' for e in events), events
