"""
A32 Microstructure Filter Tests
Comprehensive test suite for OBI/AFR filters
"""

import pytest
import time
from collections import deque
from src.utils.microstructure import (
    MicrostructureFilter,
    MicrostructureConfig,
    OrderBookSnapshot,
    TradeData,
    ConflictAction,
    calculate_order_book_imbalance,
    should_allow_trade_by_microstructure,
    get_microstructure_filter
)

# Test constants
DEFAULT_OBI_LEVELS = 5
DEFAULT_OBI_LONG_MIN = 0.20
DEFAULT_OBI_SHORT_MAX = -0.20
DEFAULT_AFR_WINDOW = 80
DEFAULT_AFR_LONG_MIN = 0.55
DEFAULT_AFR_SHORT_MAX = 0.45
DEFAULT_CACHE_TTL = 2.0
MIN_TRADES_AFR = 20
TEST_PRICE = 100.0
NEUTRAL_AFR = 0.5
ZERO_VALUE = 0.0


class TestOrderBookSnapshot:
    """Test OrderBookSnapshot data structure"""

    def test_snapshot_creation(self):
        """Test basic snapshot creation"""
        test_bid_count = 2
        test_ask_count = 2

        bids = [(TEST_PRICE, 5.0), (99.0, 3.0)]
        asks = [(101.0, 4.0), (102.0, 2.0)]

        snapshot = OrderBookSnapshot(
            timestamp=time.time(),
            bids=bids,
            asks=asks
        )

        assert len(snapshot.bids) == test_bid_count
        assert len(snapshot.asks) == test_ask_count
        # Should be sorted: bids descending, asks ascending
        assert snapshot.bids[0][0] > snapshot.bids[1][0]
        assert snapshot.asks[0][0] < snapshot.asks[1][0]

    def test_snapshot_auto_sorting(self):
        """Test automatic sorting of bids/asks"""
        # Unsorted data
        bids = [(99.0, 3.0), (100.0, 5.0), (98.0, 2.0)]
        asks = [(102.0, 2.0), (101.0, 4.0), (103.0, 1.0)]

        snapshot = OrderBookSnapshot(
            timestamp=time.time(),
            bids=bids,
            asks=asks
        )

        # Check sorting
        assert snapshot.bids == [(100.0, 5.0), (99.0, 3.0), (98.0, 2.0)]
        assert snapshot.asks == [(101.0, 4.0), (102.0, 2.0), (103.0, 1.0)]


class TestTradeData:
    """Test TradeData structure and properties"""

    def test_aggressive_buy_identification(self):
        """Test aggressive buy detection"""
        # Aggressive buy (taker buy)
        trade_buy = TradeData(
            timestamp=time.time(),
            price=100.0,
            quantity=1.0,
            is_buyer_maker=False  # Buyer is taker
        )

        assert trade_buy.is_aggressive_buy is True
        assert trade_buy.is_aggressive_sell is False

    def test_aggressive_sell_identification(self):
        """Test aggressive sell detection"""
        # Aggressive sell (taker sell)
        trade_sell = TradeData(
            timestamp=time.time(),
            price=100.0,
            quantity=1.0,
            is_buyer_maker=True  # Buyer is maker (seller is taker)
        )

        assert trade_sell.is_aggressive_buy is False
        assert trade_sell.is_aggressive_sell is True


class TestMicrostructureConfig:
    """Test MicrostructureConfig defaults and validation"""

    def test_default_config(self):
        """Test default configuration values"""
        config = MicrostructureConfig()

        assert config.enabled is False
        assert config.obi_levels == DEFAULT_OBI_LEVELS
        assert config.obi_long_min == pytest.approx(DEFAULT_OBI_LONG_MIN, abs=0.001)
        assert config.obi_short_max == pytest.approx(DEFAULT_OBI_SHORT_MAX, abs=0.001)
        assert config.afr_window_trades == DEFAULT_AFR_WINDOW
        assert config.afr_long_min == pytest.approx(DEFAULT_AFR_LONG_MIN, abs=0.001)
        assert config.afr_short_max == pytest.approx(DEFAULT_AFR_SHORT_MAX, abs=0.001)
        assert config.conflict_action == ConflictAction.WAIT
        assert config.cache_ttl_seconds == pytest.approx(DEFAULT_CACHE_TTL, abs=0.001)
        assert config.min_trades_for_afr == MIN_TRADES_AFR

    def test_custom_config(self):
        """Test custom configuration"""
        config = MicrostructureConfig(
            enabled=True,
            obi_levels=10,
            afr_window_trades=100,
            conflict_action=ConflictAction.ABORT
        )

        assert config.enabled is True
        assert config.obi_levels == 10
        assert config.afr_window_trades == 100
        assert config.conflict_action == ConflictAction.ABORT


