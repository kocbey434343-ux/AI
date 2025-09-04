import pytest
from PyQt5.QtWidgets import QWidget, QLabel

# Hizli UI smoke: sadece method wiring dogrular
from src.ui.main_window import MainWindow


class _MiniWin(MainWindow):
    def __init__(self):
        # Intentionally skip MainWindow heavy init
        QWidget.__init__(self)
        self.total_unreal_label = QLabel()


@pytest.mark.qt
def test_smoke_unrealized_label_wiring(qtbot):
    w = _MiniWin()
    qtbot.addWidget(w)
    # Pozitif
    w._set_total_unreal_label(25.0)
    label = w.total_unreal_label
    assert '25.00 USDT' in label.text()
    assert '(0.00%)' in label.text()  # pct varsayilan 0
    assert 'color:green' in label.styleSheet()
    # Negatif
    w._set_total_unreal_label(-5.5)
    assert '-5.50 USDT' in label.text()
    assert 'color:red' in label.styleSheet()
    # Sifir
    w._set_total_unreal_label(0.0)
    assert '0.00 USDT' in label.text()
    assert 'color:gray' in label.styleSheet()
