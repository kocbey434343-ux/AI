# flake8: noqa: PLR2004,FBT003,RUF001,PLW0622
"""
Test Suite for Edge Health Monitor (A32) - Simplified
"""

import pytest
from datetime import datetime

from src.utils.edge_health import (
    EdgeHealthMonitor,
    EdgeStatus,
    TradeResult,
    get_edge_health_monitor,
    add_trade_result,
    get_edge_status,
    should_allow_trade,
    get_risk_multiplier
)


class TestEdgeHealthMonitorBasic:
    """Temel EdgeHealthMonitor testleri"""

    def test_initialization_defaults(self):
        """Varsayılan başlatma"""
        monitor = EdgeHealthMonitor()
        assert monitor.window_trades == 200
        assert monitor.min_trades == 50
        assert len(monitor.trade_results) == 0

    def test_trade_result_basic(self):
        """Temel TradeResult testi"""
        result = TradeResult("BTCUSDT", 1.5, datetime.now(), True)
        assert result.symbol == "BTCUSDT"
        assert result.win is True
        assert result.strategy_id is None

    def test_add_trade_results(self):
        """Trade sonucu ekleme"""
        monitor = EdgeHealthMonitor(window_trades=3)

        result1 = TradeResult("BTC", 1.0, datetime.now(), True)
        result2 = TradeResult("ETH", -0.5, datetime.now(), False)

        monitor.add_trade_result(result1)
        monitor.add_trade_result(result2)

        assert len(monitor.trade_results) == 2

    def test_fifo_window(self):
        """FIFO pencere yönetimi"""
        monitor = EdgeHealthMonitor(window_trades=2)

        # Add 3 trades, first should be removed
        for _ in range(3):
            result = TradeResult("BTC", 1.0, datetime.now(), True)
            monitor.add_trade_result(result)

        assert len(monitor.trade_results) == 2

    def test_wilson_calculation_basic(self):
        """Wilson hesaplama - temel"""
        monitor = EdgeHealthMonitor()

        # 60 wins out of 100 trades
        lb = monitor.calculate_wilson_lower_bound(60, 100, 0.95)

        # Should be reasonable value around 0.5
        assert 0.4 <= lb <= 0.6
        assert isinstance(lb, float)

    def test_wilson_edge_cases(self):
        """Wilson hesaplama - edge case'ler"""
        monitor = EdgeHealthMonitor()

        # Zero trades
        lb = monitor.calculate_wilson_lower_bound(0, 0, 0.95)
        assert lb == pytest.approx(0.0)

        # Perfect record
        lb = monitor.calculate_wilson_lower_bound(50, 50, 0.95)
        assert lb > 0.8  # Should be high

    def test_expectancy_calculation(self):
        """Expectancy hesaplama"""
        monitor = EdgeHealthMonitor()

        # Empty results
        win_rate, avg_win, avg_loss, expectancy = monitor.calculate_expectancy_r([])
        assert win_rate == pytest.approx(0.0)

        # Basic calculation
        results = [
            TradeResult("BTC", 2.0, datetime.now(), True),
            TradeResult("ETH", -1.0, datetime.now(), False),
        ]

        win_rate, avg_win, avg_loss, expectancy = monitor.calculate_expectancy_r(results)
        assert win_rate == pytest.approx(0.5)
        assert avg_win == pytest.approx(2.0)
        assert avg_loss == pytest.approx(1.0)
        assert expectancy == pytest.approx(0.5)  # 0.5*2 - 0.5*1

    def test_edge_status_classification(self):
        """Edge durum sınıflandırması"""
        monitor = EdgeHealthMonitor(hot_threshold=0.10, warm_threshold=0.0)

        assert monitor.classify_edge_status(0.15) == EdgeStatus.HOT
        assert monitor.classify_edge_status(0.05) == EdgeStatus.WARM
        assert monitor.classify_edge_status(-0.05) == EdgeStatus.COLD

    def test_insufficient_trades(self):
        """Yetersiz trade kontrolü"""
        monitor = EdgeHealthMonitor(min_trades=10)

        # Add only 2 trades
        for _ in range(2):
            result = TradeResult("BTC", 1.0, datetime.now(), True)
            monitor.add_trade_result(result)

        # Should return None for insufficient data
        metrics = monitor.update_global_metrics()
        assert metrics is None

        # Status should default to COLD
        status = monitor.get_global_status()
        assert status == EdgeStatus.COLD

    def test_sufficient_trades_hot_edge(self):
        """Yeterli trade - HOT edge"""
        monitor = EdgeHealthMonitor(min_trades=3)

        # Add profitable trades
        for _ in range(5):
            result = TradeResult("BTC", 2.0, datetime.now(), True)
            monitor.add_trade_result(result)

        metrics = monitor.update_global_metrics()
        assert metrics is not None
        assert metrics.status == EdgeStatus.HOT

        # Should allow trades and give full risk
        assert monitor.should_allow_trade() is True
        assert monitor.get_risk_multiplier() == pytest.approx(1.0)

    def test_sufficient_trades_cold_edge(self):
        """Yeterli trade - COLD edge"""
        monitor = EdgeHealthMonitor(min_trades=3)

        # Add losing trades
        for _ in range(5):
            result = TradeResult("BTC", -1.0, datetime.now(), False)
            monitor.add_trade_result(result)

        status = monitor.get_global_status()
        assert status == EdgeStatus.COLD

        # Should block trades and give zero risk
        assert monitor.should_allow_trade() is False
        assert monitor.get_risk_multiplier() == pytest.approx(0.0)

    def test_strategy_specific_tracking(self):
        """Strateji bazlı takip"""
        monitor = EdgeHealthMonitor(min_trades=2)

        # Add winning trades for strategy A
        for _ in range(3):
            result = TradeResult("BTC", 2.0, datetime.now(), True, "strategy_a")
            monitor.add_trade_result(result)

        # Add losing trades for strategy B
        for _ in range(3):
            result = TradeResult("ETH", -1.0, datetime.now(), False, "strategy_b")
            monitor.add_trade_result(result)

        status_a = monitor.get_strategy_status("strategy_a")
        status_b = monitor.get_strategy_status("strategy_b")

        assert status_a == EdgeStatus.HOT
        assert status_b == EdgeStatus.COLD

        # Risk multipliers should differ
        risk_a = monitor.get_risk_multiplier("strategy_a")
        risk_b = monitor.get_risk_multiplier("strategy_b")

        assert risk_a == pytest.approx(1.0)  # HOT
        assert risk_b == pytest.approx(0.0)  # COLD


