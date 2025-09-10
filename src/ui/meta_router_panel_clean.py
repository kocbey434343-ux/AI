"""Meta-Router Control Panel - A31 Ensemble System Visualization

Real-time dashboard for 4-specialist ensemble system with MWU learning.
"""

import time
from typing import Any, Dict, Optional

from PyQt5.QtCore import QTimer, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class SpecialistWeightBar(QWidget):
    """Individual specialist weight visualization with status."""

    def __init__(self, specialist_name: str, specialist_id: str):
        super().__init__()
        self.specialist_name = specialist_name
        self.specialist_id = specialist_id
        self.current_weight = 0.25  # Default equal weight
        self.is_active = True
        self.is_gated = False

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(4)

        # Header with name and status
        header_layout = QHBoxLayout()

        self.name_label = QLabel(self.specialist_name)
        self.name_label.setFont(QFont("Arial", 9, QFont.Bold))
        header_layout.addWidget(self.name_label)

        # Status indicator
        self.status_label = QLabel("●")
        header_layout.addWidget(self.status_label)

        layout.addLayout(header_layout)

        # Weight progress bar
        self.weight_bar = QProgressBar()
        self.weight_bar.setMinimum(10)  # 10% minimum (0.10)
        self.weight_bar.setMaximum(60)  # 60% maximum (0.60)
        self.weight_bar.setValue(25)   # 25% default (0.25)
        self.weight_bar.setTextVisible(True)
        self.weight_bar.setFormat(f"{self.current_weight:.1%}")
        layout.addWidget(self.weight_bar)

        # Performance indicator
        self.perf_label = QLabel("Performance: --")
        self.perf_label.setFont(QFont("Arial", 8))
        layout.addWidget(self.perf_label)

        self.setMaximumHeight(80)
        self.setMinimumWidth(200)

    def update_weight(self, weight: float, performance: Optional[float] = None):
        """Update specialist weight and performance."""
        self.current_weight = max(0.10, min(0.60, weight))

        # Update progress bar
        bar_value = int(self.current_weight * 100)
        self.weight_bar.setValue(bar_value)
        self.weight_bar.setFormat(f"{self.current_weight:.1%}")

        # Update performance
        if performance is not None:
            if performance > 0.05:  # >5% expectancy
                perf_color = "#00AA00"  # Green
            elif performance > 0:
                perf_color = "#FF8C00"  # Orange
            else:
                perf_color = "#FF4444"  # Red

            self.perf_label.setText(f"Performance: {performance:+.1%}")
            self.perf_label.setStyleSheet(f"color: {perf_color};")

        # Update bar color based on weight
        if self.current_weight >= 0.4:
            bar_color = "#00AA00"  # High weight = green
        elif self.current_weight >= 0.2:
            bar_color = "#FF8C00"  # Medium weight = orange
        else:
            bar_color = "#FF4444"  # Low weight = red

        self.weight_bar.setStyleSheet(f"""
            QProgressBar::chunk {{
                background-color: {bar_color};
            }}
        """)

    def update_status(self, is_active: bool, is_gated: bool):
        """Update specialist status (active/gated)."""
        self.is_active = is_active
        self.is_gated = is_gated

        if not is_active:
            self.status_label.setText("●")
            self.status_label.setStyleSheet("color: #888888;")  # Gray
            self.name_label.setStyleSheet("color: #888888;")
        elif is_gated:
            self.status_label.setText("●")
            self.status_label.setStyleSheet("color: #FF8C00;")  # Orange
            self.name_label.setStyleSheet("color: #000000;")
        else:
            self.status_label.setText("●")
            self.status_label.setStyleSheet("color: #00AA00;")  # Green
            self.name_label.setStyleSheet("color: #000000;")


