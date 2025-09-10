"""
Comprehensive tests for Liquidity-Aware Execution Framework
"""

import pytest

from src.execution.liquidity_analyzer import (
    OrderBookAnalyzer, OrderBookSnapshot, OrderBookLevel,
    MarketImpactEstimate, LiquidityMetrics, OrderSide, ExecutionStrategy,
    get_order_book_analyzer, analyze_liquidity, should_split_order,
    get_liquidity_statistics
)


@pytest.fixture
def sample_order_book():
    """Sample order book for testing"""
    bids = [
        OrderBookLevel(price=100.0, quantity=10.0),
        OrderBookLevel(price=99.9, quantity=15.0),
        OrderBookLevel(price=99.8, quantity=20.0),
        OrderBookLevel(price=99.7, quantity=25.0),
        OrderBookLevel(price=99.6, quantity=30.0),
    ]

    asks = [
        OrderBookLevel(price=100.1, quantity=12.0),
        OrderBookLevel(price=100.2, quantity=18.0),
        OrderBookLevel(price=100.3, quantity=22.0),
        OrderBookLevel(price=100.4, quantity=28.0),
        OrderBookLevel(price=100.5, quantity=35.0),
    ]

    return OrderBookSnapshot(
        symbol="BTCUSDT",
        timestamp=1640995200.0,
        bids=bids,
        asks=asks
    )


@pytest.fixture
def thin_order_book():
    """Thin order book for testing edge cases"""
    bids = [OrderBookLevel(price=100.0, quantity=1.0)]
    asks = [OrderBookLevel(price=101.0, quantity=1.0)]

    return OrderBookSnapshot(
        symbol="THINUSDT",
        timestamp=1640995200.0,
        bids=bids,
        asks=asks
    )


@pytest.fixture
def empty_order_book():
    """Empty order book for testing edge cases"""
    return OrderBookSnapshot(
        symbol="EMPTYUSDT",
        timestamp=1640995200.0,
        bids=[],
        asks=[]
    )


class TestOrderBookLevel:
    """Test OrderBookLevel dataclass"""

    def test_valid_order_book_level(self):
        """Test valid order book level creation"""
        level = OrderBookLevel(price=100.0, quantity=10.0)
        assert abs(level.price - 100.0) < 1e-10
        assert abs(level.quantity - 10.0) < 1e-10

    def test_invalid_price(self):
        """Test invalid price validation"""
        with pytest.raises(ValueError, match="Price must be positive"):
            OrderBookLevel(price=0.0, quantity=10.0)

        with pytest.raises(ValueError, match="Price must be positive"):
            OrderBookLevel(price=-1.0, quantity=10.0)

    def test_invalid_quantity(self):
        """Test invalid quantity validation"""
        with pytest.raises(ValueError, match="Quantity must be positive"):
            OrderBookLevel(price=100.0, quantity=0.0)

        with pytest.raises(ValueError, match="Quantity must be positive"):
            OrderBookLevel(price=100.0, quantity=-1.0)


class TestOrderBookSnapshot:
    """Test OrderBookSnapshot dataclass"""

    def test_order_book_properties(self, sample_order_book):
        """Test order book basic properties"""
        assert sample_order_book.symbol == "BTCUSDT"
        assert abs(sample_order_book.best_bid - 100.0) < 1e-10
        assert abs(sample_order_book.best_ask - 100.1) < 1e-10

        # Test spread calculation
        expected_spread = ((100.1 - 100.0) / 100.05) * 10000  # ~99.95 BPS
        assert abs(sample_order_book.spread_bps - expected_spread) < 0.1

    def test_empty_order_book_properties(self, empty_order_book):
        """Test empty order book properties"""
        assert empty_order_book.best_bid is None
        assert empty_order_book.best_ask is None
        assert empty_order_book.spread_bps is None

    def test_order_book_sorting(self):
        """Test that order book levels are properly sorted"""
        # Unsorted input
        bids = [
            OrderBookLevel(price=99.8, quantity=20.0),
            OrderBookLevel(price=100.0, quantity=10.0),  # Should be first
            OrderBookLevel(price=99.9, quantity=15.0),
        ]

        asks = [
            OrderBookLevel(price=100.3, quantity=22.0),
            OrderBookLevel(price=100.1, quantity=12.0),  # Should be first
            OrderBookLevel(price=100.2, quantity=18.0),
        ]

        book = OrderBookSnapshot("TESTUSDT", 1640995200.0, bids, asks)

        # Check bids are sorted descending
        assert abs(book.bids[0].price - 100.0) < 1e-10
        assert abs(book.bids[1].price - 99.9) < 1e-10
        assert abs(book.bids[2].price - 99.8) < 1e-10

        # Check asks are sorted ascending
        assert abs(book.asks[0].price - 100.1) < 1e-10
        assert abs(book.asks[1].price - 100.2) < 1e-10
        assert abs(book.asks[2].price - 100.3) < 1e-10


