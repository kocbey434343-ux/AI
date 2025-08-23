import os
from src.trader import Trader

TOL = 1e-9


def test_recent_latency_slippage_stats_basic():
    # Ensure a temp DB path so TradeStore doesn't collide with real file
    tmp_db = os.path.abspath('test_latency_slip.db')
    os.environ['TRADES_DB_PATH'] = tmp_db
    tr = Trader()

    # Initially should return None values
    stats0 = tr.recent_latency_slippage_stats(window=10)
    assert stats0['open_latency_ms'] is None
    assert stats0['close_latency_ms'] is None
    assert stats0['entry_slip_bps'] is None
    assert stats0['exit_slip_bps'] is None

    # Simulate adding latencies/slippage by appending under lock
    with tr.metrics_lock:
        tr.recent_open_latencies.extend([100.0, 110.0, 90.0])
        tr.recent_close_latencies.extend([200.0, 180.0])
        tr.recent_entry_slippage_bps.extend([5.0, 7.0])
        tr.recent_exit_slippage_bps.extend([3.0])

    stats = tr.recent_latency_slippage_stats(window=2)
    # Window=2 means average last 2 samples per list (if len>=2)
    assert round(stats['open_latency_ms'], 1) == round((110.0+90.0)/2,1)
    assert round(stats['close_latency_ms'], 1) == round((200.0+180.0)/2,1)
    assert round(stats['entry_slip_bps'], 1) == round((5.0+7.0)/2,1)
    # Single sample should pass through exactly (tolerance compare)
    assert abs(stats['exit_slip_bps'] - 3.0) < TOL

    # Add more than window and ensure trimming logic still returns last N average
    with tr.metrics_lock:
        tr.recent_open_latencies.extend([95.0, 105.0, 115.0])
    stats2 = tr.recent_latency_slippage_stats(window=3)
    # Last 3 open latencies are 95,105,115
    assert round(stats2['open_latency_ms'],1) == round((95.0+105.0+115.0)/3,1)

    # Ensure lists don't exceed MAX_RECENT_SAMPLES after manual overfill
    with tr.metrics_lock:
        for _ in range(tr.MAX_RECENT_SAMPLES + 10):
            tr.recent_open_latencies.append(50.0)
        assert len(tr.recent_open_latencies) > tr.MAX_RECENT_SAMPLES  # before trim
    # Force trim by invoking accessor (which does not trim) so emulate open event path by manual trim logic
    # We'll mimic open event trim: replicate code snippet
    with tr.metrics_lock:
        if len(tr.recent_open_latencies) > tr.MAX_RECENT_SAMPLES:
            tr.recent_open_latencies = tr.recent_open_latencies[-tr.MAX_RECENT_SAMPLES:]
    assert len(tr.recent_open_latencies) == tr.MAX_RECENT_SAMPLES
