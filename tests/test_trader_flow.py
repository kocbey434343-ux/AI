from pathlib import Path
import contextlib

from config.settings import Settings
from src.trader import Trader


def make_signal(symbol: str, price: float, atr: float = 1.0):
    return {
        'symbol': symbol,
        'signal': 'AL',
        'close_price': price,
        'prev_close': price,
        'volume_24h': Settings.DEFAULT_MIN_VOLUME * 5,
        'indicators': {'ATR': atr},
        'total_score': 70,
    }


def test_trade_open_partial_exit_trailing_and_close():
    t = Trader()
    # Ensure clean state
    t.positions.clear()
    sig = make_signal('TESTUSDT', 100.0, atr=1.0)
    assert t.execute_trade(sig) is True
    pos = t.get_open_positions()['TESTUSDT']
    entry = pos['entry_price']
    stop0 = pos['stop_loss']
    risk = abs(entry - stop0)
    # Trigger first partial (R=1.0 level)
    t.process_price_update('TESTUSDT', entry + risk * 1.05)
    pos_after = t.get_open_positions()['TESTUSDT']
    assert pos_after['remaining_size'] < pos_after['position_size']  # partial exit yapildi
    # Trigger trailing (activation R > 1.2)
    t.process_price_update('TESTUSDT', entry + risk * 1.30)
    pos_trail = t.get_open_positions()['TESTUSDT']
    assert pos_trail['stop_loss'] >= stop0  # trailing veya BE
    closed = t.close_all_positions()
    assert closed == 1
    assert len(t.get_open_positions()) == 0


def test_halt_flag_blocks_new_trades():
    # Create halt flag
    halt_path = Path(Settings.DAILY_HALT_FLAG_PATH)
    halt_path.parent.mkdir(parents=True, exist_ok=True)
    halt_path.write_text('halt')
    try:
        t = Trader()
        sig = make_signal('HALTUSDT', 50.0)
        opened = t.execute_trade(sig)
        assert opened is False
    finally:
        with contextlib.suppress(Exception):
            halt_path.unlink(missing_ok=True)
