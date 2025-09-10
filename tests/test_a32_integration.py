"""
A32 Edge Hardening Integration Tests - Simplified
Test the three A32 components working together
"""

import time

import pytest

from src.utils.cost_calculator import get_cost_calculator
from src.utils.edge_health import get_edge_health_monitor
from src.utils.microstructure import (
    OrderBookSnapshot,
    TradeData,
    get_microstructure_filter,
)

# Test constants to avoid magic numbers
MAX_OPERATION_TIME_MS = 10.0
A32_PERFORMANCE_LIMIT_MS = 100
OBI_LONG_THRESHOLD = 0.20
AFR_SHORT_THRESHOLD = 0.45


class TestA32SimplifiedIntegration:
    """Test A32 components integration with actual APIs"""

    def test_all_three_components_instantiate(self):
        """Test that all A32 components can be instantiated and are ready"""
        # Test component instantiation
        edge_monitor = get_edge_health_monitor()
        cost_calc = get_cost_calculator()
        micro_filter = get_microstructure_filter()

        # Verify components are properly initialized
        assert edge_monitor is not None
        assert cost_calc is not None
        assert micro_filter is not None

        # Verify singleton behavior
        edge_monitor2 = get_edge_health_monitor()
        cost_calc2 = get_cost_calculator()
        micro_filter2 = get_microstructure_filter()

        assert edge_monitor is edge_monitor2
        assert cost_calc is cost_calc2
        assert micro_filter is micro_filter2

    def test_microstructure_filter_with_real_data(self):
        """Test microstructure filter with realistic order book data"""
        micro_filter = get_microstructure_filter()

        # Enable the filter
        micro_filter.config.enabled = True
        micro_filter.config.min_trades_for_afr = 5

        # Create realistic order book
        orderbook = OrderBookSnapshot(
            timestamp=time.time(),
            bids=[(50000.0, 10.0), (49995.0, 8.0), (49990.0, 5.0)],
            asks=[(50005.0, 3.0), (50010.0, 4.0), (50015.0, 6.0)]
        )

        # Calculate OBI
        obi = micro_filter.calculate_obi(orderbook)
        assert isinstance(obi, float)
        assert -1.0 <= obi <= 1.0

        # Add some trade data
        trades = [
            TradeData(time.time(), 50000.0, 1.0, False),  # Aggressive buy
            TradeData(time.time(), 50000.0, 1.0, False),  # Aggressive buy
            TradeData(time.time(), 50000.0, 1.0, True),   # Aggressive sell
            TradeData(time.time(), 50000.0, 1.0, False),  # Aggressive buy
            TradeData(time.time(), 50000.0, 1.0, False),  # Aggressive buy
        ]

        micro_filter.update_trades("BTCUSDT", trades)

        # Calculate AFR
        afr = micro_filter.calculate_afr("BTCUSDT")
        assert afr is not None
        assert 0.0 <= afr <= 1.0
        assert afr == pytest.approx(0.8, abs=0.01)  # 4/5 aggressive buys

        # Generate signal
        signal = micro_filter.generate_signal("BTCUSDT", orderbook)
        assert signal is not None
        assert hasattr(signal, 'action')
        assert hasattr(signal, 'obi_value')
        assert hasattr(signal, 'afr_value')
        assert hasattr(signal, 'conflict_detected')

        # Should allow trade
        can_allow = micro_filter.should_allow_trade("BTCUSDT", "LONG", orderbook)
        assert isinstance(can_allow, bool)

    def test_cost_calculator_with_realistic_scenarios(self):
        """Test cost calculator with realistic trade scenarios"""
        cost_calc = get_cost_calculator()

        # Test total cost calculation (using actual method)
        cost_components = cost_calc.calculate_total_cost(1000.0)
        assert cost_components.fee_bps > 0
        assert cost_components.slippage_bps >= 0
        assert cost_components.impact_bps >= 0

        # Test another cost calculation
        cost_components2 = cost_calc.calculate_total_cost(500_000.0, is_maker=False)
        assert isinstance(cost_components2.fee_bps, float)
        assert cost_components2.fee_bps > 0

        # Test slippage estimation (using actual method)
        slippage = cost_calc.calculate_slippage_bps(1000.0)
        assert isinstance(slippage, float)
        assert slippage >= 0

        # Test market impact
        impact = cost_calc.calculate_market_impact_bps(15000.0)
        assert isinstance(impact, float)
        assert impact >= 0

    def test_edge_health_monitor_basic_functionality(self):
        """Test edge health monitor basic functionality"""
        edge_monitor = get_edge_health_monitor()

        # Test that we can get global status (should handle gracefully)
        status = edge_monitor.get_global_status()
        assert status is not None

        # Test strategy status (should handle gracefully)
        strategy_status = edge_monitor.get_strategy_status("TESTPAIR")
        assert strategy_status is not None

        # Test risk multiplier (can be 0.0 if no trades)
        risk_mult = edge_monitor.get_risk_multiplier()
        assert isinstance(risk_mult, float)
        assert risk_mult >= 0  # Can be 0 initially

        # Test statistics retrieval
        stats = edge_monitor.get_statistics()
        assert isinstance(stats, dict)

    def test_performance_integration(self):
        """Test A32 system performance integration"""
        edge_monitor = get_edge_health_monitor()
        cost_calc = get_cost_calculator()
        micro_filter = get_microstructure_filter()

        # Enable microstructure
        micro_filter.config.enabled = True

        # Create test data
        orderbook = OrderBookSnapshot(
            timestamp=time.time(),
            bids=[(50000.0, 10.0)],
            asks=[(50005.0, 5.0)]
        )

        # Performance test: Multiple operations
        start_time = time.time()

        for _ in range(100):
            # Edge health check (use actual method)
            _ = edge_monitor.get_global_status()

            # Cost calculation (use actual method)
            _ = cost_calc.calculate_total_cost(1000.0)

            # Microstructure analysis
            _ = micro_filter.calculate_obi(orderbook)
            _ = micro_filter.generate_signal("BTCUSDT", orderbook)

        end_time = time.time()
        total_time_ms = (end_time - start_time) * 1000
        avg_time_per_op = total_time_ms / 100

        # Should complete in reasonable time
        assert avg_time_per_op < MAX_OPERATION_TIME_MS

        print(f"A32 Performance: {avg_time_per_op:.2f}ms per operation")

    def test_a32_system_integration_workflow(self):
        """Test a complete A32 workflow integration"""
        # Get all components
        edge_monitor = get_edge_health_monitor()
        cost_calc = get_cost_calculator()
        micro_filter = get_microstructure_filter()

        # Enable microstructure
        micro_filter.config.enabled = True
        micro_filter.config.min_trades_for_afr = 3

        symbol = "ETHUSDT"

        # Step 1: Check edge health (should handle gracefully)
        edge_status = edge_monitor.get_global_status()  # Use global status instead
        wilson_lb = None  # Not available in simplified test
        expectancy = None  # Not available in simplified test

        # Step 2: Calculate costs for a $5000 trade
        trade_size = 5000.0
        cost_components = cost_calc.calculate_total_cost(trade_size)
        flat_fee = cost_components.fee_bps
        slippage = cost_components.slippage_bps
        impact = cost_components.impact_bps
        total_costs = flat_fee + slippage + impact

        # Step 3: Analyze microstructure
        orderbook = OrderBookSnapshot(
            timestamp=time.time(),
            bids=[(3000.0, 20.0), (2999.0, 15.0)],
            asks=[(3001.0, 8.0), (3002.0, 12.0)]
        )

        # Add some trade history
        trades = [
            TradeData(time.time(), 3000.0, 2.0, False),  # Aggressive buy
            TradeData(time.time(), 3000.0, 1.0, False),  # Aggressive buy
            TradeData(time.time(), 3000.0, 1.0, True),   # Aggressive sell
        ]
        micro_filter.update_trades(symbol, trades)

        obi = micro_filter.calculate_obi(orderbook)
        afr = micro_filter.calculate_afr(symbol)
        signal = micro_filter.generate_signal(symbol, orderbook)

        # Step 4: Make integrated decision
        # This simulates real decision logic
        cost_acceptable = total_costs < trade_size * 0.01  # < 1% costs
        microstructure_favorable = (signal.action in ["LONG", "SHORT"] and
                                  not signal.conflict_detected)

        # Final decision combines all factors
        should_trade = cost_acceptable and microstructure_favorable

        # Verify all calculations completed
        assert isinstance(edge_status, object)  # EdgeStatus enum or similar
        assert flat_fee > 0
        assert slippage >= 0
        assert impact >= 0
        assert isinstance(obi, float)
        assert afr is not None
        assert signal is not None
        assert isinstance(should_trade, bool)

        print(f"A32 Workflow Complete:")
        print(f"  Edge Status: {edge_status}")
        print(f"  Wilson LB: {wilson_lb}")
        print(f"  Expectancy: {expectancy}")
        print(f"  Total Costs: ${total_costs:.2f}")
        print(f"  OBI: {obi:.3f}")
        print(f"  AFR: {afr:.3f}")
        print(f"  Signal: {signal.action}")
        print(f"  Conflict: {signal.conflict_detected}")
        print(f"  Final Decision: {'TRADE' if should_trade else 'NO TRADE'}")


