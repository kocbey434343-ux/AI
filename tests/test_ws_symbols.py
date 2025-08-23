import types

from src.ui.main_window import MainWindow


class DummyTrader:
    def __init__(self):
        self.open_positions = {
            'BTCUSDT': {'side': 'LONG', 'entry_price': 50000, 'position_size': 0.1},
            'ETHUSDT': {'side': 'SHORT', 'entry_price': 3000, 'position_size': 1},
        }
        self.trade_store = types.SimpleNamespace(open_trades=lambda: [])
    def risk_status(self):
        return {}


def test_compute_ws_symbols_prefers_positions(qtbot, monkeypatch):
    # Reduce side-effects by patching timers start methods
    monkeypatch.setattr('src.ui.main_window.QTimer.start', lambda self, *a, **k: None, raising=False)
    w = MainWindow()
    w.trader = DummyTrader()
    if not hasattr(w, 'position_table'):
        w.create_positions_tab()
    w.position_table.setRowCount(2)
    from PyQt5.QtWidgets import QTableWidgetItem
    w.position_table.setItem(0, 0, QTableWidgetItem('BTCUSDT'))
    w.position_table.setItem(1, 0, QTableWidgetItem('ETHUSDT'))
    syms = w._compute_ws_symbols()
    assert 'BTCUSDT' in syms and 'ETHUSDT' in syms


def test_compute_ws_symbols_includes_buy_signals(qtbot, monkeypatch):
    monkeypatch.setattr('src.ui.main_window.QTimer.start', lambda self, *a, **k: None, raising=False)
    w = MainWindow()
    w.latest_signals = {
        'XRPUSDT': {'signal': 'AL'},
        'BNBUSDT': {'signal': 'SAT'},
    }
    w.position_table = types.SimpleNamespace(rowCount=lambda: 0)  # no positions
    syms = w._compute_ws_symbols()
    assert 'XRPUSDT' in syms and 'BNBUSDT' not in syms