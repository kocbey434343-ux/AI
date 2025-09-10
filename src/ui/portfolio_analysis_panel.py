"""
Portfolio Analysis Panel - UI entegrasyonu

Multi-asset portfolio analizi icin PyQt5 UI paneli.
"""

from typing import Dict

from PyQt5.QtCore import QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

try:
    from src.portfolio.portfolio_analyzer import PortfolioAnalyzer, get_portfolio_analyzer
except ImportError:
    # Fallback for development
    def get_portfolio_analyzer():
        return None
    PortfolioAnalyzer = type(None)


class PortfolioMetricsWidget(QWidget):
    """Portfolio metrikleri widget'i"""

    def __init__(self):
        super().__init__()
        self.setup_ui()

    def setup_ui(self):
        """UI setup"""
        layout = QGridLayout()

        # Ana metrikler
        self.total_value_label = QLabel("Toplam Deger: --")
        self.total_value_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #2E86AB;")

        self.position_count_label = QLabel("Pozisyon Sayisi: --")
        self.leverage_label = QLabel("Kaldirac: --")
        self.cash_label = QLabel("Nakit: --")

        # Risk metrikleri
        self.volatility_label = QLabel("Yillik Volatilite: --")
        self.sharpe_label = QLabel("Sharpe Ratio: --")
        self.max_dd_label = QLabel("Max Drawdown: --")
        self.var_95_label = QLabel("VaR (95%): --")

        # Layout duzeni
        layout.addWidget(self.total_value_label, 0, 0, 1, 2)
        layout.addWidget(self.position_count_label, 1, 0)
        layout.addWidget(self.leverage_label, 1, 1)
        layout.addWidget(self.cash_label, 2, 0)
        layout.addWidget(self.volatility_label, 2, 1)
        layout.addWidget(self.sharpe_label, 3, 0)
        layout.addWidget(self.max_dd_label, 3, 1)
        layout.addWidget(self.var_95_label, 4, 0, 1, 2)

        self.setLayout(layout)

    def update_metrics(self, analytics: Dict):
        """Metrikleri guncelle"""
        try:
            # Ana metrikler
            total_value = analytics.get('total_value', 0)
            self.total_value_label.setText(f"Toplam Deger: {total_value:,.2f} USDT")

            position_count = analytics.get('position_count', 0)
            self.position_count_label.setText(f"Pozisyon Sayisi: {position_count}")

            leverage = analytics.get('leverage', 1.0)
            self.leverage_label.setText(f"Kaldirac: {leverage:.2f}x")

            # Risk metrikleri
            risk_metrics = analytics.get('risk_metrics', {})
            if risk_metrics:
                volatility = risk_metrics.get('annual_volatility', 0) * 100
                self.volatility_label.setText(f"Yillik Volatilite: {volatility:.1f}%")

                sharpe = risk_metrics.get('sharpe_ratio', 0)
                self.sharpe_label.setText(f"Sharpe Ratio: {sharpe:.2f}")

                max_dd = risk_metrics.get('max_drawdown', 0) * 100
                self.max_dd_label.setText(f"Max Drawdown: {max_dd:.1f}%")

            # VaR metrikleri
            var_metrics = analytics.get('var_metrics', {})
            if var_metrics:
                var_95 = var_metrics.get('var_95', 0) * 100
                self.var_95_label.setText(f"VaR (95%): {var_95:.2f}%")

        except Exception as e:
            print(f"Metrics update error: {e}")


