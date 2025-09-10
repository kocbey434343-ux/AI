"""
Smart Order Routing for Liquidity-Aware Execution
Adaptive order splitting and routing based on market conditions
"""

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

from .liquidity_analyzer import (
    ExecutionStrategy,
    MarketImpactEstimate,
    OrderBookAnalyzer,
    OrderBookSnapshot,
    OrderSide,
    analyze_liquidity,
    should_split_order,
)


class OrderStatus(Enum):
    """Order execution status"""
    PENDING = "pending"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELLED = "cancelled"
    FAILED = "failed"


class SliceStatus(Enum):
    """Order slice status"""
    WAITING = "waiting"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass
class OrderSlice:
    """Individual order slice for execution"""
    slice_id: str
    parent_order_id: str
    symbol: str
    side: OrderSide
    quantity: float
    target_price: Optional[float] = None
    urgency: float = 0.5
    status: SliceStatus = SliceStatus.WAITING
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    filled_quantity: float = 0.0
    average_price: float = 0.0
    execution_strategy: ExecutionStrategy = ExecutionStrategy.ADAPTIVE

    @property
    def remaining_quantity(self) -> float:
        """Get remaining quantity to fill"""
        return max(0, self.quantity - self.filled_quantity)

    @property
    def fill_rate(self) -> float:
        """Get fill rate (0-1)"""
        return self.filled_quantity / self.quantity if self.quantity > 0 else 0

    @property
    def is_complete(self) -> bool:
        """Check if slice is complete"""
        return self.status in [SliceStatus.COMPLETED, SliceStatus.CANCELLED]

    @property
    def duration_seconds(self) -> float:
        """Get execution duration in seconds"""
        if self.started_at is None:
            return 0
        end_time = self.completed_at if self.completed_at else time.time()
        return end_time - self.started_at


@dataclass
class SmartOrder:
    """Smart order with adaptive routing capability"""
    order_id: str
    symbol: str
    side: OrderSide
    total_quantity: float
    max_impact_bps: float = 50.0
    urgency: float = 0.5
    target_strategy: Optional[ExecutionStrategy] = None
    created_at: float = field(default_factory=time.time)
    slices: List[OrderSlice] = field(default_factory=list)

    @property
    def filled_quantity(self) -> float:
        """Get total filled quantity across all slices"""
        return sum(slice.filled_quantity for slice in self.slices)

    @property
    def remaining_quantity(self) -> float:
        """Get remaining quantity to fill"""
        return max(0, self.total_quantity - self.filled_quantity)

    @property
    def average_price(self) -> float:
        """Get volume-weighted average price"""
        total_value = sum(slice.filled_quantity * slice.average_price for slice in self.slices)
        total_qty = self.filled_quantity
        return total_value / total_qty if total_qty > 0 else 0

    @property
    def status(self) -> OrderStatus:
        """Get overall order status"""
        if not self.slices:
            return OrderStatus.PENDING

        filled_qty = self.filled_quantity
        if filled_qty >= self.total_quantity:
            return OrderStatus.FILLED
        if filled_qty > 0:
            return OrderStatus.PARTIAL
        if any(slice.status == SliceStatus.CANCELLED for slice in self.slices):
            return OrderStatus.CANCELLED
        if any(slice.status == SliceStatus.ACTIVE for slice in self.slices):
            return OrderStatus.PARTIAL
        return OrderStatus.PENDING


@dataclass
class ExecutionReport:
    """Execution performance report"""
    order_id: str
    symbol: str
    side: OrderSide
    total_quantity: float
    filled_quantity: float
    average_price: float
    total_slices: int
    execution_time_seconds: float
    total_cost_bps: float
    slippage_bps: float
    success_rate: float
    strategy_used: List[ExecutionStrategy]

    @property
    def fill_rate(self) -> float:
        """Get fill rate (0-1)"""
        return self.filled_quantity / self.total_quantity if self.total_quantity > 0 else 0


