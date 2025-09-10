#!/usr/bin/env python3
"""SignalGenerator dogrudan test"""
import os
import sys
import traceback

# Add project path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from config.settings import Settings
    from src.data_fetcher import DataFetcher
    from src.signal_generator import SignalGenerator

    print("Import basarili")

    # Settings load
    settings = Settings()
    print(f"Settings yuklendi. Test mode: {getattr(settings, 'IS_TEST_MODE', 'unknown')}")

    # DataFetcher
    dfetch = DataFetcher()
    print("DataFetcher olusturuldu")

    # SignalGenerator
    sg = SignalGenerator()  # Parametresiz
    print("SignalGenerator olusturuldu")

    # Test pair
    test_pair = "BTCUSDT"
    print(f"Testing signal for {test_pair}")

    # Sinyal uret
    signal_data = sg.generate_pair_signal(test_pair)
    print(f"Signal result type: {type(signal_data)}")
    print(f"Signal data: {signal_data}")

    if signal_data:
        print("✓ SignalGenerator calisiyor!")
        if 'signal' in signal_data:
            print(f"Signal: {signal_data['signal']}")
        if 'score' in signal_data:
            print(f"Score: {signal_data['score']}")
    else:
        print("X SignalGenerator signal uretmiyor")

except Exception as e:
    print(f"X HATA: {e}")
    traceback.print_exc()