class TestOrderBookAnalyzer:
    """Test OrderBookAnalyzer core functionality"""

    def test_analyzer_initialization(self):
        """Test analyzer initialization with config"""
        config = {
            'depth_levels': 15,
            'impact_model': 'sqrt',
            'min_confidence': 0.8
        }

        analyzer = OrderBookAnalyzer(config)
        assert analyzer.depth_levels == 15
        assert analyzer.impact_model == 'sqrt'
        assert abs(analyzer.min_confidence - 0.8) < 1e-10

    def test_analyzer_default_config(self):
        """Test analyzer with default configuration"""
        analyzer = OrderBookAnalyzer()
        assert analyzer.depth_levels == 20
        assert analyzer.impact_model == 'linear'
        assert abs(analyzer.min_confidence - 0.7) < 1e-10

    def test_depth_analysis_buy_side(self, sample_order_book):
        """Test depth analysis for buy orders"""
        analyzer = OrderBookAnalyzer()

        # Small buy order
        metrics = analyzer.analyze_depth(sample_order_book, OrderSide.BUY, 5.0)

        assert metrics.symbol == "BTCUSDT"
        assert metrics.ask_depth_10 > 0  # Should have some ask depth
        assert abs(metrics.bid_depth_10) < 1e-10  # No bid depth for buy analysis
        assert abs(metrics.imbalance_ratio) <= 1.0
        assert 0 <= metrics.resilience_score <= 1.0

    def test_depth_analysis_sell_side(self, sample_order_book):
        """Test depth analysis for sell orders"""
        analyzer = OrderBookAnalyzer()

        # Small sell order
        metrics = analyzer.analyze_depth(sample_order_book, OrderSide.SELL, 5.0)

        assert metrics.symbol == "BTCUSDT"
        assert metrics.bid_depth_10 > 0  # Should have some bid depth
        assert abs(metrics.ask_depth_10) < 1e-10  # No ask depth for sell analysis
        assert abs(metrics.imbalance_ratio) <= 1.0
        assert 0 <= metrics.resilience_score <= 1.0

    def test_market_impact_estimation(self, sample_order_book):
        """Test market impact estimation"""
        analyzer = OrderBookAnalyzer()

        # Small buy order - should have low impact
        impact = analyzer.estimate_market_impact(sample_order_book, OrderSide.BUY, 5.0)

        assert isinstance(impact, MarketImpactEstimate)
        assert impact.expected_price > 0
        assert impact.confidence_level > 0
        assert 0 <= impact.depth_adequacy <= 1.0
        assert impact.estimated_duration_seconds > 0
        assert impact.execution_strategy in ExecutionStrategy

        # Large order - should have higher impact
        large_impact = analyzer.estimate_market_impact(sample_order_book, OrderSide.BUY, 100.0)
        assert large_impact.total_cost_bps > impact.total_cost_bps

    def test_empty_book_handling(self, empty_order_book):
        """Test handling of empty order books"""
        analyzer = OrderBookAnalyzer()

        # Should handle empty book gracefully
        metrics = analyzer.analyze_depth(empty_order_book, OrderSide.BUY, 10.0)
        assert abs(metrics.resilience_score) < 1e-10
        assert abs(metrics.average_order_size) < 1e-10

        impact = analyzer.estimate_market_impact(empty_order_book, OrderSide.BUY, 10.0)
        assert abs(impact.confidence_level) < 1e-10
        assert abs(impact.depth_adequacy) < 1e-10
        assert impact.expected_slippage_bps > 100  # High slippage for empty book

    def test_thin_book_handling(self, thin_order_book):
        """Test handling of thin order books"""
        analyzer = OrderBookAnalyzer()

        # Thin book should have low resilience
        metrics = analyzer.analyze_depth(thin_order_book, OrderSide.BUY, 5.0)
        assert metrics.resilience_score < 0.5

        # Impact should be high for thin books
        impact = analyzer.estimate_market_impact(thin_order_book, OrderSide.BUY, 5.0)
        assert impact.total_cost_bps > 50  # Should have significant cost
        assert impact.confidence_level < 0.5  # Low confidence

    def test_execution_strategy_suggestion(self, sample_order_book):
        """Test execution strategy suggestions"""
        analyzer = OrderBookAnalyzer()

        # Small urgent order -> IMMEDIATE
        impact = analyzer.estimate_market_impact(sample_order_book, OrderSide.BUY, 2.0, urgency=0.9)
        assert impact.execution_strategy == ExecutionStrategy.IMMEDIATE

        # Large order -> should suggest splitting (ICEBERG/TWAP)
        large_impact = analyzer.estimate_market_impact(sample_order_book, OrderSide.BUY, 200.0, urgency=0.3)
        assert large_impact.execution_strategy in [ExecutionStrategy.ICEBERG, ExecutionStrategy.TWAP]

    def test_depth_calculation_within_bps(self, sample_order_book):
        """Test depth calculation within BPS bounds"""
        analyzer = OrderBookAnalyzer()

        # Test ask depth calculation
        asks = sample_order_book.asks
        reference_price = 100.1  # Best ask

        # Should include first level (exactly at reference)
        depth_0 = analyzer._calculate_depth_within_bps(asks, reference_price, 0.0)
        assert abs(depth_0 - 12.0) < 1e-10  # First level quantity

        # Should include more levels with higher BPS
        depth_50 = analyzer._calculate_depth_within_bps(asks, reference_price, 50.0)
        assert depth_50 > depth_0

    def test_execution_price_calculation(self, sample_order_book):
        """Test execution price calculation"""
        analyzer = OrderBookAnalyzer()

        # Small order - should get best price
        price, consumed = analyzer._calculate_execution_price(sample_order_book.asks, 5.0)
        assert abs(price - 100.1) < 1e-10  # Best ask price
        assert abs(consumed - 5.0) < 1e-10

        # Large order - should get volume-weighted average
        price_large, consumed_large = analyzer._calculate_execution_price(sample_order_book.asks, 50.0)
        assert price_large > 100.1  # Should be higher than best ask
        assert consumed_large <= 50.0  # Might not consume all if insufficient depth


