"""
Test CR-0076: Risk Kill-Switch Escalation Unification

Tests the unified risk escalation system that coordinates all risk controls:
- Daily loss escalation
- Consecutive loss escalation
- Latency/slippage anomaly escalation
- Manual halt flag escalation
- Risk reduction coordination
- Recovery mechanisms
"""
import pytest
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch

from src.utils.risk_escalation import RiskEscalation, RiskLevel, init_risk_escalation
from config.settings import Settings


class TestRiskEscalation:
    """Test unified risk escalation system."""

    def setup_method(self):
        """Setup for each test."""
        # Ensure no halt flag exists at start of test
        halt_flag_path = Path(Settings.DAILY_HALT_FLAG_PATH)
        if halt_flag_path.exists():
            halt_flag_path.unlink()

        self.mock_trader = Mock()
        self.mock_trader.logger = Mock()

        # Create a proper mock object that tracks attribute changes
        self.mock_risk_manager = Mock()
        self.mock_risk_manager.risk_percent = 2.0
        self.mock_trader.risk_manager = self.mock_risk_manager

        self.mock_trader.trade_store = Mock()
        self.mock_trader.trade_store.guard_events = Mock()

        # Mock recent performance stats to return valid values
        def mock_stats_method(self_param, window=30):
            return {'avg_latency_ms': 0.0, 'avg_slippage_bps': 0.0}

        self.mock_trader.recent_latency_slippage_stats = Mock(side_effect=mock_stats_method)

        self.escalation = RiskEscalation(self.mock_trader)

    def test_init_normal_level(self):
        """Test initialization starts at NORMAL level."""
        assert self.escalation.current_level == RiskLevel.NORMAL
        assert len(self.escalation.escalation_reasons) == 0
        assert self.escalation._original_risk_percent is None

    def test_manual_halt_escalation(self):
        """Test manual halt flag triggers CRITICAL escalation."""
        # Create temp halt flag file
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            halt_path = tmp.name
            tmp.write(b"Manual halt test")

        with patch.object(Settings, 'DAILY_HALT_FLAG_PATH', halt_path):
            level = self.escalation.evaluate_risk_level()
            assert level == RiskLevel.CRITICAL
            assert "manual_halt" in self.escalation.escalation_reasons

        # Cleanup
        Path(halt_path).unlink()

    def test_daily_loss_warning_escalation(self):
        """Test daily loss triggers WARNING level."""
        # Mock daily loss at 70% of limit (WARNING threshold)
        warning_threshold = Settings.MAX_DAILY_LOSS_PCT * 0.7  # 2.1%
        self.mock_trader.trade_store.daily_realized_pnl_pct.return_value = -warning_threshold
        self.mock_trader.trade_store.consecutive_losses.return_value = 0

        # Ensure no halt flag exists
        with patch.object(Settings, 'DAILY_HALT_FLAG_PATH', '/nonexistent/halt.flag'):
            level = self.escalation.evaluate_risk_level()
            assert level == RiskLevel.WARNING
            assert "daily_loss_warning" in self.escalation.escalation_reasons

    def test_daily_loss_critical_escalation(self):
        """Test daily loss triggers CRITICAL level."""
        # Mock daily loss at limit (CRITICAL threshold)
        self.mock_trader.trade_store.daily_realized_pnl_pct.return_value = -Settings.MAX_DAILY_LOSS_PCT
        self.mock_trader.trade_store.consecutive_losses.return_value = 0

        # Ensure no halt flag exists
        with patch.object(Settings, 'DAILY_HALT_FLAG_PATH', '/nonexistent/halt.flag'):
            level = self.escalation.evaluate_risk_level()
            assert level == RiskLevel.CRITICAL
            assert "daily_loss_critical" in self.escalation.escalation_reasons

    def test_consecutive_losses_escalation(self):
        """Test consecutive losses trigger escalation."""
        # Mock consecutive losses at limit
        self.mock_trader.trade_store.daily_realized_pnl_pct.return_value = 0.0
        self.mock_trader.trade_store.consecutive_losses.return_value = Settings.MAX_CONSECUTIVE_LOSSES

        level = self.escalation.evaluate_risk_level()
        assert level == RiskLevel.CRITICAL
        assert "consecutive_losses_critical" in self.escalation.escalation_reasons

    def test_latency_anomaly_escalation(self):
        """Test latency anomaly triggers escalation."""
        self.mock_trader.trade_store.daily_realized_pnl_pct.return_value = 0.0
        self.mock_trader.trade_store.consecutive_losses.return_value = 0

        # Mock high latency
        with patch.object(self.escalation, '_get_recent_performance_stats') as mock_stats:
            mock_stats.return_value = {
                'avg_latency_ms': Settings.LATENCY_ANOMALY_MS + 100,
                'avg_slippage_bps': 0
            }

            level = self.escalation.evaluate_risk_level()
            assert level == RiskLevel.WARNING
            assert "latency_warning" in self.escalation.escalation_reasons

    def test_slippage_anomaly_escalation(self):
        """Test slippage anomaly triggers escalation."""
        self.mock_trader.trade_store.daily_realized_pnl_pct.return_value = 0.0
        self.mock_trader.trade_store.consecutive_losses.return_value = 0

        # Mock high slippage
        with patch.object(self.escalation, '_get_recent_performance_stats') as mock_stats:
            mock_stats.return_value = {
                'avg_latency_ms': 0,
                'avg_slippage_bps': Settings.SLIPPAGE_ANOMALY_BPS + 10
            }

            level = self.escalation.evaluate_risk_level()
            assert level == RiskLevel.WARNING
            assert "slippage_warning" in self.escalation.escalation_reasons

    def test_risk_reduction_warning(self):
        """Test WARNING level applies risk reduction."""
        original_risk = 2.0

        # Create a real-like object that tracks attribute assignments
        class MockRiskManager:
            def __init__(self):
                self.risk_percent = original_risk

        self.mock_trader.risk_manager = MockRiskManager()
        self.mock_trader.trade_store.daily_realized_pnl_pct.return_value = -2.1  # WARNING
        self.mock_trader.trade_store.consecutive_losses.return_value = 0

        # Override Settings to ensure expected threshold and recreate escalation
        with patch.object(Settings, 'MAX_DAILY_LOSS_PCT', 3.0):
            # Recreate escalation with patched settings
            escalation = RiskEscalation(self.mock_trader)

            level = escalation.evaluate_risk_level()

            # Check that WARNING level was triggered
            assert level == RiskLevel.WARNING
            assert "daily_loss_warning" in escalation.escalation_reasons

            # Check risk was reduced
            expected_risk = original_risk * Settings.ANOMALY_RISK_MULT
            assert abs(self.mock_trader.risk_manager.risk_percent - expected_risk) < 0.001
            assert abs(escalation._original_risk_percent - original_risk) < 0.001

    def test_risk_halt_critical(self):
        """Test CRITICAL level creates halt flag."""
        self.mock_trader.trade_store.daily_realized_pnl_pct.return_value = -Settings.MAX_DAILY_LOSS_PCT
        self.mock_trader.trade_store.consecutive_losses.return_value = 0

        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            halt_path = tmp.name

        # Remove the temp file so we can test creation
        Path(halt_path).unlink()

        with patch.object(Settings, 'DAILY_HALT_FLAG_PATH', halt_path):
            self.escalation.evaluate_risk_level()

            # Check halt flag was created
            assert Path(halt_path).exists()

            # Check more aggressive risk reduction
            expected_risk = (
                self.escalation._original_risk_percent or 2.0
            ) * Settings.ANOMALY_RISK_MULT * 0.5
            assert abs(self.mock_trader.risk_manager.risk_percent - expected_risk) < 0.001

        # Cleanup
        Path(halt_path).unlink(missing_ok=True)

    def test_recovery_to_normal(self):
        """Test recovery to NORMAL restores risk."""
        # First escalate to WARNING
        original_risk = 2.0

        with patch.object(Settings, 'MAX_DAILY_LOSS_PCT', 3.0):
            self.escalation = RiskEscalation(self.mock_trader)
            self.mock_trader.risk_manager.risk_percent = original_risk
            self.mock_trader.trade_store.daily_realized_pnl_pct.return_value = -2.1
            self.mock_trader.trade_store.consecutive_losses.return_value = 0

            self.escalation.evaluate_risk_level()
            assert self.escalation.current_level == RiskLevel.WARNING

            # Then recover to NORMAL
            self.mock_trader.trade_store.daily_realized_pnl_pct.return_value = 0.0

            level = self.escalation.evaluate_risk_level()
            assert level == RiskLevel.NORMAL
            assert abs(self.mock_trader.risk_manager.risk_percent - original_risk) < 0.001
            assert self.escalation._original_risk_percent is None

    def test_force_escalation(self):
        """Test manual force escalation."""
        result = self.escalation.force_escalation(RiskLevel.CRITICAL, "test_force")
        assert result is True
        assert self.escalation.current_level == RiskLevel.CRITICAL
        assert "manual_test_force" in self.escalation.escalation_reasons

    def test_escalation_status(self):
        """Test escalation status reporting."""
        self.escalation.current_level = RiskLevel.WARNING
        self.escalation.escalation_reasons = {"daily_loss_warning"}
        self.escalation._original_risk_percent = 2.0

        status = self.escalation.get_escalation_status()

        assert status['current_level'] == 'warning'
        assert status['reasons'] == ['daily_loss_warning']
        assert status['risk_reduction_active'] is True
        assert status['original_risk'] == 2.0

    def test_escalation_history(self):
        """Test escalation history tracking."""
        # Force multiple escalations
        self.escalation.force_escalation(RiskLevel.WARNING, "test1")
        self.escalation.force_escalation(RiskLevel.CRITICAL, "test2")
        self.escalation.force_escalation(RiskLevel.NORMAL, "test3")

        assert len(self.escalation.escalation_history) == 3
        assert self.escalation.escalation_history[0]['to_level'] == 'warning'
        assert self.escalation.escalation_history[1]['to_level'] == 'critical'
        assert self.escalation.escalation_history[2]['to_level'] == 'normal'

    def test_history_bounded(self):
        """Test escalation history is bounded."""
        # Force many escalations to test history trimming
        for i in range(RiskEscalation.MAX_HISTORY_SIZE + 10):
            self.escalation.force_escalation(RiskLevel.WARNING, f"test{i}")

        assert len(self.escalation.escalation_history) <= RiskEscalation.MAX_HISTORY_SIZE

    def test_metrics_error_handling(self):
        """Test error handling when metrics fail."""
        # Mock trade_store to raise exception
        self.mock_trader.trade_store.daily_realized_pnl_pct.side_effect = Exception("DB Error")

        # Make sure no halt flag exists
        with patch.object(Settings, 'DAILY_HALT_FLAG_PATH', '/nonexistent/halt.flag'):
            level = self.escalation.evaluate_risk_level()
            # Should return current level on error
            assert level == RiskLevel.NORMAL

    def test_performance_stats_fallback(self):
        """Test performance stats fallback methods."""
        # Mock fallback attributes
        self.mock_trader.recent_open_latencies = [100, 200, 300]
        self.mock_trader.recent_entry_slippage_bps = [10, 20, 30]

        stats = self.escalation._get_recent_performance_stats()
        assert stats['avg_latency_ms'] == 200.0
        assert stats['avg_slippage_bps'] == 20.0

    def test_guard_events_integration(self):
        """Test guard events are recorded for critical escalation."""
        self.mock_trader.trade_store.daily_realized_pnl_pct.return_value = -Settings.MAX_DAILY_LOSS_PCT
        self.mock_trader.trade_store.consecutive_losses.return_value = 0
        self.mock_trader.trade_store.guard_events.record_guard_event_simple = Mock()

        self.escalation.evaluate_risk_level()

        # Verify guard event was recorded
        self.mock_trader.trade_store.guard_events.record_guard_event_simple.assert_called()