class TestGlobalConvenienceFunctions:
    """Global convenience function testleri"""

    def test_singleton_monitor(self):
        """Singleton monitor testi"""
        monitor1 = get_edge_health_monitor()
        monitor2 = get_edge_health_monitor()
        assert monitor1 is monitor2

    def test_add_trade_result_convenience(self):
        """add_trade_result convenience function"""
        monitor = get_edge_health_monitor()
        initial_count = len(monitor.trade_results)

        add_trade_result("BTCUSDT", 1.5, True, "test_strategy")

        assert len(monitor.trade_results) == initial_count + 1
        latest_result = monitor.trade_results[-1]
        assert latest_result.symbol == "BTCUSDT"
        assert latest_result.strategy_id == "test_strategy"

    def test_convenience_functions_integration(self):
        """Convenience function entegrasyonu"""
        # Clear state
        monitor = get_edge_health_monitor()
        monitor.trade_results.clear()
        monitor.strategy_results.clear()

        # Set lower min_trades for this test
        monitor.min_trades = 5

        # Add profitable trades
        for _ in range(10):
            add_trade_result("BTC", 1.5, True)

        # Test convenience functions
        status = get_edge_status()
        allow = should_allow_trade()
        risk = get_risk_multiplier()

        assert status == EdgeStatus.HOT
        assert allow is True
        assert risk == pytest.approx(1.0)