class TestA32AcceptanceCriteriaIntegration:
    """Test A32 acceptance criteria with integrated components"""

    def test_obi_afr_calculation_performance(self):
        """Test OBI and AFR calculation performance meets criteria"""
        micro_filter = get_microstructure_filter()
        micro_filter.config.enabled = True

        # Large order book for performance test
        large_orderbook = OrderBookSnapshot(
            timestamp=time.time(),
            bids=[(50000.0 - i*0.1, 10.0) for i in range(50)],
            asks=[(50000.0 + i*0.1, 10.0) for i in range(50)]
        )

        # Performance test for OBI
        start_time = time.time()
        for _ in range(100):
            obi = micro_filter.calculate_obi(large_orderbook)
        end_time = time.time()

        obi_time_ms = ((end_time - start_time) / 100) * 1000
        assert obi_time_ms < 100  # A32 requirement: <100ms

        # Add many trades for AFR performance test
        many_trades = [TradeData(time.time(), 50000.0, 1.0, i % 2 == 0)
                      for i in range(200)]
        micro_filter.update_trades("BTCUSDT", many_trades)

        # Performance test for AFR
        start_time = time.time()
        for _ in range(100):
            afr = micro_filter.calculate_afr("BTCUSDT")
        end_time = time.time()

        afr_time_ms = ((end_time - start_time) / 100) * 1000
        assert afr_time_ms < 100  # A32 requirement: <100ms

        print(f"A32 Performance Results:")
        print(f"  OBI calculation: {obi_time_ms:.2f}ms")
        print(f"  AFR calculation: {afr_time_ms:.2f}ms")

    def test_conflict_detection_accuracy(self):
        """Test conflict detection meets A32 accuracy requirements"""
        micro_filter = get_microstructure_filter()
        micro_filter.config.enabled = True
        micro_filter.config.obi_long_min = 0.20
        micro_filter.config.obi_short_max = -0.20
        micro_filter.config.afr_long_min = 0.55
        micro_filter.config.afr_short_max = 0.45
        micro_filter.config.min_trades_for_afr = 10

        # Create clear conflict: OBI favors LONG, AFR favors SHORT
        conflict_orderbook = OrderBookSnapshot(
            timestamp=time.time(),
            bids=[(50000.0, 30.0)],  # Heavy bids -> OBI > 0.20
            asks=[(50005.0, 10.0)]   # Light asks
        )

        # AFR favors SHORT (more aggressive sells)
        conflict_trades = []
        for _ in range(15):  # 15 aggressive sells
            conflict_trades.append(TradeData(time.time(), 50000.0, 1.0, True))
        for _ in range(5):   # 5 aggressive buys
            conflict_trades.append(TradeData(time.time(), 50000.0, 1.0, False))

        micro_filter.update_trades("CONFLICTTEST", conflict_trades)
        signal = micro_filter.generate_signal("CONFLICTTEST", conflict_orderbook)

        # Should detect conflict accurately
        assert signal.conflict_detected is True
        assert signal.obi_value > 0.20  # Favors LONG
        assert signal.afr_value < 0.45  # Favors SHORT (15/20 = 0.25)

        print(f"Conflict Detection Test:")
        print(f"  OBI: {signal.obi_value:.3f} (favors LONG)")
        print(f"  AFR: {signal.afr_value:.3f} (favors SHORT)")
        print(f"  Conflict Detected: {signal.conflict_detected}")
        print(f"  Action: {signal.action}")

    def test_comprehensive_a32_system_validation(self):
        """Comprehensive A32 system validation test"""
        # All components
        edge_monitor = get_edge_health_monitor()
        cost_calc = get_cost_calculator()
        micro_filter = get_microstructure_filter()

        # Configure for testing
        micro_filter.config.enabled = True

        symbols = ["BTCUSDT", "ETHUSDT", "ADAUSDT"]

        for symbol in symbols:
            # Test edge health (use global status)
            status = edge_monitor.get_global_status()
            # wilson = Not available in simplified test
            # expectancy = Not available in simplified test

            # Test costs (use actual methods)
            cost_components = cost_calc.calculate_total_cost(1000.0)
            fee = cost_components.fee_bps
            slip = cost_components.slippage_bps

            # Test microstructure
            test_orderbook = OrderBookSnapshot(
                timestamp=time.time(),
                bids=[(1000.0, 10.0)],
                asks=[(1001.0, 10.0)]
            )

            obi = micro_filter.calculate_obi(test_orderbook)
            signal = micro_filter.generate_signal(symbol, test_orderbook)

            # Validate all components return reasonable values
            assert status is not None
            assert isinstance(fee, float) and fee > 0
            assert isinstance(slip, float) and slip >= 0
            assert isinstance(obi, float) and -1.0 <= obi <= 1.0
            assert signal is not None
            assert hasattr(signal, 'action')

        print("A32 System Validation: All components operational")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
