#!/usr/bin/env python
"""Hizli smoke test calistirici.

Icerecekler:
- Temel unit subset (uygulamada kritik yollar):
  * ws_symbols
  * unreal label
  * metrics tab
- Maks calisma suresi (yumuşak): ~15 sn hedef.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

TEST_PATTERNS = [
    'tests/test_ws_symbols.py::test_compute_ws_symbols_prefers_positions',
    'tests/test_ws_symbols.py::test_compute_ws_symbols_includes_buy_signals',
    'tests/test_ui_unrealized_pnl_label.py::test_smoke_unrealized_label_wiring',
    'tests/test_ui_metrics_tab.py::test_metrics_tab_labels_update',
]

def main():
    cmd = [sys.executable, '-m', 'pytest', '-q', *TEST_PATTERNS]
    print('Running smoke tests...')
    rc = subprocess.call(cmd, cwd=ROOT)
    if rc != 0:
        print('Smoke tests FAILED', file=sys.stderr)
        sys.exit(rc)
    print('Smoke tests OK')

if __name__ == '__main__':
    main()
