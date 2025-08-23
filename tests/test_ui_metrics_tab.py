import os
import pytest
from src.ui.main_window import MainWindow

# PyQt5 Metrics sekmesi ve latency/slippage etiket senkronizasyon testidir.


@pytest.mark.ui
def test_metrics_tab_labels_update(qtbot):
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'

    w = MainWindow()
    qtbot.addWidget(w)

    # Baslangic degerleri
    assert 'Latency' in w.pos_latency_label.text()
    assert 'Slip' in w.pos_slip_label.text()

    # Ornek metrikler ekle
    with w.trader.metrics_lock:
        w.trader.recent_open_latencies.extend([90.0, 110.0, 100.0])
        w.trader.recent_close_latencies.extend([180.0, 220.0])
        w.trader.recent_entry_slippage_bps.extend([4.5, 5.5])
        w.trader.recent_exit_slippage_bps.extend([2.0])

    # Guncelleme fonksiyonunu cagir
    w._update_position_metrics_labels()

    # Etiketler guncellendi mi?
    lat_txt = w.pos_latency_label.text()
    slip_txt = w.pos_slip_label.text()
    assert 'Open' in lat_txt and 'ms' in lat_txt
    assert 'Entry' in slip_txt and 'bps' in slip_txt

    # Metrics sekmesindeki label'lar senkron mu
    assert w.metrics_latency_label.text() == lat_txt
    assert w.metrics_slip_label.text() == slip_txt
