from pathlib import Path
from src.utils.helpers import create_backup_snapshot, cleanup_old_backups
import os, time, json

def test_cr0047_backup_snapshot(monkeypatch, tmp_path):
    monkeypatch.setenv('BACKUP_PATH', str(tmp_path / 'bkp'))
    monkeypatch.setenv('TRADES_DB_PATH', str(tmp_path / 'db' / 'trades.db'))
    monkeypatch.setenv('LOG_PATH', str(tmp_path / 'logs'))
    monkeypatch.setenv('BACKUP_MAX_SNAPSHOTS', '2')
    monkeypatch.setenv('BACKUP_RETENTION_DAYS', '30')
    import importlib, config.settings as cs
    importlib.reload(cs)
    from config.settings import Settings as S
    Path(S.TRADES_DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    Path(S.TRADES_DB_PATH).write_text('DB', encoding='utf-8')
    log_dir = Path(S.LOG_PATH); log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / 'shutdown_snapshot.json').write_text('{"ok":true}', encoding='utf-8')
    snap1 = create_backup_snapshot({'note':'first'})
    assert snap1 and Path(snap1).exists()
    meta1 = json.loads((Path(snap1)/'meta.json').read_text(encoding='utf-8'))
    assert meta1['extra']['note']=='first'
    time.sleep(0.2)
    snap2 = create_backup_snapshot({'note':'second'})
    assert snap2 and Path(snap2).exists()
    snaps = list((Path(S.BACKUP_PATH)).glob('snapshot_*'))
    assert len(snaps) <= 2
    monkeypatch.setenv('BACKUP_MAX_SNAPSHOTS', '1')
    importlib.reload(cs)
    cleanup_old_backups(Path(S.BACKUP_PATH))
    snaps2 = list((Path(S.BACKUP_PATH)).glob('snapshot_*'))
    assert len(snaps2) <= 1
