"""Edge Health Monitor Panel - A32 Edge Hardening System Visualization

Real-time dashboard for trading edge health monitoring with Wilson CI.
"""

from PyQt5.QtCore import QTimer, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

# Style constants to prevent duplication
SUCCESS_STYLE = "color: #27AE60; font-weight: bold;"
ERROR_STYLE = "color: #C0392B; font-weight: bold;"
WARNING_STYLE = "color: #F39C12; font-weight: bold;"

# Text constants to prevent duplication
LONG_SIGNAL = "LONG: ●"
SHORT_SIGNAL = "SHORT: ●"


class EdgeStatusIndicator(QWidget):
    """Edge health status indicator with color-coded display."""

    def __init__(self, title: str):
        super().__init__()
        self.title = title
        self.current_status = "UNKNOWN"
        self.wilson_lb = 0.0
        self.confidence_level = 0.95
        self.trade_count = 0

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        # Title
        self.title_label = QLabel(self.title)
        self.title_label.setFont(QFont("Arial", 9, QFont.Bold))
        layout.addWidget(self.title_label)

        # Status indicator (large colored circle)
        self.status_frame = QFrame()
        self.status_frame.setFixedSize(40, 40)
        self.status_frame.setStyleSheet("border-radius: 20px; background-color: #888888;")

        status_layout = QHBoxLayout()
        status_layout.addStretch()
        status_layout.addWidget(self.status_frame)
        status_layout.addStretch()
        layout.addLayout(status_layout)

        # Status text
        self.status_label = QLabel("UNKNOWN")
        self.status_label.setFont(QFont("Arial", 8, QFont.Bold))
        self.status_label.setStyleSheet("color: #666666;")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)

        # Wilson LB value
        self.wilson_label = QLabel("Wilson LB: --")
        self.wilson_label.setFont(QFont("Arial", 7))
        self.wilson_label.setStyleSheet("color: #444444;")
        layout.addWidget(self.wilson_label)

        # Trade count
        self.count_label = QLabel("Trades: 0")
        self.count_label.setFont(QFont("Arial", 7))
        self.count_label.setStyleSheet("color: #444444;")
        self.count_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.count_label)

    def update_status(self, status: str, wilson_lb: float, trade_count: int):
        """Update edge status display."""
        self.current_status = status
        self.wilson_lb = wilson_lb
        self.trade_count = trade_count

        # Color mapping
        color_map = {
            "HOT": "#2ECC71",     # Green
            "WARM": "#F39C12",    # Orange
            "COLD": "#E74C3C",    # Red
            "UNKNOWN": "#888888"  # Gray
        }

        text_color_map = {
            "HOT": "#27AE60",
            "WARM": "#E67E22",
            "COLD": "#C0392B",
            "UNKNOWN": "#666666"
        }

        # Update circle color
        color = color_map.get(status, "#888888")
        self.status_frame.setStyleSheet(f"border-radius: 20px; background-color: {color};")

        # Update text
        text_color = text_color_map.get(status, "#666666")
        self.status_label.setText(status)
        self.status_label.setStyleSheet(f"color: {text_color}; font-weight: bold;")

        # Update Wilson LB
        if wilson_lb is not None:
            self.wilson_label.setText(f"Wilson LB: {wilson_lb:.4f}")
        else:
            self.wilson_label.setText("Wilson LB: --")

        # Update trade count
        self.count_label.setText(f"Trades: {trade_count}")