class TestMicrostructureFilter:
    """Test MicrostructureFilter main functionality"""

    def test_initialization_disabled(self):
        """Test filter initialization when disabled"""
        config = MicrostructureConfig(enabled=False)
        filter_instance = MicrostructureFilter(config)

        assert filter_instance.config.enabled is False
        assert len(filter_instance._trade_cache) == 0
        assert len(filter_instance._obi_cache) == 0

    def test_initialization_enabled(self):
        """Test filter initialization when enabled"""
        config = MicrostructureConfig(enabled=True)
        filter_instance = MicrostructureFilter(config)

        assert filter_instance.config.enabled is True

    def test_obi_calculation_disabled(self):
        """Test OBI calculation when filter is disabled"""
        config = MicrostructureConfig(enabled=False)
        filter_instance = MicrostructureFilter(config)

        orderbook = OrderBookSnapshot(
            timestamp=time.time(),
            bids=[(100.0, 10.0)],
            asks=[(101.0, 5.0)]
        )

        obi = filter_instance.calculate_obi(orderbook)
        assert obi == pytest.approx(ZERO_VALUE, abs=0.001)  # Should return 0 when disabled

    def test_obi_calculation_balanced(self):
        """Test OBI calculation with balanced order book"""
        config = MicrostructureConfig(enabled=True)
        filter_instance = MicrostructureFilter(config)

        # Balanced book
        orderbook = OrderBookSnapshot(
            timestamp=time.time(),
            bids=[(100.0, 10.0), (99.0, 5.0)],
            asks=[(101.0, 10.0), (102.0, 5.0)]
        )

        obi = filter_instance.calculate_obi(orderbook)
        assert obi == pytest.approx(ZERO_VALUE, abs=0.001)  # Balanced

    def test_obi_calculation_bid_heavy(self):
        """Test OBI calculation with bid-heavy book"""
        config = MicrostructureConfig(enabled=True)
        filter_instance = MicrostructureFilter(config)

        # Bid-heavy book
        orderbook = OrderBookSnapshot(
            timestamp=time.time(),
            bids=[(100.0, 20.0), (99.0, 10.0)],  # 30 total
            asks=[(101.0, 5.0), (102.0, 5.0)]    # 10 total
        )

        obi = filter_instance.calculate_obi(orderbook)
        expected_obi = (30 - 10) / (30 + 10)  # 0.5
        assert obi == pytest.approx(expected_obi, abs=0.001)

    def test_obi_calculation_ask_heavy(self):
        """Test OBI calculation with ask-heavy book"""
        config = MicrostructureConfig(enabled=True)
        filter_instance = MicrostructureFilter(config)

        # Ask-heavy book
        orderbook = OrderBookSnapshot(
            timestamp=time.time(),
            bids=[(100.0, 5.0)],           # 5 total
            asks=[(101.0, 15.0), (102.0, 10.0)]  # 25 total
        )

        obi = filter_instance.calculate_obi(orderbook)
        expected_obi = (5 - 25) / (5 + 25)  # -0.667
        assert obi == pytest.approx(expected_obi, abs=0.001)

    def test_obi_calculation_zero_volume(self):
        """Test OBI calculation with zero volume"""
        config = MicrostructureConfig(enabled=True)
        filter_instance = MicrostructureFilter(config)

        orderbook = OrderBookSnapshot(
            timestamp=time.time(),
            bids=[],
            asks=[]
        )

        obi = filter_instance.calculate_obi(orderbook)
        assert obi == pytest.approx(ZERO_VALUE, abs=0.001)

    def test_obi_levels_parameter(self):
        """Test OBI calculation with different level counts"""
        config = MicrostructureConfig(enabled=True, obi_levels=2)
        filter_instance = MicrostructureFilter(config)

        orderbook = OrderBookSnapshot(
            timestamp=time.time(),
            bids=[(100.0, 10.0), (99.0, 10.0), (98.0, 100.0)],  # Should ignore 98.0 level
            asks=[(101.0, 10.0), (102.0, 10.0), (103.0, 100.0)] # Should ignore 103.0 level
        )

        obi = filter_instance.calculate_obi(orderbook)
        expected_obi = 0.0  # Only first 2 levels: (20-20)/(20+20) = 0
        assert obi == pytest.approx(expected_obi, abs=0.001)

    def test_afr_calculation_disabled(self):
        """Test AFR calculation when disabled"""
        config = MicrostructureConfig(enabled=False)
        filter_instance = MicrostructureFilter(config)

        afr = filter_instance.calculate_afr("BTCUSDT")
        assert afr is None

    def test_afr_calculation_no_data(self):
        """Test AFR calculation with no trade data"""
        config = MicrostructureConfig(enabled=True)
        filter_instance = MicrostructureFilter(config)

        afr = filter_instance.calculate_afr("BTCUSDT")
        assert afr is None

    def test_afr_calculation_insufficient_trades(self):
        """Test AFR calculation with insufficient trades"""
        config = MicrostructureConfig(enabled=True, min_trades_for_afr=10)
        filter_instance = MicrostructureFilter(config)

        # Add only 5 trades
        trades = [
            TradeData(time.time(), 100.0, 1.0, False) for _ in range(5)
        ]
        filter_instance.update_trades("BTCUSDT", trades)

        afr = filter_instance.calculate_afr("BTCUSDT")
        assert afr is None

    def test_afr_calculation_all_aggressive_buys(self):
        """Test AFR calculation with all aggressive buys"""
        config = MicrostructureConfig(enabled=True, min_trades_for_afr=10)
        filter_instance = MicrostructureFilter(config)

        # All aggressive buys
        trades = [
            TradeData(time.time(), 100.0, 1.0, False) for _ in range(15)
        ]
        filter_instance.update_trades("BTCUSDT", trades)

        afr = filter_instance.calculate_afr("BTCUSDT")
        assert afr == pytest.approx(1.0, abs=0.001)

    def test_afr_calculation_all_aggressive_sells(self):
        """Test AFR calculation with all aggressive sells"""
        config = MicrostructureConfig(enabled=True, min_trades_for_afr=10)
        filter_instance = MicrostructureFilter(config)

        # All aggressive sells
        trades = [
            TradeData(time.time(), 100.0, 1.0, True) for _ in range(15)
        ]
        filter_instance.update_trades("BTCUSDT", trades)

        afr = filter_instance.calculate_afr("BTCUSDT")
        assert afr == pytest.approx(0.0, abs=0.001)

    def test_afr_calculation_mixed_trades(self):
        """Test AFR calculation with mixed trades"""
        config = MicrostructureConfig(enabled=True, min_trades_for_afr=10)
        filter_instance = MicrostructureFilter(config)

        trades = []
        # 6 aggressive buys (60 volume)
        for _ in range(6):
            trades.append(TradeData(time.time(), 100.0, 10.0, False))
        # 4 aggressive sells (40 volume)
        for _ in range(4):
            trades.append(TradeData(time.time(), 100.0, 10.0, True))

        filter_instance.update_trades("BTCUSDT", trades)

        afr = filter_instance.calculate_afr("BTCUSDT")
        expected_afr = 60.0 / 100.0  # 0.6
        assert afr == pytest.approx(expected_afr, abs=0.001)


