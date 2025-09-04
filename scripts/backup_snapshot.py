#!/usr/bin/env python
"""Saatlik (manuel tetiklenebilir) kod snapshot scripti.

Kurallar:
- Calistirildiginda git status kirli ise uyari verir; --force yoksa cikis.
- Temiz ise tracked dosyalari backup/auto/TIMESTAMP/ altina kopyalar.
- Eski (>=24h) klasorleri siler.
"""
from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from typing import List

ROOT = pathlib.Path(__file__).resolve().parent.parent
BACKUP_DIR = ROOT / 'backup' / 'auto'
RETENTION_HOURS = 24


def run(cmd: List[str]) -> str:
    return subprocess.check_output(cmd, cwd=ROOT, text=True).strip()


def git_dirty() -> bool:
    out = run(['git', 'status', '--porcelain'])
    return bool(out.strip())


def collect_files() -> list[pathlib.Path]:
    out = run(['git', 'ls-files'])
    files = []
    for line in out.splitlines():
        p = ROOT / line
        if p.is_file():
            files.append(p)
    return files


def snapshot(force: bool = False) -> pathlib.Path:
    if git_dirty() and not force:
        print('WARN: Calisma alani kirli. --force ile yine de snapshot alabilirsiniz.')
        sys.exit(1)
    ts = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
    target = BACKUP_DIR / ts
    target.mkdir(parents=True, exist_ok=True)
    for f in collect_files():
        rel = f.relative_to(ROOT)
        dest = target / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(f, dest)
        except Exception as e:  # pragma: no cover
            print(f'KOPYA HATA: {rel} -> {e}')
    return target


def prune():
    if not BACKUP_DIR.exists():
        return
    cutoff = time.time() - RETENTION_HOURS * 3600
    for child in BACKUP_DIR.iterdir():
        if child.is_dir():
            try:
                t = child.stat().st_mtime
                if t < cutoff:
                    shutil.rmtree(child, ignore_errors=True)
            except OSError:
                pass


def main(argv: list[str]):
    force = '--force' in argv
    created = snapshot(force=force)
    prune()
    print(f'Snapshot olusturuldu: {created}')


if __name__ == '__main__':  # pragma: no cover
    main(sys.argv[1:])
