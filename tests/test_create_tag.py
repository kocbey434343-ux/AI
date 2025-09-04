import subprocess
import sys

from scripts import create_tag


def test_bump_initial_patch():
    assert create_tag.bump('patch', []) == (0, 0, 1)


def test_bump_initial_minor():
    assert create_tag.bump('minor', []) == (0, 1, 0)


def test_bump_initial_major():
    assert create_tag.bump('major', []) == (1, 0, 0)


def test_bump_progression():
    tags = [(1, 0, 0, 1), (1, 0, 1, 1), (1, 1, 0, 1)]
    # Sorted latest (1,1,0,1) -> patch bump -> (1,1,1)
    assert create_tag.bump('patch', tags) == (1, 1, 1)
    assert create_tag.bump('minor', tags) == (1, 2, 0)
    assert create_tag.bump('major', tags) == (2, 0, 0)


def test_dry_run(monkeypatch, capsys):
    # Monkeypatch git tag listing to simulate existing tag
    def fake_check_output(cmd, text=True):  # noqa: ARG001
        return 'v1.0.0-rev1\n'

    monkeypatch.setattr(subprocess, 'check_output', fake_check_output)

    called = {}

    def fake_check_call(cmd):  # noqa: ARG001
        called['ok'] = True

    monkeypatch.setattr(subprocess, 'check_call', fake_check_call)

    # Monkeypatch revision reader
    def fake_read_ssot_revision():
        return 'rev1'

    monkeypatch.setattr(create_tag, 'read_ssot_revision', fake_read_ssot_revision)

    # Simulate args
    orig_argv = sys.argv[:]
    sys.argv = ['create_tag.py', '--level', 'patch', '--dry-run']
    try:
        create_tag.main()
    finally:
        sys.argv = orig_argv
    out = capsys.readouterr().out.strip()
    assert out.startswith('[DRY-RUN] v1.0.1-rev1')
    assert 'ok' not in called  # tag komutu calismadi