class SmartOrderRouter:
    """
    Smart order routing engine with adaptive execution strategies
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__)

        # Core components
        self.liquidity_analyzer = OrderBookAnalyzer(self.config.get('analyzer_config', {}))

        # Configuration
        self.default_max_impact_bps = self.config.get('default_max_impact_bps', 50.0)
        self.min_slice_size = self.config.get('min_slice_size', 0.001)
        self.max_slices = self.config.get('max_slices', 10)
        self.urgency_threshold = self.config.get('urgency_threshold', 0.8)
        self.adaptive_sizing = self.config.get('adaptive_sizing', True)

        # State tracking
        self.active_orders: Dict[str, SmartOrder] = {}
        self.execution_history: List[ExecutionReport] = []

        # Callbacks for actual execution
        self.execution_callbacks: Dict[ExecutionStrategy, Callable] = {}

        self.logger.info(f"SmartOrderRouter initialized: max_impact={self.default_max_impact_bps} BPS, "
                        f"max_slices={self.max_slices}, adaptive_sizing={self.adaptive_sizing}")

    def register_execution_callback(self, strategy: ExecutionStrategy,
                                   callback: Callable[[OrderSlice, OrderBookSnapshot], bool]):
        """Register execution callback for a strategy"""
        self.execution_callbacks[strategy] = callback
        self.logger.info(f"Registered execution callback for {strategy.value}")

    def create_smart_order(self, symbol: str, side: OrderSide, quantity: float,
                          max_impact_bps: Optional[float] = None, urgency: float = 0.5,
                          target_strategy: Optional[ExecutionStrategy] = None) -> SmartOrder:
        """Create a new smart order"""
        order_id = f"smart_{symbol}_{side.value}_{int(time.time() * 1000)}"

        smart_order = SmartOrder(
            order_id=order_id,
            symbol=symbol,
            side=side,
            total_quantity=quantity,
            max_impact_bps=max_impact_bps or self.default_max_impact_bps,
            urgency=urgency,
            target_strategy=target_strategy
        )

        self.active_orders[order_id] = smart_order

        self.logger.info(f"Created smart order {order_id}: {side.value} {quantity} {symbol}, "
                        f"max_impact={smart_order.max_impact_bps} BPS, urgency={urgency}")

        return smart_order

    def plan_execution(self, order: SmartOrder, order_book: OrderBookSnapshot) -> List[OrderSlice]:
        """Plan execution strategy and create slices"""

        # Analyze current market conditions
        _, impact_estimate = analyze_liquidity(
            order_book, order.side, order.total_quantity
        )

        self.logger.info(f"Planning execution for {order.order_id}: "
                        f"impact={impact_estimate.total_cost_bps:.1f} BPS, "
                        f"depth_adequacy={impact_estimate.depth_adequacy:.2f}, "
                        f"strategy={impact_estimate.execution_strategy.value}")

        # Determine if order should be split
        needs_splitting = should_split_order(impact_estimate, order.max_impact_bps)

        if not needs_splitting or order.urgency > self.urgency_threshold:
            # Execute as single slice
            slice_id = f"{order.order_id}_slice_1"
            order_slice = OrderSlice(
                slice_id=slice_id,
                parent_order_id=order.order_id,
                symbol=order.symbol,
                side=order.side,
                quantity=order.total_quantity,
                urgency=order.urgency,
                execution_strategy=order.target_strategy or impact_estimate.execution_strategy
            )
            return [order_slice]

        # Split order into multiple slices
        return self._create_order_slices(order, impact_estimate)

    def _create_order_slices(self, order: SmartOrder, impact: MarketImpactEstimate) -> List[OrderSlice]:
        """Create order slices based on market conditions"""

        # Determine optimal slice count
        num_slices = self._determine_slice_count(impact.depth_adequacy)

        # Calculate slice weights
        weights = self._calculate_slice_weights(num_slices)

        # Create slices
        return self._build_slices(order, weights, impact)

    def _determine_slice_count(self, depth_adequacy: float) -> int:
        """Determine optimal number of slices based on depth adequacy"""
        if depth_adequacy > 0.8:
            # Good liquidity - fewer, larger slices
            return min(3, self.max_slices)
        if depth_adequacy > 0.5:
            # Medium liquidity - moderate slicing
            return min(5, self.max_slices)
        # Poor liquidity - more, smaller slices
        return min(8, self.max_slices)

    def _calculate_slice_weights(self, num_slices: int) -> np.ndarray:
        """Calculate slice weights based on adaptive sizing preference"""
        if self.adaptive_sizing:
            # Use exponential decay for slice sizes (front-loaded)
            decay_factor = 0.7  # Larger slices first
            weights = [decay_factor ** i for i in range(num_slices)]
            weights = np.array(weights) / sum(weights)
        else:
            # Equal slice sizes
            weights = np.ones(num_slices) / num_slices
        return weights

    def _build_slices(self, order: SmartOrder, weights: np.ndarray,
                     impact: MarketImpactEstimate) -> List[OrderSlice]:
        """Build individual order slices"""
        slices = []
        remaining_qty = order.total_quantity

        for i, weight in enumerate(weights):
            if remaining_qty <= self.min_slice_size:
                break

            slice_qty = self._calculate_slice_quantity(remaining_qty, order.total_quantity, weight, i, len(weights))

            if slice_qty < self.min_slice_size and i < len(weights) - 1:
                continue

            # Create slice
            order_slice = self._create_single_slice(order, i, slice_qty, impact)
            slices.append(order_slice)
            remaining_qty -= slice_qty

        self.logger.info(f"Created {len(slices)} slices for {order.order_id}: "
                        f"sizes={[f'{s.quantity:.4f}' for s in slices]}")

        return slices

    def _calculate_slice_quantity(self, remaining_qty: float, total_qty: float,
                                 weight: float, index: int, total_slices: int) -> float:
        """Calculate quantity for a single slice"""
        is_last_slice = (index == total_slices - 1)
        return remaining_qty if is_last_slice else min(remaining_qty, total_qty * weight)

    def _create_single_slice(self, order: SmartOrder, index: int, quantity: float,
                           impact: MarketImpactEstimate) -> OrderSlice:
        """Create a single order slice with appropriate strategy"""
        slice_id = f"{order.order_id}_slice_{index+1}"

        # Adjust urgency for later slices
        slice_urgency = order.urgency * (0.9 ** index)  # Decreasing urgency

        # Select strategy
        strategy = self._select_slice_strategy(index, order, quantity, impact)

        return OrderSlice(
            slice_id=slice_id,
            parent_order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            quantity=quantity,
            urgency=slice_urgency,
            execution_strategy=strategy
        )

    def _select_slice_strategy(self, index: int, order: SmartOrder,
                              quantity: float, impact: MarketImpactEstimate) -> ExecutionStrategy:
        """Select execution strategy for a slice"""
        if index == 0 and order.urgency > 0.7:
            # First slice, high urgency - immediate
            return ExecutionStrategy.IMMEDIATE
        if impact.depth_adequacy < 0.3:
            # Poor liquidity - passive approach
            return ExecutionStrategy.PASSIVE
        if quantity > order.total_quantity * 0.5:
            # Large slice - use TWAP
            return ExecutionStrategy.TWAP
        # Default adaptive
        return ExecutionStrategy.ADAPTIVE

    def execute_slice(self, slice: OrderSlice, order_book: OrderBookSnapshot) -> bool:
        """Execute a single order slice"""

        if slice.status != SliceStatus.WAITING:
            return False

        # Get execution callback for strategy
        callback = self.execution_callbacks.get(slice.execution_strategy)
        if not callback:
            self.logger.warning(f"No execution callback for {slice.execution_strategy.value}")
            return False

        # Mark slice as active
        slice.status = SliceStatus.ACTIVE
        slice.started_at = time.time()

        self.logger.info(f"Executing slice {slice.slice_id}: "
                        f"{slice.side.value} {slice.quantity} {slice.symbol} "
                        f"using {slice.execution_strategy.value}")

        try:
            # Execute via callback
            success = callback(slice, order_book)

            if success:
                slice.status = SliceStatus.COMPLETED
                slice.completed_at = time.time()
                self.logger.info(f"Slice {slice.slice_id} completed successfully")
            else:
                self.logger.warning(f"Slice {slice.slice_id} execution failed")

            return success

        except Exception as e:
            self.logger.error(f"Error executing slice {slice.slice_id}: {e}")
            slice.status = SliceStatus.CANCELLED
            slice.completed_at = time.time()
            return False

    def update_slice_fill(self, slice_id: str, filled_qty: float, avg_price: float):
        """Update slice fill information"""

        # Find slice in active orders
        for order in self.active_orders.values():
            for slice_obj in order.slices:
                if slice_obj.slice_id == slice_id:
                    slice_obj.filled_quantity = min(filled_qty, slice_obj.quantity)
                    slice_obj.average_price = avg_price

                    if slice_obj.filled_quantity >= slice_obj.quantity:
                        slice_obj.status = SliceStatus.COMPLETED
                        slice_obj.completed_at = time.time()

                    self.logger.info(f"Updated slice {slice_id}: "
                                   f"filled {slice_obj.filled_quantity:.4f}/{slice_obj.quantity:.4f} "
                                   f"at avg price {avg_price:.6f}")
                    return

        self.logger.warning(f"Slice {slice_id} not found for fill update")

    def get_order_status(self, order_id: str) -> Optional[SmartOrder]:
        """Get current status of a smart order"""
        return self.active_orders.get(order_id)

    def cancel_order(self, order_id: str) -> bool:
        """Cancel a smart order and all its slices"""

        order = self.active_orders.get(order_id)
        if not order:
            return False

        # Cancel all active slices
        cancelled_count = 0
        for slice in order.slices:
            if slice.status in [SliceStatus.WAITING, SliceStatus.ACTIVE]:
                slice.status = SliceStatus.CANCELLED
                slice.completed_at = time.time()
                cancelled_count += 1

        self.logger.info(f"Cancelled order {order_id}: {cancelled_count} slices cancelled")
        return True

    def complete_order(self, order_id: str) -> Optional[ExecutionReport]:
        """Complete an order and generate execution report"""

        order = self.active_orders.pop(order_id, None)
        if not order:
            return None

        # Calculate execution metrics
        total_time = time.time() - order.created_at
        strategies_used = list({slice_obj.execution_strategy for slice_obj in order.slices})

        # Calculate slippage based on average price vs market price
        # For now, use a simplified calculation
        slippage_bps = 0.0  # Placeholder - would need reference market price

        # Success rate based on completed slices
        completed_slices = sum(1 for slice in order.slices if slice.status == SliceStatus.COMPLETED)
        success_rate = completed_slices / len(order.slices) if order.slices else 0

        report = ExecutionReport(
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            total_quantity=order.total_quantity,
            filled_quantity=order.filled_quantity,
            average_price=order.average_price,
            total_slices=len(order.slices),
            execution_time_seconds=total_time,
            total_cost_bps=slippage_bps,  # Use slippage as cost baseline
            slippage_bps=slippage_bps,
            success_rate=success_rate,
            strategy_used=strategies_used
        )

        self.execution_history.append(report)

        self.logger.info(f"Completed order {order_id}: "
                        f"filled {report.filled_quantity:.4f}/{report.total_quantity:.4f} "
                        f"in {report.execution_time_seconds:.1f}s "
                        f"using {len(strategies_used)} strategies")

        return report

    def get_execution_statistics(self) -> Dict[str, Any]:
        """Get execution statistics"""

        if not self.execution_history:
            return {"total_orders": 0}

        reports = self.execution_history

        return {
            "total_orders": len(reports),
            "avg_fill_rate": np.mean([r.fill_rate for r in reports]),
            "avg_execution_time": np.mean([r.execution_time_seconds for r in reports]),
            "avg_slices_per_order": np.mean([r.total_slices for r in reports]),
            "avg_success_rate": np.mean([r.success_rate for r in reports]),
            "total_volume": sum(r.filled_quantity for r in reports),
            "strategy_usage": self._get_strategy_usage_stats(),
            "active_orders": len(self.active_orders)
        }

    def _get_strategy_usage_stats(self) -> Dict[str, int]:
        """Get strategy usage statistics"""
        strategy_counts = {}

        for report in self.execution_history:
            for strategy in report.strategy_used:
                strategy_counts[strategy.value] = strategy_counts.get(strategy.value, 0) + 1

        return strategy_counts


# Global convenience functions
_smart_router = None

def get_smart_router(config: Optional[Dict[str, Any]] = None) -> SmartOrderRouter:
    """Get singleton SmartOrderRouter instance"""
    global _smart_router
    if _smart_router is None:
        _smart_router = SmartOrderRouter(config)
    return _smart_router

def create_and_plan_order(symbol: str, side: OrderSide, quantity: float,
                         order_book: OrderBookSnapshot, **kwargs) -> Tuple[SmartOrder, List[OrderSlice]]:
    """Convenience function to create and plan a smart order"""
    router = get_smart_router()

    order = router.create_smart_order(symbol, side, quantity, **kwargs)
    slices = router.plan_execution(order, order_book)
    order.slices = slices

    return order, slices

def execute_smart_order(order: SmartOrder, order_book: OrderBookSnapshot) -> List[bool]:
    """Execute all slices of a smart order"""
    router = get_smart_router()

    results = []
    for slice in order.slices:
        if slice.status == SliceStatus.WAITING:
            result = router.execute_slice(slice, order_book)
            results.append(result)

    return results
