from src.ui.main_window import MainWindow


COLS = 3  # Symbol, Plan, Executed


def test_scale_out_incremental_updates_and_colors(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)

    table = win.scale_table
    assert table.columnCount() == COLS
    assert table.rowCount() == 0

    # 1) Plan ekle
    win.set_scale_out_plan('BTCUSDT', [(1.0, 0.5), (2.0, 0.5)])
    assert table.rowCount() == 1
    assert table.item(0, 0).text() == 'BTCUSDT'
    assert table.item(0, 1).text() == '1.00:50%, 2.00:50%'
    assert table.item(0, 2).text() == '-'
    # Tooltip baslangicta 0%
    assert 'Executed(0.0%)' in (table.item(0, 0).toolTip() or '')

    # 2) Ilk execution: %50 -> sari renge doner
    win.record_scale_out_execution('BTCUSDT', 1.0, 0.5)
    # incremental guncelleme aninda uygulanir
    fg1 = table.item(0, 0).foreground().color().name()
    # QColor.name() daima lowercase verir
    assert fg1 == '#ffff00'
    assert table.item(0, 2).text() == '1.00:50%'
    assert 'Executed(50.0%)' in (table.item(0, 0).toolTip() or '')

    # 3) Ikinci execution: toplam %100 -> yesil renge doner
    win.record_scale_out_execution('BTCUSDT', 2.0, 0.5)
    fg2 = table.item(0, 0).foreground().color().name()
    assert fg2 == '#00aa00'
    assert table.item(0, 2).text() == '1.00:50%, 2.00:50%'
    assert 'Executed(100.0%)' in (table.item(0, 0).toolTip() or '')
