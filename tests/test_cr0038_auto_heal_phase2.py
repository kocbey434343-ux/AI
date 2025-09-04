from src.trader import Trader
from src.utils.structured_log import clear_slog_events, get_slog_events
import os

def test_cr0038_auto_heal_attempt_success(monkeypatch, tmp_path):
    os.environ['TRADES_DB_PATH'] = str(tmp_path / 'autoheal.db')
    monkeypatch.setattr('config.settings.Settings.OFFLINE_MODE', False, raising=False)
    t = Trader()
    t.market_mode = 'spot'
    t.positions['AHEALUSDT'] = {
        'side':'BUY','entry_price':100.0,'position_size':10.0,'remaining_size':10.0,
        'stop_loss':95.0,'take_profit':110.0,'trade_id':123,'scaled_out':[]
    }
    def _oco(symbol, side, quantity, take_profit, stop_loss):
        return {'orderReports':[{'orderId':111},{'orderId':112}]}
    monkeypatch.setattr(t.api,'place_oco_order',_oco)
    clear_slog_events()
    t._reconcile_open_orders()
    events = [e['event'] for e in get_slog_events()]
    assert 'auto_heal_attempt' in events
    assert 'auto_heal_success' in events
