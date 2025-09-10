"""
Tests for advanced market impact models.
"""

import pytest
import numpy as np
from dataclasses import dataclass
from typing import Dict, List, Any

from src.execution.advanced_impact_models import (
    ImpactModel,
    ImpactParameters,
    MarketImpactEstimate,
    AdvancedMarketImpactCalculator,
    OrderSide,
    get_market_impact_calculator,
    calculate_market_impact
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

@pytest.fixture
def sample_impact_params():
    """Sample impact parameters for testing."""
    return ImpactParameters(
        model=ImpactModel.LINEAR,
        temporary_impact_coef=0.001,
        permanent_impact_coef=0.0005,
        volatility=0.02,
        volume_rate=10000.0,
        power_exponent=0.5,
        liquidity_lambda=0.001,
        resilience_half_life=300.0
    )

@pytest.fixture
def sample_order_book():
    """Sample order book for testing."""
    return MockOrderBookSnapshot(
        symbol="BTCUSDT",
        timestamp=1609459200.0,
        bids=[
            MockOrderBookLevel(50000.0, 1.0),
            MockOrderBookLevel(49999.0, 2.0),
            MockOrderBookLevel(49998.0, 3.0),
            MockOrderBookLevel(49997.0, 4.0),
            MockOrderBookLevel(49996.0, 5.0),
        ],
        asks=[
            MockOrderBookLevel(50001.0, 1.0),
            MockOrderBookLevel(50002.0, 2.0),
            MockOrderBookLevel(50003.0, 3.0),
            MockOrderBookLevel(50004.0, 4.0),
            MockOrderBookLevel(50005.0, 5.0),
        ]
    )

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
        assert params.temporary_impact_coef == 0.001
        assert params.permanent_impact_coef == 0.0005
        assert params.volatility == 0.01  # default
        assert params.volume_rate == 5000.0  # default

    def test_impact_parameters_immutable(self):
        """Test that ImpactParameters is immutable (frozen dataclass)."""
        params = ImpactParameters(
            model=ImpactModel.LINEAR,
            temporary_impact_coef=0.001
        )
        with pytest.raises(AttributeError):
            params.temporary_impact_coef = 0.002  # Should fail

class TestMarketImpactEstimate:
    """Test MarketImpactEstimate class."""

    def test_estimate_creation(self):
        """Test basic creation of market impact estimate."""
        estimate = MarketImpactEstimate(
            symbol="BTCUSDT",
            total_cost_bps=5.0,
            temporary_impact_bps=3.0,
            permanent_impact_bps=2.0,
            confidence_interval=(4.0, 6.0),
            optimal_participation_rate=0.1
        )
        assert estimate.symbol == "BTCUSDT"
        assert estimate.total_cost_bps == 5.0
        assert estimate.confidence_interval == (4.0, 6.0)

class TestAdvancedMarketImpactCalculator:
    """Test AdvancedMarketImpactCalculator class."""

    def test_calculator_initialization(self, sample_impact_params):
        """Test calculator initialization."""
        calculator = AdvancedMarketImpactCalculator(sample_impact_params)
        assert calculator.impact_params.model == ImpactModel.LINEAR
        assert calculator.impact_params.temporary_impact_coef == 0.001

    def test_linear_impact_calculation(self, sample_impact_params, sample_order_book):
        """Test linear impact model calculation."""
        sample_impact_params = ImpactParameters(
            model=ImpactModel.LINEAR,
            temporary_impact_coef=0.001,
            permanent_impact_coef=0.0005,
            volatility=0.02,
            volume_rate=10000.0
        )
        calculator = AdvancedMarketImpactCalculator(sample_impact_params)

        estimate = calculator.calculate_impact(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_size=1.0,
            order_book=sample_order_book,
            execution_horizon=300.0
        )

        assert estimate.symbol == "BTCUSDT"
        assert estimate.total_cost_bps > 0
        assert estimate.temporary_impact_bps >= 0
        assert estimate.permanent_impact_bps >= 0
        assert len(estimate.confidence_interval) == 2
        assert estimate.confidence_interval[0] <= estimate.confidence_interval[1]

    def test_square_root_impact_calculation(self, sample_order_book):
        """Test square-root (Almgren-Chriss) impact model."""
        params = ImpactParameters(
            model=ImpactModel.SQUARE_ROOT,
            temporary_impact_coef=0.001,
            permanent_impact_coef=0.0005,
            volatility=0.02,
            volume_rate=10000.0
        )
        calculator = AdvancedMarketImpactCalculator(params)

        estimate = calculator.calculate_impact(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_size=2.0,
            order_book=sample_order_book,
            execution_horizon=300.0
        )

        assert estimate.total_cost_bps > 0
        assert estimate.optimal_participation_rate > 0
        assert estimate.optimal_participation_rate <= 1.0

    def test_kyle_lambda_impact_calculation(self, sample_order_book):
        """Test Kyle's lambda impact model."""
        params = ImpactParameters(
            model=ImpactModel.KYLE_LAMBDA,
            liquidity_lambda=0.001,
            volatility=0.02
        )
        calculator = AdvancedMarketImpactCalculator(params)

        estimate = calculator.calculate_impact(
            symbol="BTCUSDT",
            side=OrderSide.SELL,
            order_size=1.5,
            order_book=sample_order_book
        )

        assert estimate.total_cost_bps > 0
        assert estimate.symbol == "BTCUSDT"

    def test_power_law_impact_calculation(self, sample_order_book):
        """Test power-law impact model."""
        params = ImpactParameters(
            model=ImpactModel.POWER_LAW,
            temporary_impact_coef=0.001,
            power_exponent=0.6,
            volume_rate=10000.0
        )
        calculator = AdvancedMarketImpactCalculator(params)

        estimate = calculator.calculate_impact(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_size=0.5,
            order_book=sample_order_book
        )

        assert estimate.total_cost_bps > 0
        assert estimate.temporary_impact_bps >= 0

    def test_concave_impact_calculation(self, sample_order_book):
        """Test concave impact model."""
        params = ImpactParameters(
            model=ImpactModel.CONCAVE,
            temporary_impact_coef=0.001,
            volume_rate=10000.0
        )
        calculator = AdvancedMarketImpactCalculator(params)

        estimate = calculator.calculate_impact(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_size=3.0,
            order_book=sample_order_book
        )

        assert estimate.total_cost_bps > 0
        # Concave model should show sublinear scaling
        assert estimate.temporary_impact_bps >= 0

    def test_different_order_sides(self, sample_impact_params, sample_order_book):
        """Test that BUY and SELL orders produce similar impacts."""
        calculator = AdvancedMarketImpactCalculator(sample_impact_params)

        buy_estimate = calculator.calculate_impact(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_size=1.0,
            order_book=sample_order_book
        )

        sell_estimate = calculator.calculate_impact(
            symbol="BTCUSDT",
            side=OrderSide.SELL,
            order_size=1.0,
            order_book=sample_order_book
        )

        # Impacts should be similar for same size
        assert abs(buy_estimate.total_cost_bps - sell_estimate.total_cost_bps) < 0.1

    def test_order_size_scaling(self, sample_impact_params, sample_order_book):
        """Test that larger orders have higher impact."""
        calculator = AdvancedMarketImpactCalculator(sample_impact_params)

        small_estimate = calculator.calculate_impact(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_size=0.5,
            order_book=sample_order_book
        )

        large_estimate = calculator.calculate_impact(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_size=2.0,
            order_book=sample_order_book
        )

        # Larger orders should have higher total cost
        assert large_estimate.total_cost_bps > small_estimate.total_cost_bps

    def test_calibration_basic(self, sample_impact_params):
        """Test basic calibration functionality."""
        calculator = AdvancedMarketImpactCalculator(sample_impact_params)

        # Mock execution data
        execution_data = [
            {
                'order_size': 1.0,
                'participation_rate': 0.1,
                'realized_impact': 0.002,
                'execution_horizon': 300.0
            },
            {
                'order_size': 2.0,
                'participation_rate': 0.15,
                'realized_impact': 0.003,
                'execution_horizon': 400.0
            },
            {
                'order_size': 0.5,
                'participation_rate': 0.05,
                'realized_impact': 0.001,
                'execution_horizon': 200.0
            }
        ]

        result = calculator.calibrate_model(execution_data)

        assert 'calibration_result' in result
        assert 'adjusted_parameters' in result
        assert result['calibration_result'] in ['success', 'insufficient_data']

    def test_insufficient_calibration_data(self, sample_impact_params):
        """Test calibration with insufficient data."""
        calculator = AdvancedMarketImpactCalculator(sample_impact_params)

        # Only 1 data point (insufficient)
        execution_data = [
            {
                'order_size': 1.0,
                'participation_rate': 0.1,
                'realized_impact': 0.002,
                'execution_horizon': 300.0
            }
        ]

        result = calculator.calibrate_model(execution_data)
        assert result['calibration_result'] == 'insufficient_data'

class TestGlobalFunctions:
    """Test global convenience functions."""

    def test_get_market_impact_calculator(self):
        """Test singleton calculator getter."""
        calc1 = get_market_impact_calculator()
        calc2 = get_market_impact_calculator()
        assert calc1 is calc2  # Should be the same instance

    def test_calculate_market_impact_convenience(self, sample_order_book):
        """Test convenience function for impact calculation."""
        estimate = calculate_market_impact(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_size=1.0,
            order_book=sample_order_book,
            execution_horizon=300.0
        )

        assert estimate.symbol == "BTCUSDT"
        assert estimate.total_cost_bps > 0

class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_zero_order_size(self, sample_impact_params, sample_order_book):
        """Test handling of zero order size."""
        calculator = AdvancedMarketImpactCalculator(sample_impact_params)

        estimate = calculator.calculate_impact(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_size=0.0,
            order_book=sample_order_book
        )

        assert estimate.total_cost_bps == 0.0
        assert estimate.temporary_impact_bps == 0.0
        assert estimate.permanent_impact_bps == 0.0

    def test_very_large_order(self, sample_impact_params, sample_order_book):
        """Test handling of very large orders."""
        calculator = AdvancedMarketImpactCalculator(sample_impact_params)

        estimate = calculator.calculate_impact(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_size=1000.0,  # Very large order
            order_book=sample_order_book
        )

        # Should still produce valid estimate
        assert estimate.total_cost_bps > 0
        assert estimate.total_cost_bps < 10000  # Sanity check

    def test_empty_order_book(self, sample_impact_params):
        """Test handling of empty order book."""
        calculator = AdvancedMarketImpactCalculator(sample_impact_params)

        empty_book = MockOrderBookSnapshot(
            symbol="BTCUSDT",
            timestamp=1609459200.0,
            bids=[],
            asks=[]
        )

        estimate = calculator.calculate_impact(
            symbol="BTCUSDT",
            side=OrderSide.BUY,
            order_size=1.0,
            order_book=empty_book
        )

        # Should handle gracefully with higher impact
        assert estimate.total_cost_bps >= 0

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
