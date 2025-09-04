from src.trader import Trader
from src.utils.structured_log import clear_slog_events, get_slog_events
import os, json

def test_cr0045_shutdown_snapshot(monkeypatch, tmp_path):
    os.environ['TRADES_DB_PATH'] = str(tmp_path / 'snap.db')
    monkeypatch.setattr('config.settings.Settings.OFFLINE_MODE', True, raising=False)
    monkeypatch.setenv('LOG_PATH', str(tmp_path))
    clear_slog_events()
    t = Trader()
    t.positions['ZZZUSDT'] = {
        'side':'BUY','entry_price':100.0,'position_size':10.0,'remaining_size':6.0,
        'stop_loss':95.0,'take_profit':110.0,'trade_id':42,'scaled_out':[]
    }
    t.guard_counters['halt']=1
    t.stop()
    snap_path = tmp_path / 'shutdown_snapshot.json'
    assert snap_path.exists()
    data = json.loads(snap_path.read_text(encoding='utf-8'))
    assert data['open_positions'][0]['symbol']=='ZZZUSDT'
    events = {e['event'] for e in get_slog_events()}
    assert 'shutdown_snapshot' in events
