"""
Integration test for advanced market impact models framework.
"""

import pytest
from src.execution.advanced_impact_models import (
    ImpactModel,
    ImpactParameters,
    AdvancedMarketImpactCalculator,
    get_market_impact_calculator
)

# Test constants
FLOAT_TOLERANCE = 1e-6
CONFIDENCE_INTERVAL_SIZE = 2

class TestAdvancedImpactFramework:
    """Integration tests for the advanced impact framework."""

    def test_framework_initialization(self):
        """Test that the framework initializes correctly."""
        # Test default parameters
        params = ImpactParameters()
        assert params.model == ImpactModel.SQUARE_ROOT  # Default is square_root
        assert abs(params.temporary_impact_coef - 0.1) < FLOAT_TOLERANCE  # Default 0.1

        # Test custom parameters
        custom_params = ImpactParameters(
            model=ImpactModel.LINEAR,
            temporary_impact_coef=0.002,
            permanent_impact_coef=0.001
        )
        assert custom_params.model == ImpactModel.LINEAR
        assert abs(custom_params.temporary_impact_coef - 0.002) < FLOAT_TOLERANCE

    def test_calculator_creation(self):
        """Test calculator creation with different parameters."""
        # Linear model
        linear_params = ImpactParameters(
            model=ImpactModel.LINEAR,
            temporary_impact_coef=0.001
        )
        linear_calc = AdvancedMarketImpactCalculator(linear_params)
        assert linear_calc.impact_params.model == ImpactModel.LINEAR

        # Square root model
        sqrt_params = ImpactParameters(
            model=ImpactModel.SQUARE_ROOT,
            temporary_impact_coef=0.002,
            volatility=0.03
        )
        sqrt_calc = AdvancedMarketImpactCalculator(sqrt_params)
        assert sqrt_calc.impact_params.model == ImpactModel.SQUARE_ROOT
        assert abs(sqrt_calc.impact_params.volatility - 0.03) < FLOAT_TOLERANCE

    def test_all_impact_models_available(self):
        """Test that all impact models are properly defined."""
        # Check all models can be instantiated
        models_to_test = [
            ImpactModel.LINEAR,
            ImpactModel.SQUARE_ROOT,
            ImpactModel.KYLE_LAMBDA,
            ImpactModel.POWER_LAW,
            ImpactModel.CONCAVE
        ]

        for model in models_to_test:
            params = ImpactParameters(model=model)
            calculator = AdvancedMarketImpactCalculator(params)
            assert calculator.impact_params.model == model

    def test_singleton_calculator(self):
        """Test that singleton calculator works correctly."""
        calc1 = get_market_impact_calculator()
        calc2 = get_market_impact_calculator()

        # Should be the same instance
        assert calc1 is calc2

        # Should have default parameters
        assert calc1.impact_params.model == ImpactModel.SQUARE_ROOT  # Default model

    def test_parameter_validation(self):
        """Test parameter validation for edge cases."""
        # Test negative coefficients (should work)
        params = ImpactParameters(
            temporary_impact_coef=-0.001,  # Negative coefficient
            permanent_impact_coef=0.0
        )
        calculator = AdvancedMarketImpactCalculator(params)
        assert calculator.impact_params.temporary_impact_coef < 0

        # Test zero coefficients
        zero_params = ImpactParameters(
            temporary_impact_coef=0.0,
            permanent_impact_coef=0.0
        )
        zero_calc = AdvancedMarketImpactCalculator(zero_params)
        assert abs(zero_calc.impact_params.temporary_impact_coef - 0.0) < FLOAT_TOLERANCE

        # Test very large coefficients
        large_params = ImpactParameters(
            temporary_impact_coef=1.0,  # 100% impact
            volatility=0.5  # 50% volatility
        )
        large_calc = AdvancedMarketImpactCalculator(large_params)
        assert large_calc.impact_params.temporary_impact_coef > 0.9

    def test_calibration_data_structure(self):
        """Test calibration data handling."""
        # Test with empty calibration data
        calculator = AdvancedMarketImpactCalculator(calibration_data={})
        assert calculator.calibration_data == {}

        # Test with sample calibration data
        sample_data = {
            'last_calibrated': 1609459200,
            'sample_count': 100,
            'correlation': 0.85
        }
        calc_with_data = AdvancedMarketImpactCalculator(calibration_data=sample_data)
        assert calc_with_data.calibration_data['sample_count'] == 100
        assert abs(calc_with_data.calibration_data['correlation'] - 0.85) < FLOAT_TOLERANCE

    def test_model_specific_parameters(self):
        """Test model-specific parameter usage."""
        # Kyle's lambda model
        kyle_params = ImpactParameters(
            model=ImpactModel.KYLE_LAMBDA,
            liquidity_lambda=0.005,
            volatility=0.025
        )
        kyle_calc = AdvancedMarketImpactCalculator(kyle_params)
        assert abs(kyle_calc.impact_params.liquidity_lambda - 0.005) < FLOAT_TOLERANCE

        # Power law model
        power_params = ImpactParameters(
            model=ImpactModel.POWER_LAW,
            power_exponent=0.75,
            volume_rate=8000.0
        )
        power_calc = AdvancedMarketImpactCalculator(power_params)
        assert abs(power_calc.impact_params.power_exponent - 0.75) < FLOAT_TOLERANCE
        assert abs(power_calc.impact_params.volume_rate - 8000.0) < FLOAT_TOLERANCE

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
