from src.trader import Trader
from src.utils.structured_log import clear_slog_events, get_slog_events
from datetime import datetime, timedelta, timezone
import os

def test_cr0044_daily_risk_reset_cleared(monkeypatch, tmp_path):
    os.environ['TRADES_DB_PATH'] = str(tmp_path / 'risk.db')
    monkeypatch.setattr('config.settings.Settings.OFFLINE_MODE', True, raising=False)
    clear_slog_events()
    t = Trader()
    t.guard_counters['loss'] = 3
    t.guard_counters['halt'] = 1
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime('%Y-%m-%d')
    t._risk_reset_date = yesterday
    assert t._maybe_daily_risk_reset()
    ev = [e for e in get_slog_events() if e['event']=='daily_risk_reset'][-1]
    assert ev.get('cleared') == 2
    before = len(get_slog_events())
    assert not t._maybe_daily_risk_reset()
    assert len(get_slog_events()) == before
