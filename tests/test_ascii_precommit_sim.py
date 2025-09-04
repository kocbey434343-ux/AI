import tempfile, pathlib, shutil
from scripts.ascii_scan import scan_paths

def test_precommit_simulation_ascii_violation():
    with tempfile.TemporaryDirectory() as td:
        root = pathlib.Path(td)
        (root / 'scripts').mkdir()
        src_scan = pathlib.Path('scripts/ascii_scan.py')
        shutil.copy(src_scan, root / 'scripts/ascii_scan.py')
        bad = root / 'bad.py'
        bad.write_text('print("çalışma")\n', encoding='utf-8')
        issues = scan_paths([str(root)])
        assert issues and any('ç' in i[2] for i in issues)
