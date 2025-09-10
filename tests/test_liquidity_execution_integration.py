"""
Integration tests for Liquidity-Aware Execution Framework
"""

import pytest
import time

from src.execution.liquidity_analyzer import OrderBookSnapshot, OrderBookLevel
from src.execution.smart_router import SmartOrderRouter, ExecutionStrategy, OrderSide


@pytest.fixture
def deep_order_book():
    """Deep liquidity order book for testing"""
    bids = [
        OrderBookLevel(price=100.0, quantity=50.0),
        OrderBookLevel(price=99.95, quantity=40.0),
        OrderBookLevel(price=99.90, quantity=35.0),
        OrderBookLevel(price=99.85, quantity=30.0),
        OrderBookLevel(price=99.80, quantity=25.0),
    ]

    asks = [
        OrderBookLevel(price=100.05, quantity=45.0),
        OrderBookLevel(price=100.10, quantity=35.0),
        OrderBookLevel(price=100.15, quantity=30.0),
        OrderBookLevel(price=100.20, quantity=25.0),
        OrderBookLevel(price=100.25, quantity=20.0),
    ]

    return OrderBookSnapshot(
        symbol="ETHUSDT",
        timestamp=time.time(),
        bids=bids,
        asks=asks
    )


@pytest.fixture
def shallow_order_book():
    """Shallow liquidity order book for testing"""
    bids = [
        OrderBookLevel(price=100.0, quantity=5.0),
        OrderBookLevel(price=99.8, quantity=3.0),
        OrderBookLevel(price=99.6, quantity=2.0),
    ]

    asks = [
        OrderBookLevel(price=100.2, quantity=4.0),
        OrderBookLevel(price=100.4, quantity=3.0),
        OrderBookLevel(price=100.6, quantity=2.0),
    ]

    return OrderBookSnapshot(
        symbol="ADAUSDT",
        timestamp=time.time(),
        bids=bids,
        asks=asks
    )


class TestSmartRouterIntegration:
    """Integration tests for smart router with different market conditions"""

    def test_aggressive_execution_deep_book(self, deep_order_book):
        """Test aggressive execution in deep liquidity"""
        router = SmartOrderRouter({
            'default_max_impact_bps': 50.0,
            'max_slices': 3,
            'adaptive_sizing': True
        })

        # High urgency order
        order = router.create_smart_order(
            "ETHUSDT", OrderSide.BUY, 30.0, urgency=0.9
        )

        slices = router.plan_execution(order, deep_order_book)

        # Should create fewer slices due to good liquidity
        assert len(slices) <= 2
        # Strategy should be suitable for deep liquidity
        assert slices[0].execution_strategy in [ExecutionStrategy.IMMEDIATE, ExecutionStrategy.PASSIVE]

    def test_passive_execution_shallow_book(self, shallow_order_book):
        """Test passive execution in shallow liquidity"""
        router = SmartOrderRouter({
            'default_max_impact_bps': 30.0,
            'max_slices': 5,
            'adaptive_sizing': True
        })

        # Low urgency order
        order = router.create_smart_order(
            "ADAUSDT", OrderSide.BUY, 6.0, urgency=0.2
        )

        slices = router.plan_execution(order, shallow_order_book)

        # Should handle order appropriately for shallow liquidity
        assert len(slices) >= 1
        # First slice should be passive or conservative strategy
        assert slices[0].execution_strategy in [ExecutionStrategy.PASSIVE, ExecutionStrategy.TWAP]

    def test_full_execution_workflow(self, deep_order_book):
        """Test complete execution workflow"""
        router = SmartOrderRouter({
            'default_max_impact_bps': 40.0,
            'max_slices': 4
        })

        # Mock execution callback
        execution_results = []

        def mock_callback(slice_obj, order_book):
            # Simulate partial fill
            fill_ratio = 0.8  # 80% fill
            slice_obj.filled_quantity = slice_obj.quantity * fill_ratio
            slice_obj.average_price = 100.02  # Slight slippage
            execution_results.append((slice_obj.slice_id, fill_ratio))
            return True

        router.register_execution_callback(ExecutionStrategy.IMMEDIATE, mock_callback)
        router.register_execution_callback(ExecutionStrategy.PASSIVE, mock_callback)

        # Create and execute order
        order = router.create_smart_order(
            "ETHUSDT", OrderSide.BUY, 40.0, urgency=0.6
        )

        slices = router.plan_execution(order, deep_order_book)
        order.slices = slices

        # Execute each slice
        for slice_obj in slices:
            result = router.execute_slice(slice_obj, deep_order_book)
            assert result  # Should succeed

        # Check execution results
        assert len(execution_results) == len(slices)

        # Update order status
        total_filled = sum(s.filled_quantity for s in slices)
        assert total_filled > 0
        assert total_filled <= order.total_quantity

    def test_market_impact_adaptation(self, deep_order_book, shallow_order_book):
        """Test router adaptation to different market impacts"""
        router = SmartOrderRouter({
            'default_max_impact_bps': 50.0,
            'max_slices': 6,
            'adaptive_sizing': True
        })

        # Same order size, different books
        order_size = 25.0

        # Deep book execution
        order_deep = router.create_smart_order(
            "ETHUSDT", OrderSide.BUY, order_size, urgency=0.5
        )
        slices_deep = router.plan_execution(order_deep, deep_order_book)

        # Shallow book execution
        order_shallow = router.create_smart_order(
            "ADAUSDT", OrderSide.BUY, order_size, urgency=0.5
        )
        slices_shallow = router.plan_execution(order_shallow, shallow_order_book)

        # Deep book should need fewer slices
        assert len(slices_deep) <= len(slices_shallow)

        # Deep book should be more aggressive
        deep_immediate_count = sum(1 for s in slices_deep if s.execution_strategy == ExecutionStrategy.IMMEDIATE)
        shallow_immediate_count = sum(1 for s in slices_shallow if s.execution_strategy == ExecutionStrategy.IMMEDIATE)

        assert deep_immediate_count >= shallow_immediate_count


