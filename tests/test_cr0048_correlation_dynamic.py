from src.trader import Trader
from src.utils.structured_log import clear_slog_events, get_slog_events

class DummyCorrCache:
    def __init__(self, value):
        self.value = value
    def update(self, symbol, price):
        pass
    def correlation(self, a, b):
        return self.value

def test_cr0048_dynamic_threshold(monkeypatch):
    clear_slog_events()
    monkeypatch.setattr('config.settings.Settings.CORRELATION_THRESHOLD', 0.85, raising=False)
    monkeypatch.setattr('config.settings.Settings.CORRELATION_DYNAMIC_ENABLED', True, raising=False)
    monkeypatch.setattr('config.settings.Settings.CORRELATION_MIN_THRESHOLD', 0.70, raising=False)
    monkeypatch.setattr('config.settings.Settings.CORRELATION_MAX_THRESHOLD', 0.92, raising=False)
    monkeypatch.setattr('config.settings.Settings.CORRELATION_ADJ_STEP', 0.01, raising=False)
    t = Trader()
    t.corr_cache = DummyCorrCache(0.90)
    t.positions['AAAUSDT'] = {'side':'BUY','entry_price':1,'remaining_size':1}
    from src.trader.guards import _CORR_STATE
    _CORR_STATE['last_adjust_ts'] = 0
    for _ in range(4):
        t.correlation_ok('BBBUSDT', 1.0)
        _CORR_STATE['last_adjust_ts'] = 0
    evs = [e for e in get_slog_events() if e['event']=='correlation_adjust']
    assert any(e['action']=='ease' for e in evs)
    t.corr_cache = DummyCorrCache(0.10)
    _CORR_STATE['last_adjust_ts'] = 0
    for _ in range(2):
        t.correlation_ok('CCCUSDT', 1.0)
        _CORR_STATE['last_adjust_ts'] = 0
    evs2 = [e for e in get_slog_events() if e['event']=='correlation_adjust']
    assert any(e['action']=='tighten' for e in evs2)
