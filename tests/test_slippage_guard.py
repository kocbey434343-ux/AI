"""
Tests for CR-0065: Slippage Guard & Abort Protection

Test Coverage:
- Slippage calculation (BUY/SELL scenarios)
- Threshold detection and violation handling
- Policy configuration (ABORT/REDUCE)
- Order execution integration
- Metrics and logging
- Edge cases and error conditions
"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

from src.utils.slippage_guard import (
    SlippageGuard, get_slippage_guard, validate_order_slippage,
    calculate_slippage_bps
)
from src.trader.execution import OrderContext


class TestSlippageCalculation:
    """Test slippage calculation logic"""

    def setup_method(self):
        """Setup fresh guard instance for each test"""
        self.guard = SlippageGuard()

    def test_buy_slippage_calculation(self):
        """BUY order slippage calculation"""
        # BUY: higher fill price = negative slippage (unfavorable)
        expected_price = 50000.0
        fill_price = 50100.0  # 100 USD higher
        side = "BUY"

        slippage_bps = self.guard.calculate_slippage_bps(expected_price, fill_price, side)

        # (50100 - 50000) / 50000 * 10000 = 20 bps
        expected_bps = 20.0
        assert abs(slippage_bps - expected_bps) < 0.1
        assert slippage_bps > 0  # Unfavorable for BUY

    def test_sell_slippage_calculation(self):
        """SELL order slippage calculation"""
        # SELL: lower fill price = negative slippage (unfavorable)
        expected_price = 50000.0
        fill_price = 49900.0  # 100 USD lower
        side = "SELL"

        slippage_bps = self.guard.calculate_slippage_bps(expected_price, fill_price, side)

        # (50000 - 49900) / 50000 * 10000 = 20 bps
        expected_bps = 20.0
        assert abs(slippage_bps - expected_bps) < 0.1
        assert slippage_bps > 0  # Unfavorable for SELL

    def test_favorable_slippage_buy(self):
        """Favorable slippage for BUY (lower fill price)"""
        expected_price = 50000.0
        fill_price = 49950.0  # 50 USD lower - favorable
        side = "BUY"

        slippage_bps = self.guard.calculate_slippage_bps(expected_price, fill_price, side)

        # (49950 - 50000) / 50000 * 10000 = -10 bps (favorable)
        assert slippage_bps < 0
        assert abs(slippage_bps - (-10.0)) < 0.1

    def test_zero_slippage(self):
        """Perfect execution - no slippage"""
        expected_price = 50000.0
        fill_price = 50000.0

        buy_slippage = self.guard.calculate_slippage_bps(expected_price, fill_price, "BUY")
        sell_slippage = self.guard.calculate_slippage_bps(expected_price, fill_price, "SELL")

        assert buy_slippage == 0.0
        assert sell_slippage == 0.0

    def test_invalid_prices(self):
        """Invalid price inputs should return 0"""
        assert self.guard.calculate_slippage_bps(0, 100, "BUY") == 0.0
        assert self.guard.calculate_slippage_bps(-100, 100, "BUY") == 0.0
        assert self.guard.calculate_slippage_bps(100, 0, "SELL") == 0.0


class TestSlippageThreshold:
    """Test slippage threshold detection"""

    def setup_method(self):
        self.guard = SlippageGuard()

    @patch('src.utils.slippage_guard.Settings.MAX_SLIPPAGE_BPS', 50.0)  # 0.5% threshold
    def test_threshold_violation_detected(self):
        """Slippage exceeding threshold should be detected"""
        expected_price = 50000.0
        fill_price = 50300.0  # 60 bps slippage
        side = "BUY"
        symbol = "BTCUSDT"

        is_violation, slippage_bps, reason = self.guard.check_slippage_threshold(
            expected_price, fill_price, side, symbol
        )

        assert is_violation is True
        assert abs(slippage_bps - 60.0) < 0.1
        assert "60.0bps_exceeds_50.0bps" in reason
        assert self.guard.violation_count == 1
        assert self.guard.violations_by_symbol[symbol] == 1

    @patch('src.utils.slippage_guard.Settings.MAX_SLIPPAGE_BPS', 50.0)
    def test_threshold_not_violated(self):
        """Slippage within threshold should pass"""
        expected_price = 50000.0
        fill_price = 50200.0  # 40 bps slippage (within 50 bps threshold)
        side = "BUY"
        symbol = "BTCUSDT"

        is_violation, slippage_bps, reason = self.guard.check_slippage_threshold(
            expected_price, fill_price, side, symbol
        )

        assert is_violation is False
        assert abs(slippage_bps - 40.0) < 0.1
        assert reason == ""
        assert self.guard.violation_count == 0

    @patch('src.utils.slippage_guard.Settings.MAX_SLIPPAGE_BPS', 30.0)
    def test_favorable_slippage_within_threshold(self):
        """Favorable slippage should always pass"""
        expected_price = 50000.0
        fill_price = 49800.0  # Favorable slippage for BUY
        side = "BUY"
        symbol = "BTCUSDT"

        is_violation, slippage_bps, reason = self.guard.check_slippage_threshold(
            expected_price, fill_price, side, symbol
        )

        assert is_violation is False
        assert slippage_bps < 0  # Favorable
        assert self.guard.violation_count == 0


class TestSlippagePolicy:
    """Test slippage policy configuration and handling"""

    def setup_method(self):
        self.guard = SlippageGuard()

    @patch('src.utils.slippage_guard.Settings.SLIPPAGE_GUARD_POLICY', 'ABORT')
    def test_abort_policy(self):
        """ABORT policy should cancel order"""
        symbol = "BTCUSDT"
        slippage_bps = 75.0
        quantity = 0.1

        action, new_qty = self.guard.handle_slippage_violation(
            symbol, slippage_bps, quantity
        )

        assert action == "ABORT"
        assert new_qty is None

    @patch('src.utils.slippage_guard.Settings.SLIPPAGE_GUARD_POLICY', 'REDUCE')
    @patch('src.utils.slippage_guard.Settings.SLIPPAGE_REDUCTION_FACTOR', 0.5)
    def test_reduce_policy(self):
        """REDUCE policy should reduce quantity"""
        symbol = "BTCUSDT"
        slippage_bps = 75.0
        quantity = 0.1

        action, new_qty = self.guard.handle_slippage_violation(
            symbol, slippage_bps, quantity
        )

        assert action == "REDUCE"
        assert new_qty == 0.05  # 50% reduction

    @patch('src.utils.slippage_guard.Settings.SLIPPAGE_GUARD_POLICY', 'INVALID')
    def test_invalid_policy_defaults_to_abort(self):
        """Invalid policy should default to ABORT"""
        policy = self.guard.get_slippage_policy()
        assert policy == "ABORT"


class TestOrderExecutionValidation:
    """Test full order execution validation"""

    def setup_method(self):
        self.guard = SlippageGuard()

    @patch('src.utils.slippage_guard.Settings.MAX_SLIPPAGE_BPS', 50.0)
    @patch('src.utils.slippage_guard.Settings.SLIPPAGE_GUARD_POLICY', 'ABORT')
    def test_order_validation_abort(self):
        """Order validation should trigger abort on high slippage"""
        order_context = {
            'symbol': 'BTCUSDT',
            'side': 'BUY',
            'expected_price': 50000.0,
            'fill_price': 50400.0,  # 80 bps slippage
            'quantity': 0.1,
            'order_id': '12345'
        }

        is_safe, corrective_action = self.guard.validate_order_execution(order_context)

        assert is_safe is False
        assert corrective_action['action'] == 'ABORT'
        assert corrective_action['slippage_bps'] > 70  # ~80 bps
        assert corrective_action['original_qty'] == 0.1

    @patch('src.utils.slippage_guard.Settings.MAX_SLIPPAGE_BPS', 100.0)
    def test_order_validation_safe(self):
        """Order validation should pass for normal slippage"""
        order_context = {
            'symbol': 'BTCUSDT',
            'side': 'BUY',
            'expected_price': 50000.0,
            'fill_price': 50200.0,  # 40 bps slippage
            'quantity': 0.1
        }

        is_safe, corrective_action = self.guard.validate_order_execution(order_context)

        assert is_safe is True
        assert corrective_action is None

    def test_incomplete_order_context(self):
        """Incomplete order context should be rejected safely"""
        order_context = {
            'symbol': 'BTCUSDT',
            'side': 'BUY'
            # Missing required fields
        }

        is_safe, corrective_action = self.guard.validate_order_execution(order_context)

        assert is_safe is False
        assert corrective_action['action'] == 'ABORT'
        assert corrective_action['reason'] == 'incomplete_context'


class TestSlippageGuardMetrics:
    """Test metrics and reporting"""

    def setup_method(self):
        self.guard = SlippageGuard()

    def test_violation_metrics(self):
        """Violation metrics should be tracked correctly"""
        # Trigger some violations
        self.guard.check_slippage_threshold(50000, 50300, "BUY", "BTCUSDT")
        self.guard.check_slippage_threshold(51000, 51400, "BUY", "ETHUSDT")
        # SELL icin: daha dusuk fill fiyati olumsuzdur; esigi asacak sekilde ayarla (~57.7 bps)
        self.guard.check_slippage_threshold(52000, 51700, "SELL", "BTCUSDT")

        metrics = self.guard.get_metrics()

        assert metrics['violation_count'] == 3
        assert metrics['violations_by_symbol']['BTCUSDT'] == 2
        assert metrics['violations_by_symbol']['ETHUSDT'] == 1
        assert metrics['total_slippage_bps'] > 0
        assert metrics['avg_violation_slippage'] > 0
        assert metrics['guard_name'] == 'slippage'

    def test_daily_reset(self):
        """Daily reset should clear metrics"""
        # Add some violations
        self.guard.check_slippage_threshold(50000, 50300, "BUY", "BTCUSDT")
        assert self.guard.violation_count == 1

        # Reset
        self.guard.reset_daily_counters()

        assert self.guard.violation_count == 0
        assert len(self.guard.violations_by_symbol) == 0
        assert self.guard.total_slippage_bps == 0.0


class TestSlippageGuardSingleton:
    """Test singleton pattern"""

    def test_singleton_instance(self):
        """get_slippage_guard should return same instance"""
        guard1 = get_slippage_guard()
        guard2 = get_slippage_guard()

        assert guard1 is guard2
        assert isinstance(guard1, SlippageGuard)

    def test_singleton_state_persistence(self):
        """Singleton state should persist across calls"""
        guard1 = get_slippage_guard()

        # Add violation
        guard1.check_slippage_threshold(50000, 50300, "BUY", "BTCUSDT")

        # Get guard again
        guard2 = get_slippage_guard()

        # State should be preserved
        assert guard2.violation_count == 1
        assert 'BTCUSDT' in guard2.violations_by_symbol


class TestPublicAPI:
    """Test public API functions"""

    @patch('src.utils.slippage_guard.Settings.MAX_SLIPPAGE_BPS', 50.0)
    @patch('src.utils.slippage_guard.Settings.SLIPPAGE_GUARD_POLICY', 'ABORT')
    def test_validate_order_slippage_api(self):
        """Public API should work correctly"""
        is_safe, corrective_action = validate_order_slippage(
            expected_price=50000.0,
            fill_price=50400.0,  # High slippage
            side="BUY",
            symbol="BTCUSDT",
            quantity=0.1
        )

        assert is_safe is False
        assert corrective_action['action'] == 'ABORT'

    def test_calculate_slippage_bps_api(self):
        """Public slippage calculation API"""
        slippage_bps = calculate_slippage_bps(50000.0, 50100.0, "BUY")
        assert abs(slippage_bps - 20.0) < 0.1


class TestSlippageEdgeCases:
    """Test edge cases and error conditions"""

    def setup_method(self):
        self.guard = SlippageGuard()

    def test_extreme_slippage_values(self):
        """Handle extreme slippage values"""
        # 50% slippage - market crash scenario
        slippage_bps = self.guard.calculate_slippage_bps(50000, 75000, "BUY")
        assert slippage_bps == 5000.0  # 50% = 5000 bps

        # Negative prices (should return 0)
        slippage_bps = self.guard.calculate_slippage_bps(-100, 100, "BUY")
        assert slippage_bps == 0.0

    def test_order_validation_exception_handling(self):
        """Exception in validation should be handled safely"""
        # Invalid order context that might cause exceptions
        malformed_context = {
            'symbol': None,
            'side': 'INVALID',
            'expected_price': 'not_a_number',
            'fill_price': None
        }

        is_safe, corrective_action = self.guard.validate_order_execution(malformed_context)

        assert is_safe is False
        assert corrective_action['action'] == 'ABORT'
        assert 'error' in corrective_action['reason'] or 'incomplete' in corrective_action['reason']


# Integration test placeholder
class TestExecutionIntegration:
    """Test integration with execution module"""

    def test_execution_module_integration(self):
        """Integration test placeholder for execution module"""
        # TODO: Test that execution.place_main_and_protection
        # properly calls slippage guard and handles responses
        pass


if __name__ == '__main__':
    # Run basic tests
    pytest.main([__file__, '-v'])
