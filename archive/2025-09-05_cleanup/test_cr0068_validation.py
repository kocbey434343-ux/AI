"""
CR-0068 Simple Validation Tests
"""

from src.api.binance_api import BinanceAPI
from config.settings import Settings

def test_basic_futures_protection():
    """Test basic futures protection functionality"""
    print("=== CR-0068 Basic Validation ===")

    # Test 1: Offline mode futures protection
    Settings.OFFLINE_MODE = True
    api = BinanceAPI(mode='futures')

    result = api.place_futures_protection(
        symbol='BTCUSDT',
        side='BUY',
        quantity=0.1,
        take_profit=52000.0,
        stop_loss=48000.0
    )

    if result and 'sl_id' in result and 'tp_id' in result:
        print("✅ Futures protection (offline) - PASS")
        print(f"   SL ID: {result['sl_id']}")
        print(f"   TP ID: {result['tp_id']}")
    else:
        print("❌ Futures protection (offline) - FAIL")
        return False

    # Test 2: Mode validation
    spot_api = BinanceAPI(mode='spot')
    spot_result = spot_api.place_futures_protection('BTCUSDT', 'BUY', 0.1, 52000, 48000)

    if spot_result is None:
        print("✅ Spot mode rejection - PASS")
    else:
        print("❌ Spot mode should reject futures protection")
        return False

    # Test 3: Auto-heal code path validation
    from src.trader.core import Trader
    import os

    with patch.dict(os.environ, {'PYTEST_CURRENT_TEST': 'test_cr0068_validation'}):
        trader = Trader()
        trader.market_mode = 'futures'

        # Test position structure
        pos = {
            'side': 'BUY',
            'symbol': 'TESTUSDT',
            'remaining_size': 1.0,
            'stop_loss': 100.0,
            'take_profit': 200.0
        }

        # Execute auto-heal (should handle offline gracefully)
        trader._recon_auto_heal('TESTUSDT', pos)

        # Verify heal attempted flag
        if pos.get('heal_attempted_TESTUSDT'):
            print("✅ Auto-heal execution - PASS")
        else:
            print("❌ Auto-heal execution - FAIL")
            return False

    print("\n🎯 CR-0068 Basic Validation: ALL TESTS PASS")
    return True

if __name__ == "__main__":
    from unittest.mock import patch
    success = test_basic_futures_protection()
    if not success:
        exit(1)
