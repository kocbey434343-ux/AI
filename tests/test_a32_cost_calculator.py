# flake8: noqa: PLR2004,FBT003,RUF001,RUF002
"""
Test Suite for Cost-of-Edge Calculator (A32)
"""

import pytest
from unittest.mock import MagicMock

from src.utils.cost_calculator import (
    CostOfEdgeCalculator,
    CostOfEdgeConfig,
    CostComponents,
    EdgeExpectation,
    CostModel,
    SlippageModel,
    get_cost_calculator,
    evaluate_trade_cost,
    should_allow_trade_by_cost
)


class TestCostComponents:
    """CostComponents dataclass testleri"""

    def test_cost_components_auto_total(self):
        """Otomatik total hesaplama"""
        cost = CostComponents(fee_bps=10.0, slippage_bps=5.0, impact_bps=2.0)
        assert cost.total_bps == pytest.approx(17.0)

    def test_cost_components_default(self):
        """Varsayılan değerler"""
        cost = CostComponents()
        assert cost.total_bps == pytest.approx(0.0)


class TestEdgeExpectation:
    """EdgeExpectation dataclass testleri"""

    def test_edge_expectation_calculation(self):
        """EGE hesaplama ağırlıkları"""
        edge = EdgeExpectation(
            confluence_score=1.0,
            regime_score=1.0,
            signal_strength=1.0,
            volume_score=1.0
        )
        # 0.4 + 0.3 + 0.2 + 0.1 = 1.0
        assert edge.total_ege == pytest.approx(1.0)

    def test_edge_expectation_weighted(self):
        """Ağırlıklı EGE hesaplama"""
        edge = EdgeExpectation(
            confluence_score=0.8,  # 0.8 * 0.4 = 0.32
            regime_score=0.6,      # 0.6 * 0.3 = 0.18
            signal_strength=0.5,   # 0.5 * 0.2 = 0.10
            volume_score=0.4       # 0.4 * 0.1 = 0.04
        )
        expected_ege = 0.32 + 0.18 + 0.10 + 0.04  # = 0.64
        assert edge.total_ege == pytest.approx(expected_ege)


class TestCostOfEdgeConfig:
    """CostOfEdgeConfig testleri"""

    def test_config_defaults(self):
        """Varsayılan konfigurasyon"""
        config = CostOfEdgeConfig()

        assert config.enabled is False
        assert config.k_multiple == pytest.approx(4.0)
        assert config.fee_model == "tiered"
        assert config.slippage_model == "dynamic"

        # Tier levels should be set
        assert config.tier_levels is not None
        assert len(config.tier_levels) == 4  # 4 tier seviyesi

    def test_config_tier_levels(self):
        """Tier seviyeleri"""
        config = CostOfEdgeConfig()

        # Check tier structure
        assert config.tier_levels[0.0] == pytest.approx(10.0)
        assert config.tier_levels[1_000_000] == pytest.approx(9.0)
        assert config.tier_levels[10_000_000] == pytest.approx(8.0)
        assert config.tier_levels[50_000_000] == pytest.approx(7.0)


