from scripts.ascii_scan import scan_paths
import tempfile, pathlib

def test_ascii_scan_detects_and_suggests():
    with tempfile.TemporaryDirectory() as td:
        root = pathlib.Path(td)
        f = root / 'bad.py'
        f.write_text('print("çalışma")\n', encoding='utf-8')
        issues = scan_paths([str(root)])
        assert issues
        file, ln, orig, sug = issues[0]
        assert 'ç' in orig
        assert 'c' in sug


def test_ascii_scan_passes_clean():
    with tempfile.TemporaryDirectory() as td:
        root = pathlib.Path(td)
        (root / 'ok.py').write_text('print("calisma")\n', encoding='utf-8')
        issues = scan_paths([str(root)])
        assert not issues
