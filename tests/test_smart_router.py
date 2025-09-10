"""
Tests for Smart Order Router
"""

import pytest
import time
from unittest.mock import Mock, patch

from src.execution.smart_router import (
    SmartOrderRouter, SmartOrder, OrderSlice, ExecutionReport,
    OrderStatus, SliceStatus, OrderSide, ExecutionStrategy,
    get_smart_router, create_and_plan_order, execute_smart_order
)
from src.execution.liquidity_analyzer import (
    OrderBookSnapshot, OrderBookLevel
)


@pytest.fixture
def sample_order_book():
    """Sample order book for testing"""
    bids = [
        OrderBookLevel(price=100.0, quantity=10.0),
        OrderBookLevel(price=99.9, quantity=15.0),
        OrderBookLevel(price=99.8, quantity=20.0),
    ]

    asks = [
        OrderBookLevel(price=100.1, quantity=12.0),
        OrderBookLevel(price=100.2, quantity=18.0),
        OrderBookLevel(price=100.3, quantity=22.0),
    ]

    return OrderBookSnapshot(
        symbol="BTCUSDT",
        timestamp=time.time(),
        bids=bids,
        asks=asks
    )


@pytest.fixture
def smart_router():
    """Smart router for testing"""
    config = {
        'default_max_impact_bps': 30.0,
        'min_slice_size': 0.001,
        'max_slices': 5,
    }
    return SmartOrderRouter(config)


@pytest.fixture
def mock_execution_callback():
    """Mock execution callback"""
    def callback(slice_obj, order_book):
        # Simulate successful execution
        return True
    return callback


class TestOrderSlice:
    """Test OrderSlice dataclass"""

    def test_order_slice_creation(self):
        """Test order slice creation"""
        order_slice = OrderSlice(
            slice_id="test_slice_1",
            parent_order_id="test_order",
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            quantity=10.0
        )

        assert order_slice.slice_id == "test_slice_1"
        assert abs(order_slice.remaining_quantity - 10.0) < 1e-10
        assert abs(order_slice.fill_rate) < 1e-10
        assert not order_slice.is_complete
        assert abs(order_slice.duration_seconds) < 1e-10

    def test_order_slice_fill_tracking(self):
        """Test order slice fill tracking"""
        order_slice = OrderSlice(
            slice_id="test_slice_1",
            parent_order_id="test_order",
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            quantity=10.0
        )

        # Partial fill
        order_slice.filled_quantity = 5.0
        order_slice.average_price = 100.1

        assert abs(order_slice.remaining_quantity - 5.0) < 1e-10
        assert abs(order_slice.fill_rate - 0.5) < 1e-10
        assert not order_slice.is_complete

        # Complete fill
        order_slice.filled_quantity = 10.0
        order_slice.status = SliceStatus.COMPLETED

        assert abs(order_slice.remaining_quantity) < 1e-10
        assert abs(order_slice.fill_rate - 1.0) < 1e-10
        assert order_slice.is_complete


class TestSmartOrder:
    """Test SmartOrder dataclass"""

    def test_smart_order_creation(self):
        """Test smart order creation"""
        order = SmartOrder(
            order_id="test_order",
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            total_quantity=100.0
        )

        assert order.order_id == "test_order"
        assert abs(order.filled_quantity) < 1e-10
        assert abs(order.remaining_quantity - 100.0) < 1e-10
        assert abs(order.average_price) < 1e-10
        assert order.status == OrderStatus.PENDING

    def test_smart_order_with_slices(self):
        """Test smart order with slices"""
        order = SmartOrder(
            order_id="test_order",
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            total_quantity=100.0
        )

        # Add slices
        slice1 = OrderSlice(
            slice_id="slice_1",
            parent_order_id="test_order",
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            quantity=50.0
        )
        slice1.filled_quantity = 30.0
        slice1.average_price = 100.1
        slice1.status = SliceStatus.COMPLETED

        slice2 = OrderSlice(
            slice_id="slice_2",
            parent_order_id="test_order",
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            quantity=50.0
        )
        slice2.filled_quantity = 25.0
        slice2.average_price = 100.2
        slice2.status = SliceStatus.ACTIVE

        order.slices = [slice1, slice2]

        # Test aggregated values
        assert abs(order.filled_quantity - 55.0) < 1e-10
        assert abs(order.remaining_quantity - 45.0) < 1e-10
        assert order.status == OrderStatus.PARTIAL

        # Test VWAP calculation
        expected_vwap = (30.0 * 100.1 + 25.0 * 100.2) / 55.0
        assert abs(order.average_price - expected_vwap) < 1e-10