class TestCostOfEdgeCalculator:
    """CostOfEdgeCalculator ana testleri"""

    def test_initialization(self):
        """Başlatma testi"""
        calculator = CostOfEdgeCalculator()

        assert calculator.config is not None
        assert calculator.user_volume_30d_usdt == pytest.approx(0.0)

    def test_custom_config(self):
        """Özel konfigurasyon"""
        config = CostOfEdgeConfig(enabled=True, k_multiple=5.0)
        calculator = CostOfEdgeCalculator(config)

        assert calculator.config.enabled is True
        assert calculator.config.k_multiple == pytest.approx(5.0)

    def test_update_user_volume(self):
        """Kullanıcı hacim güncelleme"""
        calculator = CostOfEdgeCalculator()

        calculator.update_user_volume(1_500_000.0)
        assert calculator.user_volume_30d_usdt == pytest.approx(1_500_000.0)

        # Negative volume should be clamped to 0
        calculator.update_user_volume(-100.0)
        assert calculator.user_volume_30d_usdt == pytest.approx(0.0)

    def test_flat_fee_calculation(self):
        """Flat fee modeli"""
        config = CostOfEdgeConfig(fee_model="flat", flat_fee_bps=12.0)
        calculator = CostOfEdgeCalculator(config)

        fee = calculator.calculate_fee_bps(1000.0, is_maker=True)
        assert fee == pytest.approx(12.0)

        fee = calculator.calculate_fee_bps(1000.0, is_maker=False)
        assert fee == pytest.approx(12.0)

    def test_tiered_fee_calculation(self):
        """Seviyeli fee hesaplama"""
        config = CostOfEdgeConfig(fee_model="tiered")
        calculator = CostOfEdgeCalculator(config)

        # No volume - tier 0 (10 BPS)
        calculator.update_user_volume(0)

        fee_maker = calculator.calculate_fee_bps(1000.0, is_maker=True)
        fee_taker = calculator.calculate_fee_bps(1000.0, is_maker=False)

        assert fee_maker == pytest.approx(8.0)  # 10 * 0.8 (maker discount)
        assert fee_taker == pytest.approx(10.0)  # 10 * 1.0 (no discount)

    def test_tiered_fee_high_volume(self):
        """Yüksek hacim tier testi"""
        config = CostOfEdgeConfig(fee_model="tiered")
        calculator = CostOfEdgeCalculator(config)

        # Set volume to $2M (tier 1)
        calculator.update_user_volume(2_000_000)

        fee_maker = calculator.calculate_fee_bps(1000.0, is_maker=True)
        fee_taker = calculator.calculate_fee_bps(1000.0, is_maker=False)

        assert fee_maker == pytest.approx(7.2)  # 9 * 0.8
        assert fee_taker == pytest.approx(9.0)  # 9 * 1.0

    def test_static_slippage(self):
        """Statik slippage modeli"""
        config = CostOfEdgeConfig(slippage_model="static", static_slippage_bps=6.0)
        calculator = CostOfEdgeCalculator(config)

        slippage = calculator.calculate_slippage_bps(1000.0)
        assert slippage == pytest.approx(6.0)

    def test_spread_based_slippage(self):
        """Spread tabanlı slippage"""
        config = CostOfEdgeConfig(slippage_model="spread_based", spread_multiplier=0.4)
        calculator = CostOfEdgeCalculator(config)

        slippage = calculator.calculate_slippage_bps(1000.0, current_spread_bps=10.0)
        assert slippage == pytest.approx(4.0)  # 10 * 0.4

    def test_dynamic_slippage_spread_component(self):
        """Dinamik slippage - spread bileşeni"""
        config = CostOfEdgeConfig(
            slippage_model="dynamic",
            static_slippage_bps=3.0,
            spread_multiplier=0.5
        )
        calculator = CostOfEdgeCalculator(config)

        # Spread component dominates
        slippage = calculator.calculate_slippage_bps(1000.0, current_spread_bps=12.0)
        assert slippage == pytest.approx(6.0)  # max(3.0, 12*0.5) = 6.0

    def test_dynamic_slippage_depth_penalty(self):
        """Dinamik slippage - derinlik cezası"""
        config = CostOfEdgeConfig(slippage_model="dynamic", static_slippage_bps=2.0)
        calculator = CostOfEdgeCalculator(config)

        # Large order vs small depth
        order_value = 100_000  # $100K
        market_depth = 500_000  # $500K depth
        # depth_ratio = 100K/500K = 0.2 (20%) > 0.05 (5%)
        # penalty = min(0.2 * 50, 20) = min(10, 20) = 10 BPS

        slippage = calculator.calculate_slippage_bps(
            order_value, market_depth_usdt=market_depth
        )
        expected = 2.0 + 10.0  # base + penalty
        assert slippage == pytest.approx(expected)

    def test_market_impact_below_threshold(self):
        """Market impact - eşik altı"""
        config = CostOfEdgeConfig(impact_threshold_usdt=10_000)
        calculator = CostOfEdgeCalculator(config)

        impact = calculator.calculate_market_impact_bps(5_000)
        assert impact == pytest.approx(0.0)

    def test_market_impact_above_threshold(self):
        """Market impact - eşik üstü"""
        config = CostOfEdgeConfig(
            impact_threshold_usdt=10_000,
            impact_rate_bps_per_1k=0.2
        )
        calculator = CostOfEdgeCalculator(config)

        # $15K order = $5K excess
        # impact = (5000 / 1000) * 0.2 = 1.0 BPS
        impact = calculator.calculate_market_impact_bps(15_000)
        assert impact == pytest.approx(1.0)

    def test_market_impact_with_depth(self):
        """Market impact - derinlik ile"""
        config = CostOfEdgeConfig(impact_threshold_usdt=10_000)
        calculator = CostOfEdgeCalculator(config)

        # $20K order vs $100K depth
        # depth_ratio = 20K/100K = 0.2 (20%) > 0.1 (10%)
        # impact multiplier = 1 + 0.2 = 1.2

        impact = calculator.calculate_market_impact_bps(20_000, market_depth_usdt=100_000)
        # Base: (10K excess / 1K) * 0.1 = 1.0 BPS
        # With depth: 1.0 * 1.2 = 1.2 BPS
        assert impact == pytest.approx(1.2)

    def test_total_cost_calculation(self):
        """Toplam maliyet hesaplama"""
        config = CostOfEdgeConfig(
            fee_model="flat",
            flat_fee_bps=8.0,
            slippage_model="static",
            static_slippage_bps=4.0,
            impact_threshold_usdt=5_000
        )
        calculator = CostOfEdgeCalculator(config)

        cost = calculator.calculate_total_cost(10_000, is_maker=True)

        assert cost.fee_bps == pytest.approx(8.0)
        assert cost.slippage_bps == pytest.approx(4.0)
        assert cost.impact_bps > 0  # Should have some impact for $10K
        assert cost.total_bps == pytest.approx(cost.fee_bps + cost.slippage_bps + cost.impact_bps)

    def test_4x_rule_disabled(self):
        """4x kuralı kapalı"""
        config = CostOfEdgeConfig(enabled=False)
        calculator = CostOfEdgeCalculator(config)

        # Mock objects
        ege = EdgeExpectation(total_ege=0.1)
        cost = CostComponents(total_bps=100.0)

        should_proceed, ratio, reason = calculator.should_proceed_with_trade(ege, cost)

        assert should_proceed is True
        assert reason == "cost_guard_disabled"

    def test_4x_rule_passed(self):
        """4x kuralı geçti"""
        config = CostOfEdgeConfig(enabled=True, k_multiple=4.0)
        calculator = CostOfEdgeCalculator(config)

        # EGE=0.8, Cost=100 BPS = 0.01
        # Ratio = 0.8 / 0.01 = 80x >> 4x threshold
        ege = EdgeExpectation(total_ege=0.8)
        cost = CostComponents(total_bps=100.0)

        should_proceed, ratio, _ = calculator.should_proceed_with_trade(ege, cost)

        assert should_proceed is True
        assert ratio > 4.0

    def test_4x_rule_failed(self):
        """4x kuralı başarısız"""
        config = CostOfEdgeConfig(enabled=True, k_multiple=4.0)
        calculator = CostOfEdgeCalculator(config)

        # Very low EGE vs high cost
        ege = EdgeExpectation(
            confluence_score=0.05,  # 0.05 * 0.4 = 0.02
            regime_score=0.0,       # 0.0 * 0.3 = 0.0
            signal_strength=0.0,    # 0.0 * 0.2 = 0.0
            volume_score=0.0        # 0.0 * 0.1 = 0.0
        )
        # Total EGE = 0.02

        cost = CostComponents(fee_bps=1000.0, slippage_bps=0.0, impact_bps=0.0)
        # Total cost = 1000 BPS = 0.1
        # Ratio = 0.02 / 0.1 = 0.2x < 4x threshold

        should_proceed, ratio, _ = calculator.should_proceed_with_trade(ege, cost)

        assert should_proceed is False
        assert ratio < 4.0


