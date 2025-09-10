import contextlib
from datetime import datetime

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.utils.logger import get_logger

# Signal score thresholds
SIGNAL_SCORE_HIGH_THRESHOLD = 80
SIGNAL_SCORE_LOW_THRESHOLD = 40

class SignalWindow(QWidget):
    def __init__(self, signal_generator, parent=None, signals=None):
        # Ana pencereyi parent veriyoruz; bagimsiz ust pencere gibi gorunmesi icin Window flag kullanilir.
        super().__init__(parent)
        self.signal_generator = signal_generator
        # Onceden hesaplanmis sinyaller (ana pencereden hizli acilis icin)
        self.preloaded_signals = signals or {}
        self.signals = {}
        self._refresh_scheduled = False
        self.setWindowTitle("Sinyal Analizi")
        # Ekrana gore dinamik boyutlandirma (ana pencereden bagimsiz)
        try:
            screen_geo = QApplication.primaryScreen().availableGeometry()
            w = int(screen_geo.width() * 0.85)
            h = int(screen_geo.height() * 0.85)
            self.resize(w, h)
            geo = self.frameGeometry()
            geo.moveCenter(screen_geo.center())
            self.move(geo.topLeft())
        except Exception:
            # Fallback
            self.setGeometry(150, 120, 1300, 850)
        self.setMinimumSize(1100, 750)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        # Ana programin bu pencere kapaninca tamamen kapanmasini engelle (ihtiyaten)
        with contextlib.suppress(Exception):
            self.setAttribute(Qt.WA_QuitOnClose, False)
        self.setWindowFlag(Qt.Window, True)
        # Timer (cache geldiyse daha seyrek başlat)
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_data)
        self.refresh_timer.start(120000 if self.preloaded_signals else 60000)

        # UI'i olustur
        self.init_ui()

        # Verileri yukle
        self.load_data()
        # Olasi yanlis kapanma durumlarini gozlemek icin event filter
        self.installEventFilter(self)
        self._debug_click_count = 0

    def eventFilter(self, obj, event):
        # Tiklandiginda uygulama kapaniyorsa once hangi event geldigini saptamak icin basit sayac
        try:
            et = event.type()
            # 2-3 temel event türünde debug göstergesi
            if et in (event.MouseButtonPress, event.MouseButtonDblClick):
                self._debug_click_count += 1
        except Exception:
            pass
        return super().eventFilter(obj, event)

    def closeEvent(self, event):
        # Yalnizca kendini kapat; uygulamayi sonlandirma
        event.accept()
        # Referansi parent uzerinde temizle (varsa)
        with contextlib.suppress(Exception):
            if (self.parent() is not None 
                and hasattr(self.parent(), 'signal_window') 
                and self.parent().signal_window is self):
                self.parent().signal_window = None
        # QuitOnClose zaten False; ekstra güvenlik
        with contextlib.suppress(Exception):
            QApplication.setQuitOnLastWindowClosed(False)

    def init_ui(self):
        """Arayuzu olustur"""
        layout = QVBoxLayout(self)

        # Baslik
        title = QLabel("📊 Canli Sinyal Analizi")
        title.setAlignment(Qt.AlignCenter)
        title.setFont(QFont("Arial", 14, QFont.Bold))
        layout.addWidget(title)

        # Zaman damgasi
        self.timestamp_label = QLabel("Son Güncelleme: --:--:--")
        self.timestamp_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.timestamp_label)

        # Filtreler
        filter_group = QGroupBox("Filtreler")
        filter_layout = QHBoxLayout()

        # Sinyal filtresi
        filter_layout.addWidget(QLabel("Sinyal:"))
        self.signal_filter = QComboBox()
        self.signal_filter.addItems(["Tümü", "AL", "SAT", "BEKLE"])
        self.signal_filter.currentTextChanged.connect(self.apply_filters)
        filter_layout.addWidget(self.signal_filter)

        # Puan filtresi
        filter_layout.addWidget(QLabel("Min Puan:"))
        self.min_score_input = QLineEdit()
        self.min_score_input.setPlaceholderText("0-100")
        self.min_score_input.textChanged.connect(self.apply_filters)
        filter_layout.addWidget(self.min_score_input)

        # Arama
        filter_layout.addWidget(QLabel("Arama:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Parite adi...")
        self.search_input.textChanged.connect(self.apply_filters)
        filter_layout.addWidget(self.search_input)

        # Yenile butonu
        self.refresh_btn = QPushButton("Yenile")
        self.refresh_btn.clicked.connect(self.refresh_data)
        filter_layout.addWidget(self.refresh_btn)

        filter_group.setLayout(filter_layout)
        layout.addWidget(filter_group)

        # Splitter
        splitter = QSplitter(Qt.Vertical)

        # Sinyal tablosu
        self.signal_table = QTableWidget()
        self.signal_table.setColumnCount(10)
        self.signal_table.setHorizontalHeaderLabels([
            "Parite", "Fiyat", "Sinyal", "Puan", "RSI", "MACD", "BB", "Stoch", "Williams", "CCI"
        ])

        # Sütun genişliklerini optimized hale getir
        header = self.signal_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # Parite
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Fiyat
        header.setSectionResizeMode(2, QHeaderView.Fixed)             # Sinyal
        header.setSectionResizeMode(3, QHeaderView.Fixed)             # Puan
        header.setSectionResizeMode(4, QHeaderView.Fixed)             # RSI
        header.setSectionResizeMode(5, QHeaderView.Fixed)             # MACD
        header.setSectionResizeMode(6, QHeaderView.Fixed)             # BB
        header.setSectionResizeMode(7, QHeaderView.Fixed)             # Stoch
        header.setSectionResizeMode(8, QHeaderView.Fixed)             # Williams
        header.setSectionResizeMode(9, QHeaderView.Stretch)          # CCI (son sütun uzat)

        # Sabit sütun genişlikleri
        self.signal_table.setColumnWidth(2, 80)   # Sinyal
        self.signal_table.setColumnWidth(3, 60)   # Puan
        self.signal_table.setColumnWidth(4, 60)   # RSI
        self.signal_table.setColumnWidth(5, 70)   # MACD
        self.signal_table.setColumnWidth(6, 60)   # BB
        self.signal_table.setColumnWidth(7, 60)   # Stoch
        self.signal_table.setColumnWidth(8, 80)   # Williams

        self.signal_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.signal_table.setSelectionMode(QTableWidget.SingleSelection)
        self.signal_table.itemSelectionChanged.connect(self.show_details)
        # Görsel iyileştirmeler (gereksiz çizgileri azalt)
        self.signal_table.setShowGrid(False)
        vh = self.signal_table.verticalHeader()
        if vh:
            vh.setVisible(False)
        self.signal_table.setAlternatingRowColors(True)
        self.signal_table.verticalHeader().setDefaultSectionSize(22)
        self.signal_table.setStyleSheet(
            "QTableWidget{alternate-background-color:#2f3439;background:#262b30;border:1px solid #3a3f44;color:#ddd;}"
            "QHeaderView::section{background:#3a3f44;color:#eee;border:none;padding:4px;font-weight:bold;}"
            "QTableWidget::item{padding:2px;}"
            "QTableWidget::item:selected{background:#005fa3;color:#fff;}"
        )
        splitter.addWidget(self.signal_table)

        # Detay paneli
        self.detail_group = QGroupBox("Detayli Analiz")
        detail_layout = QVBoxLayout()

        self.detail_label = QLabel("Bir parite secin detaylari gormek icin")
        self.detail_label.setAlignment(Qt.AlignCenter)
        detail_layout.addWidget(self.detail_label)

        self.detail_table = QTableWidget()
        self.detail_table.setColumnCount(3)
        self.detail_table.setHorizontalHeaderLabels(["İndikatör", "Değer", "Puan"])
        self.detail_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        detail_layout.addWidget(self.detail_table)
        self.detail_table.setShowGrid(False)
        dvh = self.detail_table.verticalHeader()
        if dvh:
            dvh.setVisible(False)
        self.detail_table.setAlternatingRowColors(True)
        self.detail_table.verticalHeader().setDefaultSectionSize(22)
        self.detail_table.setStyleSheet(
            "QTableWidget{alternate-background-color:#2f3439;background:#262b30;border:1px solid #3a3f44;color:#ddd;}"
            "QHeaderView::section{background:#3a3f44;color:#eee;border:none;padding:4px;font-weight:bold;}"
            "QTableWidget::item{padding:2px;}"
            "QTableWidget::item:selected{background:#444477;color:#fff;}"
        )

        self.detail_group.setLayout(detail_layout)
        splitter.addWidget(self.detail_group)

        splitter.setSizes([400, 300])
        layout.addWidget(splitter)

    def load_data(self):
        """Verileri yukle"""
        if self.preloaded_signals and not self.signals:
            # Ilk acilista hazir veriyi kullan
            self.signals = self.preloaded_signals
        elif not self.preloaded_signals:
            # Gerekirse üret
            self.signals = self.signal_generator.generate_signals()
        self.apply_filters()

    def receive_signals_update(self, signals: dict):
        """Ana pencereden canli sinyal guncellemesi al."""
        if not signals:
            return
        self.preloaded_signals = signals
        self.signals = signals
        # Birikimli (coalesced) yenileme - sik emit'te flicker engeller
        if not self._refresh_scheduled:
            self._refresh_scheduled = True
            QTimer.singleShot(150, self._apply_live_update)

    def _apply_live_update(self):
        self._refresh_scheduled = False
        self.apply_filters()
        self.timestamp_label.setText(f"Son Güncelleme: {datetime.now().strftime('%H:%M:%S')}")

    def refresh_data(self):
        """Verileri yenile"""
        self.load_data()
        self.timestamp_label.setText(f"Son Güncelleme: {datetime.now().strftime('%H:%M:%S')}")

    def apply_filters(self):
        """Filtreleri uygula ve tabloyu guncelle (flicker azaltilmis)."""
        logger = get_logger("SignalWindow")
        signal_filter = self.signal_filter.currentText()
        min_score_text = self.min_score_input.text().strip()
        search_text = self.search_input.text().upper().strip()
        if not self.signals:
            self.signal_table.setRowCount(0)
            return
        try:
            min_score = float(min_score_text) if min_score_text else None
        except ValueError:
            min_score = None
        filtered = []
        try:
            for symbol, signal in self.signals.items():
                sig_type = signal.get('signal')
                if signal_filter not in ("Tumu", sig_type):
                    continue
                if min_score is not None and signal.get('total_score', 0) < min_score:
                    continue
                if search_text and search_text not in symbol.upper():
                    continue
                filtered.append((symbol, signal))
            def sort_key(item):
                _sym, sig = item
                s = sig.get('signal')
                if s == 'AL':
                    priority = 0
                elif s == 'SAT':
                    priority = 1
                else:
                    priority = 2
                return (priority, -sig.get('total_score', 0))
            filtered.sort(key=sort_key)
            self.signal_table.setUpdatesEnabled(False)
            self.signal_table.setSortingEnabled(False)
            self.signal_table.setRowCount(0)
            for symbol, signal in filtered:
                row = self.signal_table.rowCount()
                self.signal_table.insertRow(row)
                self.signal_table.setItem(row, 0, QTableWidgetItem(symbol))
                cp = signal.get('close_price')
                self.signal_table.setItem(row, 1, QTableWidgetItem(f"{cp:.2f}" if isinstance(cp, (int,float)) else "-"))
                sig_val = signal.get('signal', '-')
                sig_item = QTableWidgetItem(sig_val)
                # Arka plani sabit koyu tonda birak, sadece yazi rengini degistir
                if sig_val == 'AL':
                    sig_item.setForeground(QColor(120, 220, 120))
                elif sig_val == 'SAT':
                    sig_item.setForeground(QColor(255, 120, 120))
                else:
                    sig_item.setForeground(QColor(210, 200, 120))
                self.signal_table.setItem(row, 2, sig_item)
                total_score = signal.get('total_score', 0)
                sc_item = QTableWidgetItem(f"{total_score:.1f}")
                if total_score >= SIGNAL_SCORE_HIGH_THRESHOLD:
                    sc_item.setForeground(QColor(120, 220, 120))
                elif total_score <= SIGNAL_SCORE_LOW_THRESHOLD:
                    sc_item.setForeground(QColor(255, 120, 120))
                else:
                    sc_item.setForeground(QColor(210, 200, 120))
                self.signal_table.setItem(row, 3, sc_item)
                indicators = signal.get('scores', {})
                col = 4
                for ind_name in ["RSI", "MACD", "Bollinger Bands", "Stochastic", "Williams %R", "CCI"]:
                    if ind_name in indicators:
                        try:
                            self.signal_table.setItem(row, col, QTableWidgetItem(f"{indicators[ind_name]:.1f}"))
                        except Exception:
                            self.signal_table.setItem(row, col, QTableWidgetItem(str(indicators[ind_name])))
                    col += 1
        except Exception as e:
            logger.error(f"apply_filters hata: {e}")
        finally:
            with contextlib.suppress(Exception):
                self.signal_table.setUpdatesEnabled(True)

    def show_details(self):
        """Secili paritenin detaylarini goster"""
        logger = get_logger("SignalWindow")
        try:
            selected_items = self.signal_table.selectedItems()
            if not selected_items:
                return
            row = selected_items[0].row()
            item0 = self.signal_table.item(row, 0)
            if item0 is None:
                return
            symbol = item0.text()
            signal = self.signals.get(symbol)
            if not signal:
                return
            self.detail_label.setText(f"{symbol} Detayli Analiz")
            self.detail_table.setRowCount(0)
            for ind_name, score in signal.get('scores', {}).items():
                r = self.detail_table.rowCount()
                self.detail_table.insertRow(r)
                self.detail_table.setItem(r, 0, QTableWidgetItem(ind_name))
                ind_val_series = signal.get('indicators', {}).get(ind_name)
                value = None
                try:
                    if isinstance(ind_val_series, dict):
                        value = ind_val_series.get('histogram')
                        if hasattr(value, 'iloc'):
                            value = value.iloc[-1]
                    elif hasattr(ind_val_series, 'iloc'):
                            value = ind_val_series.iloc[-1]
                except Exception:
                    value = None
                self.detail_table.setItem(r, 1, QTableWidgetItem("-" if value is None else f"{value:.2f}"))
                score_item = QTableWidgetItem(f"{score:.1f}")
                if score >= SIGNAL_SCORE_HIGH_THRESHOLD:
                    score_item.setForeground(QColor(120, 220, 120))
                elif score <= SIGNAL_SCORE_LOW_THRESHOLD:
                    score_item.setForeground(QColor(255, 120, 120))
                else:
                    score_item.setForeground(QColor(210, 200, 120))
                self.detail_table.setItem(r, 2, score_item)
        except Exception as e:
            logger.error(f"show_details hata: {e}")
