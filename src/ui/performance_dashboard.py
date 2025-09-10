#!/usr/bin/env python3
"""
Real-time Performance Dashboard for Trading Bot
Displays advanced metrics and performance insights
"""

import sys

# Add src to path for imports
from pathlib import Path

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QApplication,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.utils.advanced_metrics import get_metrics_collector, get_trading_metrics


class PerformanceDashboard(QWidget):
    """Real-time performance monitoring dashboard"""

    def __init__(self):
        super().__init__()
        self.trading_metrics = get_trading_metrics()
        self.metrics_collector = get_metrics_collector()

        self.init_ui()
        self.setup_timer()

    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("📊 Trading Bot Performance Dashboard")
        self.setGeometry(100, 100, 1200, 800)

        # Main layout
        main_layout = QVBoxLayout()

        # Title
        title = QLabel("🚀 Advanced Performance Monitoring Dashboard")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px;")
        main_layout.addWidget(title)

        # Create splitter for sections
        splitter = QSplitter(Qt.Vertical)

        # System metrics section
        self.create_system_metrics_section(splitter)

        # Trading metrics section
        self.create_trading_metrics_section(splitter)

        # Performance profiles section
        self.create_performance_profiles_section(splitter)

        main_layout.addWidget(splitter)
        self.setLayout(main_layout)

    def create_system_metrics_section(self, parent):
        """Create system metrics display"""
        group = QGroupBox("🖥️ System Performance Metrics")
        layout = QVBoxLayout()

        # Create progress bars for system metrics
        self.cpu_bar = QProgressBar()
        self.cpu_bar.setMaximum(100)
        self.cpu_label = QLabel("CPU: 0%")

        self.memory_bar = QProgressBar()
        self.memory_bar.setMaximum(100)
        self.memory_label = QLabel("Memory: 0%")

        self.disk_bar = QProgressBar()
        self.disk_bar.setMaximum(100)
        self.disk_label = QLabel("Disk: 0%")

        # Layout system metrics
        metrics_layout = QHBoxLayout()

        cpu_layout = QVBoxLayout()
        cpu_layout.addWidget(self.cpu_label)
        cpu_layout.addWidget(self.cpu_bar)

        memory_layout = QVBoxLayout()
        memory_layout.addWidget(self.memory_label)
        memory_layout.addWidget(self.memory_bar)

        disk_layout = QVBoxLayout()
        disk_layout.addWidget(self.disk_label)
        disk_layout.addWidget(self.disk_bar)

        metrics_layout.addLayout(cpu_layout)
        metrics_layout.addLayout(memory_layout)
        metrics_layout.addLayout(disk_layout)

        layout.addLayout(metrics_layout)
        group.setLayout(layout)
        parent.addWidget(group)

    def create_trading_metrics_section(self, parent):
        """Create trading performance metrics"""
        group = QGroupBox("⚡ Trading Performance Metrics")
        layout = QVBoxLayout()

        # Trading stats labels
        self.trade_count_label = QLabel("Total Trades: 0")
        self.avg_latency_label = QLabel("Avg Latency: 0ms")
        self.success_rate_label = QLabel("Success Rate: 0%")
        self.last_trade_label = QLabel("Last Trade: N/A")

        stats_layout = QHBoxLayout()
        stats_layout.addWidget(self.trade_count_label)
        stats_layout.addWidget(self.avg_latency_label)
        stats_layout.addWidget(self.success_rate_label)
        stats_layout.addWidget(self.last_trade_label)

        layout.addLayout(stats_layout)

        # Latency table
        self.latency_table = QTableWidget()
        self.latency_table.setColumnCount(3)
        self.latency_table.setHorizontalHeaderLabels(["Time", "Latency (ms)", "Trade Type"])
        self.latency_table.setMaximumHeight(200)
        layout.addWidget(self.latency_table)

        group.setLayout(layout)
        parent.addWidget(group)

    def create_performance_profiles_section(self, parent):
        """Create performance profiling display"""
        group = QGroupBox("🔍 Function Performance Profiles")
        layout = QVBoxLayout()

        # Performance profiles table
        self.profiles_table = QTableWidget()
        self.profiles_table.setColumnCount(5)
        self.profiles_table.setHorizontalHeaderLabels([
            "Function", "Execution (ms)", "Memory (MB)", "CPU %", "Calls"
        ])
        layout.addWidget(self.profiles_table)

        group.setLayout(layout)
        parent.addWidget(group)

    def setup_timer(self):
        """Setup auto-refresh timer"""
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_dashboard)
        self.timer.start(1000)  # Update every second

    def update_dashboard(self):
        """Update all dashboard metrics"""
        self.update_system_metrics()
        self.update_trading_metrics()
        self.update_performance_profiles()

    def update_system_metrics(self):
        """Update system performance bars"""
        try:
            # Get latest system metrics from collector
            system_metrics = self.metrics_collector.get_latest_metrics()

            if system_metrics:
                cpu_usage = system_metrics.get('cpu_percent', 0)
                memory_usage = system_metrics.get('memory_percent', 0)
                disk_usage = system_metrics.get('disk_percent', 0)

                self.cpu_bar.setValue(int(cpu_usage))
                self.cpu_label.setText(f"CPU: {cpu_usage:.1f}%")

                self.memory_bar.setValue(int(memory_usage))
                self.memory_label.setText(f"Memory: {memory_usage:.1f}%")

                self.disk_bar.setValue(int(disk_usage))
                self.disk_label.setText(f"Disk: {disk_usage:.1f}%")

        except Exception:
            pass  # Graceful degradation

    def update_trading_metrics(self):
        """Update trading performance metrics"""
        try:
            latencies = list(self.trading_metrics.trade_latencies)

            # Update stats labels
            self.trade_count_label.setText(f"Total Trades: {len(latencies)}")

            if latencies:
                avg_latency = sum(l['latency_ms'] for l in latencies) / len(latencies)
                self.avg_latency_label.setText(f"Avg Latency: {avg_latency:.1f}ms")

                # Calculate success rate
                successful = sum(1 for l in latencies if 'success' in l['trade_type'])
                success_rate = (successful / len(latencies)) * 100 if latencies else 0
                self.success_rate_label.setText(f"Success Rate: {success_rate:.1f}%")

                # Last trade info
                last_trade = latencies[-1]
                last_time = last_trade['timestamp'].strftime("%H:%M:%S")
                self.last_trade_label.setText(f"Last Trade: {last_time}")

                # Update latency table (show last 10)
                recent_latencies = latencies[-10:]
                self.latency_table.setRowCount(len(recent_latencies))

                for i, latency in enumerate(recent_latencies):
                    time_str = latency['timestamp'].strftime("%H:%M:%S")
                    self.latency_table.setItem(i, 0, QTableWidgetItem(time_str))
                    self.latency_table.setItem(i, 1, QTableWidgetItem(f"{latency['latency_ms']:.1f}"))
                    self.latency_table.setItem(i, 2, QTableWidgetItem(latency['trade_type']))

        except Exception:
            pass  # Graceful degradation

    def update_performance_profiles(self):
        """Update function performance profiles"""
        try:
            profiles = list(self.metrics_collector.performance_profiles)

            # Group by function name and aggregate
            function_stats = {}
            for profile in profiles:
                func_name = profile.function_name
                if func_name not in function_stats:
                    function_stats[func_name] = {
                        'total_time': 0,
                        'total_memory': 0,
                        'total_cpu': 0,
                        'call_count': 0
                    }

                stats = function_stats[func_name]
                stats['total_time'] += profile.execution_time_ms
                stats['total_memory'] += profile.memory_delta_mb
                stats['total_cpu'] += profile.cpu_percent
                stats['call_count'] += profile.call_count

            # Update table
            self.profiles_table.setRowCount(len(function_stats))

            for i, (func_name, stats) in enumerate(function_stats.items()):
                calls = stats['call_count']
                avg_time = stats['total_time'] / calls if calls > 0 else 0
                avg_memory = stats['total_memory'] / calls if calls > 0 else 0
                avg_cpu = stats['total_cpu'] / calls if calls > 0 else 0

                # Shorten function name for display
                display_name = func_name.split('.')[-1] if '.' in func_name else func_name

                self.profiles_table.setItem(i, 0, QTableWidgetItem(display_name))
                self.profiles_table.setItem(i, 1, QTableWidgetItem(f"{avg_time:.2f}"))
                self.profiles_table.setItem(i, 2, QTableWidgetItem(f"{avg_memory:.3f}"))
                self.profiles_table.setItem(i, 3, QTableWidgetItem(f"{avg_cpu:.1f}"))
                self.profiles_table.setItem(i, 4, QTableWidgetItem(str(calls)))

        except Exception:
            pass  # Graceful degradation


def main():
    """Main function to run the performance dashboard"""
    app = QApplication(sys.argv)

    # Start metrics collection
    collector = get_metrics_collector()
    collector.start_collection()

    # Create and show dashboard
    dashboard = PerformanceDashboard()
    dashboard.show()

    try:
        sys.exit(app.exec_())
    finally:
        # Stop metrics collection on exit
        collector.stop_collection()


if __name__ == "__main__":
    main()