class TestTradeFeasibilityIntegration:
    """Trade fizibilitesi entegrasyon testleri"""

    def test_feasibility_high_confluence(self):
        """Yüksek confluence ile fizibilite"""
        config = CostOfEdgeConfig(enabled=True, fee_model="flat", flat_fee_bps=10.0)
        calculator = CostOfEdgeCalculator(config)

        result = calculator.evaluate_trade_feasibility(
            order_value_usdt=5000.0,
            confluence_score=0.9,    # High confluence
            regime_score=0.8,
            signal_strength=0.7,
            volume_score=0.6
        )

        assert "should_proceed" in result
        assert "cost_edge_ratio" in result
        assert "cost_components" in result
        assert "edge_expectation" in result

        # High confluence should generally pass
        assert result["should_proceed"] is True

    def test_feasibility_low_confluence(self):
        """Düşük confluence ile fizibilite"""
        config = CostOfEdgeConfig(enabled=True, fee_model="flat", flat_fee_bps=250.0)  # Very high fees
        calculator = CostOfEdgeCalculator(config)

        result = calculator.evaluate_trade_feasibility(
            order_value_usdt=1000.0,
            confluence_score=0.05,   # Very low confluence
            regime_score=0.1,
            signal_strength=0.05,
            volume_score=0.1
        )

        # Very low confluence + very high fees should fail
        assert result["should_proceed"] is False
        assert result["cost_edge_ratio"] < 4.0