class TestEndToEndExecution:
    """End-to-end tests combining analyzer and router"""

    def test_complete_order_lifecycle(self, deep_order_book):
        """Test complete order lifecycle from creation to completion"""
        router = SmartOrderRouter({
            'default_max_impact_bps': 35.0,
            'max_slices': 3
        })

        # Track execution calls
        execution_calls = []

        def tracking_callback(slice_obj, order_book):
            execution_calls.append({
                'slice_id': slice_obj.slice_id,
                'quantity': slice_obj.quantity,
                'strategy': slice_obj.execution_strategy.value,
                'symbol': slice_obj.symbol
            })

            # Simulate successful execution
            slice_obj.filled_quantity = slice_obj.quantity
            slice_obj.average_price = 100.03
            return True

        # Register callback for all strategies
        for strategy in ExecutionStrategy:
            router.register_execution_callback(strategy, tracking_callback)

        # Create order
        order = router.create_smart_order(
            "ETHUSDT", OrderSide.BUY, 45.0, urgency=0.7
        )

        # Plan execution
        slices = router.plan_execution(order, deep_order_book)
        order.slices = slices

        # Execute all slices
        for slice_obj in slices:
            success = router.execute_slice(slice_obj, deep_order_book)
            assert success

        # Complete order
        report = router.complete_order(order.order_id)

        # Verify execution
        assert len(execution_calls) == len(slices)

        # Check report exists and order is cleaned up
        assert report is not None
        assert order.order_id not in router.active_orders

    def test_partial_fill_handling(self, shallow_order_book):
        """Test handling of partial fills"""
        router = SmartOrderRouter({
            'default_max_impact_bps': 60.0,
            'max_slices': 4
        })

        # Mock partial execution
        def partial_callback(slice_obj, order_book):
            # Simulate 60% fill
            slice_obj.filled_quantity = slice_obj.quantity * 0.6
            slice_obj.average_price = 100.15
            return True

        router.register_execution_callback(ExecutionStrategy.PASSIVE, partial_callback)
        router.register_execution_callback(ExecutionStrategy.TWAP, partial_callback)

        # Create order
        order = router.create_smart_order(
            "ADAUSDT", OrderSide.BUY, 8.0, urgency=0.3
        )

        slices = router.plan_execution(order, shallow_order_book)
        order.slices = slices

        # Execute slices
        for slice_obj in slices:
            router.execute_slice(slice_obj, shallow_order_book)

        # Check partial fills
        total_filled = sum(s.filled_quantity for s in slices)
        expected_fill = order.total_quantity * 0.6

        assert abs(total_filled - expected_fill) < 1e-10
        assert all(abs(s.fill_rate - 0.6) < 1e-10 for s in slices)

    def test_execution_failure_handling(self, deep_order_book):
        """Test handling of execution failures"""
        router = SmartOrderRouter({
            'default_max_impact_bps': 40.0,
            'max_slices': 3
        })

        # Mock failing execution
        def failing_callback(slice_obj, order_book):
            # Simulate execution failure
            slice_obj.filled_quantity = 0.0
            slice_obj.average_price = 0.0
            return False

        router.register_execution_callback(ExecutionStrategy.IMMEDIATE, failing_callback)

        # Create order
        order = router.create_smart_order(
            "ETHUSDT", OrderSide.BUY, 20.0, urgency=0.8
        )

        slices = router.plan_execution(order, deep_order_book)
        order.slices = slices

        # Execute first slice (should fail)
        first_slice = slices[0]
        result = router.execute_slice(first_slice, deep_order_book)

        assert not result  # Execution should fail
        assert abs(first_slice.filled_quantity) < 1e-10
        assert abs(first_slice.average_price) < 1e-10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
