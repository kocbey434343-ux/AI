from src.ui.main_window import MainWindow

HEADER_COLS_CLOSED = 10  # Updated column count


def test_closed_trades_tab_structure(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    # Check main tabs exist (Closed trades now integrated into Positions tab)
    names = [win.tabs.tabText(i) for i in range(win.tabs.count())]
    assert 'Pozisyonlar' in names or '📊 Pozisyonlar' in names  # Turkish for "Positions"
    assert 'Sinyaller' in names  # Turkish for "Signals"
    # Header count for closed table (still exists as subtable)
    assert win.closed_table.columnCount() == HEADER_COLS_CLOSED


def test_signals_append_and_dedup(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    before = win.signals_table.rowCount()
    ok1 = win.append_signal('2025-08-24T10:00:00', 'BTCUSDT', 'AL', 87.123)
    ok2 = win.append_signal('2025-08-24T10:00:01', 'ETHUSDT', 'AL', 65.5)
    # duplicate
    dup = win.append_signal('2025-08-24T10:00:00', 'BTCUSDT', 'AL', 90.0)
    assert ok1 and ok2
    assert dup is False
    assert win.signals_table.rowCount() == before + 2
    # Score formatting
    last_score = win.signals_table.item(win.signals_table.rowCount()-1, 3).text()
    assert last_score.count('.') == 1
