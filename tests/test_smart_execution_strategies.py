"""
Test Suite for Smart Execution Strategies
TWAP, VWAP, and Smart Routing functionality tests
"""

import pytest
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

# Import the module to test
try:
    from src.execution.smart_execution_strategies import (
        TWAPExecutor, VWAPExecutor, SmartRouter,
        ExecutionStrategy, ExecutionSlice, ExecutionPlan,
        OrderSide, get_smart_router
    )
except ImportError:
    # Skip tests if module not available
    pytest.skip("Smart execution strategies module not available", allow_module_level=True)


class TestTWAPExecutor:
    """Test TWAP execution strategy"""

    def setup_method(self):
        """Setup test fixtures"""
        self.mock_impact_calc = Mock()
        self.mock_liquidity_analyzer = Mock()
        self.twap_executor = TWAPExecutor(self.mock_impact_calc, self.mock_liquidity_analyzer)

        # Mock impact estimate
        self.mock_impact_estimate = Mock()
        self.mock_impact_estimate.total_cost_bps = 8.0
        self.mock_impact_calc.calculate_impact.return_value = self.mock_impact_estimate

    def test_create_twap_plan_basic(self):
        """Test basic TWAP plan creation"""
        plan = self.twap_executor.create_twap_plan(
            symbol="BTCUSDT",
            side="BUY",
            total_quantity=1000,
            duration_minutes=60,
            num_slices=6
        )

        assert plan.symbol == "BTCUSDT"
        assert plan.total_quantity == 1000
        assert plan.strategy == ExecutionStrategy.TWAP
        assert len(plan.slices) == 6
        assert plan.estimated_cost_bps > 0

        # Check slice distribution
        total_slice_quantity = sum(slice_obj.quantity for slice_obj in plan.slices)
        assert abs(total_slice_quantity - 1000) < 0.01


class TestVWAPExecutor:
    """Test VWAP execution strategy"""

    def setup_method(self):
        """Setup test fixtures"""
        self.mock_impact_calc = Mock()
        self.mock_liquidity_analyzer = Mock()
        self.vwap_executor = VWAPExecutor(self.mock_impact_calc, self.mock_liquidity_analyzer)

        # Mock impact estimate
        self.mock_impact_estimate = Mock()
        self.mock_impact_estimate.total_cost_bps = 6.0
        self.mock_impact_calc.calculate_impact.return_value = self.mock_impact_estimate

    def test_create_vwap_plan_basic(self):
        """Test basic VWAP plan creation"""
        plan = self.vwap_executor.create_vwap_plan(
            symbol="ADAUSDT",
            side="BUY",
            total_quantity=2000,
            duration_minutes=90,
            target_participation=0.12
        )

        assert plan.symbol == "ADAUSDT"
        assert plan.total_quantity == 2000
        assert plan.strategy == ExecutionStrategy.VWAP
        assert len(plan.slices) > 0

        # Check total quantity distribution
        total_slice_quantity = sum(slice_obj.quantity for slice_obj in plan.slices)
        assert abs(total_slice_quantity - 2000) < 0.01


class TestSmartRouter:
    """Test Smart Router optimization logic"""

    def setup_method(self):
        """Setup test fixtures"""
        self.mock_impact_calc = Mock()
        self.mock_liquidity_analyzer = Mock()
        self.smart_router = SmartRouter(self.mock_impact_calc, self.mock_liquidity_analyzer)

        # Mock order book
        self.mock_order_book = Mock()
        self.mock_order_book.bids = [Mock(price=50000, quantity=100)]
        self.mock_order_book.asks = [Mock(price=50100, quantity=120)]
        self.mock_liquidity_analyzer.get_order_book_snapshot.return_value = self.mock_order_book

    def test_optimize_execution_strategy_integration(self):
        """Test full strategy optimization workflow"""
        plan = self.smart_router.optimize_execution_strategy(
            symbol="ADAUSDT",
            side="SELL",
            total_quantity=3000,
            urgency="low",
            max_duration_minutes=180
        )

        # Should return valid execution plan
        assert isinstance(plan, ExecutionPlan)
        assert plan.symbol == "ADAUSDT"
        assert plan.total_quantity == 3000
        assert plan.strategy in [ExecutionStrategy.TWAP, ExecutionStrategy.VWAP]
        assert len(plan.slices) > 0
        assert plan.estimated_cost_bps > 0


class TestIntegration:
    """Integration tests for the full execution strategy system"""

    def test_get_smart_router_factory(self):
        """Test factory function"""
        router = get_smart_router()

        assert isinstance(router, SmartRouter)
        assert hasattr(router, 'twap_executor')
        assert hasattr(router, 'vwap_executor')
        assert hasattr(router, 'impact_calculator')
        assert hasattr(router, 'liquidity_analyzer')

    def test_execution_plan_serialization(self):
        """Test that execution plans can be properly represented"""
        # Create a simple execution plan
        slices = [
            ExecutionSlice(slice_number=1, quantity=500, max_participation_rate=0.15),
            ExecutionSlice(slice_number=2, quantity=500, max_participation_rate=0.15)
        ]

        plan = ExecutionPlan(
            symbol="ETHUSDT",
            side="BUY",
            total_quantity=1000,
            strategy=ExecutionStrategy.TWAP,
            slices=slices,
            target_completion_time=datetime.now() + timedelta(hours=1),
            estimated_cost_bps=5.5
        )

        # Should be able to access all attributes
        assert plan.symbol == "ETHUSDT"
        assert len(plan.slices) == 2
        assert plan.estimated_cost_bps > 5.0


if __name__ == "__main__":
    # Run basic smoke test
    print("Running Smart Execution Strategies smoke test...")

    try:
        router = get_smart_router()
        print("✅ Smart Router created successfully")

        plan = router.optimize_execution_strategy(
            symbol="BTCUSDT",
            side="BUY",
            total_quantity=1000,
            urgency="normal"
        )
        print(f"✅ Execution plan created: {plan.strategy.value} with {len(plan.slices)} slices")
        print(f"   Estimated cost: {plan.estimated_cost_bps:.1f} bps")

        print("🎯 Smart Execution Strategies working correctly!")

    except Exception as e:
        print(f"❌ Smart Execution Strategies test failed: {e}")
        raise
