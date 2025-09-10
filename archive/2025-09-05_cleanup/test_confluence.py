#!/usr/bin/env python3
"""Test confluence scoring"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
from src.indicators import IndicatorCalculator

# Test data oluştur
data = {
    'open': [100, 101, 99, 102, 98, 105, 103, 107, 104, 108],
    'high': [102, 103, 101, 104, 100, 107, 105, 109, 106, 110],
    'low': [99, 100, 98, 101, 97, 104, 102, 106, 103, 107],
    'close': [101, 99, 102, 98, 105, 103, 107, 104, 108, 109],
    'volume': [1000] * 10
}

# 50 satır için genişlet
for i in range(40):
    data['open'].append(109 + i % 5)
    data['high'].append(111 + i % 5)
    data['low'].append(107 + i % 5)
    data['close'].append(108 + i % 5)
    data['volume'].append(1000)

df = pd.DataFrame(data)
print(f"DataFrame shape: {df.shape}")

# Indicators test
indicators = IndicatorCalculator()

try:
    confluence = indicators.calculate_confluence_score(df)
    print("\n🎯 CONFLUENCE SCORING TEST:")
    print("=" * 50)
    print(f"Confluence Score: {confluence['confluence_score']:.1f}")
    print(f"Signal Direction: {confluence['signal_direction']}")
    print(f"Average Signal Value: {confluence.get('avg_signal_value', 'N/A'):.1f}")
    print(f"Signal Consistency: {confluence.get('signal_consistency', 'N/A'):.1f}")

    print("\n🔍 Component Signals:")
    for name, signal in confluence['component_signals'].items():
        print(f"  {name.upper()}: {signal.get('signal', 'N/A')} (value: {signal.get('value', 'N/A')})")

    print("\n✅ Test PASSED - Confluence scoring çalışıyor!")

except Exception as e:
    print(f"❌ Test FAILED: {e}")
    import traceback
    traceback.print_exc()