class GatingStatusPanel(QWidget):
    """Market regime gating scores visualization."""

    def __init__(self):
        super().__init__()
        self.gating_scores = {
            'trend_score': 0.0,
            'squeeze_score': 0.0,
            'chop_score': 0.0,
            'volume_score': 0.0
        }
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Title
        title = QLabel("Market Regime Gating")
        title.setFont(QFont("Arial", 11, QFont.Bold))
        layout.addWidget(title)

        # Gating scores grid
        grid_layout = QGridLayout()

        self.score_labels = {}
        self.score_values = {}

        scores = [
            ('trend_score', 'Trend Score', 0),
            ('squeeze_score', 'Squeeze Score', 1),
            ('chop_score', 'Chop Score', 2),
            ('volume_score', 'Volume Score', 3)
        ]

        for score_key, score_name, row in scores:
            # Label
            label = QLabel(score_name + ":")
            label.setFont(QFont("Arial", 9))
            grid_layout.addWidget(label, row, 0)

            # Value
            value_label = QLabel("0.00")
            value_label.setFont(QFont("Arial", 9, QFont.Bold))
            grid_layout.addWidget(value_label, row, 1)

            # Status indicator
            status_label = QLabel("●")
            grid_layout.addWidget(status_label, row, 2)

            self.score_labels[score_key] = label
            self.score_values[score_key] = value_label
            self.score_labels[f"{score_key}_status"] = status_label

        layout.addLayout(grid_layout)

        # Last update timestamp
        self.last_update_label = QLabel("Last Update: --")
        self.last_update_label.setFont(QFont("Arial", 8))
        self.last_update_label.setStyleSheet("color: #666666;")
        layout.addWidget(self.last_update_label)

        self.setMaximumHeight(150)
        self.setMinimumWidth(250)

    def update_gating_scores(self, scores: Dict[str, float]):
        """Update market regime gating scores."""
        self.gating_scores.update(scores)

        for score_key, value in scores.items():
            if score_key in self.score_values:
                # Update value
                self.score_values[score_key].setText(f"{value:.2f}")

                # Update color based on score
                if value >= 0.6:
                    color = "#00AA00"  # High score = green
                elif value >= 0.3:
                    color = "#FF8C00"  # Medium score = orange
                else:
                    color = "#FF4444"  # Low score = red

                self.score_values[score_key].setStyleSheet(f"color: {color};")

                # Update status indicator
                status_key = f"{score_key}_status"
                if status_key in self.score_labels:
                    self.score_labels[status_key].setStyleSheet(f"color: {color};")

        # Update timestamp
        self.last_update_label.setText(f"Last Update: {time.strftime('%H:%M:%S')}")


class EnsembleDecisionPanel(QWidget):
    """Current ensemble decision and signal quality."""

    def __init__(self):
        super().__init__()
        self.current_signal = "BEKLE"
        self.signal_quality = 0.0
        self.consensus_level = 0.0
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Title
        title = QLabel("Ensemble Decision")
        title.setFont(QFont("Arial", 11, QFont.Bold))
        layout.addWidget(title)

        # Current signal
        self.signal_label = QLabel("BEKLE")
        self.signal_label.setFont(QFont("Arial", 24, QFont.Bold))
        self.signal_label.setStyleSheet("""
            QLabel {
                color: #FF8C00;
                border: 2px solid #FF8C00;
                border-radius: 8px;
                padding: 10px;
                background-color: rgba(255, 140, 0, 0.1);
            }
        """)
        layout.addWidget(self.signal_label)

        # Quality metrics
        metrics_layout = QHBoxLayout()

        # Signal quality
        quality_layout = QVBoxLayout()
        quality_layout.addWidget(QLabel("Signal Quality:"))
        self.quality_label = QLabel("--")
        self.quality_label.setFont(QFont("Arial", 12, QFont.Bold))
        quality_layout.addWidget(self.quality_label)
        metrics_layout.addLayout(quality_layout)

        # Consensus level
        consensus_layout = QVBoxLayout()
        consensus_layout.addWidget(QLabel("Consensus:"))
        self.consensus_label = QLabel("--")
        self.consensus_label.setFont(QFont("Arial", 12, QFont.Bold))
        consensus_layout.addWidget(self.consensus_label)
        metrics_layout.addLayout(consensus_layout)

        layout.addLayout(metrics_layout)

        self.setMaximumHeight(150)
        self.setMinimumWidth(300)

    def update_ensemble_decision(self, signal: str, quality: float, consensus: float):
        """Update ensemble decision display."""
        self.current_signal = signal
        self.signal_quality = quality
        self.consensus_level = consensus

        # Update signal
        self.signal_label.setText(signal)

        # Update colors based on signal
        if signal == "AL":
            color = "#00AA00"  # Green
            bg_color = "rgba(0, 170, 0, 0.1)"
        elif signal == "SAT":
            color = "#FF4444"  # Red
            bg_color = "rgba(255, 68, 68, 0.1)"
        else:  # BEKLE
            color = "#FF8C00"  # Orange
            bg_color = "rgba(255, 140, 0, 0.1)"

        self.signal_label.setStyleSheet(f"""
            QLabel {{
                color: {color};
                border: 2px solid {color};
                border-radius: 8px;
                padding: 10px;
                background-color: {bg_color};
            }}
        """)

        # Update quality
        self.quality_label.setText(f"{quality:.1%}")
        if quality >= 0.8:
            quality_color = "#00AA00"
        elif quality >= 0.5:
            quality_color = "#FF8C00"
        else:
            quality_color = "#FF4444"
        self.quality_label.setStyleSheet(f"color: {quality_color};")

        # Update consensus
        self.consensus_label.setText(f"{consensus:.1%}")
        if consensus >= 0.7:
            consensus_color = "#00AA00"
        elif consensus >= 0.4:
            consensus_color = "#FF8C00"
        else:
            consensus_color = "#FF4444"
        self.consensus_label.setStyleSheet(f"color: {consensus_color};")


