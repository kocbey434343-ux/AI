#!/usr/bin/env python3
# ASCII Policy Enforcement Script (CR-0031)
from __future__ import annotations
import sys, pathlib
from typing import Iterable, List, Tuple

TRANSLIT = str.maketrans({'ç':'c','Ç':'C','ğ':'g','Ğ':'G','ı':'i','İ':'I','ö':'o','Ö':'O','ş':'s','Ş':'S','ü':'u','Ü':'U'})
EXCLUDE_DIR_PREFIXES = {'docs'+pathlib.os.sep,'inventorys'+pathlib.os.sep,'.github'+pathlib.os.sep}
EXCLUDE_SUFFIXES = {'.md','.json','.png','.jpg','.jpeg','.gif'}
INCLUDE_SUFFIXES = {'.py','.txt','.yml','.yaml','.sh','.bat'}
Issue = Tuple[str,int,str,str]

def is_excluded(p: pathlib.Path) -> bool:
    rel = str(p).replace('\\','/')
    for pref in EXCLUDE_DIR_PREFIXES:
        if rel.startswith(pref) or f'/{pref}' in rel:
            return True
    if p.suffix.lower() in EXCLUDE_SUFFIXES: return True
    if p.suffix.lower() not in INCLUDE_SUFFIXES: return True
    return False

def scan_file(path: pathlib.Path) -> List[Issue]:
    issues: List[Issue] = []
    try:
        text = path.read_text(encoding='utf-8')
    except Exception:
        return issues
    for i,line in enumerate(text.splitlines(), start=1):
        if all(ord(ch)<128 for ch in line):
            continue
        suggested = ''.join((ch if ord(ch)<128 else ch.translate(TRANSLIT)) for ch in line)
        if any(ord(c)>=128 for c in suggested):
            suggested = suggested.encode('ascii','ignore').decode('ascii')
        issues.append((str(path), i, line, suggested))
    return issues

def iter_candidate_files(paths: Iterable[str]) -> Iterable[pathlib.Path]:
    for base in paths:
        p = pathlib.Path(base)
        if p.is_file():
            if not is_excluded(p):
                yield p
        elif p.is_dir():
            for sub in p.rglob('*'):
                if sub.is_file() and not is_excluded(sub):
                    yield sub

def scan_paths(paths: Iterable[str]) -> List[Issue]:
    all_issues: List[Issue] = []
    for f in iter_candidate_files(paths):
        all_issues.extend(scan_file(f))
    return all_issues

def parse_args(argv: List[str]) -> List[str]:
    if '--files' in argv:
        idx = argv.index('--files')
        return argv[idx+1:]
    # default: full repo
    return ['.']

def main(argv: List[str]) -> int:
    targets = parse_args(argv[1:])
    issues = scan_paths(targets)
    if not issues:
        print('ASCII scan passed: no violations.')
        return 0
    print(f'ASCII scan found {len(issues)} violation(s):')
    for file, ln, orig, sug in issues[:50]:
        print(f'- {file}:{ln}: {orig}')
        if orig != sug:
            print(f'  suggestion: {sug}')
    if len(issues) > 50:
        print('... (truncated) ...')
    return 1

if __name__ == '__main__':  # pragma: no cover
    sys.exit(main(sys.argv))
