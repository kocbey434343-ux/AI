"""Simple secret pattern scanner for staged files.

Usage:
  python scripts/secret_scan.py --staged
  python scripts/secret_scan.py path1 path2 ...

Ignore a line by adding: # secret-scan: ignore
"""
from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path
from typing import Iterable, List, Tuple

SECRET_REGEXPS = [
    re.compile(r"BINANCE_API_KEY\s*=\s*['\"]([A-Za-z0-9]{8,})['\"]"),
    re.compile(r"BINANCE_API_SECRET\s*=\s*['\"]([A-Za-z0-9]{16,})['\"]"),
    re.compile(r"(?i)api[-_]?key\s*=\s*['\"]([A-Za-z0-9]{8,})['\"]"),
]
IGNORE_MARK = 'secret-scan: ignore'


def scan_text(text: str) -> List[Tuple[int, str]]:
    issues: List[Tuple[int, str]] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if IGNORE_MARK in line:
            continue
        for rx in SECRET_REGEXPS:
            if rx.search(line):
                issues.append((lineno, line.strip()[:160]))
                break
    return issues


def scan_paths(paths: Iterable[Path]) -> List[Tuple[Path, List[Tuple[int, str]]]]:
    results = []
    for p in paths:
        try:
            if not p.is_file():
                continue
            # Only scan text-like small files
            if p.suffix not in {'.py', '.txt', '.cfg', '.ini', '.yaml', '.yml'}:
                continue
            text = p.read_text(encoding='utf-8', errors='ignore')
            issues = scan_text(text)
            if issues:
                results.append((p, issues))
        except Exception:
            continue
    return results


def get_staged_files() -> List[Path]:
    try:
        out = subprocess.check_output(['git', 'diff', '--cached', '--name-only'], text=True)
    except subprocess.CalledProcessError:
        return []
    return [Path(line.strip()) for line in out.splitlines() if line.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--staged', action='store_true')
    ap.add_argument('paths', nargs='*')
    args = ap.parse_args()
    paths: List[Path]
    paths = get_staged_files() if args.staged else [Path(p) for p in args.paths]
    findings = scan_paths(paths)
    if findings:
        print('SECRET SCAN FAIL: Potential secrets detected')
        for p, items in findings:
            for lineno, line in items:
                print(f'  {p}:{lineno}: {line}')
        print('If false positive add comment: # secret-scan: ignore')
        raise SystemExit(1)
    print('Secret scan OK')


if __name__ == '__main__':
    main()
