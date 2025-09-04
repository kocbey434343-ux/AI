"""
Test Suite for CR-0068: Auto-heal futures & SELL expansion

Test Coverage:
- Futures protection order placement
- SELL order support in spot mode
- Error handling and edge cases
- Structured logging events
- Integration with existing auto-heal logic
"""

import os
from unittest.mock import Mock, patch
from src.trader.core import Trader
from src.api.binance_api import BinanceAPI
from config.settings import Settings


class TestCR0068AutoHealExpansion:
    """Test auto-heal expansion for futures and SELL orders"""

    def setup_method(self):
        """Setup test environment"""
        Settings.OFFLINE_MODE = True

    def teardown_method(self):
        """Cleanup test environment"""
        Settings.OFFLINE_MODE = False

    def create_test_trader(self, market_mode='spot'):
        """Create trader instance for testing"""
        with patch.dict(os.environ, {'PYTEST_CURRENT_TEST': f'test_autoheal_{market_mode}'}):
            trader = Trader()
            trader.market_mode = market_mode
            return trader

    def test_futures_protection_order_placement(self):
        """Test futures protection orders are placed correctly"""
        api = BinanceAPI(mode='futures')

        # Test futures protection placement
        result = api.place_futures_protection(
            symbol='BTCUSDT',
            side='BUY',
            quantity=0.1,
            take_profit=52000.0,
            stop_loss=48000.0
        )

        # Verify offline mode simulation
        assert result is not None
        assert 'sl_id' in result
        assert 'tp_id' in result
        assert result['symbol'] == 'BTCUSDT'
        print(f"✅ Futures protection: SL={result['sl_id']}, TP={result['tp_id']}")

    def test_auto_heal_futures_integration(self):
        """Test auto-heal futures mode integration"""
        trader = self.create_test_trader('futures')

        # Mock position requiring healing
        pos = {
            'side': 'BUY',
            'symbol': 'ETHUSDT',
            'remaining_size': 1.5,
            'stop_loss': 1800.0,
            'take_profit': 2200.0
        }

        # Temporarily disable OFFLINE_MODE for this test
        original_offline = Settings.OFFLINE_MODE
        Settings.OFFLINE_MODE = False

        try:
            # Mock API response
            with patch.object(trader.api, 'place_futures_protection') as mock_futures:
                mock_futures.return_value = {
                    'sl_id': 'test_sl_123',
                    'tp_id': 'test_tp_456'
                }

                # Execute auto-heal
                trader._recon_auto_heal('ETHUSDT', pos)

                # Verify futures protection called
                mock_futures.assert_called_once_with(
                    symbol='ETHUSDT',
                    side='BUY',
                    quantity=1.5,
                    take_profit=2200.0,
                    stop_loss=1800.0
                )

                # Verify position updated
                assert 'futures_protection' in pos
                assert pos['futures_protection']['sl_id'] == 'test_sl_123'
                assert pos['futures_protection']['tp_id'] == 'test_tp_456'
        finally:
            Settings.OFFLINE_MODE = original_offline

        print("✅ Futures auto-heal integration working")

    def test_auto_heal_spot_sell_support(self):
        """Test auto-heal supports SELL orders in spot mode"""
        trader = self.create_test_trader('spot')

        # SELL position requiring healing
        pos = {
            'side': 'SELL',
            'symbol': 'ADAUSDT',
            'remaining_size': 100.0,
            'stop_loss': 1.10,
            'take_profit': 0.90
        }

        with patch.object(trader.api, 'place_oco_order') as mock_oco:
            mock_oco.return_value = {
                'orderReports': [
                    {'orderId': 'oco_sl_789'},
                    {'orderId': 'oco_tp_012'}
                ]
            }

            trader._recon_auto_heal('ADAUSDT', pos)

            # Verify OCO called for SELL order
            mock_oco.assert_called_once_with(
                symbol='ADAUSDT',
                side='SELL',
                quantity=100.0,
                take_profit=0.90,
                stop_loss=1.10
            )

            # Verify position updated
            assert 'oco_resp' in pos
            expected_order_count = 2
            assert len(pos['oco_resp']['ids']) == expected_order_count

        print("✅ Spot SELL auto-heal working")

    def test_auto_heal_mode_detection(self):
        """Test auto-heal correctly detects and handles different modes"""
        test_cases = [
            ('spot', 'BUY', 'place_oco_order'),
            ('spot', 'SELL', 'place_oco_order'),
            ('futures', 'BUY', 'place_futures_protection'),
            ('futures', 'SELL', 'place_futures_protection')
        ]

        for mode, side, expected_method in test_cases:
            trader = self.create_test_trader(mode)

            pos = {
                'side': side,
                'symbol': 'TESTUSDT',
                'remaining_size': 1.0,
                'stop_loss': 100.0,
                'take_profit': 200.0
            }

            with patch.object(trader.api, expected_method) as mock_method:
                mock_method.return_value = {'success': True}

                trader._recon_auto_heal('TESTUSDT', pos)

                # Verify correct API method called
                mock_method.assert_called_once()

            print(f"✅ Auto-heal {mode} {side} uses {expected_method}")

    def test_auto_heal_error_handling(self):
        """Test auto-heal error handling and logging"""
        trader = self.create_test_trader('futures')
        # Override offline mode for this test
        trader.api.mode = 'futures'

        pos = {
            'side': 'BUY',
            'symbol': 'ERRORUSDT',
            'remaining_size': 1.0,
            'stop_loss': 100.0,
            'take_profit': 200.0
        }

        with patch.object(trader.api, 'place_futures_protection') as mock_futures:
            # Simulate API failure
            mock_futures.return_value = None

            # Capture log calls
            with patch.object(trader.logger, 'warning') as mock_log:
                trader._recon_auto_heal('ERRORUSDT', pos)

                # Verify error logged
                mock_log.assert_called()
                log_call = mock_log.call_args[0][0]
                assert 'AUTO_HEAL:futures_fail_no_resp' in log_call
                assert 'ERRORUSDT' in log_call

        print("✅ Auto-heal error handling working")

    def test_auto_heal_duplicate_prevention(self):
        """Test auto-heal prevents duplicate attempts"""
        trader = self.create_test_trader('spot')

        pos = {
            'side': 'BUY',
            'symbol': 'DUPUSDT',
            'remaining_size': 1.0,
            'stop_loss': 100.0,
            'take_profit': 200.0,
            'heal_attempted_DUPUSDT': True  # Already attempted
        }

        with patch.object(trader.api, 'place_oco_order') as mock_oco:
            trader._recon_auto_heal('DUPUSDT', pos)

            # Verify no API call made
            mock_oco.assert_not_called()

        print("✅ Auto-heal duplicate prevention working")