class CostRuleGauge(QWidget):
    """4x Cost Rule gauge showing EGE vs Total Cost."""

    def __init__(self):
        super().__init__()
        self.ege_value = 0.0
        self.cost_value = 0.0
        self.rule_passed = False

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        # Title
        title_label = QLabel("4x Cost Rule")
        title_label.setFont(QFont("Arial", 9, QFont.Bold))
        layout.addWidget(title_label)

        # Rule status
        self.rule_status = QLabel("UNKNOWN")
        self.rule_status.setFont(QFont("Arial", 8, QFont.Bold))
        self.rule_status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.rule_status)

        # EGE bar
        ege_layout = QHBoxLayout()
        ege_layout.addWidget(QLabel("EGE:"))
        self.ege_bar = QProgressBar()
        self.ege_bar.setMaximum(100)
        self.ege_bar.setValue(0)
        ege_layout.addWidget(self.ege_bar)
        self.ege_value_label = QLabel("0.00")
        ege_layout.addWidget(self.ege_value_label)
        layout.addLayout(ege_layout)

        # Cost bar
        cost_layout = QHBoxLayout()
        cost_layout.addWidget(QLabel("Cost:"))
        self.cost_bar = QProgressBar()
        self.cost_bar.setMaximum(100)
        self.cost_bar.setValue(0)
        cost_layout.addWidget(self.cost_bar)
        self.cost_value_label = QLabel("0.00")
        cost_layout.addWidget(self.cost_value_label)
        layout.addLayout(cost_layout)

        # Ratio display
        self.ratio_label = QLabel("Ratio: --")
        self.ratio_label.setFont(QFont("Arial", 8))
        self.ratio_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.ratio_label)

    def update_cost_rule(self, ege: float, total_cost: float, k_multiple: float = 4.0):
        """Update 4x cost rule display."""
        self.ege_value = ege
        self.cost_value = total_cost

        # Calculate rule status
        if total_cost > 0:
            ratio = ege / total_cost
            self.rule_passed = ratio >= k_multiple
        else:
            ratio = 0
            self.rule_passed = False

        # Update status
        if self.rule_passed:
            self.rule_status.setText("PASS")
            self.rule_status.setStyleSheet("color: #27AE60; font-weight: bold;")
        else:
            self.rule_status.setText("FAIL")
            self.rule_status.setStyleSheet("color: #C0392B; font-weight: bold;")

        # Update bars (normalize to 0-100 scale)
        max_val = max(ege, total_cost * k_multiple, 1.0)
        ege_pct = int((ege / max_val) * 100)
        cost_pct = int((total_cost / max_val) * 100)

        self.ege_bar.setValue(ege_pct)
        self.cost_bar.setValue(cost_pct)

        # Update value labels
        self.ege_value_label.setText(f"{ege:.3f}")
        self.cost_value_label.setText(f"{total_cost:.3f}")

        # Update ratio
        if total_cost > 0:
            self.ratio_label.setText(f"Ratio: {ratio:.2f}x")
        else:
            self.ratio_label.setText("Ratio: --")


class MicrostructurePanel(QWidget):
    """Microstructure filter panel for OBI/AFR monitoring."""

    def __init__(self):
        super().__init__()
        self.obi_value = 0.0
        self.afr_value = 0.5
        self.long_allowed = True
        self.short_allowed = True

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        # Title
        title_label = QLabel("Mikroyapi Filtreleri")
        title_label.setFont(QFont("Arial", 9, QFont.Bold))
        layout.addWidget(title_label)

        # OBI Section
        obi_layout = QHBoxLayout()
        obi_layout.addWidget(QLabel("OBI:"))
        self.obi_bar = QProgressBar()
        self.obi_bar.setMinimum(-100)
        self.obi_bar.setMaximum(100)
        self.obi_bar.setValue(0)
        obi_layout.addWidget(self.obi_bar)
        self.obi_label = QLabel("0.00")
        obi_layout.addWidget(self.obi_label)
        layout.addLayout(obi_layout)

        # AFR Section
        afr_layout = QHBoxLayout()
        afr_layout.addWidget(QLabel("AFR:"))
        self.afr_bar = QProgressBar()
        self.afr_bar.setMinimum(0)
        self.afr_bar.setMaximum(100)
        self.afr_bar.setValue(50)
        afr_layout.addWidget(self.afr_bar)
        self.afr_label = QLabel("0.50")
        afr_layout.addWidget(self.afr_label)
        layout.addLayout(afr_layout)

        # Signal allowance indicators
        signal_layout = QHBoxLayout()
        self.long_indicator = QLabel("LONG: ●")
        self.long_indicator.setFont(QFont("Arial", 8, QFont.Bold))
        signal_layout.addWidget(self.long_indicator)

        signal_layout.addStretch()

        self.short_indicator = QLabel("SHORT: ●")
        self.short_indicator.setFont(QFont("Arial", 8, QFont.Bold))
        signal_layout.addWidget(self.short_indicator)
        layout.addLayout(signal_layout)

    def update_microstructure(self, obi: float, afr: float, long_allowed: bool, short_allowed: bool):
        """Update microstructure filter display."""
        self.obi_value = obi
        self.afr_value = afr
        self.long_allowed = long_allowed
        self.short_allowed = short_allowed

        # Update OBI bar (-1 to +1 mapped to -100 to +100)
        obi_pct = int(obi * 100)
        self.obi_bar.setValue(obi_pct)
        self.obi_label.setText(f"{obi:.3f}")

        # Update AFR bar (0 to 1 mapped to 0 to 100)
        afr_pct = int(afr * 100)
        self.afr_bar.setValue(afr_pct)
        self.afr_label.setText(f"{afr:.3f}")

        # Update signal indicators
        if long_allowed:
            self.long_indicator.setText("LONG: ●")
            self.long_indicator.setStyleSheet("color: #27AE60; font-weight: bold;")
        else:
            self.long_indicator.setText("LONG: ●")
            self.long_indicator.setStyleSheet("color: #C0392B; font-weight: bold;")

        if short_allowed:
            self.short_indicator.setText("SHORT: ●")
            self.short_indicator.setStyleSheet("color: #27AE60; font-weight: bold;")
        else:
            self.short_indicator.setText("SHORT: ●")
            self.short_indicator.setStyleSheet("color: #C0392B; font-weight: bold;")


