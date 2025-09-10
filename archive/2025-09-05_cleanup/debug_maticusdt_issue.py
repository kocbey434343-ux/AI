#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.signal_generator import SignalGenerator

print("🔍 MATICUSDT VERİ ÇEKİMİ TESTİ")
print("=" * 50)

signal_gen = SignalGenerator()

# Test MATICUSDT
symbol = 'MATICUSDT'
print(f"\n🎯 {symbol} sinyal üretimi:")

try:
    signal_data = signal_gen.generate_pair_signal(symbol)

    if signal_data is None:
        print("❌ signal_data = None (veri çekme hatası)")
    else:
        print("✅ signal_data başarılı:")
        print(f"  Signal: {signal_data.get('signal', 'N/A')}")
        print(f"  Total Score: {signal_data.get('total_score', 'N/A')}")
        confluence = signal_data.get('confluence', {})
        print(f"  Confluence Score: {confluence.get('confluence_score', 'N/A')}")

except Exception as e:
    print(f"❌ Exception yakalandı: {e}")

print(f"\n🎯 UI'da bu nasıl görünür:")
print("signal_data None ise:")
print("  - confluence_score: 0")
print("  - expected_return: 0.26")
print("  - quality: 'DUSUK'")
print("  - win_rate: 30%")
print("  - trade_freq: 6")

print(f"\n🔍 Karşılaştırma için BTCUSDT:")
signal_data_btc = signal_gen.generate_pair_signal('BTCUSDT')
if signal_data_btc:
    confluence_btc = signal_data_btc.get('confluence', {})
    print(f"  BTCUSDT Confluence: {confluence_btc.get('confluence_score', 0):.2f}%")
else:
    print("  BTCUSDT de None döndürüyor!")
