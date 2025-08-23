import os
import tempfile
import shutil
import pandas as pd
from pathlib import Path
from config.settings import Settings
from src.trader import Trader
from src.utils.trade_store import TradeStore

# Helper to create a fresh isolated DB for each test

def fresh_trader(tmp_path):
    # Override DB path env for isolation
    db_file = tmp_path / 'trades.db'
    os.environ['TRADES_DB_PATH'] = str(db_file)
    # Re-import Settings dependent modules if needed (Settings is loaded once; we rely on path variable only)
    tr = Trader()
    # Force empty store
    tr.trade_store = TradeStore(str(db_file))
    return tr

SIGNAL_TEMPLATE = {
    'symbol': 'TESTUSDT',
    'signal': 'AL',
    'close_price': 100.0,
    'prev_close': 100.0,
    'volume_24h': 1_000_000,
    'total_score': 80,
    'indicators': {}
}

def test_daily_loss_guard(tmp_path):
    tr = fresh_trader(tmp_path)
    # Insert losing closed trades summing beyond MAX_DAILY_LOSS_PCT
    loss_pct_each = - (Settings.MAX_DAILY_LOSS_PCT / 2)
    # Two trades each half -> total daily loss = -MAX_DAILY_LOSS_PCT
    for i in range(2):
        tid = tr.trade_store.insert_open(symbol=f'L{i}USDT', side='BUY', entry_price=100, size=1,
                                         opened_at=pd.Timestamp.utcnow().isoformat(), strategy_tag='t')
        tr.trade_store.close_trade(tid, exit_price=100 * (1 + loss_pct_each/100.0), closed_at=pd.Timestamp.utcnow().isoformat())
    # Now attempt a new trade -> should be blocked (>= threshold triggers halt)
    allowed = tr.execute_trade(dict(SIGNAL_TEMPLATE))
    assert allowed is False, 'Trade should be blocked by daily loss guard'


def test_consecutive_losses_guard(tmp_path):
    tr = fresh_trader(tmp_path)
    # Insert MAX_CONSECUTIVE_LOSSES losing trades
    for i in range(Settings.MAX_CONSECUTIVE_LOSSES):
        tid = tr.trade_store.insert_open(symbol=f'C{i}USDT', side='BUY', entry_price=100, size=1,
                                         opened_at=pd.Timestamp.utcnow().isoformat(), strategy_tag='t')
        # 1% loss
        tr.trade_store.close_trade(tid, exit_price=99, closed_at=pd.Timestamp.utcnow().isoformat())
    # Next trade should be blocked
    allowed = tr.execute_trade(dict(SIGNAL_TEMPLATE))
    assert allowed is False, 'Trade should be blocked by consecutive losses guard'


def test_correlation_guard_blocks(tmp_path, monkeypatch):
    tr = fresh_trader(tmp_path)
    # Open one position manually
    tr.open_positions['AAAUSDT'] = {
        'order_id': 1,
        'side': 'BUY',
        'entry_price': 10.0,
        'position_size': 1.0,
        'stop_loss': 9.0,
        'take_profit': 12.0,
        'timestamp': pd.Timestamp.utcnow(),
        'atr': None,
        'rr': 2.0,
        'trade_id': None,
        'remaining_size': 1.0,
        'scaled_out': [],
        'risk_per_unit': 1.0,
        'entry_risk_distance': 1.0
    }
    # Force correlation cache to return high correlation
    def fake_corr(symbol_a, symbol_b):
        return Settings.CORRELATION_THRESHOLD + 0.05
    monkeypatch.setattr(tr.corr_cache, 'correlation', fake_corr)
    # Adapt signal for a new symbol
    sig = dict(SIGNAL_TEMPLATE)
    sig['symbol'] = 'BBBUSDT'
    allowed = tr.execute_trade(sig)
    assert allowed is False, 'High correlation should block new position'


def test_weighted_pnl_scale_out(tmp_path):
    tr = fresh_trader(tmp_path)
    # Simulate a trade with scale-outs
    entry = 100.0
    tid = tr.trade_store.insert_open(symbol='SCLUSDT', side='BUY', entry_price=entry, size=10,
                                     opened_at=pd.Timestamp.utcnow().isoformat(), strategy_tag='t')
    # Scale out 30% at +5%
    price1 = entry * 1.05
    tr.trade_store.record_execution(trade_id=tid, symbol='SCLUSDT', exec_type='scale_out', qty=3, price=price1, side='BUY', r_mult=0.0)
    # Scale out 20% at +8%
    price2 = entry * 1.08
    tr.trade_store.record_execution(trade_id=tid, symbol='SCLUSDT', exec_type='scale_out', qty=2, price=price2, side='BUY', r_mult=0.0)
    # Final exit remaining 50% at +2%
    exit_price = entry * 1.02
    tr.trade_store.close_trade(tid, exit_price=exit_price, closed_at=pd.Timestamp.utcnow().isoformat())
    # Fetch closed row
    row = tr.trade_store.recent_trades(limit=1)[0]
    pnl = row['pnl_pct']
    # Weighted: 0.3*5 + 0.2*8 + 0.5*2 = 1.5 + 1.6 + 1 = 4.1%
    assert abs(pnl - 4.1) < 0.01, f'Weighted PnL expected ~4.1 got {pnl}'
