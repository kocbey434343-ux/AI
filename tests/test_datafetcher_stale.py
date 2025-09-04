import os
import time
from config.settings import Settings
from src.data_fetcher import DataFetcher


def test_cr0020_detect_stale_pairs(tmp_path, monkeypatch):
    # Isolated data directory
    data_dir = tmp_path / 'data'
    raw_dir = data_dir / 'raw'
    processed_dir = data_dir / 'processed'
    logs_dir = data_dir / 'logs'
    for d in (raw_dir, processed_dir, logs_dir):
        d.mkdir(parents=True, exist_ok=True)

    # Monkeypatch settings data path
    monkeypatch.setattr(Settings, 'DATA_PATH', str(data_dir))
    # Top pairs list: we will create file
    top_pairs_path = data_dir / 'top_150_pairs.json'
    top_pairs_path.write_text('["FRESH1","STALE1","MISSING1"]', encoding='utf-8')

    # Create fresh file (age < max_age) and stale file (age > max_age)
    fresh_file = raw_dir / 'FRESH1_1h.csv'
    stale_file = raw_dir / 'STALE1_1h.csv'
    fresh_file.write_text('timestamp,open\n2024-01-01 00:00:00,1', encoding='utf-8')
    stale_file.write_text('timestamp,open\n2024-01-01 00:00:00,1', encoding='utf-8')

    # Set mtimes: fresh now, stale older than threshold (set 3 hours old)
    now = time.time()
    os.utime(fresh_file, (now, now))
    three_hours_ago = now - 3 * 3600
    os.utime(stale_file, (three_hours_ago, three_hours_ago))

    dfetch = DataFetcher()
    # Force DataFetcher to use the isolated data path
    dfetch.data_path = str(data_dir)
    dfetch.ensure_directories()
    res = dfetch.detect_stale_pairs(interval='1h', max_age_minutes=120)  # 2h threshold

    # AC1: stale should include STALE1 and MISSING1 (missing file)
    assert 'STALE1' in res['stale']
    assert 'MISSING1' in res['stale']
    # AC2: fresh should include FRESH1
    assert 'FRESH1' in res['fresh']
    # AC3: errors empty
    assert res['errors'] == {}