class TestSmartOrderRouter:
    """Test SmartOrderRouter core functionality"""

    def test_router_initialization(self):
        """Test router initialization"""
        config = {
            'default_max_impact_bps': 25.0,
            'max_slices': 8,
            'adaptive_sizing': False
        }

        router = SmartOrderRouter(config)
        assert abs(router.default_max_impact_bps - 25.0) < 1e-10
        assert router.max_slices == 8
        assert not router.adaptive_sizing
        assert len(router.active_orders) == 0

    def test_create_smart_order(self, smart_router):
        """Test smart order creation"""
        order = smart_router.create_smart_order(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            quantity=50.0,
            urgency=0.7
        )

        assert order.symbol == "BTCUSDT"
        assert order.side == OrderSide.BUY
        assert abs(order.total_quantity - 50.0) < 1e-10
        assert abs(order.urgency - 0.7) < 1e-10
        assert order.order_id in smart_router.active_orders

    def test_execution_callback_registration(self, smart_router, mock_execution_callback):
        """Test execution callback registration"""
        smart_router.register_execution_callback(ExecutionStrategy.IMMEDIATE, mock_execution_callback)

        assert ExecutionStrategy.IMMEDIATE in smart_router.execution_callbacks
        assert smart_router.execution_callbacks[ExecutionStrategy.IMMEDIATE] == mock_execution_callback

    @patch('src.execution.smart_router.analyze_liquidity')
    def test_plan_execution_single_slice(self, mock_analyze, smart_router, sample_order_book):
        """Test execution planning for single slice"""
        # Mock low impact scenario
        mock_impact = Mock()
        mock_impact.total_cost_bps = 20.0
        mock_impact.depth_adequacy = 0.8
        mock_impact.execution_strategy = ExecutionStrategy.IMMEDIATE
        mock_analyze.return_value = (Mock(), mock_impact)

        order = smart_router.create_smart_order("BTCUSDT", OrderSide.BUY, 10.0, urgency=0.9)
        slices = smart_router.plan_execution(order, sample_order_book)

        assert len(slices) == 1
        assert abs(slices[0].quantity - 10.0) < 1e-10
        assert slices[0].execution_strategy == ExecutionStrategy.IMMEDIATE

    @patch('src.execution.smart_router.analyze_liquidity')
    def test_plan_execution_multiple_slices(self, mock_analyze, smart_router, sample_order_book):
        """Test execution planning for multiple slices"""
        # Mock high impact scenario requiring splitting
        mock_impact = Mock()
        mock_impact.total_cost_bps = 80.0
        mock_impact.depth_adequacy = 0.3
        mock_impact.execution_strategy = ExecutionStrategy.ICEBERG
        mock_analyze.return_value = (Mock(), mock_impact)

        # Mock should_split_order to return True
        with patch('src.execution.smart_router.should_split_order', return_value=True):
            order = smart_router.create_smart_order("BTCUSDT", OrderSide.BUY, 100.0, urgency=0.3)
            slices = smart_router.plan_execution(order, sample_order_book)

        assert len(slices) > 1
        assert len(slices) <= smart_router.max_slices

        # Total quantity should match
        total_slice_qty = sum(s.quantity for s in slices)
        assert abs(total_slice_qty - 100.0) < 1e-10

    def test_execute_slice(self, smart_router, sample_order_book, mock_execution_callback):
        """Test slice execution"""
        # Register callback
        smart_router.register_execution_callback(ExecutionStrategy.IMMEDIATE, mock_execution_callback)

        # Create slice
        order_slice = OrderSlice(
            slice_id="test_slice",
            parent_order_id="test_order",
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            quantity=10.0,
            execution_strategy=ExecutionStrategy.IMMEDIATE
        )

        # Execute
        result = smart_router.execute_slice(order_slice, sample_order_book)

        assert result
        assert order_slice.status == SliceStatus.COMPLETED
        assert order_slice.started_at is not None
        assert order_slice.completed_at is not None

    def test_update_slice_fill(self, smart_router):
        """Test slice fill update"""
        # Create order with slice
        order = smart_router.create_smart_order("BTCUSDT", OrderSide.BUY, 10.0)
        order_slice = OrderSlice(
            slice_id="test_slice",
            parent_order_id=order.order_id,
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            quantity=10.0
        )
        order.slices = [order_slice]

        # Update fill
        smart_router.update_slice_fill("test_slice", 5.0, 100.1)

        assert abs(order_slice.filled_quantity - 5.0) < 1e-10
        assert abs(order_slice.average_price - 100.1) < 1e-10
        assert order_slice.status == SliceStatus.WAITING  # Not complete

        # Complete fill
        smart_router.update_slice_fill("test_slice", 10.0, 100.15)

        assert abs(order_slice.filled_quantity - 10.0) < 1e-10
        assert order_slice.status == SliceStatus.COMPLETED

    def test_cancel_order(self, smart_router):
        """Test order cancellation"""
        # Create order with slices
        order = smart_router.create_smart_order("BTCUSDT", OrderSide.BUY, 20.0)

        slice1 = OrderSlice(
            slice_id="slice_1",
            parent_order_id=order.order_id,
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            quantity=10.0,
            status=SliceStatus.WAITING
        )

        slice2 = OrderSlice(
            slice_id="slice_2",
            parent_order_id=order.order_id,
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            quantity=10.0,
            status=SliceStatus.ACTIVE
        )

        order.slices = [slice1, slice2]

        # Cancel order
        result = smart_router.cancel_order(order.order_id)

        assert result
        assert slice1.status == SliceStatus.CANCELLED
        assert slice2.status == SliceStatus.CANCELLED

    def test_complete_order(self, smart_router):
        """Test order completion and reporting"""
        # Create order with completed slices
        order = smart_router.create_smart_order("BTCUSDT", OrderSide.BUY, 20.0)

        slice1 = OrderSlice(
            slice_id="slice_1",
            parent_order_id=order.order_id,
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            quantity=10.0,
            status=SliceStatus.COMPLETED,
            execution_strategy=ExecutionStrategy.IMMEDIATE
        )
        slice1.filled_quantity = 10.0
        slice1.average_price = 100.1

        slice2 = OrderSlice(
            slice_id="slice_2",
            parent_order_id=order.order_id,
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            quantity=10.0,
            status=SliceStatus.COMPLETED,
            execution_strategy=ExecutionStrategy.PASSIVE
        )
        slice2.filled_quantity = 8.0
        slice2.average_price = 100.2

        order.slices = [slice1, slice2]

        # Complete order
        report = smart_router.complete_order(order.order_id)

        assert report is not None
        assert report.order_id == order.order_id
        assert abs(report.filled_quantity - 18.0) < 1e-10
        assert abs(report.total_quantity - 20.0) < 1e-10
        assert report.total_slices == 2
        assert abs(report.success_rate - 1.0) < 1e-10
        assert order.order_id not in smart_router.active_orders

    def test_execution_statistics(self, smart_router):
        """Test execution statistics"""
        # Add some execution history
        report1 = ExecutionReport(
            order_id="order_1",
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            total_quantity=100.0,
            filled_quantity=95.0,
            average_price=100.1,
            total_slices=3,
            execution_time_seconds=30.0,
            total_cost_bps=25.0,
            slippage_bps=15.0,
            success_rate=1.0,
            strategy_used=[ExecutionStrategy.IMMEDIATE, ExecutionStrategy.PASSIVE]
        )

        smart_router.execution_history.append(report1)

        stats = smart_router.get_execution_statistics()

        assert stats["total_orders"] == 1
        assert abs(stats["avg_fill_rate"] - 0.95) < 1e-10
        assert abs(stats["avg_execution_time"] - 30.0) < 1e-10
        assert abs(stats["avg_slices_per_order"] - 3.0) < 1e-10
        assert abs(stats["total_volume"] - 95.0) < 1e-10