class TestMarketImpactEstimate:
    """Test MarketImpactEstimate functionality"""

    def test_impact_acceptability(self):
        """Test impact acceptability check"""
        # Acceptable impact
        low_impact = MarketImpactEstimate(
            expected_price=100.0,
            expected_slippage_bps=25.0,
            total_cost_bps=30.0,
            confidence_level=0.8,
            execution_strategy=ExecutionStrategy.PASSIVE,
            estimated_duration_seconds=30.0,
            depth_adequacy=0.9
        )
        assert low_impact.is_acceptable(max_slippage_bps=50.0)

        # Unacceptable impact
        high_impact = MarketImpactEstimate(
            expected_price=100.0,
            expected_slippage_bps=75.0,
            total_cost_bps=80.0,
            confidence_level=0.5,
            execution_strategy=ExecutionStrategy.ICEBERG,
            estimated_duration_seconds=120.0,
            depth_adequacy=0.3
        )
        assert not high_impact.is_acceptable(max_slippage_bps=50.0)


class TestConvenienceFunctions:
    """Test module-level convenience functions"""

    def test_get_order_book_analyzer_singleton(self):
        """Test singleton pattern for analyzer"""
        analyzer1 = get_order_book_analyzer()
        analyzer2 = get_order_book_analyzer()

        # Should return same instance
        assert analyzer1 is analyzer2

    def test_analyze_liquidity_convenience(self, sample_order_book):
        """Test analyze_liquidity convenience function"""
        metrics, impact = analyze_liquidity(sample_order_book, OrderSide.BUY, 10.0)

        assert isinstance(metrics, LiquidityMetrics)
        assert isinstance(impact, MarketImpactEstimate)
        assert metrics.symbol == "BTCUSDT"
        assert impact.expected_price > 0

    def test_should_split_order_logic(self):
        """Test order splitting logic"""
        # Low impact - no split needed
        low_impact = MarketImpactEstimate(
            expected_price=100.0,
            expected_slippage_bps=20.0,
            total_cost_bps=25.0,
            confidence_level=0.9,
            execution_strategy=ExecutionStrategy.PASSIVE,
            estimated_duration_seconds=30.0,
            depth_adequacy=0.8
        )
        assert not should_split_order(low_impact, max_impact_bps=50.0)

        # High impact - should split
        high_impact = MarketImpactEstimate(
            expected_price=100.0,
            expected_slippage_bps=60.0,
            total_cost_bps=70.0,
            confidence_level=0.6,
            execution_strategy=ExecutionStrategy.ICEBERG,
            estimated_duration_seconds=180.0,
            depth_adequacy=0.3
        )
        assert should_split_order(high_impact, max_impact_bps=50.0)

        # Low depth adequacy - should split
        low_depth = MarketImpactEstimate(
            expected_price=100.0,
            expected_slippage_bps=30.0,
            total_cost_bps=40.0,
            confidence_level=0.7,
            execution_strategy=ExecutionStrategy.ADAPTIVE,
            estimated_duration_seconds=60.0,
            depth_adequacy=0.4  # Below 0.5 threshold
        )
        assert should_split_order(low_depth, max_impact_bps=50.0)

    def test_get_liquidity_statistics(self):
        """Test liquidity statistics function"""
        stats = get_liquidity_statistics()

        assert stats["analyzer_available"] is True
        assert len(stats["supported_strategies"]) == len(ExecutionStrategy)
        assert "linear" in stats["impact_models"]
        assert abs(stats["default_max_impact_bps"] - 50.0) < 1e-10
        assert abs(stats["min_confidence_level"] - 0.7) < 1e-10


