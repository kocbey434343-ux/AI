import os
from pathlib import Path

import pandas as pd

from config.settings import Settings
from src.trader import Trader
from src.utils.trade_store import TradeStore
from src.utils.structured_log import clear_slog_events, get_slog_events


def fresh_trader(tmp_path):
    db_file = tmp_path / 'trades.db'
    os.environ['TRADES_DB_PATH'] = str(db_file)
    tr = Trader()
    tr.trade_store = TradeStore(str(db_file))
    return tr


def test_outlier_bar_guard_blocks(tmp_path):
    tr = fresh_trader(tmp_path)
    # Halt flag yok
    halt_path = Path(Settings.DAILY_HALT_FLAG_PATH)
    if halt_path.exists():
        halt_path.unlink()
    sig = {
        'symbol': 'OUTLIERUSDT',
        'signal': 'AL',
        'close_price': 106.0,   # +6%
        'prev_close': 100.0,
        'volume_24h': 2_000_000,
        'total_score': 80,
        'indicators': {}
    }
    allowed = tr.execute_trade(sig)
    assert allowed is False, 'Outlier bar hareket esigi asinca trade engellenmeli'


def test_atr_trailing_updates_stop(tmp_path):
    tr = fresh_trader(tmp_path)
    symbol = 'ATRTESTUSDT'
    entry = 100.0
    stop = 95.0
    atr = 2.0
    clear_slog_events()
    tr.open_positions[symbol] = {
        'order_id': 1,
        'side': 'BUY',
        'entry_price': entry,
        'position_size': 1.0,
        'stop_loss': stop,
        'take_profit': 120.0,
        'timestamp': pd.Timestamp.utcnow(),
        'atr': atr,
        'rr': 2.0,
        'trade_id': None,
        'remaining_size': 1.0,
        'scaled_out': [],
        'risk_per_unit': entry - stop,
        'entry_risk_distance': entry - stop,
        'current_stop_distance': entry - stop,
        'state': 'OPEN'
    }
    # Fiyat R>=1.2 olacak sekilde (risk=5, 1.2R => +6) last_price >= 106; sec 107
    tr.process_price_update(symbol, 107.0)
    new_sl = tr.open_positions[symbol]['stop_loss']
    # _maybe_update_trailing once: step = gain*(TRAILING_STEP_PCT/100)=7*0.25=1.75 => 101.75
    # ATR trailing sonra: new_sl = max(prev_sl, last_price - atr*ATR_TRAILING_MULT)= max(101.75, 107 - 2*1.2)=max(101.75,104.6)=104.6
    EXPECT_MIN = 104.5
    EXPECT_MAX = 104.7
    assert EXPECT_MIN < new_sl < EXPECT_MAX, f'Stop beklenen aralikta degil: {new_sl}'
    events_classic = get_slog_events('trailing_classic_update')
    assert len(events_classic) == 1, 'trailing_classic_update olayi yok'
    classic_sl = events_classic[0]['new_sl']
    CLASSIC_MIN = 101.7
    CLASSIC_MAX = 101.8
    assert CLASSIC_MIN < classic_sl < CLASSIC_MAX, f'Classic trailing SL beklenen degil: {classic_sl}'
    events_atr = get_slog_events('trailing_atr_update')
    assert len(events_atr) == 1, 'trailing_atr_update olayi yok'


def test_close_position_removes_and_closes(tmp_path):
    tr = fresh_trader(tmp_path)
    symbol = 'CLOSEMEUSDT'
    entry = 50.0
    tid = tr.trade_store.insert_open(symbol=symbol, side='BUY', entry_price=entry, size=1.0,
                                     opened_at=pd.Timestamp.utcnow().isoformat(), strategy_tag='t')
    tr.open_positions[symbol] = {
        'order_id': 123,
        'side': 'BUY',
        'entry_price': entry,
        'position_size': 1.0,
        'stop_loss': 48.0,
        'take_profit': 55.0,
        'timestamp': pd.Timestamp.utcnow(),
        'atr': None,
        'rr': 2.0,
        'trade_id': tid,
        'remaining_size': 1.0,
        'scaled_out': [],
        'risk_per_unit': 2.0,
        'entry_risk_distance': 2.0,
        'current_stop_distance': 2.0,
        'state': 'OPEN'
    }
    ok = tr.close_position(symbol)
    assert ok
    assert symbol not in tr.open_positions
    # DB'de kapanmis trade olmali
    rows = tr.trade_store.recent_trades(limit=5)
    assert any(r['id'] == tid and r.get('closed_at') for r in rows), 'Trade kapanmamis gorunuyor'