class TestConvenienceFunctions:
    """Test module-level convenience functions"""

    def test_get_smart_router_singleton(self):
        """Test singleton pattern for router"""
        router1 = get_smart_router()
        router2 = get_smart_router()

        # Should return same instance
        assert router1 is router2

    @patch('src.execution.smart_router.analyze_liquidity')
    def test_create_and_plan_order(self, mock_analyze, sample_order_book):
        """Test create and plan convenience function"""
        # Mock analyze_liquidity
        mock_impact = Mock()
        mock_impact.total_cost_bps = 20.0
        mock_impact.depth_adequacy = 0.8
        mock_impact.execution_strategy = ExecutionStrategy.IMMEDIATE
        mock_analyze.return_value = (Mock(), mock_impact)

        order, slices = create_and_plan_order(
            "BTCUSDT", OrderSide.BUY, 10.0, sample_order_book, urgency=0.8
        )

        assert isinstance(order, SmartOrder)
        assert isinstance(slices, list)
        assert len(slices) > 0
        assert order.slices == slices

    def test_execute_smart_order_no_callbacks(self, sample_order_book):
        """Test execute smart order without callbacks"""
        order = SmartOrder(
            order_id="test_order",
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            total_quantity=10.0
        )

        order_slice = OrderSlice(
            slice_id="slice_1",
            parent_order_id="test_order",
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            quantity=10.0,
            execution_strategy=ExecutionStrategy.IMMEDIATE
        )

        order.slices = [order_slice]

        # Execute without callbacks should return list with False results
        results = execute_smart_order(order, sample_order_book)
        assert len(results) == 1  # One slice processed
        assert results[0] is False  # Failed due to no callback


