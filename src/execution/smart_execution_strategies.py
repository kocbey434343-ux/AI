"""
Advanced Execution Strategies: TWAP, VWAP, Iceberg Orders
Liquidity-aware execution algorithms with market impact optimization
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

import numpy as np

try:
    from .advanced_impact_models import (
        AdvancedMarketImpactCalculator,
        ImpactModel,
        ImpactParameters,
        MarketImpactEstimate,
        get_advanced_impact_calculator,
    )
    from .liquidity_analyzer import (
        LiquidityAnalyzer,
        OrderBookSnapshot,
        OrderSide,
        get_liquidity_analyzer,
    )
except ImportError:
    # Fallback imports for development
    class AdvancedMarketImpactCalculator:
        def calculate_impact(self, **kwargs):
            from types import SimpleNamespace
            return SimpleNamespace(total_cost_bps=5.0)

    class LiquidityAnalyzer:
        def get_order_book_snapshot(self, symbol):
            return None

    class OrderSide(Enum):
        BUY = "BUY"
        SELL = "SELL"

    OrderBookSnapshot = None

    def get_advanced_impact_calculator():
        return AdvancedMarketImpactCalculator()

    def get_liquidity_analyzer():
        return LiquidityAnalyzer()

logger = logging.getLogger(__name__)


class ExecutionStrategy(Enum):
    """Execution strategy types"""
    TWAP = "twap"           # Time-Weighted Average Price
    VWAP = "vwap"           # Volume-Weighted Average Price
    ICEBERG = "iceberg"     # Iceberg orders
    SMART_ROUTING = "smart_routing"  # Intelligent routing
    IMPLEMENTATION_SHORTFALL = "is"  # Implementation Shortfall


@dataclass
class ExecutionSlice:
    """Individual execution slice"""
    slice_number: int
    quantity: float
    target_price: Optional[float] = None
    max_participation_rate: float = 0.20  # Max 20% of volume
    urgency_factor: float = 1.0  # 1.0 = normal, >1.0 = more urgent
    timestamp: Optional[datetime] = None


@dataclass
class ExecutionPlan:
    """Complete execution plan for large order"""
    symbol: str
    side: OrderSide
    total_quantity: float
    strategy: ExecutionStrategy
    slices: List[ExecutionSlice]
    target_completion_time: datetime
    max_participation_rate: float = 0.15  # Conservative default
    benchmark_price: Optional[float] = None  # For IS calculation
    estimated_cost_bps: float = 0.0


class TWAPExecutor:
    """Time-Weighted Average Price execution"""

    def __init__(self,
                 impact_calculator: AdvancedMarketImpactCalculator,
                 liquidity_analyzer: LiquidityAnalyzer):
        self.impact_calculator = impact_calculator
        self.liquidity_analyzer = liquidity_analyzer
        self.logger = logging.getLogger(__name__ + ".TWAPExecutor")

    def create_twap_plan(self,
                        symbol: str,
                        side: OrderSide,
                        total_quantity: float,
                        duration_minutes: int = 60,
                        num_slices: Optional[int] = None) -> ExecutionPlan:
        """
        Create TWAP execution plan

        Args:
            symbol: Trading symbol
            side: BUY or SELL
            total_quantity: Total quantity to execute
            duration_minutes: Time to complete execution
            num_slices: Number of slices (auto-calculated if None)

        Returns:
            Complete execution plan
        """
        # Auto-calculate optimal number of slices
        if num_slices is None:
            num_slices = self._calculate_optimal_slices(
                total_quantity, duration_minutes
            )

        # Calculate slice size
        slice_size = total_quantity / num_slices
        slice_interval = duration_minutes / num_slices

        # Create execution slices
        slices = []
        start_time = datetime.now()

        for i in range(num_slices):
            slice_time = start_time + timedelta(minutes=i * slice_interval)

            slice_obj = ExecutionSlice(
                slice_number=i + 1,
                quantity=slice_size,
                timestamp=slice_time,
                max_participation_rate=0.15,  # Conservative for TWAP
                urgency_factor=1.0  # Constant for TWAP
            )
            slices.append(slice_obj)

        # Estimate total cost using impact models
        estimated_cost = self._estimate_twap_cost(
            symbol, total_quantity, duration_minutes
        )

        plan = ExecutionPlan(
            symbol=symbol,
            side=side,
            total_quantity=total_quantity,
            strategy=ExecutionStrategy.TWAP,
            slices=slices,
            target_completion_time=start_time + timedelta(minutes=duration_minutes),
            max_participation_rate=0.15,
            estimated_cost_bps=estimated_cost
        )

        self.logger.info(f"TWAP plan created: {symbol} {side} {total_quantity:.2f} "
                        f"over {duration_minutes}min in {num_slices} slices, "
                        f"estimated cost: {estimated_cost:.1f} bps")

        return plan

    def _calculate_optimal_slices(self, quantity: float, duration_minutes: int) -> int:
        """Calculate optimal number of slices based on quantity and duration"""
        # Heuristic: 1 slice per 5-10 minutes, adjusted for quantity
        base_slices = max(1, duration_minutes // 8)  # Every 8 minutes

        # Adjust for large quantities (more slices for better execution)
        if quantity > 10000:
            multiplier = 1.5
        elif quantity > 5000:
            multiplier = 1.3
        else:
            multiplier = 1.0

        optimal_slices = min(20, max(2, int(base_slices * multiplier)))
        return optimal_slices

    def _estimate_twap_cost(self, symbol: str, quantity: float, duration_minutes: int) -> float:
        """Estimate TWAP execution cost in basis points"""
        try:
            # Use impact calculator for cost estimation
            impact_estimate = self.impact_calculator.calculate_impact(
                symbol=symbol,
                order_size=quantity,
                order_book=None,  # Will use default/cached data
            )

            # TWAP typically achieves better prices due to time spreading
            twap_improvement = min(2.0, 20 / duration_minutes)  # Up to 2 bps improvement

            total_cost = impact_estimate.total_cost_bps - twap_improvement
            return max(0.1, total_cost)  # Minimum cost floor

        except Exception as e:
            self.logger.warning(f"TWAP cost estimation failed: {e}")
            # Fallback estimate
            return 5.0 + (quantity / 10000) * 2.0


class VWAPExecutor:
    """Volume-Weighted Average Price execution"""

    def __init__(self,
                 impact_calculator: AdvancedMarketImpactCalculator,
                 liquidity_analyzer: LiquidityAnalyzer):
        self.impact_calculator = impact_calculator
        self.liquidity_analyzer = liquidity_analyzer
        self.logger = logging.getLogger(__name__ + ".VWAPExecutor")
        self.historical_volume_profile: Dict[str, List[float]] = {}  # Cache for volume patterns

    def create_vwap_plan(self,
                        symbol: str,
                        side: OrderSide,
                        total_quantity: float,
                        duration_minutes: int = 60,
                        target_participation: float = 0.15) -> ExecutionPlan:
        """
        Create VWAP execution plan based on historical volume patterns
        """
        # Get volume profile for the symbol
        volume_profile = self._get_volume_profile(symbol, duration_minutes)

        # Create volume-weighted slices
        slices = self._create_volume_weighted_slices(
            total_quantity, volume_profile, target_participation
        )

        # Estimate total cost
        estimated_cost = self._estimate_vwap_cost(
            symbol, total_quantity, target_participation
        )

        plan = ExecutionPlan(
            symbol=symbol,
            side=side,
            total_quantity=total_quantity,
            strategy=ExecutionStrategy.VWAP,
            slices=slices,
            target_completion_time=datetime.now() + timedelta(minutes=duration_minutes),
            max_participation_rate=target_participation,
            estimated_cost_bps=estimated_cost
        )

        self.logger.info(f"VWAP plan created: {symbol} {side} {total_quantity:.2f} "
                        f"over {duration_minutes}min, target participation: {target_participation:.1%}, "
                        f"estimated cost: {estimated_cost:.1f} bps")

        return plan

    def _get_volume_profile(self, symbol: str, duration_minutes: int) -> List[float]:
        """
        Get historical volume profile for the symbol
        Returns normalized volume weights for each time slice
        """
        # Check cache first
        cache_key = f"{symbol}_{duration_minutes}"
        if cache_key in self.historical_volume_profile:
            return self.historical_volume_profile[cache_key]

        # Generate realistic volume profile based on time of day
        current_hour = datetime.now().hour

        # Typical crypto volume pattern (UTC time)
        volume_pattern = {
            0: 0.8, 1: 0.7, 2: 0.6, 3: 0.6, 4: 0.7,    # Asian session declining
            5: 0.8, 6: 0.9, 7: 1.0, 8: 1.1, 9: 1.2,    # European session
            10: 1.1, 11: 1.0, 12: 1.2, 13: 1.3, 14: 1.4, # EU + US overlap
            15: 1.3, 16: 1.2, 17: 1.1, 18: 1.0, 19: 0.9, # US session
            20: 0.8, 21: 0.8, 22: 0.9, 23: 0.8          # End of US session
        }

        # Create volume profile for execution window
        num_slices = min(20, max(4, duration_minutes // 5))  # 5-minute slices
        profile: List[float] = []

        for i in range(num_slices):
            slice_hour = (current_hour + (i * duration_minutes / num_slices / 60)) % 24
            hour_int = int(slice_hour)
            volume_factor = volume_pattern.get(hour_int, 1.0)

            # Add some randomness but keep it realistic
            rng = np.random.default_rng(seed=42)  # Consistent seed for testing
            volume_factor *= rng.uniform(0.85, 1.15)
            profile.append(volume_factor)

        # Normalize so sum = 1.0
        total_volume = sum(profile)
        normalized_profile = [v / total_volume for v in profile]

        # Cache result
        self.historical_volume_profile[cache_key] = normalized_profile

        return normalized_profile

    def _create_volume_weighted_slices(self,
                                     total_quantity: float,
                                     volume_profile: List[float],
                                     target_participation: float) -> List[ExecutionSlice]:
        """Create execution slices weighted by expected volume"""
        slices = []
        start_time = datetime.now()

        for i, volume_weight in enumerate(volume_profile):
            slice_time = start_time + timedelta(
                minutes=i * (60 / len(volume_profile))  # Spread over 60 minutes
            )

            # Quantity proportional to expected volume
            slice_quantity = total_quantity * volume_weight

            # Adjust participation rate based on volume
            # Higher volume periods allow higher participation
            adjusted_participation = min(
                0.25,  # Maximum 25%
                target_participation * (1 + volume_weight * 0.5)
            )

            slice_obj = ExecutionSlice(
                slice_number=i + 1,
                quantity=slice_quantity,
                timestamp=slice_time,
                max_participation_rate=adjusted_participation,
                urgency_factor=volume_weight  # Higher urgency in high-volume periods
            )
            slices.append(slice_obj)

        return slices

    def _estimate_vwap_cost(self, symbol: str, quantity: float, participation_rate: float) -> float:
        """Estimate VWAP execution cost in basis points"""
        try:
            # Use impact calculator
            impact_estimate = self.impact_calculator.calculate_impact(
                symbol=symbol,
                order_size=quantity,
                order_book=None,
            )

            # VWAP typically beats TWAP in high-volume periods
            vwap_improvement = min(1.5, 1.0 / participation_rate * 0.1)

            total_cost = impact_estimate.total_cost_bps - vwap_improvement
            return max(0.1, total_cost)

        except Exception as e:
            self.logger.warning(f"VWAP cost estimation failed: {e}")
            # Fallback: cost increases with participation rate
            base_cost = 3.0
            participation_penalty = (participation_rate - 0.1) * 10  # Penalty above 10%
            return base_cost + max(0, participation_penalty)


class SmartRouter:
    """Intelligent execution routing and optimization"""

    def __init__(self,
                 impact_calculator: AdvancedMarketImpactCalculator,
                 liquidity_analyzer: LiquidityAnalyzer):
        self.impact_calculator = impact_calculator
        self.liquidity_analyzer = liquidity_analyzer
        self.twap_executor = TWAPExecutor(impact_calculator, liquidity_analyzer)
        self.vwap_executor = VWAPExecutor(impact_calculator, liquidity_analyzer)
        self.logger = logging.getLogger(__name__ + ".SmartRouter")

    def optimize_execution_strategy(self,
                                  symbol: str,
                                  side: OrderSide,
                                  total_quantity: float,
                                  urgency: str = "normal",  # "low", "normal", "high"
                                  max_duration_minutes: int = 120) -> ExecutionPlan:
        """
        Determine optimal execution strategy based on market conditions
        """
        self.logger.info(f"Optimizing execution strategy for {symbol} {side} "
                        f"{total_quantity:.2f} with {urgency} urgency")

        # Analyze market conditions
        market_analysis = self._analyze_market_conditions(symbol, total_quantity)

        # Generate candidate strategies
        candidates = self._generate_strategy_candidates(
            symbol, side, total_quantity, urgency, max_duration_minutes, market_analysis
        )

        # Select best strategy based on cost-benefit analysis
        best_plan = self._select_optimal_strategy(candidates)

        self.logger.info(f"Selected {best_plan.strategy} strategy with "
                        f"estimated cost: {best_plan.estimated_cost_bps:.1f} bps")

        return best_plan

    def _analyze_market_conditions(self, symbol: str, quantity: float) -> Dict[str, Any]:
        """Analyze current market conditions for strategy selection"""
        analysis = {
            "liquidity_score": 0.5,  # 0=illiquid, 1=very liquid
            "volatility_score": 0.5,  # 0=stable, 1=highly volatile
            "spread_score": 0.5,     # 0=tight, 1=wide
            "volume_score": 0.5,     # 0=low volume, 1=high volume
            "size_impact": "medium"   # "low", "medium", "high"
        }

        try:
            # Get order book for liquidity analysis
            order_book = self.liquidity_analyzer.get_order_book_snapshot(symbol)

            if order_book and len(order_book.bids) > 0 and len(order_book.asks) > 0:
                # Calculate spread
                spread_bps = ((order_book.asks[0].price - order_book.bids[0].price) /
                             order_book.bids[0].price) * 10000
                analysis["spread_score"] = min(1.0, spread_bps / 20)  # 20 bps = score 1.0

                # Calculate liquidity depth
                total_liquidity = sum(level.quantity for level in order_book.bids[:5]) + \
                                sum(level.quantity for level in order_book.asks[:5])

                liquidity_ratio = total_liquidity / max(quantity, 1)
                analysis["liquidity_score"] = min(1.0, liquidity_ratio / 10)  # 10x quantity = score 1.0

                # Size impact assessment
                if quantity > total_liquidity * 0.1:
                    analysis["size_impact"] = "high"
                elif quantity > total_liquidity * 0.05:
                    analysis["size_impact"] = "medium"
                else:
                    analysis["size_impact"] = "low"

        except Exception as e:
            self.logger.warning(f"Market analysis failed: {e}")

        return analysis

    def _generate_strategy_candidates(self, symbol: str, side: OrderSide,
                                    total_quantity: float, urgency: str,
                                    max_duration_minutes: int,
                                    market_analysis: Dict[str, Any]) -> List[ExecutionPlan]:
        """Generate candidate execution strategies"""
        candidates = []

        # Adjust parameters based on urgency
        urgency_params = {
            "low": {"duration": max_duration_minutes, "participation": 0.10},
            "normal": {"duration": max_duration_minutes * 0.7, "participation": 0.15},
            "high": {"duration": max_duration_minutes * 0.4, "participation": 0.25}
        }

        params = urgency_params.get(urgency, urgency_params["normal"])

        try:
            # TWAP candidate
            twap_plan = self.twap_executor.create_twap_plan(
                symbol, side, total_quantity, int(params["duration"])
            )
            candidates.append(twap_plan)

            # VWAP candidate (if sufficient duration)
            if params["duration"] >= 30:
                vwap_plan = self.vwap_executor.create_vwap_plan(
                    symbol, side, total_quantity,
                    int(params["duration"]), params["participation"]
                )
                candidates.append(vwap_plan)

        except Exception as e:
            self.logger.error(f"Failed to generate strategy candidates: {e}")

        return candidates

    def _select_optimal_strategy(self, candidates: List[ExecutionPlan]) -> ExecutionPlan:
        """Select optimal strategy based on cost-benefit analysis"""
        if not candidates:
            raise ValueError("No execution strategy candidates available")

        # Simple selection: choose lowest cost
        best_plan = min(candidates, key=lambda plan: plan.estimated_cost_bps)
        return best_plan


# Factory function for easy access
def get_smart_router() -> SmartRouter:
    """Get configured SmartRouter instance"""
    impact_calculator = get_advanced_impact_calculator()
    liquidity_analyzer = get_liquidity_analyzer()

    return SmartRouter(impact_calculator, liquidity_analyzer)
