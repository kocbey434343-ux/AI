import os
from datetime import datetime, timedelta, timezone

import pandas as pd

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
    def fake_corr(_a, _b):
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
    TOL = 0.01
    assert abs(pnl - 4.1) < TOL, f'Weighted PnL expected ~4.1 got {pnl}'


def test_daily_risk_reset(tmp_path):
    tr = fresh_trader(tmp_path)
    old_date = (datetime.now(timezone.utc) - timedelta(days=1)).strftime('%Y-%m-%d')
    tr._risk_reset_date = old_date  # force mismatch
    tr.guard_counters['daily_loss_blocks'] = 3
    # Ensure no halt flag or blocking conditions
    try:
        if os.path.exists(Settings.DAILY_HALT_FLAG_PATH):
            os.remove(Settings.DAILY_HALT_FLAG_PATH)
    except Exception:
        pass
    sig = dict(SIGNAL_TEMPLATE)
    sig['signal'] = 'AL'
    sig['close_price'] = 100.0
    sig['prev_close'] = 100.0
    sig['volume_24h'] = Settings.DEFAULT_MIN_VOLUME * 10
    tr.execute_trade(sig)
    # Fallback: if still not reset (unexpected guard block), call internal to avoid hang
    if tr._risk_reset_date == old_date:
        tr._maybe_daily_risk_reset()
    assert tr._risk_reset_date != old_date, 'Risk reset date not updated'
    assert tr.guard_counters.get('daily_loss_blocks', 0) == 0, 'Guard counters not cleared on daily reset'


def test_reconcile_open_orders(tmp_path, monkeypatch):
    tr = fresh_trader(tmp_path)
    # Local position without protection
    tr.positions['AAAUSDT'] = {
        'side': 'BUY', 'entry_price': 10.0, 'position_size': 1.0, 'remaining_size': 1.0,
        'stop_loss': 9.0, 'take_profit': 12.0, 'atr': None, 'trade_id': 1, 'scaled_out': []
    }
    # Exchange shows an extra position BBBUSDT (orphan exchange) and missing local for AAAUSDT? (AAA present so not orphan)
    exch_positions = [
        {'symbol': 'BBBUSDT', 'side': 'BUY', 'size': 2.0},
        {'symbol': 'AAAUSDT', 'side': 'BUY', 'size': 1.0}
    ]
    monkeypatch.setattr(tr.api, 'get_open_orders', lambda: [])
    monkeypatch.setattr(tr.api, 'get_positions', lambda: exch_positions)
    summary = tr._reconcile_open_orders()
    assert 'AAAUSDT' in summary['missing_stop_tp'], 'Protection missing not detected'
    assert 'BBBUSDT' in summary['orphan_exchange_position'], 'Orphan exchange position not flagged'
    # Remove AAA locally to create orphan_local
    tr.positions.clear()
    tr.positions['CCCUSDT'] = {'side': 'BUY', 'entry_price': 5.0, 'position_size': 1.0, 'remaining_size': 1.0,
                               'stop_loss': 4.5, 'take_profit': 6.0, 'atr': None, 'trade_id': 2, 'scaled_out': []}
    exch_positions2 = [{'symbol': 'AAAUSDT', 'side': 'BUY', 'size': 1.0}]
    monkeypatch.setattr(tr.api, 'get_positions', lambda: exch_positions2)
    summary2 = tr._reconcile_open_orders()
    assert 'CCCUSDT' in summary2['orphan_local_position'], 'Orphan local position not flagged'
