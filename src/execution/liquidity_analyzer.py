"""
Liquidity-Aware Execution Framework
Core order book analysis and market impact modeling
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


class OrderSide(Enum):
    """Order side enumeration"""
    BUY = "BUY"
    SELL = "SELL"


class ExecutionStrategy(Enum):
    """Execution strategy types"""
    IMMEDIATE = "immediate"           # Market order, immediate execution
    PASSIVE = "passive"               # Limit order at best price
    ICEBERG = "iceberg"              # Break into smaller chunks
    TWAP = "twap"                    # Time-weighted average price
    VWAP = "vwap"                    # Volume-weighted average price
    ADAPTIVE = "adaptive"            # Adaptive based on conditions


@dataclass
class OrderBookLevel:
    """Single order book level"""
    price: float
    quantity: float

    def __post_init__(self):
        if self.price <= 0:
            raise ValueError("Price must be positive")
        if self.quantity <= 0:
            raise ValueError("Quantity must be positive")


@dataclass
class OrderBookSnapshot:
    """Order book snapshot with bids and asks"""
    symbol: str
    timestamp: float
    bids: List[OrderBookLevel]
    asks: List[OrderBookLevel]

    def __post_init__(self):
        # Sort bids by price descending (highest first)
        self.bids = sorted(self.bids, key=lambda x: x.price, reverse=True)
        # Sort asks by price ascending (lowest first)
        self.asks = sorted(self.asks, key=lambda x: x.price)

    @property
    def best_bid(self) -> Optional[float]:
        """Get best bid price"""
        return self.bids[0].price if self.bids else None

    @property
    def best_ask(self) -> Optional[float]:
        """Get best ask price"""
        return self.asks[0].price if self.asks else None

    @property
    def spread_bps(self) -> Optional[float]:
        """Get bid-ask spread in basis points"""
        if self.best_bid and self.best_ask:
            mid_price = (self.best_bid + self.best_ask) / 2
            spread = self.best_ask - self.best_bid
            return (spread / mid_price) * 10000
        return None


@dataclass
class MarketImpactEstimate:
    """Market impact estimation results"""
    expected_price: float
    expected_slippage_bps: float
    total_cost_bps: float
    confidence_level: float
    execution_strategy: ExecutionStrategy
    estimated_duration_seconds: float
    depth_adequacy: float  # 0-1 scale

    def is_acceptable(self, max_slippage_bps: float = 50.0) -> bool:
        """Check if market impact is within acceptable limits"""
        return self.expected_slippage_bps <= max_slippage_bps


@dataclass
class LiquidityMetrics:
    """Comprehensive liquidity metrics"""
    symbol: str
    timestamp: float
    bid_depth_10: float      # Cumulative quantity within 10 bps of best bid
    ask_depth_10: float      # Cumulative quantity within 10 bps of best ask
    bid_depth_50: float      # Cumulative quantity within 50 bps
    ask_depth_50: float      # Cumulative quantity within 50 bps
    imbalance_ratio: float   # (bid_vol - ask_vol) / (bid_vol + ask_vol)
    resilience_score: float  # Liquidity resilience estimate (0-1)
    average_order_size: float
    book_pressure: float     # Directional pressure from order book


class OrderBookAnalyzer:
    """
    Advanced order book analysis for liquidity-aware execution
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__)

        # Configuration parameters
        self.depth_levels = self.config.get('depth_levels', 20)
        self.impact_model = self.config.get('impact_model', 'linear')
        self.min_confidence = self.config.get('min_confidence', 0.7)

        # Impact model parameters
        self.temp_impact_decay = self.config.get('temp_impact_decay', 0.95)
        self.permanent_impact_ratio = self.config.get('permanent_impact_ratio', 0.3)

        self.logger.info(f"OrderBookAnalyzer initialized: depth_levels={self.depth_levels}, "
                        f"impact_model={self.impact_model}")

    def analyze_depth(self, order_book: OrderBookSnapshot, side: OrderSide,
                     quantity: float) -> LiquidityMetrics:
        """
        Analyze order book depth and liquidity metrics
        """
        if side == OrderSide.BUY:
            relevant_levels = order_book.asks
            best_price = order_book.best_ask
        else:
            relevant_levels = order_book.bids
            best_price = order_book.best_bid

        if not relevant_levels or not best_price:
            # Return minimal liquidity metrics for empty book
            return LiquidityMetrics(
                symbol=order_book.symbol,
                timestamp=order_book.timestamp,
                bid_depth_10=0, ask_depth_10=0,
                bid_depth_50=0, ask_depth_50=0,
                imbalance_ratio=0, resilience_score=0,
                average_order_size=0, book_pressure=0
            )

        # Calculate depth within price bands
        depth_10 = self._calculate_depth_within_bps(relevant_levels, best_price, 10.0)
        depth_50 = self._calculate_depth_within_bps(relevant_levels, best_price, 50.0)

        # Calculate imbalance ratio
        total_bid_qty = sum(level.quantity for level in order_book.bids[:self.depth_levels])
        total_ask_qty = sum(level.quantity for level in order_book.asks[:self.depth_levels])

        if total_bid_qty + total_ask_qty > 0:
            imbalance_ratio = (total_bid_qty - total_ask_qty) / (total_bid_qty + total_ask_qty)
        else:
            imbalance_ratio = 0

        # Calculate resilience score (simplified)
        resilience_score = self._calculate_resilience_score(order_book, quantity)

        # Average order size
        avg_order_size = float(np.mean([level.quantity for level in relevant_levels[:10]]))

        # Book pressure (directional bias)
        book_pressure = self._calculate_book_pressure(order_book)

        return LiquidityMetrics(
            symbol=order_book.symbol,
            timestamp=order_book.timestamp,
            bid_depth_10=depth_10 if side == OrderSide.SELL else 0,
            ask_depth_10=depth_10 if side == OrderSide.BUY else 0,
            bid_depth_50=depth_50 if side == OrderSide.SELL else 0,
            ask_depth_50=depth_50 if side == OrderSide.BUY else 0,
            imbalance_ratio=imbalance_ratio,
            resilience_score=resilience_score,
            average_order_size=avg_order_size,
            book_pressure=book_pressure
        )

    def estimate_market_impact(self, order_book: OrderBookSnapshot, side: OrderSide,
                              quantity: float, urgency: float = 0.5) -> MarketImpactEstimate:
        """
        Estimate market impact for a given order

        Args:
            order_book: Current order book snapshot
            side: Order side (BUY/SELL)
            quantity: Order quantity
            urgency: Execution urgency (0=patient, 1=urgent)
        """
        if side == OrderSide.BUY:
            levels = order_book.asks
            best_price = order_book.best_ask
        else:
            levels = order_book.bids
            best_price = order_book.best_bid

        if not levels or not best_price:
            # Return pessimistic estimate for empty book
            return MarketImpactEstimate(
                expected_price=0,
                expected_slippage_bps=1000,  # Very high slippage
                total_cost_bps=1000,
                confidence_level=0,
                execution_strategy=ExecutionStrategy.IMMEDIATE,
                estimated_duration_seconds=0,
                depth_adequacy=0
            )

        # Calculate expected execution price
        expected_price, _ = self._calculate_execution_price(levels, quantity)

        # Calculate slippage
        slippage_bps = ((expected_price - best_price) / best_price) * 10000
        if side == OrderSide.SELL:
            slippage_bps = -slippage_bps  # Negative slippage for sells

        # Estimate temporary impact (recovers over time)
        temp_impact_bps = self._estimate_temporary_impact(order_book, quantity, side)

        # Estimate permanent impact (price moves permanently)
        perm_impact_bps = temp_impact_bps * self.permanent_impact_ratio

        # Total cost including both impacts
        total_cost_bps = abs(slippage_bps) + temp_impact_bps + perm_impact_bps

        # Calculate depth adequacy
        available_depth = sum(level.quantity for level in levels[:self.depth_levels])
        depth_adequacy = min(1.0, available_depth / quantity) if quantity > 0 else 1.0

        # Suggest execution strategy based on impact and urgency
        strategy = self._suggest_execution_strategy(
            total_cost_bps, depth_adequacy, urgency, quantity
        )

        # Estimate execution duration
        duration = self._estimate_execution_duration(strategy, quantity, order_book)

        # Confidence level based on book quality
        confidence = self._calculate_confidence_level(order_book, depth_adequacy)

        return MarketImpactEstimate(
            expected_price=expected_price,
            expected_slippage_bps=slippage_bps,
            total_cost_bps=total_cost_bps,
            confidence_level=confidence,
            execution_strategy=strategy,
            estimated_duration_seconds=duration,
            depth_adequacy=depth_adequacy
        )

    def _calculate_depth_within_bps(self, levels: List[OrderBookLevel],
                                   reference_price: float, max_bps: float) -> float:
        """Calculate cumulative quantity within BPS of reference price"""
        cumulative_qty = 0

        for level in levels:
            price_diff_bps = abs((level.price - reference_price) / reference_price) * 10000
            if price_diff_bps <= max_bps:
                cumulative_qty += level.quantity
            else:
                break  # Levels are sorted, so we can break early

        return cumulative_qty

    def _calculate_execution_price(self, levels: List[OrderBookLevel],
                                  quantity: float) -> Tuple[float, float]:
        """Calculate volume-weighted average execution price"""
        remaining_qty = quantity
        total_cost = 0
        consumed_qty = 0

        for level in levels:
            if remaining_qty <= 0:
                break

            qty_from_level = min(remaining_qty, level.quantity)
            total_cost += qty_from_level * level.price
            consumed_qty += qty_from_level
            remaining_qty -= qty_from_level

        if consumed_qty > 0:
            avg_price = total_cost / consumed_qty
        else:
            avg_price = levels[0].price if levels else 0

        return avg_price, consumed_qty

    def _estimate_temporary_impact(self, order_book: OrderBookSnapshot,
                                  quantity: float, side: OrderSide) -> float:
        """Estimate temporary market impact in BPS"""
        # Simplified Kyle's lambda model
        # Impact ∝ sqrt(quantity / average_volume)

        total_depth = sum(level.quantity for level in
                         (order_book.asks if side == OrderSide.BUY else order_book.bids)[:10])

        if total_depth <= 0:
            return 100.0  # High impact for thin books

        # Normalized quantity impact
        qty_ratio = quantity / total_depth

        # Square root law of market impact
        base_impact = 20 * np.sqrt(qty_ratio)  # Base impact in BPS

        # Adjust for order book imbalance
        imbalance_adjustment = self._get_imbalance_adjustment(order_book, side)

        return min(base_impact * imbalance_adjustment, 500.0)  # Cap at 500 BPS

    def _get_imbalance_adjustment(self, order_book: OrderBookSnapshot,
                                 side: OrderSide) -> float:
        """Adjust impact based on order book imbalance"""
        bid_depth = sum(level.quantity for level in order_book.bids[:5])
        ask_depth = sum(level.quantity for level in order_book.asks[:5])

        if bid_depth + ask_depth == 0:
            return 2.0  # High adjustment for empty book

        imbalance = (bid_depth - ask_depth) / (bid_depth + ask_depth)

        if side == OrderSide.BUY:
            # Buying into thin ask side increases impact
            return 1.0 + max(0, -imbalance)
        # Selling into thin bid side increases impact
        return 1.0 + max(0, imbalance)

    def _calculate_resilience_score(self, order_book: OrderBookSnapshot,
                                   quantity: float) -> float:
        """Calculate order book resilience score (0-1)"""
        # Factors: depth diversity, level distribution, quantity adequacy

        total_levels = len(order_book.bids) + len(order_book.asks)
        if total_levels < 5:
            return 0.2  # Low resilience for thin books

        # Check depth distribution
        bid_depth_variance = self._calculate_depth_variance(order_book.bids)
        ask_depth_variance = self._calculate_depth_variance(order_book.asks)

        # Higher variance = more resilient (diverse liquidity providers)
        depth_diversity = min(1.0, (bid_depth_variance + ask_depth_variance) / 2)

        # Check if there's adequate depth for the order
        total_near_depth = (
            sum(level.quantity for level in order_book.bids[:5]) +
            sum(level.quantity for level in order_book.asks[:5])
        )

        adequacy = min(1.0, total_near_depth / (quantity * 2)) if quantity > 0 else 1.0

        return (depth_diversity + adequacy) / 2

    def _calculate_depth_variance(self, levels: List[OrderBookLevel]) -> float:
        """Calculate variance in order sizes"""
        if len(levels) < 2:
            return 0

        quantities = [level.quantity for level in levels[:10]]
        mean_qty = np.mean(quantities)
        return float(np.var(quantities) / (mean_qty ** 2)) if mean_qty > 0 else 0.0

    def _calculate_book_pressure(self, order_book: OrderBookSnapshot) -> float:
        """Calculate directional pressure from order book"""
        # Weight levels by proximity to mid price
        mid_price = ((order_book.best_bid or 0) + (order_book.best_ask or 0)) / 2
        if mid_price <= 0:
            return 0

        bid_pressure = 0
        ask_pressure = 0

        for level in order_book.bids[:10]:
            weight = level.price / mid_price  # Closer to mid = higher weight
            bid_pressure += level.quantity * weight

        for level in order_book.asks[:10]:
            weight = mid_price / level.price  # Closer to mid = higher weight
            ask_pressure += level.quantity * weight

        total_pressure = bid_pressure + ask_pressure
        if total_pressure > 0:
            return (bid_pressure - ask_pressure) / total_pressure
        return 0

    def _suggest_execution_strategy(self, total_cost_bps: float, depth_adequacy: float,
                                   urgency: float, quantity: float) -> ExecutionStrategy:
        """Suggest optimal execution strategy"""

        # High urgency or low cost → immediate execution
        if urgency > 0.8 or total_cost_bps < 10:
            return ExecutionStrategy.IMMEDIATE

        # Very high cost → break into smaller pieces
        if total_cost_bps > 100 or depth_adequacy < 0.3:
            return ExecutionStrategy.ICEBERG

        # Medium cost, good depth → passive approach
        if total_cost_bps < 50 and depth_adequacy > 0.7:
            return ExecutionStrategy.PASSIVE

        # Large orders → TWAP/VWAP
        if quantity > depth_adequacy * 10:  # Order is much larger than available depth
            return ExecutionStrategy.TWAP

        # Default adaptive approach
        return ExecutionStrategy.ADAPTIVE

    def _estimate_execution_duration(self, strategy: ExecutionStrategy,
                                    quantity: float, order_book: OrderBookSnapshot) -> float:
        """Estimate execution duration in seconds"""

        base_duration = {
            ExecutionStrategy.IMMEDIATE: 1.0,
            ExecutionStrategy.PASSIVE: 30.0,
            ExecutionStrategy.ICEBERG: 120.0,
            ExecutionStrategy.TWAP: 300.0,
            ExecutionStrategy.VWAP: 600.0,
            ExecutionStrategy.ADAPTIVE: 60.0
        }

        duration = base_duration.get(strategy, 60.0)

        # Adjust based on order size relative to market depth
        total_depth = sum(level.quantity for level in order_book.asks[:10]) + \
                     sum(level.quantity for level in order_book.bids[:10])

        if total_depth > 0:
            size_factor = max(1.0, quantity / total_depth)
            duration *= size_factor

        return min(duration, 3600.0)  # Cap at 1 hour

    def _calculate_confidence_level(self, order_book: OrderBookSnapshot,
                                   depth_adequacy: float) -> float:
        """Calculate confidence level in the impact estimate"""

        # Base confidence from book quality
        total_levels = len(order_book.bids) + len(order_book.asks)
        level_confidence = min(1.0, total_levels / 20)  # 20 levels = full confidence

        # Confidence from spread
        spread_bps = order_book.spread_bps or 1000
        spread_confidence = max(0, 1.0 - spread_bps / 100)  # 100 BPS spread = 0 confidence

        # Confidence from depth adequacy
        depth_confidence = depth_adequacy

        # Combined confidence
        return (level_confidence + spread_confidence + depth_confidence) / 3