class TestSignalGeneration:
    """Test signal generation logic"""

    def test_signal_generation_disabled(self):
        """Test signal generation when filter is disabled"""
        config = MicrostructureConfig(enabled=False)
        filter_instance = MicrostructureFilter(config)

        signal = filter_instance.generate_signal("BTCUSDT")

        assert signal.action == "WAIT"
        assert signal.obi_value == pytest.approx(ZERO_VALUE, abs=0.001)
        assert signal.afr_value == pytest.approx(NEUTRAL_AFR, abs=0.001)  # Neutral default
        assert signal.conflict_detected is False

    def test_signal_generation_long_allowed(self):
        """Test signal generation allowing LONG"""
        config = MicrostructureConfig(
            enabled=True,
            obi_long_min=0.20,
            afr_long_min=0.55,
            min_trades_for_afr=5
        )
        filter_instance = MicrostructureFilter(config)

        # Setup favorable conditions for LONG
        orderbook = OrderBookSnapshot(
            timestamp=time.time(),
            bids=[(100.0, 30.0)],  # Heavy bids
            asks=[(101.0, 10.0)]   # Light asks -> OBI = 0.5
        )

        # Add aggressive buy trades -> AFR = 1.0
        trades = [TradeData(time.time(), 100.0, 1.0, False) for _ in range(10)]
        filter_instance.update_trades("BTCUSDT", trades)

        signal = filter_instance.generate_signal("BTCUSDT", orderbook)

        assert signal.action == "LONG"
        assert signal.long_allowed is True
        assert signal.short_allowed is False
        assert signal.obi_value > 0.20
        assert signal.afr_value > 0.55

    def test_signal_generation_short_allowed(self):
        """Test signal generation allowing SHORT"""
        config = MicrostructureConfig(
            enabled=True,
            obi_short_max=-0.20,
            afr_short_max=0.45,
            min_trades_for_afr=5
        )
        filter_instance = MicrostructureFilter(config)

        # Setup favorable conditions for SHORT
        orderbook = OrderBookSnapshot(
            timestamp=time.time(),
            bids=[(100.0, 10.0)],  # Light bids
            asks=[(101.0, 30.0)]   # Heavy asks -> OBI = -0.5
        )

        # Add aggressive sell trades -> AFR = 0.0
        trades = [TradeData(time.time(), 100.0, 1.0, True) for _ in range(10)]
        filter_instance.update_trades("BTCUSDT", trades)

        signal = filter_instance.generate_signal("BTCUSDT", orderbook)

        assert signal.action == "SHORT"
        assert signal.long_allowed is False
        assert signal.short_allowed is True
        assert signal.obi_value < -0.20
        assert signal.afr_value < 0.45

    def test_signal_generation_conflict_wait(self):
        """Test signal generation with conflict (WAIT action)"""
        config = MicrostructureConfig(
            enabled=True,
            conflict_action=ConflictAction.WAIT,
            obi_long_min=0.20,
            afr_short_max=0.45,
            min_trades_for_afr=5
        )
        filter_instance = MicrostructureFilter(config)

        # Conflicting conditions: OBI favors LONG, AFR favors SHORT
        orderbook = OrderBookSnapshot(
            timestamp=time.time(),
            bids=[(100.0, 30.0)],  # Heavy bids -> OBI > 0.20
            asks=[(101.0, 10.0)]
        )

        # Aggressive sell trades -> AFR < 0.45
        trades = [TradeData(time.time(), 100.0, 1.0, True) for _ in range(10)]
        filter_instance.update_trades("BTCUSDT", trades)

        signal = filter_instance.generate_signal("BTCUSDT", orderbook)

        assert signal.action == "WAIT"
        assert signal.conflict_detected is True

    def test_signal_generation_conflict_abort(self):
        """Test signal generation with conflict (ABORT action)"""
        config = MicrostructureConfig(
            enabled=True,
            conflict_action=ConflictAction.ABORT,
            obi_long_min=0.20,
            afr_short_max=0.45,
            min_trades_for_afr=5
        )
        filter_instance = MicrostructureFilter(config)

        # Conflicting conditions
        orderbook = OrderBookSnapshot(
            timestamp=time.time(),
            bids=[(100.0, 30.0)],
            asks=[(101.0, 10.0)]
        )

        trades = [TradeData(time.time(), 100.0, 1.0, True) for _ in range(10)]
        filter_instance.update_trades("BTCUSDT", trades)

        signal = filter_instance.generate_signal("BTCUSDT", orderbook)

        assert signal.action == "ABORT"
        assert signal.conflict_detected is True