class TestA32AcceptanceCriteria:
    """A32 kabul kriterleri testleri"""

    def test_200_trade_window_management(self):
        """200 trade pencere yönetimi"""
        monitor = EdgeHealthMonitor(window_trades=200, min_trades=50)

        # Add exactly 200 trades
        for i in range(200):
            win = i < 120  # 60% win rate
            r_mult = 1.5 if win else -1.0
            result = TradeResult("BTC", r_mult, datetime.now(), win)
            monitor.add_trade_result(result)

        assert len(monitor.trade_results) == 200

        # Add one more - should still be 200
        result_201 = TradeResult("BTC", 1.0, datetime.now(), True)
        monitor.add_trade_result(result_201)
        assert len(monitor.trade_results) == 200

    def test_wilson_ci_calculation_accuracy(self):
        """Wilson CI hesaplama doğruluğu"""
        monitor = EdgeHealthMonitor()

        # Test known values
        lb_60_100 = monitor.calculate_wilson_lower_bound(60, 100, 0.95)
        lb_80_100 = monitor.calculate_wilson_lower_bound(80, 100, 0.95)

        # Higher win rate should give higher lower bound
        assert lb_80_100 > lb_60_100

        # Both should be reasonable
        assert 0.4 < lb_60_100 < 0.6
        assert 0.7 < lb_80_100 < 0.9

    def test_hot_warm_cold_thresholds(self):
        """HOT/WARM/COLD eşik testleri"""
        monitor = EdgeHealthMonitor(
            min_trades=5,
            hot_threshold=0.10,
            warm_threshold=0.0
        )

        # Test HOT edge
        for _ in range(10):
            result = TradeResult("BTC", 2.0, datetime.now(), True)
            monitor.add_trade_result(result)

        assert monitor.get_global_status() == EdgeStatus.HOT
        assert monitor.should_allow_trade() is True
        assert monitor.get_risk_multiplier() == pytest.approx(1.0)

        # Reset and test COLD edge
        monitor.trade_results.clear()
        for _ in range(10):
            result = TradeResult("BTC", -1.0, datetime.now(), False)
            monitor.add_trade_result(result)

        assert monitor.get_global_status() == EdgeStatus.COLD
        assert monitor.should_allow_trade() is False
        assert monitor.get_risk_multiplier() == pytest.approx(0.0)

    def test_strategy_independence(self):
        """Strateji bağımsızlığı"""
        monitor = EdgeHealthMonitor(min_trades=5)

        # Global profitable, strategy losing
        for _ in range(10):
            monitor.add_trade_result(TradeResult("BTC", 1.5, datetime.now(), True))
            monitor.add_trade_result(TradeResult("ETH", -1.0, datetime.now(), False, "bad_strategy"))

        global_status = monitor.get_global_status()
        strategy_status = monitor.get_strategy_status("bad_strategy")

        # Should be independent
        assert global_status == EdgeStatus.HOT
        assert strategy_status == EdgeStatus.COLD

        # Risk multipliers should differ
        assert monitor.get_risk_multiplier() == pytest.approx(1.0)
        assert monitor.get_risk_multiplier("bad_strategy") == pytest.approx(0.0)

    def test_statistics_comprehensive(self):
        """Kapsamlı istatistik testi"""
        monitor = EdgeHealthMonitor(min_trades=3)

        # Add mixed results
        for _ in range(5):
            monitor.add_trade_result(TradeResult("BTC", 1.0, datetime.now(), True))
            monitor.add_trade_result(TradeResult("ETH", -0.5, datetime.now(), False, "test_strategy"))

        stats = monitor.get_statistics()

        # Check structure
        assert "global" in stats
        assert "strategies" in stats
        assert "trade_counts" in stats
        assert "config" in stats

        # Check counts
        assert stats["trade_counts"]["global"] == 10
        assert stats["trade_counts"]["by_strategy"]["test_strategy"] == 5


if __name__ == "__main__":
    pytest.main([__file__])
