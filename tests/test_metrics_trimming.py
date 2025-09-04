from src.trader.metrics import maybe_trim_metrics
import threading


class Dummy:
    def __init__(self, max_samples=500):
        self.MAX_RECENT_SAMPLES = max_samples
        self.metrics_lock = threading.RLock()
        self.recent_open_latencies = []
        self.recent_close_latencies = []
        self.recent_entry_slippage_bps = []
        self.recent_exit_slippage_bps = []


def test_maybe_trim_metrics_manual_trim():
    d = Dummy()
    max_n = d.MAX_RECENT_SAMPLES
    with d.metrics_lock:
        d.recent_open_latencies = list(range(max_n + 50))
        d.recent_close_latencies = list(range(max_n + 10))
        d.recent_entry_slippage_bps = list(range(max_n - 1))  # no trim needed
        d.recent_exit_slippage_bps = list(range(max_n + 5))
    maybe_trim_metrics(d)
    assert len(d.recent_open_latencies) == max_n
    assert len(d.recent_close_latencies) == max_n
    assert len(d.recent_entry_slippage_bps) == max_n - 1  # untouched
    assert len(d.recent_exit_slippage_bps) == max_n
    # Tail preservation
    assert d.recent_open_latencies[-1] == max_n + 49