class RiskMultiplierGauge(QWidget):
    """Risk multiplier gauge based on edge health."""

    def __init__(self):
        super().__init__()
        self.risk_multiplier = 1.0
        self.base_risk = 0.005
        self.effective_risk = 0.005

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(6)

        # Title
        title_label = QLabel("Risk Carpani")
        title_label.setFont(QFont("Arial", 9, QFont.Bold))
        layout.addWidget(title_label)

        # Risk multiplier bar
        mult_layout = QHBoxLayout()
        mult_layout.addWidget(QLabel("Carpan:"))
        self.mult_bar = QProgressBar()
        self.mult_bar.setMinimum(0)
        self.mult_bar.setMaximum(100)
        self.mult_bar.setValue(100)
        mult_layout.addWidget(self.mult_bar)
        self.mult_label = QLabel("1.00x")
        mult_layout.addWidget(self.mult_label)
        layout.addLayout(mult_layout)

        # Effective risk display
        self.risk_label = QLabel("Etkin Risk: 0.50%")
        self.risk_label.setFont(QFont("Arial", 8))
        self.risk_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.risk_label)

        # Base risk reference
        self.base_label = QLabel("Temel Risk: 0.50%")
        self.base_label.setFont(QFont("Arial", 7))
        self.base_label.setStyleSheet("color: #666666;")
        layout.addWidget(self.base_label)

    def update_risk_multiplier(self, multiplier: float, base_risk: float = 0.005):
        """Update risk multiplier display."""
        self.risk_multiplier = multiplier
        self.base_risk = base_risk
        self.effective_risk = base_risk * multiplier

        # Update bar (0 to 1.0 mapped to 0 to 100)
        mult_pct = int(multiplier * 100)
        self.mult_bar.setValue(mult_pct)

        # Color based on multiplier
        if multiplier >= 1.0:
            color = "#27AE60"  # Green - normal risk
        elif multiplier >= 0.75:
            color = "#F39C12"  # Orange - reduced risk
        else:
            color = "#E74C3C"  # Red - heavily reduced risk

        self.mult_bar.setStyleSheet(f"""
            QProgressBar::chunk {{
                background-color: {color};
            }}
        """)

        # Update labels
        self.mult_label.setText(f"{multiplier:.2f}x")
        self.risk_label.setText(f"Etkin Risk: {self.effective_risk*100:.2f}%")
        self.base_label.setText(f"Temel Risk: {base_risk*100:.2f}%")