class TestTradeAllowance:
    """Test trade allowance logic"""

    def test_should_allow_trade_disabled(self):
        """Test trade allowance when filter is disabled"""
        config = MicrostructureConfig(enabled=False)
        filter_instance = MicrostructureFilter(config)

        assert filter_instance.should_allow_trade("BTCUSDT", "LONG") is True
        assert filter_instance.should_allow_trade("BTCUSDT", "SHORT") is True

    def test_should_allow_trade_abort_action(self):
        """Test trade allowance with ABORT action"""
        config = MicrostructureConfig(
            enabled=True,
            conflict_action=ConflictAction.ABORT,
            obi_long_min=0.20,
            afr_short_max=0.45,
            min_trades_for_afr=5
        )
        filter_instance = MicrostructureFilter(config)

        # Create conflicting conditions
        orderbook = OrderBookSnapshot(
            timestamp=time.time(),
            bids=[(100.0, 30.0)],
            asks=[(101.0, 10.0)]
        )
        trades = [TradeData(time.time(), 100.0, 1.0, True) for _ in range(10)]
        filter_instance.update_trades("BTCUSDT", trades)

        assert filter_instance.should_allow_trade("BTCUSDT", "LONG", orderbook) is False
        assert filter_instance.should_allow_trade("BTCUSDT", "SHORT", orderbook) is False

    def test_should_allow_long_trade(self):
        """Test allowing LONG trade"""
        config = MicrostructureConfig(
            enabled=True,
            obi_long_min=0.20,
            afr_long_min=0.55,
            min_trades_for_afr=5
        )
        filter_instance = MicrostructureFilter(config)

        # Favorable for LONG
        orderbook = OrderBookSnapshot(
            timestamp=time.time(),
            bids=[(100.0, 30.0)],
            asks=[(101.0, 10.0)]
        )
        trades = [TradeData(time.time(), 100.0, 1.0, False) for _ in range(10)]
        filter_instance.update_trades("BTCUSDT", trades)

        assert filter_instance.should_allow_trade("BTCUSDT", "LONG", orderbook) is True
        assert filter_instance.should_allow_trade("BTCUSDT", "SHORT", orderbook) is False

    def test_should_allow_short_trade(self):
        """Test allowing SHORT trade"""
        config = MicrostructureConfig(
            enabled=True,
            obi_short_max=-0.20,
            afr_short_max=0.45,
            min_trades_for_afr=5
        )
        filter_instance = MicrostructureFilter(config)

        # Favorable for SHORT
        orderbook = OrderBookSnapshot(
            timestamp=time.time(),
            bids=[(100.0, 10.0)],
            asks=[(101.0, 30.0)]
        )
        trades = [TradeData(time.time(), 100.0, 1.0, True) for _ in range(10)]
        filter_instance.update_trades("BTCUSDT", trades)

        assert filter_instance.should_allow_trade("BTCUSDT", "SHORT", orderbook) is True
        assert filter_instance.should_allow_trade("BTCUSDT", "LONG", orderbook) is False