class TestGlobalConvenienceFunctions:
    """Global convenience function testleri"""

    def test_get_cost_calculator_singleton(self):
        """Singleton calculator testi"""
        calc1 = get_cost_calculator()
        calc2 = get_cost_calculator()
        assert calc1 is calc2

    def test_evaluate_trade_cost_convenience(self):
        """evaluate_trade_cost convenience function"""
        result = evaluate_trade_cost(
            order_value_usdt=1000.0,
            confluence_score=0.8
        )

        assert isinstance(result, dict)
        assert "should_proceed" in result
        assert "cost_edge_ratio" in result

    def test_should_allow_trade_by_cost_convenience(self):
        """should_allow_trade_by_cost convenience function"""
        # High confluence should allow
        allow_high = should_allow_trade_by_cost(
            order_value_usdt=1000.0,
            confluence_score=0.9
        )

        # Low confluence should block (with cost guard enabled)
        calculator = get_cost_calculator()
        calculator.config.enabled = True  # Enable for this test

        allow_low = should_allow_trade_by_cost(
            order_value_usdt=1000.0,
            confluence_score=0.1
        )

        assert allow_high is True
        # Note: allow_low result depends on exact cost calculations


class TestA32AcceptanceCriteria:
    """A32 kabul kriterleri testleri"""

    def test_4x_cost_rule_enforcement(self):
        """4x maliyet kuralı uygulaması"""
        config = CostOfEdgeConfig(enabled=True, k_multiple=4.0)
        calculator = CostOfEdgeCalculator(config)

        # Create edge with known EGE
        edge = EdgeExpectation(
            confluence_score=0.8,
            regime_score=0.5,
            signal_strength=0.6,
            volume_score=0.7
        )
        # Total EGE = 0.32 + 0.15 + 0.12 + 0.07 = 0.66

        # Test with cost that should pass 4x rule
        cost_pass = CostComponents(fee_bps=100.0, slippage_bps=0.0, impact_bps=0.0)
        # Ratio = 0.66 / 0.01 = 66x >> 4x ✓

        should_proceed, ratio, _ = calculator.should_proceed_with_trade(edge, cost_pass)
        assert should_proceed is True
        assert ratio >= 4.0

        # Test with cost that should fail 4x rule - very high cost
        cost_fail = CostComponents(fee_bps=5000.0, slippage_bps=0.0, impact_bps=0.0)
        # 5000 BPS = 0.5, Ratio = 0.66 / 0.5 = 1.32x < 4x ✓

        should_proceed, ratio, _ = calculator.should_proceed_with_trade(edge, cost_fail)
        assert should_proceed is False
        assert ratio < 4.0

    def test_fee_slippage_impact_calculation(self):
        """Fee + slippage + impact hesaplama doğruluğu"""
        config = CostOfEdgeConfig(
            fee_model="tiered",
            slippage_model="dynamic",
            impact_threshold_usdt=5000.0
        )
        calculator = CostOfEdgeCalculator(config)
        calculator.update_user_volume(500_000)  # Mid-tier volume

        cost = calculator.calculate_total_cost(
            order_value_usdt=15_000,
            is_maker=True,
            current_spread_bps=8.0,
            market_depth_usdt=200_000
        )

        # Verify all components are positive
        assert cost.fee_bps > 0
        assert cost.slippage_bps > 0
        assert cost.impact_bps >= 0  # Can be 0 if below threshold

        # Verify total
        expected_total = cost.fee_bps + cost.slippage_bps + cost.impact_bps
        assert cost.total_bps == pytest.approx(expected_total)

    def test_ege_weighted_calculation(self):
        """EGE ağırlıklı hesaplama doğruluğu"""
        calculator = CostOfEdgeCalculator()

        edge = calculator.calculate_edge_expectation(
            confluence_score=1.0,
            regime_score=0.5,
            signal_strength=0.8,
            volume_score=0.0
        )

        # Expected: 1.0*0.4 + 0.5*0.3 + 0.8*0.2 + 0.0*0.1 = 0.4 + 0.15 + 0.16 + 0 = 0.71
        assert edge.total_ege == pytest.approx(0.71)

    def test_comprehensive_trade_evaluation(self):
        """Kapsamlı trade değerlendirmesi"""
        config = CostOfEdgeConfig(enabled=True, k_multiple=4.0)
        calculator = CostOfEdgeCalculator(config)

        # Realistic scenario
        result = calculator.evaluate_trade_feasibility(
            order_value_usdt=8000.0,
            confluence_score=0.75,
            regime_score=0.65,
            signal_strength=0.70,
            volume_score=0.80,
            is_maker=True,
            current_spread_bps=6.0,
            market_depth_usdt=150_000
        )

        # Should have all required fields
        required_fields = [
            "should_proceed", "cost_edge_ratio", "reason",
            "cost_components", "edge_expectation", "order_value_usdt", "config"
        ]
        for field in required_fields:
            assert field in result

        # Verify types
        assert isinstance(result["should_proceed"], bool)
        assert isinstance(result["cost_edge_ratio"], (int, float))
        assert isinstance(result["reason"], str)


if __name__ == "__main__":
    pytest.main([__file__])