class TestEdgeCases:
    """Test edge cases and error conditions"""

    def test_zero_quantity_order(self, sample_order_book):
        """Test handling of zero quantity orders"""
        analyzer = OrderBookAnalyzer()

        metrics = analyzer.analyze_depth(sample_order_book, OrderSide.BUY, 0.0)
        assert metrics.resilience_score >= 0  # Should handle gracefully

        impact = analyzer.estimate_market_impact(sample_order_book, OrderSide.BUY, 0.0)
        assert abs(impact.depth_adequacy - 1.0) < 1e-10  # Zero order has perfect adequacy

    def test_extremely_large_order(self, sample_order_book):
        """Test handling of extremely large orders"""
        analyzer = OrderBookAnalyzer()

        # Order much larger than available liquidity
        large_qty = 10000.0
        impact = analyzer.estimate_market_impact(sample_order_book, OrderSide.BUY, large_qty)

        assert impact.total_cost_bps > 100  # Should have very high cost
        assert impact.depth_adequacy < 0.1  # Very poor depth adequacy
        assert impact.execution_strategy in [ExecutionStrategy.ICEBERG, ExecutionStrategy.TWAP]

    def test_single_level_order_book(self):
        """Test order book with single level on each side"""
        single_level_book = OrderBookSnapshot(
            symbol="SINGLEUSDT",
            timestamp=1640995200.0,
            bids=[OrderBookLevel(price=100.0, quantity=5.0)],
            asks=[OrderBookLevel(price=100.1, quantity=5.0)]
        )

        analyzer = OrderBookAnalyzer()

        metrics = analyzer.analyze_depth(single_level_book, OrderSide.BUY, 3.0)
        assert metrics.resilience_score < 0.5  # Low resilience

        impact = analyzer.estimate_market_impact(single_level_book, OrderSide.BUY, 3.0)
        assert impact.confidence_level < 0.7  # Low confidence

    def test_wide_spread_order_book(self):
        """Test order book with very wide spread"""
        wide_spread_book = OrderBookSnapshot(
            symbol="WIDEUSDT",
            timestamp=1640995200.0,
            bids=[OrderBookLevel(price=100.0, quantity=10.0)],
            asks=[OrderBookLevel(price=110.0, quantity=10.0)]  # 10% spread
        )

        analyzer = OrderBookAnalyzer()

        # Wide spread should reduce confidence
        impact = analyzer.estimate_market_impact(wide_spread_book, OrderSide.BUY, 5.0)
        assert impact.confidence_level < 0.5  # Very low confidence due to wide spread
        assert impact.total_cost_bps > 10  # Should have some cost due to spread


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
