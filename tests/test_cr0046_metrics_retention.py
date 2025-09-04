import time, os
from pathlib import Path
from importlib import reload
from src.trader import Trader
from src.trader.metrics import maybe_flush_metrics

def test_cr0046_metrics_retention(monkeypatch, tmp_path):
    monkeypatch.setenv('METRICS_FILE_ENABLED','true')
    monkeypatch.setenv('METRICS_FILE_DIR', str(tmp_path))
    monkeypatch.setenv('METRICS_FLUSH_INTERVAL_SEC','0')
    monkeypatch.setenv('METRICS_RETENTION_HOURS','0')  # deletion threshold
    monkeypatch.setenv('METRICS_RETENTION_COMPRESS','false')
    import config.settings as cs
    reload(cs)
    from config.settings import Settings as S
    t = Trader()
    t.recent_open_latencies = [10,20,30]
    maybe_flush_metrics(t, force=True)
    files = list(Path(S.METRICS_FILE_DIR).glob('metrics_*'))
    # With retention 0 they should be deleted
    assert not files