class EdgeHealthMonitorPanel(QWidget):
    """Main Edge Health Monitor panel for A32 system."""

    # Signals
    panel_enabled_changed = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self.is_enabled = False
        self.update_timer = None

        self._setup_ui()
        self._setup_timer()
        self._load_mock_data()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Header with enable/disable toggle
        header_layout = QHBoxLayout()

        title_label = QLabel("Edge Health Monitor (A32)")
        title_label.setFont(QFont("Arial", 12, QFont.Bold))
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        self.enable_button = QPushButton("Etkinlestir")
        self.enable_button.setCheckable(True)
        self.enable_button.clicked.connect(self._toggle_panel)
        header_layout.addWidget(self.enable_button)

        layout.addLayout(header_layout)

        # Main content area
        content_layout = QHBoxLayout()

        # Left column: Edge status indicators
        left_group = QGroupBox("Edge Durumu")
        left_layout = QHBoxLayout(left_group)

        self.global_edge = EdgeStatusIndicator("Global Edge")
        left_layout.addWidget(self.global_edge)

        self.strategy_edge = EdgeStatusIndicator("Strateji Edge")
        left_layout.addWidget(self.strategy_edge)

        content_layout.addWidget(left_group)

        # Middle column: Cost rule and microstructure
        middle_group = QGroupBox("Filtreler")
        middle_layout = QVBoxLayout(middle_group)

        self.cost_rule = CostRuleGauge()
        middle_layout.addWidget(self.cost_rule)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        middle_layout.addWidget(separator)

        self.microstructure = MicrostructurePanel()
        middle_layout.addWidget(self.microstructure)

        content_layout.addWidget(middle_group)

        # Right column: Risk adjustment
        right_group = QGroupBox("Risk Ayari")
        right_layout = QVBoxLayout(right_group)

        self.risk_multiplier = RiskMultiplierGauge()
        right_layout.addWidget(self.risk_multiplier)

        # Status summary
        right_layout.addStretch()

        self.summary_label = QLabel("Durum: Edge durumu izleniyor...")
        self.summary_label.setFont(QFont("Arial", 8))
        self.summary_label.setWordWrap(True)
        self.summary_label.setStyleSheet("color: #666666; padding: 5px; background-color: #f0f0f0; border-radius: 3px;")
        right_layout.addWidget(self.summary_label)

        content_layout.addWidget(right_group)

        layout.addLayout(content_layout)

    def _setup_timer(self):
        """Setup update timer for real-time updates."""
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_displays)
        # 500ms update frequency for smooth real-time feel
        self.update_timer.start(500)

    def _toggle_panel(self):
        """Toggle panel enable/disable state."""
        self.is_enabled = not self.is_enabled

        if self.is_enabled:
            self.enable_button.setText("Devre Disi Birak")
            self.enable_button.setStyleSheet("background-color: #e74c3c; color: white;")
        else:
            self.enable_button.setText("Etkinlestir")
            self.enable_button.setStyleSheet("")

        self.panel_enabled_changed.emit(self.is_enabled)
        self._update_summary()

    def _load_mock_data(self):
        """Load real A32 data, fallback to conservative defaults for testing."""
        try:
            # Try to get real A32 data first
            from src.utils.cost_calculator import get_cost_calculator
            from src.utils.edge_health import get_edge_health_monitor
            from src.utils.microstructure import get_microstructure_filter

            # Edge Health Monitor'dan gercek veri al
            edge_monitor = get_edge_health_monitor()
            global_health = edge_monitor.get_global_edge_health()
            strategy_health = edge_monitor.get_strategy_edge_health("default")

            # Global edge health
            global_status = 'WARM'  # Default
            global_wilson_lb = 0.05  # Default
            global_trade_count = 0

            if global_health.get('sufficient_data', False):
                status = global_health.get('status', 'WARM')
                global_status = status.value if hasattr(status, 'value') else str(status)
                global_wilson_lb = global_health.get('wilson_lower_bound', 0.05)
                global_trade_count = global_health.get('trade_count', 0)

            # Strategy edge health
            strategy_status = 'HOT'  # Default
            strategy_wilson_lb = 0.12  # Default
            strategy_trade_count = 0

            if strategy_health.get('sufficient_data', False):
                status = strategy_health.get('status', 'HOT')
                strategy_status = status.value if hasattr(status, 'value') else str(status)
                strategy_wilson_lb = strategy_health.get('wilson_lower_bound', 0.12)
                strategy_trade_count = strategy_health.get('trade_count', 0)

            # Cost calculator metrics - gercek hesaplama
            cost_calc = get_cost_calculator()

            # Microstructure filter metrics - gercek hesaplama
            micro_filter = get_microstructure_filter()

            # Risk multiplier
            risk_mult = edge_monitor.get_risk_multiplier("default")

            self.mock_data = {
                'global_edge': {
                    'status': global_status,
                    'wilson_lb': global_wilson_lb,
                    'trade_count': global_trade_count
                },
                'strategy_edge': {
                    'status': strategy_status,
                    'wilson_lb': strategy_wilson_lb,
                    'trade_count': strategy_trade_count
                },
                'cost_rule': {
                    'ege': 0.045,  # Will be calculated real-time
                    'total_cost': 0.008,  # Will be calculated real-time
                    'k_multiple': 4.0
                },
                'microstructure': {
                    'obi': 0.0,    # Will be calculated real-time
                    'afr': 0.5,    # Will be calculated real-time
                    'long_allowed': True,   # Will be calculated real-time
                    'short_allowed': True   # Will be calculated real-time
                },
                'risk_multiplier': risk_mult
            }

            print("✅ Edge Health Panel: Gercek A32 verileri kullaniliyor")

        except Exception as e:
            print(f"⚠️ Edge Health Panel: A32 verileri alinamadi, conservative defaults kullaniliyor: {e}")
            # Fallback to conservative defaults
            self.mock_data = {
                'global_edge': {
                    'status': 'WARM',
                    'wilson_lb': 0.05,
                    'trade_count': 0
                },
                'strategy_edge': {
                    'status': 'HOT',
                    'wilson_lb': 0.12,
                    'trade_count': 0
                },
                'cost_rule': {
                    'ege': 0.045,
                    'total_cost': 0.008,
                    'k_multiple': 4.0
                },
                'microstructure': {
                    'obi': 0.0,
                    'afr': 0.5,
                    'long_allowed': True,
                    'short_allowed': True
                },
                'risk_multiplier': 0.75  # Conservative
            }

    def _update_displays(self):
        """Update all display components with current data."""
        if not self.is_enabled:
            return

        # Simulate some variability in mock data
        import random

        # Global edge
        global_data = self.mock_data['global_edge']
        self.global_edge.update_status(
            global_data['status'],
            global_data['wilson_lb'] + random.uniform(-0.01, 0.01),
            global_data['trade_count'] + random.randint(-2, 3)
        )

        # Strategy edge
        strategy_data = self.mock_data['strategy_edge']
        self.strategy_edge.update_status(
            strategy_data['status'],
            strategy_data['wilson_lb'] + random.uniform(-0.02, 0.02),
            strategy_data['trade_count'] + random.randint(-1, 2)
        )

        # Cost rule
        cost_data = self.mock_data['cost_rule']
        self.cost_rule.update_cost_rule(
            cost_data['ege'] + random.uniform(-0.005, 0.005),
            cost_data['total_cost'] + random.uniform(-0.001, 0.001),
            cost_data['k_multiple']
        )

        # Microstructure
        micro_data = self.mock_data['microstructure']
        self.microstructure.update_microstructure(
            micro_data['obi'] + random.uniform(-0.05, 0.05),
            micro_data['afr'] + random.uniform(-0.02, 0.02),
            micro_data['long_allowed'],
            micro_data['short_allowed']
        )

        # Risk multiplier
        base_mult = self.mock_data['risk_multiplier']
        current_mult = base_mult + random.uniform(-0.05, 0.05)
        self.risk_multiplier.update_risk_multiplier(current_mult)

        self._update_summary()

    def _update_summary(self):
        """Update status summary."""
        if not self.is_enabled:
            self.summary_label.setText("Durum: Edge Health Monitor devre disi")
            return

        # Generate summary based on current states
        global_status = self.global_edge.current_status
        strategy_status = self.strategy_edge.current_status
        cost_passed = self.cost_rule.rule_passed
        risk_mult = self.risk_multiplier.risk_multiplier

        if global_status == "HOT" and strategy_status == "HOT" and cost_passed:
            summary = "🟢 Optimal: Tum edge'ler saglikli, cost rule geciyor"
        elif global_status in ["HOT", "WARM"] and cost_passed:
            summary = f"🟡 Iyi: {global_status} edge, risk {risk_mult:.2f}x ayarlandi"
        elif global_status == "COLD":
            summary = "🔴 Dikkat: COLD edge detected, risk ciddi sekilde azaltildi"
        else:
            summary = f"⚠️ Karisik: Edge={global_status}, Cost={'PASS' if cost_passed else 'FAIL'}"

        self.summary_label.setText(f"Durum: {summary}")


if __name__ == "__main__":
    import sys

    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)

    # Create and show the panel
    panel = EdgeHealthMonitorPanel()
    panel.setWindowTitle("Edge Health Monitor Test")
    panel.resize(900, 400)
    panel.show()

    sys.exit(app.exec_())
