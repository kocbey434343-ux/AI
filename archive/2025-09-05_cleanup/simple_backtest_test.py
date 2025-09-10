#!/usr/bin/env python3
"""
Minimal test
"""
try:
    import sys
    sys.path.append('src')
    from ui.main_window import MainWindow
    from PyQt5.QtWidgets import QApplication

    app = QApplication([])
    window = MainWindow()
    print("MainWindow oluşturuldu!")

    print(f"Tablo öncesi satır sayısı: {window.backtest_table.rowCount()}")

    window._run_pure_backtest()
    print("Backtest çalıştırıldı!")

    print(f"Tablo sonrası satır sayısı: {window.backtest_table.rowCount()}")

    if window.backtest_table.rowCount() > 0:
        item = window.backtest_table.item(0, 0)
        print(f"İlk hücre: {item.text() if item else 'BOŞ'}")

    app.quit()
    print("✅ Test tamamlandı!")

except Exception as e:
    print(f"❌ Hata: {e}")
    import traceback
    traceback.print_exc()