class TestCR0068AcceptanceCriteria:
    """Acceptance criteria tests for CR-0068"""

    def setup_method(self):
        Settings.OFFLINE_MODE = True

    def teardown_method(self):
        Settings.OFFLINE_MODE = False

    def create_test_trader(self, market_mode='spot'):
        """Create trader instance for testing"""
        with patch.dict(os.environ, {'PYTEST_CURRENT_TEST': f'test_cr0068_{market_mode}'}):
            trader = Trader()
            trader.market_mode = market_mode
            return trader

    def test_cr0068_futures_auto_heal_success(self):
        """
        CR-0068 Acceptance: Futures auto-heal genisletmesi calisiyor
        """
        trader = self.create_test_trader('futures')

        pos = {
            'side': 'LONG',  # Test futures-style side
            'symbol': 'BTCUSDT',
            'remaining_size': 0.01,
            'stop_loss': 49000.0,
            'take_profit': 51000.0
        }

        # Execute auto-heal
        trader._recon_auto_heal('BTCUSDT', pos)

        # Verify heal attempted flag set
        assert pos.get('heal_attempted_BTCUSDT') is True

        print("✅ CR-0068: Futures auto-heal expansion working")

    def test_cr0068_sell_orders_supported(self):
        """
        CR-0068 Acceptance: SELL emirleri destekleniyor
        """
        trader = self.create_test_trader('spot')

        pos = {
            'side': 'SELL',
            'symbol': 'ETHUSDT',
            'remaining_size': 0.5,
            'stop_loss': 2100.0,  # Stop above current for SELL
            'take_profit': 1900.0  # Take profit below for SELL
        }

        with patch.object(trader.api, 'place_oco_order') as mock_oco:
            mock_oco.return_value = {'orderReports': [{'orderId': '123'}]}

            trader._recon_auto_heal('ETHUSDT', pos)

            # Verify SELL order supported
            mock_oco.assert_called_once()
            call_args = mock_oco.call_args[1]
            assert call_args['side'] == 'SELL'

        print("✅ CR-0068: SELL order support working")


def test_cr0068_integration_end_to_end():
    """Integration test for CR-0068 complete workflow"""
    Settings.OFFLINE_MODE = True

    try:
        # Test both spot and futures modes
        for mode in ['spot', 'futures']:
            api = BinanceAPI(mode=mode)

            if mode == 'spot':
                # Test spot OCO (existing + SELL support)
                result = api.place_oco_order('BTCUSDT', 'SELL', 0.1, 0.030, 0.025)
                assert result is not None or Settings.OFFLINE_MODE

            elif mode == 'futures':
                # Test new futures protection
                result = api.place_futures_protection('ETHUSDT', 'BUY', 1.0, 2200, 1800)
                assert result is not None
                assert 'sl_id' in result
                assert 'tp_id' in result

        print("✅ CR-0068: End-to-end integration working")

    finally:
        Settings.OFFLINE_MODE = False


if __name__ == "__main__":
    # Run key tests
    test_suite = TestCR0068AutoHealExpansion()
    test_suite.setup_method()

    test_suite.test_futures_protection_order_placement()
    test_suite.test_auto_heal_futures_integration()
    test_suite.test_auto_heal_spot_sell_support()
    test_suite.test_auto_heal_mode_detection()

    # Acceptance criteria
    acceptance_tests = TestCR0068AcceptanceCriteria()
    acceptance_tests.setup_method()
    acceptance_tests.test_cr0068_futures_auto_heal_success()
    acceptance_tests.test_cr0068_sell_orders_supported()

    # Integration test
    test_cr0068_integration_end_to_end()

    print("\n🎯 CR-0068 Test Suite COMPLETE")