# Global convenience functions
_order_book_analyzer = None

def get_order_book_analyzer(config: Optional[Dict[str, Any]] = None) -> OrderBookAnalyzer:
    """Get singleton OrderBookAnalyzer instance"""
    global _order_book_analyzer
    if _order_book_analyzer is None:
        _order_book_analyzer = OrderBookAnalyzer(config)
    return _order_book_analyzer

def analyze_liquidity(order_book: OrderBookSnapshot, side: OrderSide,
                     quantity: float) -> Tuple[LiquidityMetrics, MarketImpactEstimate]:
    """Convenience function for comprehensive liquidity analysis"""
    analyzer = get_order_book_analyzer()

    liquidity_metrics = analyzer.analyze_depth(order_book, side, quantity)
    impact_estimate = analyzer.estimate_market_impact(order_book, side, quantity)

    return liquidity_metrics, impact_estimate

def should_split_order(impact_estimate: MarketImpactEstimate,
                      max_impact_bps: float = 50.0) -> bool:
    """Determine if order should be split based on impact"""
    return (impact_estimate.total_cost_bps > max_impact_bps or
            impact_estimate.depth_adequacy < 0.5)

def get_liquidity_statistics() -> Dict[str, Any]:
    """Get liquidity analyzer statistics"""
    return {
        "analyzer_available": True,
        "supported_strategies": [s.value for s in ExecutionStrategy],
        "impact_models": ["linear", "sqrt", "adaptive"],
        "default_max_impact_bps": 50.0,
        "min_confidence_level": 0.7
    }