class TestCachingMechanisms:
    """Test OBI caching and trade cache management"""

    def test_obi_cache_update(self):
        """Test OBI cache update mechanism"""
        config = MicrostructureConfig(enabled=True)
        filter_instance = MicrostructureFilter(config)

        orderbook = OrderBookSnapshot(
            timestamp=time.time(),
            bids=[(100.0, 20.0)],
            asks=[(101.0, 10.0)]
        )

        obi = filter_instance.update_obi_cache("BTCUSDT", orderbook)
        cached_obi = filter_instance.get_cached_obi("BTCUSDT")

        assert obi == cached_obi
        assert obi == pytest.approx(0.333, abs=0.001)  # (20-10)/(20+10)

    def test_obi_cache_expiry(self):
        """Test OBI cache expiry"""
        config = MicrostructureConfig(enabled=True, cache_ttl_seconds=0.1)
        filter_instance = MicrostructureFilter(config)

        orderbook = OrderBookSnapshot(
            timestamp=time.time(),
            bids=[(100.0, 20.0)],
            asks=[(101.0, 10.0)]
        )

        filter_instance.update_obi_cache("BTCUSDT", orderbook)

        # Should be available immediately
        cached_obi = filter_instance.get_cached_obi("BTCUSDT")
        assert cached_obi is not None

        # Wait for expiry
        time.sleep(0.15)

        # Should be expired
        cached_obi = filter_instance.get_cached_obi("BTCUSDT")
        assert cached_obi is None

    def test_trade_cache_management(self):
        """Test trade cache size and age management"""
        config = MicrostructureConfig(enabled=True, afr_window_trades=5)
        filter_instance = MicrostructureFilter(config)

        # Add more trades than max window
        trades = [TradeData(time.time(), 100.0, 1.0, False) for _ in range(10)]
        filter_instance.update_trades("BTCUSDT", trades)

        # Should only keep last 5 trades
        cache = filter_instance._trade_cache["BTCUSDT"]
        assert len(cache) == 5

    def test_trade_cache_age_cleanup(self):
        """Test trade cache age-based cleanup"""
        config = MicrostructureConfig(enabled=True)
        filter_instance = MicrostructureFilter(config)

        # Add old trade
        old_time = time.time() - 7200  # 2 hours ago
        old_trade = TradeData(old_time, 100.0, 1.0, False)

        # Add recent trade
        recent_trade = TradeData(time.time(), 100.0, 1.0, False)

        filter_instance.update_trades("BTCUSDT", [old_trade, recent_trade])

        # Old trade should be removed, recent should remain
        cache = filter_instance._trade_cache["BTCUSDT"]
        assert len(cache) == 1
        assert cache[0].timestamp == recent_trade.timestamp


