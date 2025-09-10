"""
Basic tests for advanced market impact models.
"""

import pytest
import numpy as np
from dataclasses import dataclass
from typing import Dict, List

from src.execution.advanced_impact_models import (
    ImpactModel,
    ImpactParameters,
    MarketImpactEstimate,
    AdvancedMarketImpactCalculator,
    OrderSide,
    get_market_impact_calculator
)

@dataclass
class MockOrderBookLevel:
    """Mock order book level for testing."""
    price: float
    quantity: float

@dataclass
class MockOrderBookSnapshot:
    """Mock order book snapshot for testing."""
    symbol: str
    timestamp: float
    bids: List[MockOrderBookLevel]
    asks: List[MockOrderBookLevel]

    def get_bids(self) -> List[Dict[str, float]]:
        """Get bids in expected format."""
        return [{'price': b.price, 'quantity': b.quantity} for b in self.bids]

    def get_asks(self) -> List[Dict[str, float]]:
        """Get asks in expected format."""
        return [{'price': a.price, 'quantity': a.quantity} for a in self.asks]

class TestImpactParameters:
    """Test ImpactParameters dataclass."""

    def test_impact_parameters_creation(self):
        """Test basic creation of impact parameters."""
        params = ImpactParameters(
            model=ImpactModel.LINEAR,
            temporary_impact_coef=0.001,
            permanent_impact_coef=0.0005
        )
        assert params.model == ImpactModel.LINEAR
        assert abs(params.temporary_impact_coef - 0.001) < 1e-6
        assert abs(params.permanent_impact_coef - 0.0005) < 1e-6
        assert abs(params.volatility - 0.01) < 1e-6  # default
        assert abs(params.volume_rate - 5000.0) < 1e-6  # default

class TestAdvancedMarketImpactCalculator:
    """Test AdvancedMarketImpactCalculator class."""

    def test_calculator_initialization(self):
        """Test calculator initialization."""
        params = ImpactParameters(
            model=ImpactModel.LINEAR,
            temporary_impact_coef=0.001
        )
        calculator = AdvancedMarketImpactCalculator(params)
        assert calculator.impact_params.model == ImpactModel.LINEAR
        assert abs(calculator.impact_params.temporary_impact_coef - 0.001) < 1e-6

    def test_linear_impact_calculation(self):
        """Test linear impact model calculation."""
        params = ImpactParameters(
            model=ImpactModel.LINEAR,
            temporary_impact_coef=0.001,
            permanent_impact_coef=0.0005,
            volatility=0.02,
            volume_rate=10000.0
        )
        calculator = AdvancedMarketImpactCalculator(params)

        # Create mock order book
        order_book = MockOrderBookSnapshot(
            symbol="BTCUSDT",
            timestamp=1609459200.0,
            bids=[MockOrderBookLevel(50000.0, 1.0)],
            asks=[MockOrderBookLevel(50001.0, 1.0)]
        )

        estimate = calculator.calculate_impact(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_size=1.0,
            order_book=order_book,
            execution_horizon=300.0
        )

        assert estimate.order_size > 0
        assert estimate.total_impact_bps > 0
        assert estimate.temporary_impact_bps >= 0
        assert estimate.permanent_impact_bps >= 0
        assert len(estimate.confidence_interval) == 2
        assert estimate.confidence_interval[0] <= estimate.confidence_interval[1]

    def test_square_root_impact_calculation(self):
        """Test square-root (Almgren-Chriss) impact model."""
        params = ImpactParameters(
            model=ImpactModel.SQUARE_ROOT,
            temporary_impact_coef=0.001,
            permanent_impact_coef=0.0005,
            volatility=0.02,
            volume_rate=10000.0
        )
        calculator = AdvancedMarketImpactCalculator(params)

        order_book = MockOrderBookSnapshot(
            symbol="BTCUSDT",
            timestamp=1609459200.0,
            bids=[MockOrderBookLevel(50000.0, 2.0)],
            asks=[MockOrderBookLevel(50001.0, 2.0)]
        )

        estimate = calculator.calculate_impact(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_size=2.0,
            order_book=order_book,
            execution_horizon=300.0
        )

        assert estimate.total_impact_bps > 0
        assert estimate.optimal_participation_rate > 0
        assert estimate.optimal_participation_rate <= 1.0

    def test_kyle_lambda_impact_calculation(self):
        """Test Kyle's lambda impact model."""
        params = ImpactParameters(
            model=ImpactModel.KYLE_LAMBDA,
            liquidity_lambda=0.001,
            volatility=0.02
        )
        calculator = AdvancedMarketImpactCalculator(params)

        order_book = MockOrderBookSnapshot(
            symbol="BTCUSDT",
            timestamp=1609459200.0,
            bids=[MockOrderBookLevel(50000.0, 1.5)],
            asks=[MockOrderBookLevel(50001.0, 1.5)]
        )

        estimate = calculator.calculate_impact(
            symbol="BTCUSDT",
            side=OrderSide.SELL,
            order_size=1.5,
            order_book=order_book
        )

        assert estimate.total_impact_bps > 0

    def test_order_size_scaling(self):
        """Test that larger orders have higher impact."""
        params = ImpactParameters(
            model=ImpactModel.LINEAR,
            temporary_impact_coef=0.001,
            permanent_impact_coef=0.0005
        )
        calculator = AdvancedMarketImpactCalculator(params)

        order_book = MockOrderBookSnapshot(
            symbol="BTCUSDT",
            timestamp=1609459200.0,
            bids=[MockOrderBookLevel(50000.0, 5.0)],
            asks=[MockOrderBookLevel(50001.0, 5.0)]
        )

        small_estimate = calculator.calculate_impact(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_size=0.5,
            order_book=order_book
        )

        large_estimate = calculator.calculate_impact(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_size=2.0,
            order_book=order_book
        )

        # Larger orders should have higher total cost
        assert large_estimate.total_impact_bps > small_estimate.total_impact_bps

    def test_calibration_insufficient_data(self):
        """Test calibration with insufficient data."""
        params = ImpactParameters(model=ImpactModel.LINEAR)
        calculator = AdvancedMarketImpactCalculator(params)

        # Only 1 data point (insufficient)
        execution_data = [
            {
                'order_size': 1.0,
                'participation_rate': 0.1,
                'realized_impact': 0.002,
                'execution_horizon': 300.0
            }
        ]

        result = calculator.calibrate_model(execution_data, {})
        assert result['calibration_result'] == 'insufficient_data'

    def test_zero_order_size(self):
        """Test handling of zero order size."""
        params = ImpactParameters(model=ImpactModel.LINEAR)
        calculator = AdvancedMarketImpactCalculator(params)

        order_book = MockOrderBookSnapshot(
            symbol="BTCUSDT",
            timestamp=1609459200.0,
            bids=[MockOrderBookLevel(50000.0, 1.0)],
            asks=[MockOrderBookLevel(50001.0, 1.0)]
        )

        estimate = calculator.calculate_impact(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_size=0.0,
            order_book=order_book
        )

        assert abs(estimate.total_impact_bps - 0.0) < 1e-6
        assert abs(estimate.temporary_impact_bps - 0.0) < 1e-6
        assert abs(estimate.permanent_impact_bps - 0.0) < 1e-6

class TestGlobalFunctions:
    """Test global convenience functions."""

    def test_get_market_impact_calculator(self):
        """Test singleton calculator getter."""
        calc1 = get_market_impact_calculator()
        calc2 = get_market_impact_calculator()
        assert calc1 is calc2  # Should be the same instance

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
