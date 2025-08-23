#!/usr/bin/env python3
import sys
import os

# Python path'e proje dizinini ekle
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.signal_generator import SignalGenerator

def test_signal_generation():
    print("Testing Signal Generation...")
    
    try:
        signal_gen = SignalGenerator()
        print("✓ SignalGenerator initialized")
        
        # Test single pair
        symbol = "BTCUSDT"
        print(f"Testing signal generation for {symbol}...")
        
        signal = signal_gen.generate_pair_signal(symbol)
        
        if signal:
            print(f"✓ Signal generated for {symbol}")
            print(f"Signal data: {signal}")
        else:
            print(f"✗ No signal generated for {symbol}")
            
        print("✓ Test completed!")
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_signal_generation()
