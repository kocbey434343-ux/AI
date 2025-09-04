from src.ui.main_window import MainWindow

HEADER_COLS_CLOSED = 9


def test_closed_trades_tab_structure(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    # Closed tab exists
    names = [win.tabs.tabText(i) for i in range(win.tabs.count())]
    assert 'Closed' in names
    assert 'Signals' in names
    # Header count
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