class PortfolioPositionsTable(QTableWidget):
    """Portfolio pozisyonlari tablosu"""

    def __init__(self):
        super().__init__()
        self.setup_table()

    def setup_table(self):
        """Tablo kurulumu"""
        self.setColumnCount(6)
        self.setHorizontalHeaderLabels([
            'Sembol', 'Miktar', 'Fiyat', 'Deger', 'Agirlik', 'Sektor'
        ])

        # Kolon genislikleri
        header = self.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # Sembol
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Miktar
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Fiyat
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Deger
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # Agirlik

        # Stil
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableWidget.SelectRows)

    def update_positions(self, snapshot_data: Dict):
        """Pozisyonlari guncelle"""
        try:
            positions = snapshot_data.get('positions', [])

            self.setRowCount(len(positions))

            for row, position in enumerate(positions):
                # Sembol
                symbol_item = QTableWidgetItem(position.get('symbol', ''))
                symbol_item.setFont(QFont("Arial", 9, QFont.Bold))
                self.setItem(row, 0, symbol_item)

                # Miktar
                quantity = position.get('quantity', 0)
                self.setItem(row, 1, QTableWidgetItem(f"{quantity:.4f}"))

                # Fiyat
                price = position.get('price', 0)
                self.setItem(row, 2, QTableWidgetItem(f"{price:.4f}"))

                # Deger
                value = position.get('value', 0)
                value_item = QTableWidgetItem(f"{value:,.2f}")
                self.setItem(row, 3, value_item)

                # Agirlik
                weight = position.get('weight', 0) * 100
                weight_item = QTableWidgetItem(f"{weight:.1f}%")

                # Agirlik renklendirmesi
                if weight > 30:
                    weight_item.setBackground(QColor("#FFE5E5"))  # Acik kirmizi
                elif weight > 20:
                    weight_item.setBackground(QColor("#FFF5E5"))  # Acik turuncu

                self.setItem(row, 4, weight_item)

                # Sektor
                sector = position.get('sector', 'Unknown')
                self.setItem(row, 5, QTableWidgetItem(sector))

        except Exception as e:
            print(f"Positions update error: {e}")


class CorrelationMatrixWidget(QWidget):
    """Korelasyon matrisi widget'i"""

    def __init__(self):
        super().__init__()
        self.setup_ui()

    def setup_ui(self):
        """UI setup"""
        layout = QVBoxLayout()

        # Baslik
        title = QLabel("Korelasyon Matrisi")
        title.setFont(QFont("Arial", 12, QFont.Bold))
        layout.addWidget(title)

        # Korelasyon tablosu
        self.correlation_table = QTableWidget()
        self.correlation_table.setMaximumHeight(200)
        layout.addWidget(self.correlation_table)

        # Istatistikler
        self.stats_label = QLabel("Istatistikler: --")
        layout.addWidget(self.stats_label)

        self.setLayout(layout)

    def update_correlation(self, analytics: Dict):
        """Korelasyon matrisini guncelle"""
        try:
            correlation_stats = analytics.get('correlation_stats', {})

            if correlation_stats:
                mean_corr = correlation_stats.get('mean_correlation', 0)
                max_corr = correlation_stats.get('max_correlation', 0)
                min_corr = correlation_stats.get('min_correlation', 0)

                stats_text = (f"Ortalama: {mean_corr:.3f}, "
                             f"Max: {max_corr:.3f}, "
                             f"Min: {min_corr:.3f}")
                self.stats_label.setText(f"Korelasyon Istatistikleri: {stats_text}")
            else:
                self.stats_label.setText("Korelasyon Istatistikleri: Yeterli veri yok")

        except Exception as e:
            print(f"Correlation update error: {e}")


class OptimizationSuggestionsWidget(QWidget):
    """Optimizasyon onerileri widget'i"""

    def __init__(self):
        super().__init__()
        self.setup_ui()

    def setup_ui(self):
        """UI setup"""
        layout = QVBoxLayout()

        # Baslik
        title = QLabel("Portfolio Optimizasyon Onerileri")
        title.setFont(QFont("Arial", 12, QFont.Bold))
        layout.addWidget(title)

        # Oneriler text alani
        self.suggestions_text = QTextEdit()
        self.suggestions_text.setMaximumHeight(150)
        self.suggestions_text.setReadOnly(True)
        layout.addWidget(self.suggestions_text)

        self.setLayout(layout)

    def update_suggestions(self, analytics: Dict):
        """Onerileri guncelle"""
        try:
            suggestions = analytics.get('optimization_suggestions', [])

            if suggestions:
                suggestions_html = "<ul>"
                for suggestion in suggestions:
                    suggestions_html += f"<li>{suggestion}</li>"
                suggestions_html += "</ul>"

                self.suggestions_text.setHtml(suggestions_html)
            else:
                self.suggestions_text.setPlainText("Optimizasyon onerisi bulunmuyor.")

        except Exception as e:
            print(f"Suggestions update error: {e}")


