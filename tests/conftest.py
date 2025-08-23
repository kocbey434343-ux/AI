import json
from contextlib import suppress
from pathlib import Path
from typing import Dict, List

import pytest

_results: List[Dict] = []


def pytest_runtest_logreport(report: pytest.TestReport):  # type: ignore
    if report.when == 'call':
        _results.append({
            'nodeid': report.nodeid,
            'outcome': report.outcome,
            'duration': round(report.duration, 6),
            'longrepr': str(report.longrepr) if report.failed else None,
        })


def pytest_sessionfinish(session: pytest.Session, exitstatus: int):  # type: ignore[arg-type]
    out = {
        'exitstatus': exitstatus,
        'summary': {
            'passed': sum(1 for r in _results if r['outcome'] == 'passed'),
            'failed': sum(1 for r in _results if r['outcome'] == 'failed'),
            'skipped': sum(1 for r in _results if r['outcome'] == 'skipped'),
            'total': len(_results),
            'collected': len(getattr(session, 'items', []) or []),
        },
        'results': _results,
    }
    path = Path('test_output_summary.json')
    with suppress(Exception):
        path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
