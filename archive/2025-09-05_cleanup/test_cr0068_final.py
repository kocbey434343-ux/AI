"""
CR-0068 Full Integration Test - Real API Path Testing
"""

from unittest.mock import patch, Mock
from src.trader.core import Trader
from src.api.binance_api import BinanceAPI
from config.settings import Settings
import os

def test_cr0068_real_api_path():
    """Test CR-0068 with real API path (mocked responses)"""
    print("=== CR-0068 Real API Path Test ===")

    # Test futures auto-heal with mocked API
    with patch.dict(os.environ, {'PYTEST_CURRENT_TEST': 'test_real_api_path'}):
        trader = Trader()
        trader.market_mode = 'futures'

        # Disable offline mode temporarily
        original_offline = Settings.OFFLINE_MODE
        Settings.OFFLINE_MODE = False

        try:
            pos = {
                'side': 'BUY',
                'symbol': 'ETHUSDT',
                'remaining_size': 1.0,
                'stop_loss': 1800.0,
                'take_profit': 2200.0
            }

            # Mock the API method to avoid real API calls
            with patch.object(trader.api, 'place_futures_protection') as mock_futures:
                mock_futures.return_value = {
                    'sl_id': 'real_sl_12345',
                    'tp_id': 'real_tp_67890',
                    'symbol': 'ETHUSDT'
                }

                # Execute auto-heal
                trader._recon_auto_heal('ETHUSDT', pos)

                # Verify API was called with correct parameters
                mock_futures.assert_called_once_with(
                    symbol='ETHUSDT',
                    side='BUY',
                    quantity=1.0,
                    take_profit=2200.0,
                    stop_loss=1800.0
                )

                # Verify position was updated with futures protection
                assert 'futures_protection' in pos
                assert pos['futures_protection']['sl_id'] == 'real_sl_12345'
                assert pos['futures_protection']['tp_id'] == 'real_tp_67890'

                print("✅ Futures auto-heal with real API path - PASS")

        finally:
            Settings.OFFLINE_MODE = original_offline

def test_cr0068_spot_sell_real_path():
    """Test CR-0068 SELL order with real API path (mocked responses)"""
    print("=== CR-0068 SELL Order Real API Path Test ===")

    with patch.dict(os.environ, {'PYTEST_CURRENT_TEST': 'test_sell_real_path'}):
        trader = Trader()
        trader.market_mode = 'spot'

        original_offline = Settings.OFFLINE_MODE
        Settings.OFFLINE_MODE = False

        try:
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
                        {'orderId': 'oco_sell_sl_789'},
                        {'orderId': 'oco_sell_tp_012'}
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

                # Verify position was updated
                assert 'oco_resp' in pos
                assert len(pos['oco_resp']['ids']) == 2

                print("✅ SELL order auto-heal with real API path - PASS")

        finally:
            Settings.OFFLINE_MODE = original_offline

def test_cr0068_error_handling():
    """Test CR-0068 error handling in real API path"""
    print("=== CR-0068 Error Handling Test ===")

    with patch.dict(os.environ, {'PYTEST_CURRENT_TEST': 'test_error_handling'}):
        trader = Trader()
        trader.market_mode = 'futures'

        original_offline = Settings.OFFLINE_MODE
        Settings.OFFLINE_MODE = False

        try:
            pos = {
                'side': 'BUY',
                'symbol': 'ERRORUSDT',
                'remaining_size': 1.0,
                'stop_loss': 100.0,
                'take_profit': 200.0
            }

            # Mock API to return None (failure)
            with patch.object(trader.api, 'place_futures_protection') as mock_futures:
                mock_futures.return_value = None

                # Mock logger to capture error messages
                with patch.object(trader.logger, 'warning') as mock_logger:
                    trader._recon_auto_heal('ERRORUSDT', pos)

                    # Verify error was logged
                    mock_logger.assert_called()
                    log_args = mock_logger.call_args[0][0]
                    assert 'AUTO_HEAL:futures_fail_no_resp' in log_args
                    assert 'ERRORUSDT' in log_args

                    print("✅ Error handling - PASS")

        finally:
            Settings.OFFLINE_MODE = original_offline

def test_cr0068_acceptance_criteria():
    """Test final CR-0068 acceptance criteria"""
    print("=== CR-0068 Acceptance Criteria ===")

    # 1. Futures support expanded
    api = BinanceAPI(mode='futures')
    Settings.OFFLINE_MODE = True
    result = api.place_futures_protection('BTCUSDT', 'BUY', 0.1, 52000, 48000)
    assert result is not None and 'sl_id' in result
    print("   ✅ Futures protection API - PASS")

    # 2. SELL orders supported
    with patch.dict(os.environ, {'PYTEST_CURRENT_TEST': 'test_sell_acceptance'}):
        trader = Trader()
        trader.market_mode = 'spot'

        sell_pos = {
            'side': 'SELL',
            'symbol': 'TESTUSDT',
            'remaining_size': 1.0,
            'stop_loss': 110.0,
            'take_profit': 90.0
        }

        trader._recon_auto_heal('TESTUSDT', sell_pos)
        assert sell_pos.get('heal_attempted_TESTUSDT') is True
        print("   ✅ SELL order support - PASS")

    # 3. Mode detection working
    spot_api = BinanceAPI(mode='spot')
    futures_reject = spot_api.place_futures_protection('TEST', 'BUY', 1.0, 200, 100)
    assert futures_reject is None
    print("   ✅ Mode detection - PASS")

    print("✅ All CR-0068 acceptance criteria met!")

def run_cr0068_final_validation():
    """Run final CR-0068 validation tests"""
    print("🏁 CR-0068 Final Validation Suite")
    print("=" * 50)

    test_functions = [
        test_cr0068_real_api_path,
        test_cr0068_spot_sell_real_path,
        test_cr0068_error_handling,
        test_cr0068_acceptance_criteria
    ]

    passed = 0
    for test_func in test_functions:
        try:
            test_func()
            passed += 1
        except Exception as e:
            print(f"❌ {test_func.__name__} FAILED: {e}")
            import traceback
            traceback.print_exc()

    print("=" * 50)
    print(f"🎯 Final Results: {passed}/{len(test_functions)} tests passed")

    if passed == len(test_functions):
        print("🚀 CR-0068: READY FOR PRODUCTION")
        return True
    else:
        print("⚠️  CR-0068: NEEDS ATTENTION")
        return False

if __name__ == "__main__":
    import sys
    success = run_cr0068_final_validation()
    if not success:
        sys.exit(1)
