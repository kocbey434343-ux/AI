#!/usr/bin/env python3
"""
Backtest table test - debugging
"""
import sys
sys.path.append('src')

try:
    from ui.main_window import MainWindow
    from PyQt5.QtWidgets import QApplication

    app = QApplication([])
    window = MainWindow()

    print(f"Backtest table mevcut mu: {hasattr(window, 'backtest_table')}")
    if hasattr(window, 'backtest_table'):
        print(f"Tablo oncesi satir sayisi: {window.backtest_table.rowCount()}")
        print(f"Tablo sutun sayisi: {window.backtest_table.columnCount()}")

        # Headers kontrol et
        headers = []
        for col in range(window.backtest_table.columnCount()):
            header_item = window.backtest_table.horizontalHeaderItem(col)
            headers.append(header_item.text() if header_item else f"Col_{col}")
        print(f"Tablo headers: {headers}")

    print("\n--- BACKTEST CALISTIRILIYOR ---")
    window._run_pure_backtest()

    if hasattr(window, 'backtest_table'):
        print(f"Tablo sonrasi satir sayisi: {window.backtest_table.rowCount()}")

        if window.backtest_table.rowCount() > 0:
            print("\n--- TABLO ICERIGI ---")
            for col in range(window.backtest_table.columnCount()):
                header_item = window.backtest_table.horizontalHeaderItem(col)
                header = header_item.text() if header_item else f"Col_{col}"
                item = window.backtest_table.item(0, col)
                value = item.text() if item else "EMPTY"
                print(f"{header}: {value}")
            print("✅ BASARILI - Tablo dolduruldu!")
        else:
            print("❌ HATA - Tablo bos!")

    # Label'i de kontrol et
    print(f"\nLabel text: {window.backtest_result_label.text()}")

    app.quit()

except Exception as e:
    print(f"❌ Hata: {e}")
    import traceback
    traceback.print_exc()