class TestConvenienceFunctions:
    """Test global convenience functions"""

    def test_calculate_order_book_imbalance_function(self):
        """Test global OBI calculation function"""
        bids = [(100.0, 20.0), (99.0, 10.0)]
        asks = [(101.0, 5.0), (102.0, 5.0)]

        obi = calculate_order_book_imbalance(bids, asks, levels=2)
        expected_obi = (30 - 10) / (30 + 10)  # 0.5
        assert obi == pytest.approx(expected_obi, abs=0.001)

    def test_should_allow_trade_by_microstructure_function(self):
        """Test global trade allowance function"""
        # Reset the global singleton and ensure it starts with disabled state
        import src.utils.microstructure as ms_module
        ms_module._microstructure_filter = None

        # Test without orderbook data - should be True when filter is disabled by default
        result = should_allow_trade_by_microstructure("BTCUSDT", "LONG")
        assert result is True  # Should be True when filter is disabled by default

        # Test with orderbook data
        orderbook_data = {
            'bids': [(100.0, 20.0)],
            'asks': [(101.0, 10.0)]
        }
        result = should_allow_trade_by_microstructure("BTCUSDT", "LONG", orderbook_data)
        assert result is True

    def test_get_microstructure_filter_singleton(self):
        """Test singleton pattern of global filter"""
        filter1 = get_microstructure_filter()
        filter2 = get_microstructure_filter()
        assert filter1 is filter2


