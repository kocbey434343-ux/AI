#!/usr/bin/env python3
"""
UI Backtest Debug: Backtest butonuna basildiginda ne veriler donuyor kontrol edelim
"""

import sys
import os

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from src.signal_generator import SignalGenerator

def main():
    print("🎯 UI BACKTEST FLOW DEBUG")
    print("=" * 50)

    # UI'da kullanilan ayni kod
    signal_gen = SignalGenerator()
    test_symbols = ['BTCUSDT', 'ETHUSDT']  # Sadece iki coin test

    for symbol in test_symbols:
        print(f"\n🔍 {symbol} SINYAL VERISI:")
        print("-" * 30)

        try:
            # UI'da cagirilan ayni metot
            signal_data = signal_gen.generate_pair_signal(symbol)

            if not signal_data:
                print(f"❌ signal_data = None for {symbol}")
                continue

            # UI'da extract edilen veriler
            confluence = signal_data.get('confluence', {})
            confluence_score = confluence.get('confluence_score', 0)
            total_score = signal_data.get('total_score', 0)
            signal = signal_data.get('signal', 'BEKLE')

            print(f"  signal: {signal}")
            print(f"  total_score: {total_score}")
            print(f"  confluence dict: {confluence}")
            print(f"  confluence_score: {confluence_score}")

            # Expected return hesapla (UI'daki gibi)
            if confluence_score >= 75:
                quality, expected_return = 'YUKSEK', 0.26 + (confluence_score / 100 * 0.75)
            elif confluence_score >= 50:
                quality, expected_return = 'ORTA', 0.26 + (confluence_score / 100 * 0.35)
            else:
                quality, expected_return = 'DUSUK', 0.26

            print(f"  calculated_quality: {quality}")
            print(f"  calculated_expected_return: {expected_return:.3f}")

            # Table'da gozukecek veri
            print(f"  🎯 TABLE DATA:")
            print(f"    Config: {symbol}")
            print(f"    Win Rate: {30 + (confluence_score * 0.5):.0f}%")  # UI'daki formul
            print(f"    Total Trades: {6 + int(confluence_score * 0.15)}")  # UI'daki formul
            print(f"    Avg PnL: {expected_return:.3f}%")
            print(f"    Score: {confluence_score:.1f}")

        except Exception as e:
            print(f"❌ ERROR for {symbol}: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    main()
