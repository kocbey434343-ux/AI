"""Lightweight tag creation script.

Usage (manual):
  python scripts/create_tag.py --level patch
Levels: patch (default), minor, major.
Tag format: v<major>.<minor>.<patch>-rev<ssot_rev>
Reads SSoT revision from .github/copilot-instructions.md.
Determines next tag by scanning existing git tags.
Does NOT push automatically (safety); print push command.
"""
from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path
from typing import Tuple

SSOT_PATH = Path('.github') / 'copilot-instructions.md'
TAG_PATTERN = re.compile(r'^v(\d+)\.(\d+)\.(\d+)-rev(\d+)$')
REV_PATTERN = re.compile(r'SSoT Revizyon: v?(\d+\.\d+) \(.*rev(?:izyon)? v?(\d+)')


def read_ssot_revision() -> str:
    text = SSOT_PATH.read_text(encoding='utf-8', errors='ignore')
    # Fallback: search for 'SSoT Revizyon: v1.31'
    rev_match = re.search(r'SSoT Revizyon: v.*?v?(\d+)\b', text)
    rev_num = rev_match.group(1) if rev_match else '0'
    return f'rev{rev_num}'


def get_existing_tags() -> list[Tuple[int,int,int,int]]:
    try:
        out = subprocess.check_output(['git', 'tag'], text=True)
    except subprocess.CalledProcessError:
        return []
    tags = []
    for line in out.splitlines():
        m = TAG_PATTERN.match(line.strip())
        if m:
            major, minor, patch, rev = map(int, m.groups())
            tags.append((major, minor, patch, rev))
    return tags


def bump(level: str, tags: list[Tuple[int,int,int,int]]) -> Tuple[int,int,int]:
    if not tags:
        if level == 'major':
            return (1, 0, 0)
        if level == 'minor':
            return (0, 1, 0)
        return (0, 0, 1)
    # Use latest by lexicographic (sorted)
    latest = sorted(tags)[-1]
    major, minor, patch, _ = latest
    if level == 'major':
        return (major + 1, 0, 0)
    if level == 'minor':
        return (major, minor + 1, 0)
    return (major, minor, patch + 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--level', choices=['patch', 'minor', 'major'], default='patch')
    ap.add_argument('--dry-run', action='store_true', help='Hesapla fakat tag olusturma')
    args = ap.parse_args()
    rev = read_ssot_revision()
    tags = get_existing_tags()
    major, minor, patch = bump(args.level, tags)
    tag_name = f'v{major}.{minor}.{patch}-{rev}'
    if args.dry_run:
        print(f'[DRY-RUN] {tag_name}')
        return
    subprocess.check_call(['git', 'tag', tag_name])
    print(f'Created tag: {tag_name}')
    print('Push with: git push origin --tags')


if __name__ == '__main__':
    main()