class TestA32AcceptanceCriteria:
    """Test A32 acceptance criteria"""

    def test_obi_real_time_calculation_under_100ms(self):
        """Test OBI calculation performance < 100ms"""
        config = MicrostructureConfig(enabled=True)
        filter_instance = MicrostructureFilter(config)

        # Large order book
        bids = [(100.0 - i*0.01, 10.0) for i in range(100)]
        asks = [(101.0 + i*0.01, 10.0) for i in range(100)]

        orderbook = OrderBookSnapshot(
            timestamp=time.time(),
            bids=bids,
            asks=asks
        )

        start_time = time.time()
        obi = filter_instance.calculate_obi(orderbook, levels=5)
        end_time = time.time()

        calculation_time_ms = (end_time - start_time) * 1000
        assert calculation_time_ms < 100  # Should be under 100ms
        assert obi == pytest.approx(ZERO_VALUE, abs=0.001)  # Should be balanced

    def test_afr_real_time_calculation(self):
        """Test AFR real-time calculation with 80 trades"""
        config = MicrostructureConfig(enabled=True, afr_window_trades=80, min_trades_for_afr=20)
        filter_instance = MicrostructureFilter(config)

        # Add exactly 80 trades
        trades = []
        for i in range(80):
            # 55% aggressive buys, 45% aggressive sells
            is_aggressive_buy = i < 44
            trades.append(TradeData(time.time(), 100.0, 1.0, not is_aggressive_buy))

        start_time = time.time()
        filter_instance.update_trades("BTCUSDT", trades)
        afr = filter_instance.calculate_afr("BTCUSDT")
        end_time = time.time()

        calculation_time_ms = (end_time - start_time) * 1000
        assert calculation_time_ms < 100  # Should be fast
        assert afr == pytest.approx(0.55, abs=0.02)

    def test_microstructure_conflict_detection(self):
        """Test OBI/AFR conflict detection accuracy"""
        config = MicrostructureConfig(
            enabled=True,
            obi_long_min=0.20,
            afr_long_min=0.55,
            obi_short_max=-0.20,
            afr_short_max=0.45,
            min_trades_for_afr=5
        )
        filter_instance = MicrostructureFilter(config)

        # Create conflict: OBI favors LONG, AFR favors SHORT
        orderbook = OrderBookSnapshot(
            timestamp=time.time(),
            bids=[(100.0, 30.0)],  # OBI = +0.5 (> 0.20)
            asks=[(101.0, 10.0)]
        )

        # AFR = 0.2 (< 0.45, favors SHORT)
        trades = [TradeData(time.time(), 100.0, 1.0, True) for _ in range(8)]  # 8 aggressive sells
        trades.extend([TradeData(time.time(), 100.0, 1.0, False) for _ in range(2)])  # 2 aggressive buys
        filter_instance.update_trades("BTCUSDT", trades)

        signal = filter_instance.generate_signal("BTCUSDT", orderbook)

        assert signal.conflict_detected is True
        assert signal.obi_value > 0.20  # Favors LONG
        assert signal.afr_value < 0.45  # Favors SHORT
        assert signal.action in ["WAIT", "ABORT"]  # Should not provide clear direction

    def test_comprehensive_microstructure_evaluation(self):
        """Test comprehensive microstructure signal evaluation"""
        config = MicrostructureConfig(
            enabled=True,
            obi_levels=5,
            obi_long_min=0.20,
            obi_short_max=-0.20,
            afr_window_trades=80,
            afr_long_min=0.55,
            afr_short_max=0.45,
            min_trades_for_afr=20,
            conflict_action=ConflictAction.WAIT
        )
        filter_instance = MicrostructureFilter(config)

        # Perfect LONG setup
        orderbook = OrderBookSnapshot(
            timestamp=time.time(),
            bids=[(100.0, 25.0), (99.9, 20.0), (99.8, 15.0)],  # Strong bids
            asks=[(100.1, 5.0), (100.2, 5.0), (100.3, 5.0)]    # Weak asks
        )

        # Strong aggressive buying
        trades = [TradeData(time.time(), 100.0, 1.0, False) for _ in range(25)]  # 25 aggressive buys
        trades.extend([TradeData(time.time(), 100.0, 1.0, True) for _ in range(5)])  # 5 aggressive sells
        filter_instance.update_trades("BTCUSDT", trades)

        signal = filter_instance.generate_signal("BTCUSDT", orderbook)

        # Verify comprehensive evaluation
        assert signal.obi_value > 0.20  # Strong bid imbalance
        assert signal.afr_value > 0.55  # Strong aggressive buying (25/30 = 0.833)
        assert signal.long_allowed is True
        assert signal.short_allowed is False
        assert signal.conflict_detected is False
        assert signal.action == "LONG"

        # Verify trade allowance
        assert filter_instance.should_allow_trade("BTCUSDT", "LONG", orderbook) is True
        assert filter_instance.should_allow_trade("BTCUSDT", "SHORT", orderbook) is False