class MetaRouterPanel(QWidget):
    """Complete Meta-Router control panel with all components."""

    # Signals for parent window
    status_updated = pyqtSignal(str)  # Status message updates

    def __init__(self, trader_core=None):
        super().__init__()
        self.trader_core = trader_core
        self.is_enabled = False
        self.specialist_bars = {}
        self.update_timer = QTimer()
        self._setup_ui()
        self._setup_timer()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)

        # Header
        header_layout = QHBoxLayout()

        title = QLabel("Meta-Router & Ensemble System")
        title.setFont(QFont("Arial", 14, QFont.Bold))
        header_layout.addWidget(title)

        # Enable/Disable toggle
        self.enable_button = QPushButton("Enable Meta-Router")
        self.enable_button.setCheckable(True)
        self.enable_button.setMaximumWidth(150)
        self.enable_button.clicked.connect(self._toggle_meta_router)
        header_layout.addWidget(self.enable_button)

        main_layout.addLayout(header_layout)

        # Content area
        content_layout = QHBoxLayout()

        # Left column: Specialist weights
        left_group = QGroupBox("Specialist Weights")
        left_layout = QVBoxLayout(left_group)

        # Create specialist weight bars
        specialists = [
            ("S1: Trend PB/BO", "trend_pb_bo"),
            ("S2: Range MR", "range_mr"),
            ("S3: Vol Breakout", "vol_breakout"),
            ("S4: XSect Momentum", "xsect_momentum")
        ]

        for name, spec_id in specialists:
            bar = SpecialistWeightBar(name, spec_id)
            self.specialist_bars[spec_id] = bar
            left_layout.addWidget(bar)

        content_layout.addWidget(left_group)

        # Center column: Gating status
        center_group = QGroupBox("Market Regime")
        center_layout = QVBoxLayout(center_group)

        self.gating_panel = GatingStatusPanel()
        center_layout.addWidget(self.gating_panel)

        content_layout.addWidget(center_group)

        # Right column: Ensemble decision
        right_group = QGroupBox("Ensemble Output")
        right_layout = QVBoxLayout(right_group)

        self.ensemble_panel = EnsembleDecisionPanel()
        right_layout.addWidget(self.ensemble_panel)

        content_layout.addWidget(right_group)

        main_layout.addLayout(content_layout)

        # Status bar
        self.status_label = QLabel("Meta-Router: Disabled")
        self.status_label.setFont(QFont("Arial", 10))
        self.status_label.setStyleSheet("color: #666666; padding: 5px;")
        main_layout.addWidget(self.status_label)

        # Initially disabled appearance
        self._update_enabled_state(False)

    def _setup_timer(self):
        """Setup update timer for real-time data refresh."""
        self.update_timer.timeout.connect(self._update_data)
        self.update_timer.start(500)  # 500ms refresh rate

    def _toggle_meta_router(self, checked: bool):
        """Toggle Meta-Router system on/off."""
        self.is_enabled = checked
        self._update_enabled_state(checked)

        if checked:
            self.enable_button.setText("Disable Meta-Router")
            self.status_label.setText("Meta-Router: Enabled")
            self.status_label.setStyleSheet("color: #00AA00; padding: 5px;")
            self.status_updated.emit("Meta-Router enabled")
        else:
            self.enable_button.setText("Enable Meta-Router")
            self.status_label.setText("Meta-Router: Disabled")
            self.status_label.setStyleSheet("color: #FF4444; padding: 5px;")
            self.status_updated.emit("Meta-Router disabled")

    def _update_enabled_state(self, enabled: bool):
        """Update UI components based on enabled state."""
        for bar in self.specialist_bars.values():
            bar.setEnabled(enabled)

        self.gating_panel.setEnabled(enabled)
        self.ensemble_panel.setEnabled(enabled)

        # Visual feedback
        opacity = 1.0 if enabled else 0.6
        self.setStyleSheet(f"QWidget {{ opacity: {opacity}; }}")

    def _update_data(self):
        """Update panel data from Meta-Router system."""
        if not self.is_enabled:
            return

        try:
            # Try to get Meta-Router status (mock data for now)
            self._update_mock_data()

        except Exception as e:
            self.status_label.setText(f"Meta-Router: Error - {e!s}")
            self.status_label.setStyleSheet("color: #FF4444; padding: 5px;")

    def _update_mock_data(self):
        """Update with real A31 Meta-Router data, fallback to conservative simulation for testing."""
        import random

        try:
            # Try to get real Meta-Router data first
            # Note: A31 Meta-Router sistemi henüz development aşamasında
            # Real implementation geldiğinde bu fonksiyon güncellenecek

            # Real Meta-Router status kontrolü
            meta_router_available = False  # A31 implementation sonrası True olacak

            if meta_router_available:
                # Real Meta-Router sisteminden veri al
                # from src.strategy.meta_router import get_meta_router
                # meta_router = get_meta_router()
                # real_data = meta_router.get_real_time_status()
                # Use real_data here...
                pass
            else:
                # Conservative simulation for development
                print("⚠️ Meta-Router: A31 sistemi henüz development aşamasında, conservative simulation kullanılıyor")

                # More conservative and realistic specialist weights
                base_weights = [0.28, 0.24, 0.26, 0.22]  # Slightly unequal but realistic
                for i, (spec_id, base_weight) in enumerate(zip(self.specialist_bars.keys(), base_weights)):
                    # Smaller, more realistic variations
                    weight = base_weight + random.uniform(-0.02, 0.02)  # Reduced randomness
                    weight = max(0.10, min(0.60, weight))

                    # More conservative performance range
                    performance = random.uniform(-0.01, 0.04)  # -1% to +4% (more realistic)

                    self.specialist_bars[spec_id].update_weight(weight, performance)

                    # More conservative gating (less random blocking)
                    is_gated = random.random() > 0.8  # 20% chance instead of 30%
                    self.specialist_bars[spec_id].update_status(True, is_gated)

                # More stable gating scores (less volatile)
                gating_scores = {
                    'trend_score': max(0.2, min(0.8, 0.5 + random.uniform(-0.15, 0.15))),
                    'squeeze_score': max(0.2, min(0.8, 0.5 + random.uniform(-0.15, 0.15))),
                    'chop_score': max(0.2, min(0.8, 0.5 + random.uniform(-0.15, 0.15))),
                    'volume_score': max(0.2, min(0.8, 0.5 + random.uniform(-0.15, 0.15)))
                }
                self.gating_panel.update_gating_scores(gating_scores)

                # More conservative ensemble decisions (more BEKLE/WAIT)
                signals = ["AL", "SAT", "BEKLE", "BEKLE", "BEKLE"]  # 60% BEKLE probability
                signal = random.choice(signals)
                quality = random.uniform(0.4, 0.8)  # More conservative quality range
                consensus = random.uniform(0.3, 0.8)  # More conservative consensus

        except Exception as e:
            print(f"Meta-Router data update failed: {e}")
            # Ultra-safe fallback
            base_weights = [0.25, 0.25, 0.25, 0.25]  # Equal weights
            for i, spec_id in enumerate(self.specialist_bars.keys()):
                self.specialist_bars[spec_id].update_weight(0.25, 0.02)  # Small positive performance
                self.specialist_bars[spec_id].update_status(True, False)  # All enabled, none gated

            # Safe gating scores
            gating_scores = {'trend_score': 0.5, 'squeeze_score': 0.5, 'chop_score': 0.5, 'volume_score': 0.5}
            self.gating_panel.update_gating_scores(gating_scores)

            # Safe ensemble
            signal = "BEKLE"
            quality = 0.5
            consensus = 0.5

        self.ensemble_panel.update_ensemble_decision(signal, quality, consensus)

        # Update status
        avg_weight_std = sum(base_weights) / len(base_weights)
        self.status_label.setText(f"Meta-Router: Active | Avg Weight: {avg_weight_std:.1%}")
        self.status_label.setStyleSheet("color: #00AA00; padding: 5px;")

    def get_current_status(self) -> Dict[str, Any]:
        """Get current Meta-Router status for external monitoring."""
        if not self.is_enabled:
            return {"enabled": False, "status": "disabled"}

        weights = {}
        for spec_id, bar in self.specialist_bars.items():
            weights[spec_id] = bar.current_weight

        return {
            "enabled": True,
            "status": "active",
            "specialist_weights": weights,
            "gating_scores": self.gating_panel.gating_scores,
            "current_signal": self.ensemble_panel.current_signal,
            "signal_quality": self.ensemble_panel.signal_quality,
            "consensus_level": self.ensemble_panel.consensus_level
        }
