import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTableWidget, QTableWidgetItem,
    QTabWidget, QHeaderView, QMessageBox, QSpinBox,
    QDoubleSpinBox, QComboBox, QLineEdit, QGroupBox, QAction, QCheckBox,
    QDialog
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QCoreApplication, QThread
from PyQt5.QtGui import QColor, QFont, QCloseEvent, QPainter, QPen

from src.ui.signal_window import SignalWindow
from src.data_fetcher import DataFetcher
from src.signal_generator import SignalGenerator
from src.trader import Trader
from src.api.health_check import HealthChecker
from config.settings import Settings
from src.utils.ws_utils import should_restart_ws
from src.backtest.calibrate import run_calibration
try:
    from src.api.price_stream import PriceStreamManager  # alias for tests monkeypatching
except Exception:  # pragma: no cover
    PriceStreamManager = None


class MainWindow(QMainWindow):
    signals_updated = pyqtSignal(dict)
    calibration_finished = pyqtSignal(dict)

    def __init__(self):
        super(MainWindow, self).__init__()
        self.setWindowTitle("Trade Bot - Ana Panel")
        self.setGeometry(100, 100, 1200, 800)

        # Core components
        self.data_fetcher = DataFetcher()
        self.signal_generator = SignalGenerator()
        self.trader = Trader()
        self.health_checker = HealthChecker()
        self.latest_signals = {}

        # Caches / mappings
        self.last_prices = {}
        self.position_row_map = {}

        # WS helpers
        self.ws_stream = None
        self._ws_symbols = []

        # Incremental signal processing state
        self.incremental_pairs = []
        self.incremental_index = 0
        self.incremental_signals = {}

        # Timers (created later where needed)
        self.metrics_timer = None
        self.auto_calib_timer = QTimer(self)
        self.auto_calib_timer.setSingleShot(False)
        self.auto_calib_timer.timeout.connect(self._auto_calibration_tick)

        # Build UI & load initial data
        self.setup_ui()
        self.load_data()


    # --- Settings runtime update helpers (type checker friendly) ---
    def _set_setting(self, name: str, value):
        try:
            setattr(Settings, name, value)
        except Exception:
            pass

    def begin_incremental_signals(self):
        """Parçalı sinyal üretimini başlatır (eksik tanım geri eklendi)."""
        try:
            self.incremental_pairs = self.data_fetcher.load_top_pairs()
        except Exception:
            self.incremental_pairs = []
        if not self.incremental_pairs:
            return
        self.incremental_index = 0
        self.incremental_signals = {}
        if hasattr(self, 'signal_table'):
            self.signal_table.setRowCount(0)
        if hasattr(self, 'refresh_btn'):
            self.refresh_btn.setEnabled(False)
        if hasattr(self, 'last_update_label'):
            self.last_update_label.setText("Son: hesaplanıyor...")
        QTimer.singleShot(1, self._process_next_signal)

    def show_signal_window(self):
        """Detay sinyal penceresini aç."""
        try:
            if not hasattr(self, '_signal_window') or self._signal_window is None:
                # SignalWindow(signature): (signal_generator, parent=None, signals=None)
                preload = getattr(self, 'incremental_signals', {})
                self._signal_window = SignalWindow(self.signal_generator, parent=self, signals=preload)
                # Mevcut sinyalleri aktar
                if getattr(self, 'incremental_signals', None):
                    try:
                        self._signal_window.receive_signals_update(self.incremental_signals)
                    except Exception:
                        pass
            self._signal_window.show()
            self._signal_window.raise_()
            self._signal_window.activateWindow()
        except Exception:
            pass

    def _maybe_auto_refresh_closed(self):
        """Kapalı işlemler sekmesi aktifse periyodik yenile."""
        try:
            if not hasattr(self, 'closed_tab_index'):
                return
            # Sadece ilgili sekmedeyken (yoğun DB sorgusunu azaltmak için)
            if self.tabs.currentIndex() != self.closed_tab_index:
                return
            self.refresh_closed_trades()
        except Exception:
            pass

    def start_calibration(self):
        """Kalibrasyon thread'ini başlat (UI bloklanmasın)."""
        try:
            if getattr(self, 'calib_thread', None) and self.calib_thread.isRunning():
                return
            limit = int(self.calib_pair_limit.value()) if hasattr(self,'calib_pair_limit') else 40
            self.calib_status_label.setText(f"Kalibrasyon başlıyor (limit={limit}) ...")
            self.run_calib_btn.setEnabled(False)
            if hasattr(self, 'apply_thresholds_btn'):
                self.apply_thresholds_btn.setEnabled(False)
            if hasattr(self, 'calib_result_label'):
                self.calib_result_label.setText("-")
            if hasattr(self, 'optim_table'):
                self.optim_table.clearContents()
                self.optim_table.setRowCount(0)
                self.optim_table.setVisible(False)
            if hasattr(self, 'apply_selected_candidate_btn'):
                self.apply_selected_candidate_btn.setEnabled(False)
            if hasattr(self, 'calib_progress'):
                self.calib_progress.setVisible(True)
            # Thread
            self.calib_thread = _CalibrationThread(limit)
            self.calib_thread.finished_with_result.connect(self.calibration_finished.emit)
            self.calib_thread.finished.connect(lambda: self.run_calib_btn.setEnabled(True))
            self.calib_thread.start()
        except Exception:
            pass
    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        lay = QVBoxLayout(central)

        title = QLabel("Trade Bot Ana Panel")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Arial", 16, QFont.Bold))
        lay.addWidget(title)

        self.tabs = QTabWidget()
        lay.addWidget(self.tabs)

        # Sekmeler
        self.create_control_tab()
        self.create_signals_tab()
        self.create_positions_tab()
        self.create_metrics_tab()
        self.create_closed_trades_tab()
        self.create_settings_tab()
        self.create_health_tab()

        # Diğer UI ayarları
        self.add_dark_mode_toggle()
        self.calibration_finished.connect(self.on_calibration_finished)
        # Periyodik latency / slippage label güncellemesi
        try:
            self.metrics_timer = QTimer(self)
            self.metrics_timer.timeout.connect(self._update_position_metrics_labels)
            self.metrics_timer.start(3000)  # every 3s
        except Exception:
            pass

    def _update_position_metrics_labels(self):
        """Update latency/slippage mini labels from trader recent metrics."""
        try:
            if not hasattr(self, 'trader'):
                return
            stats = self.trader.recent_latency_slippage_stats(window=30) if hasattr(self.trader, 'recent_latency_slippage_stats') else {}
            if hasattr(self, 'pos_latency_label') and stats:
                ol = stats.get('open_latency_ms'); cl = stats.get('close_latency_ms')
                parts = []
                if ol is not None:
                    parts.append(f"Open {ol:.1f}ms")
                if cl is not None:
                    parts.append(f"Close {cl:.1f}ms")
                if parts:
                    self.pos_latency_label.setText("Latency: " + ", ".join(parts))
            if hasattr(self, 'pos_slip_label') and stats:
                es = stats.get('entry_slip_bps'); xs = stats.get('exit_slip_bps')
                sparts = []
                if es is not None:
                    sparts.append(f"Entry {es:.1f}")
                if xs is not None:
                    sparts.append(f"Exit {xs:.1f}")
                if sparts:
                    self.pos_slip_label.setText("Slip: " + "/".join(sparts) + " bps")
            # Also refresh metrics tab widgets if present
            if hasattr(self, 'metrics_latency_label') and stats:
                self.metrics_latency_label.setText(self.pos_latency_label.text())
            if hasattr(self, 'metrics_slip_label') and stats:
                self.metrics_slip_label.setText(self.pos_slip_label.text())
            if hasattr(self, 'metrics_history_list') and hasattr(self.trader, 'recent_open_latencies'):
                # Simple textual history (last 10) for open latency and entry slip
                try:
                    with self.trader.metrics_lock:
                        ol_hist = self.trader.recent_open_latencies[-10:]
                        es_hist = self.trader.recent_entry_slippage_bps[-10:]
                    lines = ["Open Lat (ms): " + ", ".join(f"{v:.0f}" for v in ol_hist),
                             "Entry Slip (bps): " + ", ".join(f"{v:.1f}" for v in es_hist)]
                    self.metrics_history_list.clear()
                    for ln in lines:
                        self.metrics_history_list.addItem(ln)
                    # Sparkline charts update
                    if hasattr(self, 'latency_chart'):
                        with self.trader.metrics_lock:
                            self.latency_chart.set_values(self.trader.recent_open_latencies)
                    if hasattr(self, 'slip_chart'):
                        with self.trader.metrics_lock:
                            self.slip_chart.set_values(self.trader.recent_entry_slippage_bps)
                except Exception:
                    pass
        except Exception:
            pass

    def create_metrics_tab(self):
        """Basit Metrics sekmesi: latency & slippage özet + son örnekler."""
        tab = QWidget()
        lay = QVBoxLayout(tab)
        header = QLabel("Canlı Metrikler")
        header.setFont(QFont("Arial", 12, QFont.Bold))
        lay.addWidget(header)

        row = QHBoxLayout()
        self.metrics_latency_label = QLabel("Latency: -")
        self.metrics_slip_label = QLabel("Slip: -")
        for w in (self.metrics_latency_label, self.metrics_slip_label):
            w.setStyleSheet("color:#888; font-size:12px")
        row.addWidget(self.metrics_latency_label)
        row.addWidget(self.metrics_slip_label)
        row.addStretch()
        lay.addLayout(row)

        from PyQt5.QtWidgets import QListWidget
        self.metrics_history_list = QListWidget()
        self.metrics_history_list.setMinimumHeight(120)
        lay.addWidget(self.metrics_history_list)

        # Mini sparkline widgets (latency & slippage)
        try:
            class _MiniSeriesWidget(QWidget):
                def __init__(self, color: QColor, parent=None, max_points: int = 120):
                    super().__init__(parent)
                    self._color = color
                    self._values: list[float] = []
                    self._max_points = max_points
                    self.setMinimumHeight(50)
                    self.setMaximumHeight(60)
                def set_values(self, values: list[float]):
                    self._values = list(values[-self._max_points:]) if values else []
                    self.update()
                def paintEvent(self, a0):  # noqa
                    if len(self._values) < 2:
                        return
                    try:
                        p = QPainter(self)
                        p.setRenderHint(QPainter.Antialiasing)
                        w = self.width(); h = self.height()
                        vmin = min(self._values); vmax = max(self._values)
                        rng = (vmax - vmin) or 1.0
                        pen = QPen(self._color, 2)
                        p.setPen(pen)
                        step = w / (len(self._values) - 1)
                        last_x = 0
                        last_y = h - ((self._values[0]-vmin)/rng) * h
                        for idx, v in enumerate(self._values[1:], start=1):
                            x = step * idx
                            y = h - ((v - vmin)/rng) * h
                            p.drawLine(int(last_x), int(last_y), int(x), int(y))
                            last_x, last_y = x, y
                        # Baseline (min or zero line)
                        base_val = 0 if vmin < 0 < vmax else vmin
                        base_y = h - ((base_val - vmin)/rng) * h
                        p.setPen(QPen(QColor('#555'), 1))
                        p.drawLine(0, int(base_y), w, int(base_y))
                        p.end()
                    except Exception:
                        pass
            charts = QHBoxLayout()
            lat_box = QVBoxLayout(); lat_box.addWidget(QLabel("Open Latency Sparkline"))
            self.latency_chart = _MiniSeriesWidget(QColor('#4CAF50'))
            lat_box.addWidget(self.latency_chart)
            slip_box = QVBoxLayout(); slip_box.addWidget(QLabel("Entry Slippage Sparkline"))
            self.slip_chart = _MiniSeriesWidget(QColor('#FF9800'))
            slip_box.addWidget(self.slip_chart)
            charts.addLayout(lat_box)
            charts.addLayout(slip_box)
            lay.addLayout(charts)
        except Exception:
            pass

        hint = QLabel("Not: Son 100 örnekten pencere ortalaması gösterilir. Genişletme: histogram / guard sayaçları.")
        hint.setStyleSheet("color:#666; font-size:11px")
        lay.addWidget(hint)

        self.tabs.addTab(tab, "Metrics")

    def add_dark_mode_toggle(self):
        act = QAction("Toggle Dark Mode", self)
        act.triggered.connect(self.toggle_dark_mode)
        self.menuBar().addAction(act)

    def toggle_dark_mode(self):
        if self.styleSheet():
            self.setStyleSheet("")
        else:
            self.setStyleSheet("background:#2E2E2E; color:#fff;")

    def create_control_tab(self):
            tab = QWidget()
            layout = QVBoxLayout(tab)

            # --- Buttons row ---
            btn_row = QHBoxLayout()
            self.start_btn = QPushButton("Botu Başlat"); self.start_btn.clicked.connect(self.start_bot); btn_row.addWidget(self.start_btn)
            self.stop_btn = QPushButton("Botu Durdur"); self.stop_btn.clicked.connect(self.stop_bot); self.stop_btn.setEnabled(False); btn_row.addWidget(self.stop_btn)
            self.update_data_btn = QPushButton("Verileri Güncelle"); self.update_data_btn.clicked.connect(self.update_data); btn_row.addWidget(self.update_data_btn)
            self.backup_btn = QPushButton("Verileri Yedekle"); self.backup_btn.clicked.connect(self.backup_data); btn_row.addWidget(self.backup_btn)
            btn_row.addStretch(); layout.addLayout(btn_row)

            # --- Calibration group ---
            calib_group = QGroupBox("Backtest Kalibrasyon")
            cg_layout = QVBoxLayout()
            from PyQt5.QtWidgets import QFormLayout, QSpinBox as _QSpinBox
            form = QFormLayout()
            self.calib_pair_limit = _QSpinBox(); self.calib_pair_limit.setRange(5, 150); self.calib_pair_limit.setValue(40)
            form.addRow("Parite Limiti:", self.calib_pair_limit)
            self.auto_apply_checkbox = QCheckBox("Eşikleri otomatik uygula (p85/p15)"); self.auto_apply_checkbox.setChecked(False); form.addRow("Oto Uygula:", self.auto_apply_checkbox)
            self.auto_calib_checkbox = QCheckBox("Periyodik kalibrasyon"); self.auto_calib_checkbox.setChecked(False); self.auto_calib_checkbox.stateChanged.connect(self._toggle_auto_calib); form.addRow("Oto Kalibrasyon:", self.auto_calib_checkbox)
            from PyQt5.QtWidgets import QSpinBox as _Spin
            self.auto_calib_hours = _Spin(); self.auto_calib_hours.setRange(1, 48); self.auto_calib_hours.setValue(12); self.auto_calib_hours.valueChanged.connect(self._update_auto_calib_interval); form.addRow("Aralık (saat):", self.auto_calib_hours)
            cg_layout.addLayout(form)

            cb_row = QHBoxLayout()
            self.run_calib_btn = QPushButton("Kalibrasyonu Çalıştır"); self.run_calib_btn.clicked.connect(self.start_calibration); cb_row.addWidget(self.run_calib_btn)
            self.apply_thresholds_btn = QPushButton("Önerilen Eşikleri Uygula"); self.apply_thresholds_btn.setEnabled(False); self.apply_thresholds_btn.clicked.connect(self.apply_suggested_thresholds); cb_row.addWidget(self.apply_thresholds_btn)
            self.apply_best_candidate_btn = QPushButton("En İyi Adayı Uygula"); self.apply_best_candidate_btn.setEnabled(False); self.apply_best_candidate_btn.clicked.connect(self.apply_best_candidate_thresholds); cb_row.addWidget(self.apply_best_candidate_btn)
            self.apply_selected_candidate_btn = QPushButton("Seçili Adayı Uygula"); self.apply_selected_candidate_btn.setEnabled(False); self.apply_selected_candidate_btn.clicked.connect(self.apply_selected_candidate_thresholds); cb_row.addWidget(self.apply_selected_candidate_btn)
            cb_row.addStretch(); cg_layout.addLayout(cb_row)

            self.calib_status_label = QLabel("Kalibrasyon durumu: Hazır"); self.calib_status_label.setStyleSheet("color: gray; font-size:11px"); cg_layout.addWidget(self.calib_status_label)
            self.calib_result_label = QLabel("-"); self.calib_result_label.setWordWrap(True); cg_layout.addWidget(self.calib_result_label)
            self.calib_stats_label = QLabel(""); self.calib_stats_label.setStyleSheet("color: gray; font-size:11px"); self.calib_stats_label.setWordWrap(True); cg_layout.addWidget(self.calib_stats_label)
            # Cost & fill controls
            cost_row = QHBoxLayout()
            from PyQt5.QtWidgets import QDoubleSpinBox as _DSpin
            cost_row.addWidget(QLabel("Komisyon% (tek taraf):"))
            self.commission_spin = _DSpin(); self.commission_spin.setRange(0,1); self.commission_spin.setDecimals(4); self.commission_spin.setSingleStep(0.01); self.commission_spin.setValue(float(getattr(Settings,'COMMISSION_PCT_PER_SIDE',0.04))/100.0)
            cost_row.addWidget(self.commission_spin)
            cost_row.addWidget(QLabel("Slippage% (tek taraf):"))
            self.slippage_spin = _DSpin(); self.slippage_spin.setRange(0,1); self.slippage_spin.setDecimals(4); self.slippage_spin.setSingleStep(0.01); self.slippage_spin.setValue(float(getattr(Settings,'SLIPPAGE_PCT_PER_SIDE',0.02))/100.0)
            cost_row.addWidget(self.slippage_spin)
            self.next_bar_fill_chk = QCheckBox("Next bar fill"); self.next_bar_fill_chk.setChecked(getattr(Settings,'USE_NEXT_BAR_FILL',False)); cost_row.addWidget(self.next_bar_fill_chk)
            self.auto_recalib_cost_chk = QCheckBox("Maliyet değişince yeniden kalibre"); self.auto_recalib_cost_chk.setChecked(False); cost_row.addWidget(self.auto_recalib_cost_chk)
            cost_row.addStretch(); cg_layout.addLayout(cost_row)
            # Cost ayar değişikliklerini anlık persist et
            def _costs_changed():
                try:
                    Settings.COMMISSION_PCT_PER_SIDE = float(self.commission_spin.value() * 100.0)
                    Settings.SLIPPAGE_PCT_PER_SIDE = float(self.slippage_spin.value() * 100.0)
                    Settings.USE_NEXT_BAR_FILL = self.next_bar_fill_chk.isChecked()
                    from config.runtime_costs import persist_runtime_costs
                    persist_runtime_costs(source="ui")
                    if self.auto_recalib_cost_chk.isChecked() and (not hasattr(self, 'calib_thread') or not self.calib_thread.isRunning()):
                        self.start_calibration()
                except Exception:
                    pass
            self.commission_spin.valueChanged.connect(lambda _: _costs_changed())
            self.slippage_spin.valueChanged.connect(lambda _: _costs_changed())
            self.next_bar_fill_chk.stateChanged.connect(lambda _: _costs_changed())
            self.current_thresholds_label = QLabel(self._format_current_thresholds()); self.current_thresholds_label.setStyleSheet("color: #888; font-size:11px"); cg_layout.addWidget(self.current_thresholds_label)
            # Progress bar (busy) for calibration
            from PyQt5.QtWidgets import QProgressBar as _QPB
            self.calib_progress = _QPB(); self.calib_progress.setRange(0,0); self.calib_progress.setVisible(False)
            cg_layout.addWidget(self.calib_progress)

            # Manuel exit eşikleri grubu
            exit_group = QGroupBox("Histerezis Exit Eşikleri")
            egl = QHBoxLayout()
            from PyQt5.QtWidgets import QDoubleSpinBox as _DSpin
            self.buy_exit_spin = _DSpin(); self.buy_exit_spin.setDecimals(2); self.buy_exit_spin.setRange(0, 120); self.buy_exit_spin.setValue(float(getattr(Settings, 'BUY_EXIT_THRESHOLD', Settings.BUY_SIGNAL_THRESHOLD - 5)))
            self.sell_exit_spin = _DSpin(); self.sell_exit_spin.setDecimals(2); self.sell_exit_spin.setRange(0, 120); self.sell_exit_spin.setValue(float(getattr(Settings, 'SELL_EXIT_THRESHOLD', Settings.SELL_SIGNAL_THRESHOLD + 5)))
            def _exit_changed():
                try:
                    Settings.BUY_EXIT_THRESHOLD = float(self.buy_exit_spin.value())
                    Settings.SELL_EXIT_THRESHOLD = float(self.sell_exit_spin.value())
                    self.current_thresholds_label.setText(self._format_current_thresholds())
                    # Persist anlık güncelleme (giriş eşikleri ile birlikte)
                    from config.runtime_thresholds import persist_runtime_thresholds
                    persist_runtime_thresholds(Settings.BUY_SIGNAL_THRESHOLD, Settings.SELL_SIGNAL_THRESHOLD,
                                               Settings.BUY_EXIT_THRESHOLD, Settings.SELL_EXIT_THRESHOLD, source="manual-exit")
                except Exception:
                    pass
            self.buy_exit_spin.valueChanged.connect(_exit_changed)
            self.sell_exit_spin.valueChanged.connect(_exit_changed)
            egl.addWidget(QLabel("AL Çıkış:")); egl.addWidget(self.buy_exit_spin)
            egl.addWidget(QLabel("SAT Çıkış:")); egl.addWidget(self.sell_exit_spin)
            egl.addStretch(); exit_group.setLayout(egl); layout.addWidget(exit_group)

            # Kalibrasyon trade istatistikleri görüntüleme butonu
            self.view_calib_stats_btn = QPushButton("Kalibrasyon Trade İstatistikleri")
            self.view_calib_stats_btn.setEnabled(False)
            self.view_calib_stats_btn.clicked.connect(self._show_calibration_symbol_stats)
            layout.addWidget(self.view_calib_stats_btn)

            # Optimization candidates table
            from PyQt5.QtWidgets import QTableWidget as _QTW
            self.optim_table = _QTW(); self.optim_table.setColumnCount(10)
            self.optim_table.setHorizontalHeaderLabels(["Tag","Buy","Sell","BExit","SExit","Win%","Win%(c)","Exp%","Exp%(c)","Trades"])
            self.optim_table.setVisible(False)
            self.optim_table.setStyleSheet("font-size:11px")
            cg_layout.addWidget(self.optim_table)

            calib_group.setLayout(cg_layout)
            layout.addWidget(calib_group)

            # --- Status ---
            self.status_label = QLabel("Durum: Bot hazır"); layout.addWidget(self.status_label)
            # Risk durum göstergesi
            risk_row = QHBoxLayout(); risk_row.addWidget(QLabel("Günlük Risk Durumu:"))
            self.risk_status_label = QLabel("-"); self.risk_status_label.setStyleSheet("color: gray; font-size:11px"); risk_row.addWidget(self.risk_status_label); risk_row.addStretch(); layout.addLayout(risk_row)
            # Risk timer (30s)
            self.risk_timer = QTimer(self); self.risk_timer.timeout.connect(self._update_risk_status); self.risk_timer.start(30000)

            # --- Run hours ---
            tl = QHBoxLayout(); tl.addWidget(QLabel("Çalışma Süresi (saat):"))
            self.hours_spin = QSpinBox(); self.hours_spin.setRange(1, 24); self.hours_spin.setValue(8); tl.addWidget(self.hours_spin); tl.addStretch(); layout.addLayout(tl)

            self.tabs.addTab(tab, "Kontrol")

    def create_signals_tab(self):
        tab = QWidget(); lay = QVBoxLayout(tab)
        bar = QHBoxLayout()
        self.signal_btn = QPushButton("Detay Analiz"); self.signal_btn.clicked.connect(self.show_signal_window); bar.addWidget(self.signal_btn)
        self.refresh_btn = QPushButton("Yenile"); self.refresh_btn.clicked.connect(self.begin_incremental_signals); bar.addWidget(self.refresh_btn)
        bar.addWidget(QLabel("Interval:"))
        self.interval_combo = QComboBox(); self.interval_combo.addItems(["1h","4h","1d"]); self.interval_combo.setCurrentText(Settings.TIMEFRAME); self.interval_combo.currentTextChanged.connect(lambda: self.begin_incremental_signals()); bar.addWidget(self.interval_combo)
        bar.addWidget(QLabel("Filtre:"))
        self.filter_edit = QLineEdit(); self.filter_edit.setPlaceholderText("Parite / sinyal / >puan (örn: >70) ..."); self.filter_edit.textChanged.connect(self.apply_signal_filter); bar.addWidget(self.filter_edit)
        self.last_update_label = QLabel("Son: -"); self.last_update_label.setStyleSheet("color: gray; font-size:11px"); bar.addWidget(self.last_update_label)
        bar.addStretch(); lay.addLayout(bar)
        self.signal_table = QTableWidget(); self.signal_table.setColumnCount(8)
        self.signal_table.setHorizontalHeaderLabels(["Parite","Fiyat","%","Sinyal","Puan","Hacim","Risk","Zaman"])
        self.signal_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        lay.addWidget(self.signal_table)
        self.tabs.addTab(tab, "Sinyaller")

    # (Removed earlier malformed create_positions_tab stub; real implementation defined later.)

    def create_settings_tab(self):
        tab = QWidget(); lay = QVBoxLayout(tab)
        rg = QGroupBox("Risk Yönetimi"); rlay = QVBoxLayout()
        rp = QHBoxLayout(); rp.addWidget(QLabel("Risk Yüzdesi (%):")); self.risk_percent_spin = QDoubleSpinBox(); self.risk_percent_spin.setRange(1,100); self.risk_percent_spin.setValue(Settings.DEFAULT_RISK_PERCENT); rp.addWidget(self.risk_percent_spin); rlay.addLayout(rp)
        lev = QHBoxLayout(); lev.addWidget(QLabel("Kaldıraç (x):")); self.leverage_spin = QSpinBox(); self.leverage_spin.setRange(1,125); self.leverage_spin.setValue(Settings.DEFAULT_LEVERAGE); lev.addWidget(self.leverage_spin); rlay.addLayout(lev)
        mp = QHBoxLayout(); mp.addWidget(QLabel("Maks. Pozisyon:")); self.max_pos_spin = QSpinBox(); self.max_pos_spin.setRange(1,10); self.max_pos_spin.setValue(Settings.DEFAULT_MAX_POSITIONS); mp.addWidget(self.max_pos_spin); rlay.addLayout(mp)
        mv = QHBoxLayout(); mv.addWidget(QLabel("Min. Hacim (USDT):")); self.min_vol_spin = QDoubleSpinBox(); self.min_vol_spin.setRange(1000, 10000000); self.min_vol_spin.setValue(Settings.DEFAULT_MIN_VOLUME); mv.addWidget(self.min_vol_spin); rlay.addLayout(mv)
        rg.setLayout(rlay); lay.addWidget(rg)
        mg = QGroupBox("Piyasa Modu"); ml = QHBoxLayout(); ml.addWidget(QLabel("Mod:")); self.mode_combo = QComboBox(); self.mode_combo.addItems(["spot","futures"]); self.mode_combo.setCurrentText(Settings.MARKET_MODE); ml.addWidget(self.mode_combo); ml.addStretch(); mg.setLayout(ml); lay.addWidget(mg)
        self.save_settings_btn = QPushButton("Ayarları Kaydet"); self.save_settings_btn.clicked.connect(self.save_settings); lay.addWidget(self.save_settings_btn)
        self.tabs.addTab(tab, "Ayarlar")

    def create_health_tab(self):
        tab = QWidget(); lay = QVBoxLayout(tab)
        self.health_label = QLabel("Sağlık durumu kontrol ediliyor..."); lay.addWidget(self.health_label)
        self.api_test_btn = QPushButton("API Testi Yap"); self.api_test_btn.clicked.connect(self.test_api); lay.addWidget(self.api_test_btn)
        self.connection_label = QLabel("Bağlantı durumu: Bilinmiyor"); lay.addWidget(self.connection_label)
        self.tabs.addTab(tab, "Sağlık")

    def update_positions(self):
        """Açık pozisyonları incremental diff ile güncelle.

        Tam tabloyu yeniden oluşturmak yerine:
         - Yeni semboller: eklenir
         - Kapanan semboller: satır silinir
         - Mevcut semboller: sadece değişen hücreler güncellenir
        Böylece GUI'de flicker ve repaint maliyeti azalır.
        """
        try:
            if not hasattr(self, 'position_table'):
                return
            # --- Topla ---
            pos_map = {}
            try:
                for rec in self.trader.trade_store.open_trades():
                    sym = rec.get('symbol');
                    if sym:
                        pos_map[sym] = {
                            'symbol': sym,
                            'side': rec.get('side'),
                            'entry_price': rec.get('entry_price'),
                            'size': rec.get('size'),
                            'stop_loss': rec.get('stop_loss'),
                            'take_profit': rec.get('take_profit'),
                            'opened_at': rec.get('opened_at')
                        }
            except Exception:
                pass
            try:
                for sym, pos in (self.trader.open_positions or {}).items():
                    if sym not in pos_map:
                        pos_map[sym] = {
                            'symbol': sym,
                            'side': pos.get('side'),
                            'entry_price': pos.get('entry_price'),
                            'size': pos.get('position_size') or pos.get('size'),
                            'stop_loss': pos.get('stop_loss'),
                            'take_profit': pos.get('take_profit'),
                            'opened_at': getattr(pos.get('timestamp'), 'isoformat', lambda: '')() if pos.get('timestamp') else ''
                        }
            except Exception:
                pass

            # Mevcut tablo sembolleri
            existing_map = {}
            row_count = self.position_table.rowCount()
            for r in range(row_count):
                item = self.position_table.item(r, 0)
                if item:
                    existing_map[item.text()] = r

            new_symbols = list(pos_map.keys())
            existing_symbols = set(existing_map.keys())
            current_set = set(new_symbols)
            removed = existing_symbols - current_set
            added = current_set - existing_symbols
            stayed = existing_symbols & current_set

            # Silinecek satırları indekslerine göre ters sırada sil
            if removed:
                remove_rows = sorted([existing_map[s] for s in removed], reverse=True)
                for r in remove_rows:
                    self.position_table.removeRow(r)

            # Eklenen semboller için satır append
            from PyQt5.QtWidgets import QTableWidgetItem  # local import (already at top normally)
            total_unreal = 0.0

            def compute_vals(sym, pdata):
                side = pdata.get('side','')
                entry = pdata.get('entry_price')
                size = pdata.get('size','')
                sl = pdata.get('stop_loss','')
                tp = pdata.get('take_profit','')
                opened = pdata.get('opened_at','')
                last = self.last_prices.get(sym)
                pnl_pct = ''
                partial_pct = ''
                trail_info = ''
                try:
                    pos = self.trader.open_positions.get(sym) if hasattr(self.trader, 'open_positions') else None
                    if pos:
                        init_sz = pos.get('position_size') or pos.get('size')
                        rem = pos.get('remaining_size')
                        if init_sz and rem is not None and float(init_sz) > 0:
                            used = float(init_sz) - float(rem)
                            partial_pct = f"{(used/float(init_sz))*100.0:.1f}"
                        if pos.get('atr_trail_active') and pos.get('atr_stop') is not None:
                            trail_info = f"ATR {pos.get('atr_stop')}"
                        elif pos.get('trailing_active') and pos.get('trail_stop') is not None:
                            trail_info = f"TR {pos.get('trail_stop')}"
                except Exception:
                    pass
                if entry and last is not None:
                    try:
                        entry_f = float(entry); last_f = float(last)
                        if side and side.upper() in ('LONG','BUY'):
                            pnl = (last_f-entry_f)/entry_f*100.0
                        elif side and side.upper() in ('SHORT','SELL'):
                            pnl = (entry_f-last_f)/entry_f*100.0
                        else:
                            pnl = 0.0
                        pnl_pct = f"{pnl:.2f}"
                        # Unrealized nominal katkı
                        try:
                            qty_f = float(size) if size not in ('', None) else 0.0
                            if qty_f and entry_f:
                                if side.upper() in ('LONG','BUY'):
                                    return (sym, side, entry, last, pnl_pct, size, sl, tp, opened, partial_pct, trail_info, (last_f - entry_f) * qty_f)
                                elif side.upper() in ('SHORT','SELL'):
                                    return (sym, side, entry, last, pnl_pct, size, sl, tp, opened, partial_pct, trail_info, (entry_f - last_f) * qty_f)
                        except Exception:
                            pass
                        return (sym, side, entry, last, pnl_pct, size, sl, tp, opened, partial_pct, trail_info, 0.0)
                    except Exception:
                        pass
                return (sym, side, entry, last if last is not None else '', pnl_pct, size, sl, tp, opened, partial_pct, trail_info, 0.0)

            # Güncellenecek + eklenecek
            # Önce stayed semboller için hücre farkı güncelle
            for sym in stayed:
                pdata = pos_map[sym]
                row_idx = existing_map.get(sym)
                if row_idx is None:
                    continue
                sym, side, entry, last, pnl_pct, size, sl, tp, opened, partial_pct, trail_info, unreal = compute_vals(sym, pdata)
                total_unreal += unreal
                new_vals = [sym, side, entry, last if last != '' else '', pnl_pct, size, sl, tp, opened, partial_pct, trail_info]
                for c, nv in enumerate(new_vals):
                    cur_item = self.position_table.item(row_idx, c)
                    if nv is None:
                        txt = ''
                    else:
                        txt = str(nv)
                    if cur_item is None:
                        cur_item = QTableWidgetItem(txt)
                        self.position_table.setItem(row_idx, c, cur_item)
                    elif cur_item.text() != txt:
                        cur_item.setText(txt)
                    if c == 4 and txt not in ('', None):
                        try:
                            pv = float(txt)
                            if pv > 0: cur_item.setForeground(QColor('green'))
                            elif pv < 0: cur_item.setForeground(QColor('red'))
                        except Exception:
                            pass

            for sym in added:
                pdata = pos_map[sym]
                sym, side, entry, last, pnl_pct, size, sl, tp, opened, partial_pct, trail_info, unreal = compute_vals(sym, pdata)
                total_unreal += unreal
                row_idx = self.position_table.rowCount()
                self.position_table.insertRow(row_idx)
                vals = [sym, side, entry, last if last != '' else '', pnl_pct, size, sl, tp, opened, partial_pct, trail_info]
                for c, v in enumerate(vals):
                    item = QTableWidgetItem(str(v))
                    if c == 4 and isinstance(v, str) and v not in ('', None):
                        try:
                            pv = float(v)
                            if pv > 0: item.setForeground(QColor('green'))
                            elif pv < 0: item.setForeground(QColor('red'))
                        except Exception:
                            pass
                    self.position_table.setItem(row_idx, c, item)

            # position_row_map'i yeniden oluştur
            self.position_row_map = {}
            for r in range(self.position_table.rowCount()):
                itm = self.position_table.item(r, 0)
                if itm:
                    self.position_row_map[itm.text()] = r

            # Toplam unrealized etiketi
            try:
                if hasattr(self, 'total_unreal_label') and self.total_unreal_label is not None:
                    self.total_unreal_label.setText(f"Toplam Unrealized: {total_unreal:.2f} USDT")
                    col = 'green' if total_unreal >= 0 else 'red'
                    self.total_unreal_label.setStyleSheet(f"color:{col}; font-size:11px")
            except Exception:
                pass
            # WS sembol refresh
            self._maybe_refresh_ws_symbols()
        except Exception:
            pass

    def load_data(self):
        """Verileri yükle"""
        try:
            import os
            if not os.environ.get('SKIP_SIGNAL_INIT'):
                self.begin_incremental_signals()
        except Exception:
            self.begin_incremental_signals()
        self.update_positions()

    def _process_next_signal(self):
        if self.incremental_index >= len(self.incremental_pairs):
            self._finalize_incremental_signals()
            return
        symbol = self.incremental_pairs[self.incremental_index]
        try:
            signal = self.signal_generator.generate_pair_signal(symbol)
        except Exception:
            signal = None
        if signal:
            self._append_signal_row(symbol, signal)
            self.incremental_signals[symbol] = signal
        self.incremental_index += 1
        if self.filter_edit.text().strip():
            self.apply_signal_filter()
        QCoreApplication.processEvents()
        QTimer.singleShot(1, self._process_next_signal)

    def _append_signal_row(self, symbol, signal):
        row = self.signal_table.rowCount()
        self.signal_table.insertRow(row)
        # Parite
        self.signal_table.setItem(row, 0, QTableWidgetItem(symbol))
        # Fiyat
        self.signal_table.setItem(row, 1, QTableWidgetItem(f"{signal['close_price']:.2f}"))
        # % Değişim
        pct = signal.get('percent_change', 0.0)
        pct_item = QTableWidgetItem(f"{pct:.2f}")
        if pct >= 2:
            pct_item.setBackground(QColor(144, 238, 144))
        elif pct <= -2:
            pct_item.setBackground(QColor(255, 182, 193))
        else:
            pct_item.setBackground(QColor(255, 255, 224))
        self.signal_table.setItem(row, 2, pct_item)
        # Sinyal (raw vs final histerezis tooltip)
        signal_item = QTableWidgetItem(signal['signal'])
        if signal['signal'] == "AL":
            signal_item.setBackground(QColor(144, 238, 144))
        elif signal['signal'] == "SAT":
            signal_item.setBackground(QColor(255, 182, 193))
        else:
            signal_item.setBackground(QColor(255, 255, 224))
        raw_sig = signal.get('signal_raw')
        if raw_sig and raw_sig != signal['signal']:
            signal_item.setToolTip(f"Raw: {raw_sig} (histerezis)")
        self.signal_table.setItem(row, 3, signal_item)
        # Puan + katkı tooltips
        score_val = signal['total_score']
        score_item = QTableWidgetItem(f"{score_val:.1f}")
        buy_thr = getattr(Settings, 'BUY_SIGNAL_THRESHOLD', 80)
        sell_thr = getattr(Settings, 'SELL_SIGNAL_THRESHOLD', 40)
        buy_exit = getattr(Settings, 'BUY_EXIT_THRESHOLD', buy_thr - 1)
        sell_exit = getattr(Settings, 'SELL_EXIT_THRESHOLD', sell_thr + 1)
        # Dynamic coloring
        if score_val >= buy_thr:
            score_item.setBackground(QColor(144, 238, 144))
        elif score_val <= sell_thr:
            score_item.setBackground(QColor(255, 182, 193))
        else:
            # Near exit zones subtle shading
            if score_val >= buy_exit:
                score_item.setBackground(QColor(200, 255, 200))
            elif score_val <= sell_exit:
                score_item.setBackground(QColor(255, 210, 210))
            else:
                score_item.setBackground(QColor(255, 255, 224))
        contrib = signal.get('contributions') or {}
        if contrib:
            lines = [f"{k}: {v:.1f}" for k, v in sorted(contrib.items(), key=lambda x: x[1], reverse=True)]
            score_item.setToolTip(
                f"Aktif: AL≥{buy_thr} / SAT≤{sell_thr} | Exit AL<{buy_exit} SAT>{sell_exit}\nKatkılar:\n" + "\n".join(lines)
            )
        self.signal_table.setItem(row, 4, score_item)
        # Hacim
        self.signal_table.setItem(row, 5, QTableWidgetItem(f"{signal['volume_24h']:.0f}"))
        # Risk
        risk_score = 100 - signal['total_score']
        risk_item = QTableWidgetItem(f"{risk_score:.1f}")
        if risk_score >= 70:
            risk_item.setBackground(QColor(255, 182, 193))
        elif risk_score <= 30:
            risk_item.setBackground(QColor(144, 238, 144))
        else:
            risk_item.setBackground(QColor(255, 255, 224))
        self.signal_table.setItem(row, 6, risk_item)
        # Zaman
        from datetime import datetime
        ts_display = ''
        ts_obj = signal.get('timestamp')
        if isinstance(ts_obj, str):
            try:
                ts_obj_dt = datetime.fromisoformat(ts_obj.replace('Z',''))
            except Exception:
                ts_obj_dt = None
        else:
            ts_obj_dt = ts_obj
        if ts_obj_dt and hasattr(ts_obj_dt, 'strftime'):
            ts_display = ts_obj_dt.strftime('%H:%M')
        else:
            ts_iso = signal.get('timestamp_iso')
            if isinstance(ts_iso, str):
                try:
                    ts_obj_dt = datetime.fromisoformat(ts_iso.replace('Z',''))
                    ts_display = ts_obj_dt.strftime('%H:%M')
                except Exception:
                    ts_display = ts_iso
        self.signal_table.setItem(row, 7, QTableWidgetItem(ts_display))
        # Canlı pencere varsa güncelle sinyal yayını
        try:
            # Emit current incremental snapshot (kopya değil referans; SignalWindow kendi saklar)
            self.signals_updated.emit(self.incremental_signals)
        except Exception:
            pass

    def _finalize_incremental_signals(self):
        """Incremental sinyal işlemesi tamamlandığında tabloyu sıralayıp persist eder."""
        try:
            rows = []
            for r in range(self.signal_table.rowCount()):
                signal_txt = self.signal_table.item(r, 3).text()
                score_txt = self.signal_table.item(r, 4).text()
                try:
                    score_val = float(score_txt)
                except Exception:
                    score_val = 0.0
                priority = 0 if signal_txt == 'AL' else (1 if signal_txt == 'SAT' else 2)
                cells = []
                for c in range(self.signal_table.columnCount()):
                    orig = self.signal_table.item(r, c)
                    clone = QTableWidgetItem(orig.text())
                    clone.setBackground(orig.background())
                    cells.append(clone)
                rows.append((priority, -score_val, cells))
            rows.sort()
            self.signal_table.setRowCount(0)
            for _, _, cells in rows:
                rr = self.signal_table.rowCount()
                self.signal_table.insertRow(rr)
                for ci, cell in enumerate(cells):
                    self.signal_table.setItem(rr, ci, cell)
            # Kaydet & güncelleme zamanı
            from datetime import datetime as _dt
            self.signal_generator.save_signals(self.incremental_signals)
            self.latest_signals = dict(self.incremental_signals)
            self.last_update_label.setText(f"Son: {_dt.now().strftime('%H:%M:%S')}")
            self.refresh_btn.setEnabled(True)
            if self.filter_edit.text().strip():
                self.apply_signal_filter()
            # Final snapshot yayınla
            try:
                self.signals_updated.emit(self.latest_signals)
            except Exception:
                pass
            # WS sembol listesini gözden geçir
            self._maybe_refresh_ws_symbols()
        except Exception:
            pass

    def apply_signal_filter(self):
        """Metin filtre kutusuna göre satırları gizle/göster"""
        text = self.filter_edit.text().strip()
        # Basit kurallar:
        #  - '>70' veya '<40' -> puan filtresi
        #  - normal string -> parite ya da sinyal substring araması
        cmp_op = None
        cmp_val = None
        if text.startswith(('>', '<')):
            try:
                cmp_op = text[0]
                cmp_val = float(text[1:])
            except ValueError:
                cmp_op = None
        for row in range(self.signal_table.rowCount()):
            show = True
            symbol_item = self.signal_table.item(row, 0)
            signal_item = self.signal_table.item(row, 3)
            score_item = self.signal_table.item(row, 4)
            if cmp_op and cmp_val is not None:
                try:
                    score_val = float(score_item.text())
                    if cmp_op == '>' and not (score_val > cmp_val):
                        show = False
                    if cmp_op == '<' and not (score_val < cmp_val):
                        show = False
                except Exception:
                    pass
            elif text:
                lower = text.lower()
                if lower not in symbol_item.text().lower() and lower not in signal_item.text().lower():
                    show = False
            self.signal_table.setRowHidden(row, not show)

    def create_positions_tab(self):
        """Acik pozisyonlar sekmesi."""
        tab = QWidget()
        lay = QVBoxLayout(tab)

        # Search / filter bar
        search_bar = QHBoxLayout()
        self.pos_search_edit = QLineEdit()
        self.pos_search_edit.setPlaceholderText("Ara: sembol / yon ...")
        self.pos_search_edit.textChanged.connect(self._filter_positions_table)
        search_bar.addWidget(QLabel("Hizli Arama:"))
        search_bar.addWidget(self.pos_search_edit)
        self.pos_latency_label = QLabel("Latency: - ms")
        self.pos_latency_label.setStyleSheet("color:#888; font-size:11px")
        self.pos_slip_label = QLabel("Slip: - bps")
        self.pos_slip_label.setStyleSheet("color:#888; font-size:11px")
        search_bar.addWidget(self.pos_latency_label)
        search_bar.addWidget(self.pos_slip_label)
        search_bar.addStretch()
        lay.addLayout(search_bar)

        # Table
        self.position_table = QTableWidget()
        self.position_table.setColumnCount(11)
        self.position_table.setHorizontalHeaderLabels([
            "Parite", "Yon", "Giris", "Mevcut", "PnL%", "Miktar", "SL", "TP", "Zaman", "Partial%", "Trail"
        ])
        self.position_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.position_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.position_table.setSelectionMode(QTableWidget.SingleSelection)
        lay.addWidget(self.position_table)

        # Buttons
        btn_row = QHBoxLayout()
        self.close_position_btn = QPushButton("Secili Pozisyonu Kapat")
        self.close_position_btn.clicked.connect(self.close_selected_position)
        btn_row.addWidget(self.close_position_btn)
        self.recompute_pnl_btn = QPushButton("Weighted PnL Hesapla")
        self.recompute_pnl_btn.clicked.connect(self.recompute_weighted_pnl)
        btn_row.addWidget(self.recompute_pnl_btn)
        self.refresh_pos_btn = QPushButton("Yenile")
        self.refresh_pos_btn.clicked.connect(self.update_positions)
        btn_row.addWidget(self.refresh_pos_btn)
        self.ws_toggle_btn = QPushButton("Canli Fiyat Akisi: Kapali")
        self.ws_toggle_btn.setCheckable(True)
        self.ws_toggle_btn.clicked.connect(self.toggle_price_stream)
        btn_row.addWidget(self.ws_toggle_btn)
        self.ws_status_label = QLabel("WS: Kapali")
        self.ws_status_label.setStyleSheet("color: gray; font-size:11px")
        btn_row.addWidget(self.ws_status_label)
        btn_row.addStretch()
        lay.addLayout(btn_row)

        try:
            show_unreal = getattr(Settings, 'SHOW_UNREALIZED_TOTAL', True)
        except Exception:
            show_unreal = True
        if show_unreal:
            self.total_unreal_label = QLabel("Toplam Unrealized: -")
            self.total_unreal_label.setStyleSheet("color: #888; font-size:11px")
            lay.addWidget(self.total_unreal_label)
        else:
            self.total_unreal_label = None
        self.tabs.addTab(tab, "Pozisyonlar")

    def _filter_positions_table(self):  # basit satır filtreleme
        try:
            txt = self.pos_search_edit.text().strip().lower()
            for r in range(self.position_table.rowCount()):
                symbol_item = self.position_table.item(r, 0)
                side_item = self.position_table.item(r, 1)
                if not symbol_item or not side_item:
                    continue
                show = (not txt) or (txt in symbol_item.text().lower()) or (txt in side_item.text().lower())
                self.position_table.setRowHidden(r, not show)
        except Exception:
            pass

    def create_closed_trades_tab(self):
        """Geçmiş (kapalı) işlemler sekmesi."""
        tab = QWidget()
        lay = QVBoxLayout(tab)

        # Tablo
        self.closed_table = QTableWidget()
        self.closed_table.setColumnCount(9)
        self.closed_table.setHorizontalHeaderLabels([
            "ID", "Parite", "Yön", "Giriş", "Çıkış", "Boyut", "PnL%", "Açılış", "Kapanış"
        ])
        self.closed_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        lay.addWidget(self.closed_table)

        # Buton satırı
        btn_row = QHBoxLayout()
        self.refresh_closed_btn = QPushButton("Kapatılanları Yenile")
        self.refresh_closed_btn.clicked.connect(self.refresh_closed_trades)
        btn_row.addWidget(self.refresh_closed_btn)

        self.export_csv_btn = QPushButton("CSV Aktar")
        self.export_csv_btn.clicked.connect(lambda: self.export_closed_trades('csv'))
        btn_row.addWidget(self.export_csv_btn)

        self.export_json_btn = QPushButton("JSON Aktar")
        self.export_json_btn.clicked.connect(lambda: self.export_closed_trades('json'))
        btn_row.addWidget(self.export_json_btn)
        btn_row.addStretch()
        lay.addLayout(btn_row)

        # İstatistik etiketi
        self.closed_stats_label = QLabel("-")
        self.closed_stats_label.setStyleSheet("color: gray; font-size:11px")
        lay.addWidget(self.closed_stats_label)

        # Sekmeyi ekle
        self.closed_tab_index = self.tabs.addTab(tab, "Geçmiş")

        # İlk doldurma (hafif gecikme)
        QTimer.singleShot(500, self.refresh_closed_trades)

    def refresh_closed_trades(self):
        try:
            rows = self.trader.trade_store.closed_trades(limit=300)
            self.closed_table.setRowCount(len(rows))
            for r_i, rec in enumerate(rows):
                vals = [rec.get('id'), rec.get('symbol'), rec.get('side'), rec.get('entry_price'), rec.get('exit_price'), rec.get('size'), rec.get('pnl_pct'), rec.get('opened_at'), rec.get('closed_at')]
                for c_i, v in enumerate(vals):
                    item = QTableWidgetItem(str(round(v,4)) if isinstance(v,(int,float)) else (v or ''))
                    if c_i==6 and isinstance(v,(int,float)):
                        if v > 0: item.setForeground(QColor('green'))
                        elif v < 0: item.setForeground(QColor('red'))
                    self.closed_table.setItem(r_i, c_i, item)
            st = self.trader.trade_store.stats()
            if st:
                self.closed_stats_label.setText(f"Toplam: {st['total_closed']} | Win%: {st['winrate_pct']} | AvgPnL: {st['avg_pnl_pct']}% | W:{st['wins']} L:{st['losses']}")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Kapanmış trade listesi alınamadı: {e}")

    def export_closed_trades(self, fmt: str):
        try:
            import datetime, os
            from pathlib import Path
            ts = datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            out_dir = Path('data/exports'); out_dir.mkdir(parents=True, exist_ok=True)
            file_path = out_dir / f"closed_trades_{ts}.{fmt}"
            self.trader.trade_store.export_closed(str(file_path), fmt=fmt, limit=1000)
            QMessageBox.information(self, "Başarılı", f"Aktarıldı: {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Aktarım hatası: {e}")

    def on_calibration_finished(self, summary: dict):
        if not summary:
            self.calib_status_label.setText("Kalibrasyon başarısız")
            return
        g = summary.get('global', {})
        buy = g.get('suggested_buy_threshold')
        sell = g.get('suggested_sell_threshold')
        mean = g.get('mean')
        std = g.get('std')
        self.calib_status_label.setText("Kalibrasyon tamamlandı")
        buy_exit_s = g.get('suggested_buy_exit_threshold')
        sell_exit_s = g.get('suggested_sell_exit_threshold')
        opt = (g.get('optimization') or {}).get('candidates') or []
        self.calib_result_label.setText(
            f"Önerilen AL ≥ {buy:.2f} (exit<{buy_exit_s:.2f}) | SAT ≤ {sell:.2f} (exit>{sell_exit_s:.2f}) | mean={mean:.2f} std={std:.2f}"
            if buy_exit_s and sell_exit_s else
            f"Önerilen AL ≥ {buy:.2f} | SAT ≤ {sell:.2f} | mean={mean:.2f} std={std:.2f}"
        )
        if opt:
            lines = []
            for c in opt:
                tag = "*" if c.get('baseline') else ""
                lines.append(
                    f"{tag}B:{c.get('buy')} S:{c.get('sell')} Win:{c.get('winrate','-')}/{c.get('winrate_after_costs','-')} Exp:{c.get('expectancy_pct','-')}/{c.get('expectancy_after_costs_pct','-')} T:{c.get('total_trades','-')}"
                )
            self.calib_result_label.setToolTip("Optimizasyon Adayları:\n" + "\n".join(lines))
            self._optimization_candidates = opt
            self.apply_best_candidate_btn.setEnabled(True)
            # Populate table
            self._populate_optimization_candidates(opt)
        # Hide progress
        if hasattr(self, 'calib_progress'):
            self.calib_progress.setVisible(False)
        # Ek istatistikler: ADX & ATR Risk dağılım percentilleri
        adx_p = g.get('adx_percentiles') or {}
        atr_p = g.get('atr_risk_percentiles') or {}
        def _fmt(pdict):
            if not pdict:
                return "-"
            keys = sorted(pdict.keys(), key=lambda x: float(x))
            return ", ".join(f"p{int(k)}:{pdict[k]:.1f}" for k in keys)
        trade_stats = g.get('trade_stats') or {}
        winrate = trade_stats.get('winrate')
        expectancy = trade_stats.get('avg_expectancy_pct')
        winrate_after = trade_stats.get('winrate_after_costs')
        expectancy_after = trade_stats.get('avg_expectancy_after_costs_pct')
        trades = trade_stats.get('total_trades')
        # Maliyet ayarlarını göster
        comm = trade_stats.get('commission_pct_per_side')
        slip = trade_stats.get('slippage_pct_per_side')
        next_bar = trade_stats.get('next_bar_fill')
        base_line = f"ADX: {_fmt(adx_p)} | ATR Risk%: {_fmt(atr_p)}"
        if winrate is not None:
            base_line += f" | Winrate: {winrate:.2f}% | Exp: {expectancy:.2f}%"
            if winrate_after is not None:
                base_line += f" | Win(c): {winrate_after:.2f}% | Exp(c): {expectancy_after:.2f}%"
            base_line += f" | Trades: {trades}"
        if comm is not None and slip is not None:
            base_line += f" | Cost(side)%: {comm:.3f}/{slip:.3f} | NextBarFill: {'Evet' if next_bar else 'Hayır'}"
        self.calib_stats_label.setText(base_line)
        self._suggested_buy = buy
        self._suggested_sell = sell
        if buy_exit_s and sell_exit_s:
            self._suggested_buy_exit = buy_exit_s
            self._suggested_sell_exit = sell_exit_s
        self.apply_thresholds_btn.setEnabled(True)
        if self.auto_apply_checkbox.isChecked():
            self.apply_suggested_thresholds()
        # Trade istatistik pencere butonunu aktif et
        if 'symbols' in summary:
            self._last_calibration_summary = summary
            self.view_calib_stats_btn.setEnabled(True)
        if hasattr(self, 'optim_table') and self.optim_table.rowCount() > 0:
            self.optim_table.setVisible(True)

    def apply_suggested_thresholds(self):
        if not hasattr(self, '_suggested_buy'):
            return
        # Settings üzerinde runtime override
        try:
            Settings.BUY_SIGNAL_THRESHOLD = float(self._suggested_buy)
            Settings.SELL_SIGNAL_THRESHOLD = float(self._suggested_sell)
            # Exit önerileri varsa uygula
            if hasattr(self, '_suggested_buy_exit') and hasattr(self, '_suggested_sell_exit'):
                Settings.BUY_EXIT_THRESHOLD = float(self._suggested_buy_exit)
                Settings.SELL_EXIT_THRESHOLD = float(self._suggested_sell_exit)
                if hasattr(self, 'buy_exit_spin'):
                    self.buy_exit_spin.blockSignals(True); self.buy_exit_spin.setValue(Settings.BUY_EXIT_THRESHOLD); self.buy_exit_spin.blockSignals(False)
                if hasattr(self, 'sell_exit_spin'):
                    self.sell_exit_spin.blockSignals(True); self.sell_exit_spin.setValue(Settings.SELL_EXIT_THRESHOLD); self.sell_exit_spin.blockSignals(False)
            # Persist et
            try:
                from config.runtime_thresholds import persist_runtime_thresholds
                persist_runtime_thresholds(Settings.BUY_SIGNAL_THRESHOLD, Settings.SELL_SIGNAL_THRESHOLD,
                                           getattr(Settings, 'BUY_EXIT_THRESHOLD', None), getattr(Settings, 'SELL_EXIT_THRESHOLD', None))
            except Exception as pe:
                QMessageBox.warning(self, "Uyarı", f"Eşik persist edilemedi: {pe}")
            QMessageBox.information(self, "Başarılı", f"Eşikler güncellendi: AL≥{self._suggested_buy:.2f} SAT≤{self._suggested_sell:.2f}")
            if hasattr(self, 'current_thresholds_label'):
                self.current_thresholds_label.setText(self._format_current_thresholds())
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Eşik güncelleme hatası: {e}")

    def apply_best_candidate_thresholds(self):
        cand = getattr(self, '_optimization_candidates', None)
        if not cand:
            return
        # İlk eleman baseline olabilir, en iyi aday baseline değilse onu kullan
        best = None
        for c in cand:
            if not c.get('baseline'):
                best = c
                break
        if best is None:
            QMessageBox.information(self, "Bilgi", "Aday listesinde baseline dışı yok")
            return
        try:
            Settings.BUY_SIGNAL_THRESHOLD = float(best['buy'])
            Settings.SELL_SIGNAL_THRESHOLD = float(best['sell'])
            Settings.BUY_EXIT_THRESHOLD = float(best.get('buy_exit', Settings.BUY_SIGNAL_THRESHOLD - 5))
            Settings.SELL_EXIT_THRESHOLD = float(best.get('sell_exit', Settings.SELL_SIGNAL_THRESHOLD + 5))
            from config.runtime_thresholds import persist_runtime_thresholds
            persist_runtime_thresholds(Settings.BUY_SIGNAL_THRESHOLD, Settings.SELL_SIGNAL_THRESHOLD,
                                       Settings.BUY_EXIT_THRESHOLD, Settings.SELL_EXIT_THRESHOLD,
                                       source="optimization-best")
            if hasattr(self, 'buy_exit_spin'):
                self.buy_exit_spin.blockSignals(True); self.buy_exit_spin.setValue(Settings.BUY_EXIT_THRESHOLD); self.buy_exit_spin.blockSignals(False)
            if hasattr(self, 'sell_exit_spin'):
                self.sell_exit_spin.blockSignals(True); self.sell_exit_spin.setValue(Settings.SELL_EXIT_THRESHOLD); self.sell_exit_spin.blockSignals(False)
            if hasattr(self, 'current_thresholds_label'):
                self.current_thresholds_label.setText(self._format_current_thresholds())
            QMessageBox.information(self, "Başarılı", f"En iyi aday uygulandı: AL≥{Settings.BUY_SIGNAL_THRESHOLD} SAT≤{Settings.SELL_SIGNAL_THRESHOLD}")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Aday uygulanamadı: {e}")

    def apply_selected_candidate_thresholds(self):
        if not hasattr(self, 'optim_table') or self.optim_table.rowCount() == 0:
            return
        row = self.optim_table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Bilgi", "Önce bir satır seçin")
            return
        try:
            data = self.optim_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            if not data:
                QMessageBox.warning(self, "Uyarı", "Satır verisi yok")
                return
            Settings.BUY_SIGNAL_THRESHOLD = float(data['buy'])
            Settings.SELL_SIGNAL_THRESHOLD = float(data['sell'])
            Settings.BUY_EXIT_THRESHOLD = float(data.get('buy_exit', Settings.BUY_SIGNAL_THRESHOLD - 5))
            Settings.SELL_EXIT_THRESHOLD = float(data.get('sell_exit', Settings.SELL_SIGNAL_THRESHOLD + 5))
            from config.runtime_thresholds import persist_runtime_thresholds
            persist_runtime_thresholds(Settings.BUY_SIGNAL_THRESHOLD, Settings.SELL_SIGNAL_THRESHOLD,
                                       Settings.BUY_EXIT_THRESHOLD, Settings.SELL_EXIT_THRESHOLD,
                                       source="optimization-select")
            if hasattr(self, 'buy_exit_spin'):
                self.buy_exit_spin.blockSignals(True); self.buy_exit_spin.setValue(Settings.BUY_EXIT_THRESHOLD); self.buy_exit_spin.blockSignals(False)
            if hasattr(self, 'sell_exit_spin'):
                self.sell_exit_spin.blockSignals(True); self.sell_exit_spin.setValue(Settings.SELL_EXIT_THRESHOLD); self.sell_exit_spin.blockSignals(False)
            if hasattr(self, 'current_thresholds_label'):
                self.current_thresholds_label.setText(self._format_current_thresholds())
            QMessageBox.information(self, "Başarılı", "Seçili aday uygulandı")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Seçili aday uygulanamadı: {e}")

    def _populate_optimization_candidates(self, candidates: list[dict]):
        try:
            if not hasattr(self, 'optim_table'):
                return
            self.optim_table.setRowCount(0)
            for c in candidates:
                r = self.optim_table.rowCount(); self.optim_table.insertRow(r)
                tag_item = QTableWidgetItem('*' if c.get('baseline') else '')
                tag_item.setData(Qt.ItemDataRole.UserRole, c)
                if c.get('baseline'):
                    tag_item.setBackground(QColor(230,230,250))
                self.optim_table.setItem(r,0, tag_item)
                self.optim_table.setItem(r,1, QTableWidgetItem(str(c.get('buy'))))
                self.optim_table.setItem(r,2, QTableWidgetItem(str(c.get('sell'))))
                self.optim_table.setItem(r,3, QTableWidgetItem(str(c.get('buy_exit','-'))))
                self.optim_table.setItem(r,4, QTableWidgetItem(str(c.get('sell_exit','-'))))
                self.optim_table.setItem(r,5, QTableWidgetItem(str(c.get('winrate','-'))))
                self.optim_table.setItem(r,6, QTableWidgetItem(str(c.get('winrate_after_costs','-'))))
                self.optim_table.setItem(r,7, QTableWidgetItem(str(c.get('expectancy_pct','-'))))
                self.optim_table.setItem(r,8, QTableWidgetItem(str(c.get('expectancy_after_costs_pct','-'))))
                self.optim_table.setItem(r,9, QTableWidgetItem(str(c.get('total_trades','-'))))
            if self.optim_table.rowCount() > 0:
                self.apply_selected_candidate_btn.setEnabled(True)
        except Exception:
            pass

    def _format_current_thresholds(self):
        be = getattr(Settings, 'BUY_EXIT_THRESHOLD', Settings.BUY_SIGNAL_THRESHOLD - 1)
        se = getattr(Settings, 'SELL_EXIT_THRESHOLD', Settings.SELL_SIGNAL_THRESHOLD + 1)
        return (
            f"Aktif Eşikler → AL≥{Settings.BUY_SIGNAL_THRESHOLD:.2f} (exit<{be:.2f}) | "
            f"SAT≤{Settings.SELL_SIGNAL_THRESHOLD:.2f} (exit>{se:.2f})"
        )

    # --------- Kalibrasyon sembol trade istatistik penceresi ---------
    def _show_calibration_symbol_stats(self):
        if not hasattr(self, '_last_calibration_summary'):
            QMessageBox.information(self, "Bilgi", "Henüz kalibrasyon sonuçları yok")
            return
        data = self._last_calibration_summary.get('symbols') or {}
        if not data:
            QMessageBox.information(self, "Bilgi", "Sembol istatistiği yok")
            return
        dlg = _SymbolStatsWindow(data, self)
        dlg.exec_()

    # --------- Otomatik Kalibrasyon Yardımcıları ---------
    def _toggle_auto_calib(self, state):
        enabled = state == Qt.CheckState.Checked
        if enabled:
            self._update_auto_calib_interval()
            self.calib_status_label.setText("Oto kalibrasyon aktif")
        else:
            self.auto_calib_timer.stop()
            self.calib_status_label.setText("Oto kalibrasyon kapalı")

    def _update_auto_calib_interval(self):
        if not self.auto_calib_checkbox.isChecked():
            return
        hours = self.auto_calib_hours.value()
        ms = hours * 3600 * 1000
        self.auto_calib_timer.start(ms)
        # İlk tick'i hemen tetikleme (istersek):
        # self.start_calibration()

    def _auto_calibration_tick(self):
        if hasattr(self, 'calib_thread') and self.calib_thread and self.calib_thread.isRunning():
            return  # zaten çalışıyor
        self.start_calibration()

    def start_bot(self):
        """Botu başlat"""
        hours = self.hours_spin.value()
        self.status_label.setText(f"Durum: Bot çalışıyor ({hours} saat)")
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        try:
            started = self.trader.start(hours)
            if not started:
                self.status_label.setText("Durum: Zaten çalışıyor")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Başlatma hatası: {e}")
        self._update_risk_status()

    def stop_bot(self):
        """Botu durdur"""
        try:
            stopped = self.trader.stop()
            if stopped:
                self.status_label.setText("Durum: Bot durduruldu")
            else:
                self.status_label.setText("Durum: Çalışmıyor")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Durdurma hatası: {e}")
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self._update_risk_status()

    def _update_risk_status(self):
        try:
            rs = self.trader.risk_status()
            if rs:
                daily = rs.get('daily_realized_pct', 0)
                consec = rs.get('consecutive_losses', 0)
                limit = rs.get('daily_limit_pct')
                c_limit = rs.get('consec_limit')
                txt = f"PnL: {daily:.2f}% (limit -{limit}%) | Ardışık: {consec}/{c_limit}"
                color = "green" if daily >= 0 else "red"
                self.risk_status_label.setText(txt)
                self.risk_status_label.setStyleSheet(f"color:{color}; font-size:11px")
        except Exception:
            pass

    def update_data(self):
        """Verileri güncelle"""
        try:
            self.data_fetcher.update_top_pairs()
            self.data_fetcher.fetch_all_pairs_data()
            QMessageBox.information(self, "Başarılı", "Veriler başarıyla güncellendi")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Veri güncelleme hatası: {str(e)}")

    def backup_data(self):
        """Verileri yedekle"""
        try:
            self.data_fetcher.backup_data()
            QMessageBox.information(self, "Başarılı", "Veriler başarıyla yedeklendi")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Yedekleme hatası: {str(e)}")

    def save_settings(self):
        """Ayarları kaydet"""
        try:
            # Risk yönetimi ayarlarını güncelle
            from config.settings import RuntimeConfig
            # Piyasa modu uygula
            RuntimeConfig.set_market_mode(self.mode_combo.currentText())
            # Bağımlı bileşenleri yeniden oluştur
            self.trader = Trader()
            self.signal_generator = SignalGenerator()
            self.data_fetcher = DataFetcher()

            self.trader.risk_manager.update_settings(
                risk_percent=self.risk_percent_spin.value(),
                leverage=self.leverage_spin.value(),
                max_positions=self.max_pos_spin.value(),
                min_volume=self.min_vol_spin.value()
            )

            QMessageBox.information(self, "Başarılı", "Ayarlar kaydedildi")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Ayar kaydetme hatası: {str(e)}")

    def check_health(self):
        """Sağlık durumunu kontrol et"""
        try:
            is_healthy, message = self.health_checker.run_full_check()

            if is_healthy:
                self.health_label.setText(f"Sağlık durumu: İyi")
                self.health_label.setStyleSheet("color: green")
            else:
                self.health_label.setText(f"Sağlık durumu: Sorunlu - {message}")
                self.health_label.setStyleSheet("color: red")

            # Bağlantı durumunu güncelle
            if self.trader.check_connection():
                self.connection_label.setText("Bağlantı durumu: Bağlı")
                self.connection_label.setStyleSheet("color: green")
            else:
                self.connection_label.setText("Bağlantı durumu: Kopuk")
                self.connection_label.setStyleSheet("color: red")

        except Exception as e:
            self.health_label.setText(f"Sağlık kontrolü hatası: {str(e)}")
            self.health_label.setStyleSheet("color: red")

    def test_api(self):
        """API testi yap"""
        try:
            is_healthy, message = self.health_checker.run_full_check()

            if is_healthy:
                QMessageBox.information(self, "API Testi", "API bağlantısı sağlıklı")
            else:
                QMessageBox.warning(self, "API Testi", f"API sorunu: {message}")

        except Exception as e:
            QMessageBox.critical(self, "Hata", f"API testi hatası: {str(e)}")

    def close_selected_position(self):
        """Seçili pozisyonu kapat"""
        selected_items = self.position_table.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Uyarı", "Lütfen bir pozisyon seçin")
            return

        row = selected_items[0].row()
        symbol = self.position_table.item(row, 0).text()

        reply = QMessageBox.question(
            self, "Pozisyon Kapatma",
            f"{symbol} pozisyonunu kapatmak istediğinize emin misiniz?",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            if self.trader.close_position(symbol):
                QMessageBox.information(self, "Başarılı", f"{symbol} pozisyonu kapatıldı")
                self.update_positions()
            else:
                QMessageBox.critical(self, "Hata", f"{symbol} pozisyonu kapatılamadı")

    def recompute_weighted_pnl(self):
        """Tüm geçmiş işlemler için weighted PnL yeniden hesapla"""
        try:
            self.trader.recompute_weighted_pnl()
            QMessageBox.information(self, "Tamam", "Weighted PnL yeniden hesaplandı")
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Yeniden hesaplama hatası: {e}")

    # ---- Canlı fiyat akışı & kapanış ----
    def toggle_price_stream(self):
        """Pozisyonlar sekmesi canlı fiyat akışı aç/kapat."""
        try:
            if not hasattr(self, 'ws_toggle_btn'):
                return
            if self.ws_toggle_btn.isChecked():
                from src.api.price_stream import PriceStreamManager
                symbols = self._compute_ws_symbols()
                self.ws_stream = PriceStreamManager(symbols, self._on_price_update, self._on_ws_status)
                self.ws_stream.start()
                self._ws_symbols = symbols
                self.ws_toggle_btn.setText("Canlı Fiyat Akışı: Açık")
                if hasattr(self, 'ws_status_label'):
                    self.ws_status_label.setText(f"Aktif ({len(symbols)} sembol)")
                    self.ws_status_label.setStyleSheet("color: green; font-size:11px")
            else:
                ws_stream = getattr(self, 'ws_stream', None)
                if ws_stream and hasattr(ws_stream, 'stop'):
                    try:
                        ws_stream.stop()
                    except Exception:
                        pass
                self.ws_stream = None
                self._ws_symbols = []
                self.ws_toggle_btn.setText("Canlı Fiyat Akışı: Kapalı")
                if hasattr(self, 'ws_status_label'):
                    self.ws_status_label.setText("Kapalı")
                    self.ws_status_label.setStyleSheet("color: gray; font-size:11px")
        except Exception:
            pass

    def _compute_ws_symbols(self) -> list:
        """Dinamik websocket sembol listesi oluştur.
        Öncelik: Açık pozisyonlar -> AL sinyalleri -> Incremental list -> Top pairs fallback."""
        symbols: list[str] = []
        try:
            # Açık pozisyonlar tablosu
            if hasattr(self, 'position_table'):
                for row in range(self.position_table.rowCount()):
                    it = self.position_table.item(row, 0)
                    if it:
                        s = it.text().strip()
                        if s:
                            symbols.append(s)
        except Exception:
            pass
        try:
            al_syms = [s for s, v in (self.latest_signals or {}).items() if isinstance(v, dict) and v.get('signal') == 'AL']
            for s in al_syms:
                if s not in symbols:
                    symbols.append(s)
        except Exception:
            pass
        try:
            if len(symbols) < 10 and getattr(self, 'incremental_signals', None):
                for s in list(self.incremental_signals.keys()):
                    if s not in symbols:
                        symbols.append(s)
                    from config.settings import Settings
                    symbol_limit = getattr(Settings, 'WS_SYMBOL_LIMIT', 40)
                    if len(symbols) >= symbol_limit:
                        break
        except Exception:
            pass
        if not symbols:
            try:
                symbols = self.data_fetcher.load_top_pairs()[:25]
            except Exception:
                symbols = []
        # Kısıtla & sırayı koru (uniq)
        uniq = []
        seen = set()
        from config.settings import Settings
        symbol_limit = getattr(Settings, 'WS_SYMBOL_LIMIT', 40)
        for s in symbols:
            if s not in seen:
                seen.add(s); uniq.append(s)
            if len(uniq) >= symbol_limit:
                break
        return uniq

    def _maybe_refresh_ws_symbols(self):
        """Debounce + sembol farkına göre websocket'i yeniden başlat."""
        try:
            if not getattr(self, 'ws_stream', None):
                return
            import time
            now = time.time(); last = getattr(self, '_last_ws_refresh_check', 0.0)
            debounce_sec = getattr(Settings, 'WS_REFRESH_DEBOUNCE_SEC', 2.0)
            current = list(getattr(self, '_ws_symbols', []) or [])
            new_syms = self._compute_ws_symbols()
            if not should_restart_ws(last, now, debounce_sec, current, new_syms):
                return
            self._last_ws_refresh_check = now
            if hasattr(self, 'ws_stream') and self.ws_stream:
                self.ws_stream.stop()
            base_b = getattr(Settings, 'WS_BASE_BACKOFF_SEC', 1.0)
            max_b = getattr(Settings, 'WS_MAX_BACKOFF_SEC', 30.0)
            timeout_s = getattr(Settings, 'WS_TIMEOUT_SEC', 20.0)
            max_r = getattr(Settings, 'WS_MAX_RETRIES', 10)
            from src.api.price_stream import PriceStreamManager
            self.ws_stream = PriceStreamManager(new_syms, self._on_price_update, self._on_ws_status,
                                                base_backoff=base_b, max_backoff=max_b,
                                                timeout_sec=timeout_s, max_retries=max_r)
            self.ws_stream.start()
            self._ws_symbols = new_syms
            if hasattr(self, 'ws_status_label'):
                self.ws_status_label.setText(f"Aktif ({len(new_syms)} sembol)")
        except Exception:
            pass

    def _on_price_update(self, symbol: str, price: float):
        """WS fiyat güncellemesi geldiğinde trader'a ilet."""
        try:
            if hasattr(self, 'trader') and hasattr(self.trader, 'process_price_update'):
                self.trader.process_price_update(symbol, price)
            # GUI fiyat & PnL güncelle
            self.last_prices[symbol] = price
            if symbol in self.position_row_map:
                self._update_position_price_row(symbol)
        except Exception:
            pass

    def _on_ws_status(self, status: str, info: str | None):
        try:
            if not hasattr(self, 'ws_status_label'):
                return
            color_map = {
                'connecting': 'orange',
                'open': 'green',
                'reconnecting': 'orange',
                'error': 'red',
                'closed': 'gray',
                'stopped': 'gray'
            }
            color = color_map.get(status, 'gray')
            base = status.capitalize()
            extra = f" - {info}" if info and status == 'error' else ''
            # Sembol sayısı ekle (varsa)
            count = len(getattr(self, '_ws_symbols', []) or [])
            self.ws_status_label.setText(f"{base} ({count}){extra}")
            self.ws_status_label.setStyleSheet(f"color: {color}; font-size:11px")
        except Exception:
            pass

    def _ws_health_check(self):
        """WS akışının mesaj aktivitesini izleyip timeout durumunda restart."""
        try:
            ws_stream = getattr(self, 'ws_stream', None)
            if ws_stream is None:
                return
            # PriceStreamManager health API
            try:
                if hasattr(ws_stream, 'is_timed_out') and ws_stream.is_timed_out():
                    # Label güncelle
                    if hasattr(self, 'ws_status_label'):
                        self.ws_status_label.setText("Timeout - restart")
                        self.ws_status_label.setStyleSheet("color: orange; font-size:11px")
                    # restart aynı sembollerle
                    syms = getattr(self, '_ws_symbols', [])
                    if hasattr(ws_stream, 'restart'):
                        ws_stream.restart(syms)
                    return
            except Exception:
                pass
        except Exception:
            pass

    def _update_position_price_row(self, symbol: str):
        try:
            r = self.position_row_map.get(symbol)
            if r is None:
                return
            entry_item = self.position_table.item(r, 2)  # Giriş
            side_item = self.position_table.item(r, 1)
            if not entry_item or not side_item:
                return
            entry_txt = entry_item.text()
            side_txt = side_item.text().upper()
            last_price = self.last_prices.get(symbol)
            if last_price is None:
                return
            self.position_table.setItem(r, 3, QTableWidgetItem(f"{last_price}"))
            try:
                entry_f = float(entry_txt)
                last_f = float(last_price)
                if side_txt in ('LONG','BUY'):
                    pnl = (last_f-entry_f)/entry_f*100.0
                elif side_txt in ('SHORT','SELL'):
                    pnl = (entry_f-last_f)/entry_f*100.0
                else:
                    pnl = 0.0
                pnl_item = QTableWidgetItem(f"{pnl:.2f}")
                if pnl > 0: pnl_item.setForeground(QColor('green'))
                elif pnl < 0: pnl_item.setForeground(QColor('red'))
                self.position_table.setItem(r, 4, pnl_item)
            except Exception:
                pass
        except Exception:
            pass

    def closeEvent(self, event):  # type: ignore[override]
        """Pencere kapanırken kaynakları temizle."""
        try:
            ws_stream = getattr(self, 'ws_stream', None)
            if ws_stream and hasattr(ws_stream, 'stop'):
                try:
                    ws_stream.stop()
                except Exception:
                    pass
            if hasattr(self, 'trader'):
                try:
                    self.trader.stop()
                except Exception:
                    pass
        finally:
            super().closeEvent(event)

class _CalibrationThread(QThread):
    finished_with_result = pyqtSignal(dict)
    def __init__(self, limit: int):
        super().__init__()
        self.limit = limit
    def run(self):
        try:
            res = run_calibration(pairs_limit=self.limit, save=True)
        except Exception:
            res = None
        self.finished_with_result.emit(res or {})


class _SymbolStatsWindow(QDialog):
    def __init__(self, data: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Kalibrasyon Trade İstatistikleri")
        from PyQt5.QtWidgets import QVBoxLayout, QTableWidget, QHeaderView, QTableWidgetItem, QPushButton
        lay = QVBoxLayout(self)
        table = QTableWidget()
        headers = [
            "Sembol","Trades","Win%","Win%(c)","Exp%","Exp%(c)",
            "AvgGain%","AvgLoss%","MaxConsecL","Mean","Std"
        ]
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        rows = []
        for sym, stats in (data or {}).items():
            try:
                tr = stats.get('trade_stats') or {}
                total_tr = tr.get('total_trades', 0)
                if total_tr == 0:
                    continue
                rows.append((
                    tr.get('expectancy_after_costs_pct', tr.get('expectancy_pct', 0)) or 0,
                    sym, stats, tr
                ))
            except Exception:
                continue
        rows.sort(reverse=True)
        table.setRowCount(len(rows))
        for r_i, (_, sym, stats, tr) in enumerate(rows):
            def _fmt(v):
                return '-' if v in (None, '') else str(v)
            vals = [
                sym,
                tr.get('total_trades','-'),
                tr.get('winrate','-'),
                tr.get('winrate_after_costs','-'),
                tr.get('expectancy_pct','-'),
                tr.get('expectancy_after_costs_pct','-'),
                tr.get('avg_gain_pct','-'),
                tr.get('avg_loss_pct','-'),
                tr.get('max_consec_losses','-'),
                f"{stats.get('global',{}).get('mean','-')}",
                f"{stats.get('global',{}).get('std','-')}"
            ]
            for c_i, v in enumerate(vals):
                table.setItem(r_i, c_i, QTableWidgetItem(_fmt(v)))
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        lay.addWidget(table)
        close_btn = QPushButton("Kapat")
        close_btn.clicked.connect(self.accept)
        lay.addWidget(close_btn)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())