class TestSliceStrategies:
    """Test strategy selection for slices"""

    def test_slice_count_determination(self, smart_router):
        """Test slice count determination based on depth adequacy"""
        # Good liquidity
        count_good = smart_router._determine_slice_count(0.9)
        assert count_good <= 3

        # Medium liquidity
        count_medium = smart_router._determine_slice_count(0.6)
        assert count_medium <= 5

        # Poor liquidity
        count_poor = smart_router._determine_slice_count(0.2)
        assert count_poor <= 8

        # Verify ascending order
        assert count_good <= count_medium <= count_poor

    def test_slice_weight_calculation(self, smart_router):
        """Test slice weight calculation"""
        # Adaptive sizing (default)
        weights_adaptive = smart_router._calculate_slice_weights(3)
        assert len(weights_adaptive) == 3
        assert abs(sum(weights_adaptive) - 1.0) < 1e-10
        assert weights_adaptive[0] > weights_adaptive[1]  # Front-loaded

        # Equal sizing
        smart_router.adaptive_sizing = False
        weights_equal = smart_router._calculate_slice_weights(3)
        assert len(weights_equal) == 3
        assert abs(sum(weights_equal) - 1.0) < 1e-10
        assert abs(weights_equal[0] - weights_equal[1]) < 1e-10  # Equal

    def test_strategy_selection(self, smart_router):
        """Test strategy selection for slices"""
        order = SmartOrder(
            order_id="test_order",
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            total_quantity=100.0,
            urgency=0.8
        )

        mock_impact = Mock()
        mock_impact.depth_adequacy = 0.5

        # First slice, high urgency -> IMMEDIATE
        strategy_1 = smart_router._select_slice_strategy(0, order, 30.0, mock_impact)
        assert strategy_1 == ExecutionStrategy.IMMEDIATE

        # Large slice -> TWAP
        strategy_2 = smart_router._select_slice_strategy(1, order, 60.0, mock_impact)
        assert strategy_2 == ExecutionStrategy.TWAP

        # Poor liquidity -> PASSIVE
        mock_impact.depth_adequacy = 0.2
        strategy_3 = smart_router._select_slice_strategy(1, order, 20.0, mock_impact)
        assert strategy_3 == ExecutionStrategy.PASSIVE


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
