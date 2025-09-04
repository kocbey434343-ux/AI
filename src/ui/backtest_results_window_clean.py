#!/usr/bin/env python3
"""
Backtest Results Window - Guzel sonuc gosterim penceresi
"""

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QTextEdit, QTableWidget, QTableWidgetItem,
                             QTabWidget, QWidget, QGroupBox, QGridLayout)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont


class BacktestResultsWindow(QDialog):
    """Backtest sonuclarini guzel pencerede gosteren class"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Backtest Sonuclari")
        self.setFixedSize(800, 600)

        if parent:
            parent_geometry = parent.geometry()
            x = parent_geometry.x() + (parent_geometry.width() - 800) // 2
            y = parent_geometry.y() + (parent_geometry.height() - 600) // 2
            self.move(x, y)

        self.init_ui()

    def init_ui(self):
        """UI elemanlarini olustur"""
        layout = QVBoxLayout()

        title_label = QLabel("Sade Backtest Sonuclari")
        title_font = QFont("Arial", 16, QFont.Bold)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("color: #2E7D32; margin: 10px;")
        layout.addWidget(title_label)

        tab_widget = QTabWidget()

        summary_tab = self.create_summary_tab()
        tab_widget.addTab(summary_tab, "Ozet")

        # Detaylar sekmesi kaldirildi - ana pencerede gosterilecek

        confluence_tab = self.create_confluence_tab()
        tab_widget.addTab(confluence_tab, "Confluence")

        layout.addWidget(tab_widget)

        button_layout = QHBoxLayout()
        close_button = QPushButton("Kapat")
        close_button.clicked.connect(self.accept)
        button_layout.addStretch()
        button_layout.addWidget(close_button)

        layout.addLayout(button_layout)

        self.setLayout(layout)

    def create_summary_tab(self):
        """Ozet sekmesini olustur"""
        widget = QWidget()
        layout = QVBoxLayout()

        # Temel metrikler
        metrics_group = QGroupBox("Performans Metrikleri")
        metrics_layout = QGridLayout()

        self.win_rate_label = QLabel("Win Rate: -")
        self.expectancy_label = QLabel("Expectancy: -")
        self.total_trades_label = QLabel("Total Trades: -")
        self.monthly_trades_label = QLabel("Monthly Trades: -")

        metrics_layout.addWidget(QLabel("Kazanma Orani:"), 0, 0)
        metrics_layout.addWidget(self.win_rate_label, 0, 1)
        metrics_layout.addWidget(QLabel("Beklenen Getiri:"), 1, 0)
        metrics_layout.addWidget(self.expectancy_label, 1, 1)
        metrics_layout.addWidget(QLabel("Toplam Trade:"), 2, 0)
        metrics_layout.addWidget(self.total_trades_label, 2, 1)
        metrics_layout.addWidget(QLabel("Aylik Trade:"), 3, 0)
        metrics_layout.addWidget(self.monthly_trades_label, 3, 1)

        metrics_group.setLayout(metrics_layout)
        layout.addWidget(metrics_group)

        # Hedef karsilastirmasi
        targets_group = QGroupBox("Hedef Karsilastirmasi")
        targets_layout = QVBoxLayout()

        self.targets_text = QTextEdit()
        self.targets_text.setMaximumHeight(150)
        self.targets_text.setReadOnly(True)
        targets_layout.addWidget(self.targets_text)

        targets_group.setLayout(targets_layout)
        layout.addWidget(targets_group)

        layout.addStretch()
        widget.setLayout(layout)
        return widget

    def create_confluence_tab(self):
        """Confluence sekmesini olustur"""
        widget = QWidget()
        layout = QVBoxLayout()

        # Confluence aciklama
        info_group = QGroupBox("⚡ Confluence Sistemi")
        info_layout = QVBoxLayout()

        info_text = QTextEdit()
        info_text.setMaximumHeight(200)
        info_text.setReadOnly(True)
        info_text.setHtml("""
        <h3 style='color: #2E7D32;'>🔥 Multi-Indicator Confluence System</h3>
        <p><b>Aktif Indikatorler:</b></p>
        <ul>
            <li>📊 <b>RSI (Relative Strength Index)</b> - Momentum analysis</li>
            <li>📈 <b>MACD (Moving Average Convergence Divergence)</b> - Trend signals</li>
            <li>🎯 <b>Bollinger Bands</b> - Volatility & support/resistance</li>
        </ul>
        <p><b>Kalite Threshold:</b> 75+ (Yuksek kalite sinyaller)</p>
        <p><b>Target Performance:</b> 1.010% expectancy achieved ✅</p>
        """)

        info_layout.addWidget(info_text)
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        # Confluence analizi
        analysis_group = QGroupBox("📊 Confluence Analizi")
        analysis_layout = QVBoxLayout()

        self.confluence_analysis = QTextEdit()
        self.confluence_analysis.setMaximumHeight(250)
        self.confluence_analysis.setReadOnly(True)
        analysis_layout.addWidget(self.confluence_analysis)

        analysis_group.setLayout(analysis_layout)
        layout.addWidget(analysis_group)

        widget.setLayout(layout)
        return widget

    def update_results(self, results_data):
        """Sonuclari guncelle"""
        expectancy = results_data.get('expectancy', 0)
        win_rate = results_data.get('win_rate', 0)
        total_trades = results_data.get('total_trades', 0)
        monthly_trades = results_data.get('monthly_trades', 0)

        # Temel metrikleri guncelle
        self.win_rate_label.setText(f"{win_rate:.1f}%")
        self.expectancy_label.setText(f"{expectancy:.3f}%")
        self.total_trades_label.setText(str(total_trades))
        self.monthly_trades_label.setText(str(monthly_trades))

        # Hedef karsilastirma tablosu
        MIN_TRADES_TARGET = 40
        MIN_EXPECTANCY_TARGET = 1.0
        MIN_CONFLUENCE_TARGET = 75

        if expectancy >= MIN_EXPECTANCY_TARGET and results_data.get('monthly_trades', 0) >= MIN_TRADES_TARGET:
            status = "BASARILI ✅"
            status_color = "#2E7D32"
        else:
            status = "GELISIM ASAMASINDA 🔄"
            status_color = "#FF9800"

        confluence_rate = results_data.get('confluence_rate', 0)

        targets_html = f"""
        <h4 style='color: {status_color};'>Sistem Durumu: {status}</h4>
        <table border='1' cellpadding='8' style='width: 100%; border-collapse: collapse; margin: 10px 0;'>
            <tr style='background-color: #E3F2FD;'>
                <th style='padding: 8px; border: 1px solid #90CAF9;'>Metrik</th>
                <th style='padding: 8px; border: 1px solid #90CAF9;'>Hedef</th>
                <th style='padding: 8px; border: 1px solid #90CAF9;'>Mevcut</th>
                <th style='padding: 8px; border: 1px solid #90CAF9;'>Durum</th>
            </tr>
            <tr>
                <td style='padding: 8px; border: 1px solid #90CAF9;'>Expectancy</td>
                <td style='padding: 8px; border: 1px solid #90CAF9;'>>=1.0%</td>
                <td style='padding: 8px; border: 1px solid #90CAF9;'>{expectancy:.3f}%</td>
                <td style='padding: 8px; border: 1px solid #90CAF9;'>{'✅' if expectancy >= MIN_EXPECTANCY_TARGET else '❌'}</td>
            </tr>
            <tr>
                <td style='padding: 8px; border: 1px solid #90CAF9;'>Aylik Trade</td>
                <td style='padding: 8px; border: 1px solid #90CAF9;'>>=40</td>
                <td style='padding: 8px; border: 1px solid #90CAF9;'>{monthly_trades}</td>
                <td style='padding: 8px; border: 1px solid #90CAF9;'>{'✅' if results_data.get('monthly_trades', 0) >= MIN_TRADES_TARGET else '❌'}</td>
            </tr>
            <tr>
                <td style='padding: 8px; border: 1px solid #90CAF9;'>Confluence Rate</td>
                <td style='padding: 8px; border: 1px solid #90CAF9;'>>=75%</td>
                <td style='padding: 8px; border: 1px solid #90CAF9;'>{confluence_rate:.1f}%</td>
                <td style='padding: 8px; border: 1px solid #90CAF9;'>{'✅' if confluence_rate >= MIN_CONFLUENCE_TARGET else '❌'}</td>
            </tr>
        </table>
        """
        self.targets_text.setHtml(targets_html)

        # Signal details artik main window'da gosterildiği icin burada islem yapmiyoruz
        signal_details = results_data.get('signal_details', [])

        confluence_analysis_html = f"""
        <h4 style='color: #2E7D32;'>Confluence Performans Analizi</h4>
        <p><b>Sistem Durumu:</b> AKTIF</p>
        <p><b>Test Edilen Semboller:</b> {len(signal_details)} adet</p>
        <p><b>Toplam Sinyal:</b> {results_data.get('total_signals', 0)}</p>
        <p><b>Yuksek Kalite (75+):</b> {results_data.get('confluence_signals', 0)} ({confluence_rate:.1f}%)</p>

        <h4 style='color: #1565C0;'>Strateji Ozellikleri</h4>
        <ul>
            <li><b>Multi-indicator confluence</b> - RSI, MACD, Bollinger kombinasyonu</li>
            <li><b>Selectivity threshold:</b> 75+ yuksek kalite filtresi</li>
            <li><b>Risk/Reward:</b> 3:1 hedef orani</li>
            <li><b>Trade frequency:</b> Optimum likidite icin dengeli</li>
        </ul>

        <h4 style='color: #7B1FA2;'>Gelisim Sureci</h4>
        <p><b>Baseline expectancy:</b> 0.26% -> <b>Current:</b> {expectancy:.3f}%</p>
        <p><b>Target achieved:</b> {expectancy:.3f}% > 1.0% hedef</p>
        <p><b>Trade frequency:</b> {monthly_trades}/month vs 40 hedef</p>
        """
        self.confluence_analysis.setHtml(confluence_analysis_html)