class PortfolioAnalysisPanel(QWidget):
    """Ana Portfolio Analysis Paneli"""

    # Signals
    refresh_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.portfolio_analyzer = get_portfolio_analyzer()
        self.setup_ui()
        self.setup_timer()

    def setup_ui(self):
        """UI kurulumu"""
        layout = QVBoxLayout()

        # Baslik ve kontroller
        header_layout = QHBoxLayout()

        title = QLabel("Portfolio Analizi")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        title.setStyleSheet("color: #2E86AB; margin: 10px;")

        self.refresh_btn = QPushButton("Yenile")
        self.refresh_btn.clicked.connect(self.refresh_data)
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #2E86AB;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1F5F8B;
            }
        """)

        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(self.refresh_btn)

        layout.addLayout(header_layout)

        # Ana icerik - Tabs
        self.tabs = QTabWidget()

        # Portfolio Overview Tab
        overview_tab = QWidget()
        overview_layout = QVBoxLayout()

        # Metrikler
        metrics_group = QGroupBox("Portfolio Metrikleri")
        self.metrics_widget = PortfolioMetricsWidget()
        metrics_layout = QVBoxLayout()
        metrics_layout.addWidget(self.metrics_widget)
        metrics_group.setLayout(metrics_layout)

        # Pozisyonlar tablosu
        positions_group = QGroupBox("Pozisyonlar")
        self.positions_table = PortfolioPositionsTable()
        positions_layout = QVBoxLayout()
        positions_layout.addWidget(self.positions_table)
        positions_group.setLayout(positions_layout)

        overview_layout.addWidget(metrics_group)
        overview_layout.addWidget(positions_group)
        overview_tab.setLayout(overview_layout)

        # Risk Analysis Tab
        risk_tab = QWidget()
        risk_layout = QVBoxLayout()

        # Korelasyon
        correlation_group = QGroupBox("Korelasyon Analizi")
        self.correlation_widget = CorrelationMatrixWidget()
        correlation_layout = QVBoxLayout()
        correlation_layout.addWidget(self.correlation_widget)
        correlation_group.setLayout(correlation_layout)

        # Optimizasyon onerileri
        optimization_group = QGroupBox("Optimizasyon")
        self.optimization_widget = OptimizationSuggestionsWidget()
        optimization_layout = QVBoxLayout()
        optimization_layout.addWidget(self.optimization_widget)
        optimization_group.setLayout(optimization_layout)

        risk_layout.addWidget(correlation_group)
        risk_layout.addWidget(optimization_group)
        risk_tab.setLayout(risk_layout)

        # Tabs'leri ekle
        self.tabs.addTab(overview_tab, "Genel Bakis")
        self.tabs.addTab(risk_tab, "Risk Analizi")

        layout.addWidget(self.tabs)

        # Status bar
        self.status_label = QLabel("Portfolio analizi hazir")
        self.status_label.setStyleSheet("color: #666; padding: 5px;")
        layout.addWidget(self.status_label)

        self.setLayout(layout)

    def setup_timer(self):
        """Otomatik yenileme timer'i"""
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.refresh_data)
        self.update_timer.start(30000)  # 30 saniye

    def refresh_data(self):
        """Veriyi yenile"""
        try:
            if not self.portfolio_analyzer:
                self.status_label.setText("Portfolio analyzer mevcut degil")
                return

            # Analytics al
            analytics = self.portfolio_analyzer.get_analytics_summary()

            if not analytics:
                self.status_label.setText("Portfolio verisi mevcut degil")
                return

            # Widget'lari guncelle
            self.metrics_widget.update_metrics(analytics)

            # Export data ile snapshot al
            export_data = self.portfolio_analyzer.export_to_dict()
            snapshot_data = export_data.get('snapshot', {})

            self.positions_table.update_positions(snapshot_data)
            self.correlation_widget.update_correlation(analytics)
            self.optimization_widget.update_suggestions(analytics)

            # Status guncelle
            timestamp = analytics.get('timestamp', '')
            self.status_label.setText(f"Son guncelleme: {timestamp[:19] if timestamp else 'Bilinmiyor'}")

            self.refresh_requested.emit()

        except Exception as e:
            self.status_label.setText(f"Guncelleme hatasi: {e!s}")
            print(f"Portfolio panel refresh error: {e}")

    def add_sample_data(self):
        """Real portfolio verisi ekle, fallback olarak test verisi"""
        try:
            if not self.portfolio_analyzer:
                return

            # Try to get real portfolio positions first
            real_positions_available = False
            real_positions = {}

            # Check if we have access to a real trader instance
            if hasattr(self, 'trader') and self.trader:
                try:
                    # Get real positions from trader
                    open_positions = self.trader.store.get_open_positions()
                    if open_positions:
                        real_positions_available = True
                        for pos in open_positions:
                            symbol = pos.get('symbol', '')
                            size = float(pos.get('position_size', 0))
                            entry_price = float(pos.get('entry_price', 0))
                            if symbol and size > 0 and entry_price > 0:
                                real_positions[symbol] = (size, entry_price)
                        print(f"✅ Portfolio: {len(real_positions)} gercek pozisyon bulundu")
                except Exception as e:
                    print(f"Real positions alinamadi: {e}")

            if real_positions_available and real_positions:
                # Use real positions
                positions = real_positions

                # Real sector mapping (crypto siniflandirmasi)
                sector_mapping = {}
                for symbol in positions.keys():
                    if 'BTC' in symbol:
                        sector_mapping[symbol] = 'Cryptocurrency'
                    elif 'ETH' in symbol or symbol in ['ADAUSDT', 'DOTUSD', 'KSMUSDT']:
                        sector_mapping[symbol] = 'Smart Contracts'
                    elif symbol in ['SOLUSDT', 'AVAXUSDT', 'MATICUSDT']:
                        sector_mapping[symbol] = 'Layer 1'
                    elif symbol in ['UNIUSDT', 'LINKUSDT', 'AAVEUSDT']:
                        sector_mapping[symbol] = 'DeFi'
                    else:
                        sector_mapping[symbol] = 'Altcoins'

                self.portfolio_analyzer.add_sector_mapping(sector_mapping)

                # Real cash amount (if available)
                cash_amount = 1000.0  # Default or get from account balance
                try:
                    if hasattr(self.trader, 'get_account_balance'):
                        balance = self.trader.get_account_balance()
                        if isinstance(balance, dict) and 'USDT' in balance:
                            cash_amount = float(balance['USDT'].get('free', 1000.0))
                except Exception:
                    pass

            else:
                # Fallback to sample data for testing
                print("⚠️ Portfolio: Gercek pozisyon bulunamadi, sample data kullaniliyor")
                positions = {
                    'BTCUSDT': (1.0, 50000.0),
                    'ETHUSDT': (10.0, 3000.0),
                    'ADAUSDT': (1000.0, 1.5),
                    'DOTUSDT': (100.0, 20.0)
                }

                # Sample sector mapping
                self.portfolio_analyzer.add_sector_mapping({
                    'BTCUSDT': 'Cryptocurrency',
                    'ETHUSDT': 'Smart Contracts',
                    'ADAUSDT': 'Smart Contracts',
                    'DOTUSDT': 'Interoperability'
                })

                cash_amount = 5000.0

            # Snapshot al
            self.portfolio_analyzer.take_snapshot(positions, cash=cash_amount)

            # Refresh
            self.refresh_data()

        except Exception as e:
            print(f"Portfolio data error: {e}")
            # Emergency fallback
            try:
                self.portfolio_analyzer.take_snapshot({}, cash=1000.0)
                self.refresh_data()
            except Exception:
                pass


def main():
    """Test icin ana fonksiyon"""
    import sys

    from PyQt5.QtWidgets import QApplication, QMainWindow

    app = QApplication(sys.argv)

    window = QMainWindow()
    window.setWindowTitle("Portfolio Analysis Panel Test")
    window.resize(1000, 700)

    panel = PortfolioAnalysisPanel()
    window.setCentralWidget(panel)

    # Sample data ekle
    panel.add_sample_data()

    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