class TestRiskEscalationIntegration:
    """Integration tests with trader instance."""

    def test_init_risk_escalation(self):
        """Test initialization with real trader."""
        mock_trader = Mock()
        mock_trader.logger = Mock()

        result = init_risk_escalation(mock_trader)

        assert hasattr(mock_trader, 'risk_escalation')
        assert isinstance(mock_trader.risk_escalation, RiskEscalation)
        assert result is mock_trader.risk_escalation

    def test_init_risk_escalation_idempotent(self):
        """Test initialization is idempotent."""
        mock_trader = Mock()
        mock_trader.logger = Mock()
        mock_trader.risk_escalation = Mock()

        original_escalation = mock_trader.risk_escalation
        result = init_risk_escalation(mock_trader)

        # Should return existing instance
        assert result is original_escalation

    @pytest.mark.parametrize("risk_level,expected_actions", [
        (RiskLevel.NORMAL, "no_action"),
        (RiskLevel.WARNING, "risk_reduction"),
        (RiskLevel.CRITICAL, "halt_flag"),
        (RiskLevel.EMERGENCY, "close_all"),
    ])
    def test_escalation_action_matrix(self, risk_level, expected_actions):
        """Test different risk levels trigger appropriate actions."""
        mock_trader = Mock()
        mock_trader.logger = Mock()
        mock_trader.risk_manager = Mock()
        mock_trader.risk_manager.risk_percent = 2.0
        mock_trader.close_all_positions = Mock() if risk_level == RiskLevel.EMERGENCY else None

        escalation = RiskEscalation(mock_trader)
        escalation.force_escalation(risk_level, "test")

        if expected_actions == "risk_reduction":
            assert escalation._original_risk_percent is not None
        elif expected_actions == "halt_flag":
            # Would create halt flag (tested separately)
            assert escalation.current_level == RiskLevel.CRITICAL
        elif expected_actions == "close_all":
            if mock_trader.close_all_positions:
                mock_trader.close_all_positions.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
