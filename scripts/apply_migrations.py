#!/usr/bin/env python
"""Basit migration uygulayici.

- data/migrations_applied.txt dosyasinda uygulananlar listelenir.
- migrations klasorundeki *.sql dosyalari sira ile okunur.
- Yeni olanlar sqlite veritabanina exec edilir.
"""
from __future__ import annotations

import pathlib
import sqlite3

ROOT = pathlib.Path(__file__).resolve().parent.parent
DB_PATH = ROOT / 'data' / 'trades.db'
APPLIED_FILE = ROOT / 'data' / 'migrations_applied.txt'
MIGR_DIR = ROOT / 'migrations'


def load_applied() -> set[str]:
    if not APPLIED_FILE.exists():
        return set()
    return {line.strip() for line in APPLIED_FILE.read_text(encoding='utf-8').splitlines() if line.strip()}


def save_applied(ids: set[str]):
    APPLIED_FILE.parent.mkdir(parents=True, exist_ok=True)
    APPLIED_FILE.write_text('\n'.join(sorted(ids)) + '\n', encoding='utf-8')


def main():
    applied = load_applied()
    MIGR_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        for sql_file in sorted(MIGR_DIR.glob('*.sql')):
            name = sql_file.name
            if name in applied:
                continue
            sql = sql_file.read_text(encoding='utf-8')
            print(f'Applying migration {name}...')
            conn.executescript(sql)
            applied.add(name)
        conn.commit()
    finally:
        conn.close()
    save_applied(applied)
    print('Migrations complete.')

if __name__ == '__main__':  # pragma: no cover
    main()
