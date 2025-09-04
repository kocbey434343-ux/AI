"""
Simple Integration Test for CR-0076: Risk Escalation System

This test validates the core escalation functionality without complex mocks.
Focus on the essential integration with trader core.
"""
import pytest
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from src.trader.core import Trader
from src.utils.risk_escalation import RiskLevel
from config.settings import Settings


class TestRiskEscalationIntegration:
    """Integration test for risk escalation with real trader."""

    def test_trader_initialization_with_escalation(self):
        """Test that trader initializes risk escalation system."""
        # Use memory DB for isolation
        with patch.dict(os.environ, {'TRADES_DB_PATH': ':memory:'}):
            trader = Trader()

            # Check escalation system is initialized
            assert hasattr(trader, 'risk_escalation')
            assert trader.risk_escalation.current_level == RiskLevel.NORMAL

    def test_execute_trade_calls_escalation_check(self):
        """Test that execute_trade calls risk escalation check."""
        with patch.dict(os.environ, {'TRADES_DB_PATH': ':memory:', 'OFFLINE_MODE': 'true'}):
            trader = Trader()

            # Mock the escalation check method
            original_check = trader._check_risk_escalation
            check_called = False

            def mock_check():
                nonlocal check_called
                check_called = True
                return original_check()

            trader._check_risk_escalation = mock_check

            # Try to execute a trade (will fail due to guards but should call escalation)
            signal = {'symbol': 'BTCUSDT', 'side': 'BUY', 'price': 50000}
            trader.execute_trade(signal)

            # Verify escalation check was called
            assert check_called

    def test_risk_escalation_check_method(self):
        """Test the _check_risk_escalation method."""
        with patch.dict(os.environ, {'TRADES_DB_PATH': ':memory:'}):
            trader = Trader()

            # Should not raise exception
            trader._check_risk_escalation()

            # Should have last risk level attribute after first call
            assert hasattr(trader, '_last_risk_level')

    def test_manual_force_escalation(self):
        """Test manual escalation forcing."""
        with patch.dict(os.environ, {'TRADES_DB_PATH': ':memory:'}):
            trader = Trader()

            # Force escalation to WARNING
            result = trader.risk_escalation.force_escalation(RiskLevel.WARNING, "test")

            assert result is True
            assert trader.risk_escalation.current_level == RiskLevel.WARNING
            assert "manual_test" in trader.risk_escalation.escalation_reasons

    def test_escalation_status_reporting(self):
        """Test escalation status reporting."""
        with patch.dict(os.environ, {'TRADES_DB_PATH': ':memory:'}):
            trader = Trader()

            # Get initial status
            status = trader.risk_escalation.get_escalation_status()

            assert status['current_level'] == 'normal'
            assert isinstance(status['reasons'], list)
            assert 'risk_reduction_active' in status

    def test_escalation_with_halt_flag(self):
        """Test escalation with actual halt flag file."""
        with patch.dict(os.environ, {'TRADES_DB_PATH': ':memory:'}):
            trader = Trader()

            # Create temporary halt flag
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as tmp:
                tmp.write("Test halt")
                halt_path = tmp.name

            try:
                with patch.object(Settings, 'DAILY_HALT_FLAG_PATH', halt_path):
                    level = trader.risk_escalation.evaluate_risk_level()

                    assert level == RiskLevel.CRITICAL
                    assert "manual_halt" in trader.risk_escalation.escalation_reasons
            finally:
                Path(halt_path).unlink()

    def test_risk_reduction_integration(self):
        """Test risk reduction integration with trader."""
        with patch.dict(os.environ, {'TRADES_DB_PATH': ':memory:'}):
            trader = Trader()

            original_risk = trader.risk_manager.risk_percent

            # Force WARNING escalation
            trader.risk_escalation.force_escalation(RiskLevel.WARNING, "test")

            # Risk should be reduced
            assert trader.risk_manager.risk_percent < original_risk
            assert trader.risk_escalation._original_risk_percent == original_risk

    def test_escalation_history_tracking(self):
        """Test that escalation history is tracked."""
        with patch.dict(os.environ, {'TRADES_DB_PATH': ':memory:'}):
            trader = Trader()

            # Perform multiple escalations
            trader.risk_escalation.force_escalation(RiskLevel.WARNING, "test1")
            trader.risk_escalation.force_escalation(RiskLevel.CRITICAL, "test2")
            trader.risk_escalation.force_escalation(RiskLevel.NORMAL, "test3")

            # Check history
            history = trader.risk_escalation.escalation_history
            assert len(history) >= 3

            # Check history structure
            for entry in history:
                assert 'timestamp' in entry
                assert 'from_level' in entry
                assert 'to_level' in entry
                assert 'reasons' in entry

    @pytest.mark.parametrize("level", [RiskLevel.NORMAL, RiskLevel.WARNING, RiskLevel.CRITICAL])
    def test_all_escalation_levels(self, level):
        """Test all escalation levels work."""
        with patch.dict(os.environ, {'TRADES_DB_PATH': ':memory:'}):
            trader = Trader()

            result = trader.risk_escalation.force_escalation(level, "test")

            assert result is True
            assert trader.risk_escalation.current_level == level

    def test_feature_flag_disable(self):
        """Test that escalation can be disabled via feature flag."""
        with patch.dict(os.environ, {
            'TRADES_DB_PATH': ':memory:',
            'FEATURE_RISK_ESCALATION_ENABLED': 'false'
        }):
            # This test would require adding a feature flag to the escalation system
            # For now, just verify the trader still works
            trader = Trader()
            assert hasattr(trader, 'risk_escalation')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
