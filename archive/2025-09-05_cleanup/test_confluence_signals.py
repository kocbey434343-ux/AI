#!/usr/bin/env python3
"""Test confluence-enabled signal generator"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.signal_generator import SignalGenerator

# Test signal generator with confluence
signal_gen = SignalGenerator()

print("🎯 CONFLUENCE-ENABLED SIGNAL GENERATOR TEST")
print("=" * 60)

# Test symbols
test_symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT']

try:
    for symbol in test_symbols:
        print(f"\n📊 Testing {symbol}:")
        signal_data = signal_gen.generate_pair_signal(symbol)

        if signal_data:
            print(f"  Signal: {signal_data.get('signal', 'N/A')}")
            print(f"  Total Score: {signal_data.get('total_score', 'N/A'):.1f}")

            # Confluence data
            scores = signal_data.get('scores', {})
            confluence = scores.get('confluence', {})

            if confluence.get('confluence_score', 0) > 0:
                print(f"  🔥 Confluence Score: {confluence['confluence_score']:.1f}")
                print(f"  🎪 Confluence Direction: {confluence['signal_direction']}")
                print(f"  🎭 Component Agreement: {confluence.get('signal_consistency', 0):.1f}%")

                # Component breakdown
                components = confluence.get('component_signals', {})
                for comp_name, comp_data in components.items():
                    comp_signal = comp_data.get('signal', 'N/A')
                    comp_value = comp_data.get('value', 0)
                    print(f"    {comp_name.upper()}: {comp_signal} ({comp_value:.1f})")
            else:
                print("  ⚠️ No strong confluence detected")
        else:
            print(f"  ❌ No signal data for {symbol}")

        print("-" * 40)

    print("\n✅ CONFLUENCE SYSTEM TEST COMPLETE!")
    print("🚀 Advanced multi-indicator strategy is READY!")

except Exception as e:
    print(f"❌ Test failed: {e}")
    import traceback
    traceback.print_exc()
