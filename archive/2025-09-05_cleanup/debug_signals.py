#!/usr/bin/env python3
"""Quick signal test"""
import sys
import os

# Add project path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from src.signal_generator import SignalGenerator
    print("✅ SignalGenerator import OK")

    sg = SignalGenerator()
    print("✅ SignalGenerator init OK")

    # Test with a single symbol
    test_symbol = "BTCUSDT"

    # Check data first
    from src.data_fetcher import DataFetcher
    df = DataFetcher()
    data = df.get_pair_data(test_symbol, "1h")
    print(f"✅ Data fetched for {test_symbol}: {len(data) if data is not None else 'None'} rows")

    if data is not None and not data.empty:
        signal = sg.generate_pair_signal(test_symbol)
        print(f"✅ Signal generated for {test_symbol}: {signal is not None}")

        if signal:
            print(f"   Signal: {signal.get('signal', 'N/A')}")
            print(f"   Score: {signal.get('total_score', 'N/A')}")
            print(f"   Price: {signal.get('close_price', 'N/A')}")
        else:
            print("❌ Signal is None - check pipeline")
    else:
        print("❌ No data available for signal generation")

    # Test batch signals
    signals = sg.generate_signals()
    print(f"✅ Batch signals: {len(signals)} generated")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
