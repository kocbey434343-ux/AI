#!/usr/bin/env python3
"""
Debug: Backtest Rakamları Kontrolü
==================================

Bu script, confluence skorlaması ve expected return hesaplamalarını
detaylı olarak kontrol eder ve gerçek rakamları analiz eder.
"""

import sys
import os
sys.path.append('src')

from src.signal_generator import SignalGenerator
from src.indicators import IndicatorCalculator

def debug_single_coin_calculation(symbol: str):
    """Tek coin için detaylı hesaplama debug"""
    print(f"\n🔍 {symbol} DETAYLI ANALİZ")
    print("="*50)

    signal_gen = SignalGenerator()

    try:
        # Signal hesapla
        signal_data = signal_gen.generate_pair_signal(symbol)

        if not signal_data:
            print("❌ Signal data alınamadı")
            return

        print(f"📊 Signal Data:")
        for key, value in signal_data.items():
            if key == 'confluence':
                print(f"  {key}: {value}")
                # Confluence detayları
                conf = value
                print(f"    - confluence_score: {conf.get('confluence_score', 0)}")
                print(f"    - rsi_signal: {conf.get('rsi_signal', 'N/A')}")
                print(f"    - macd_signal: {conf.get('macd_signal', 'N/A')}")
                print(f"    - bb_signal: {conf.get('bb_signal', 'N/A')}")
                print(f"    - confluence_count: {conf.get('confluence_count', 0)}")
            elif key in ['rsi_score', 'macd_score', 'bb_score', 'volume_score']:
                print(f"  {key}: {value:.2f}")
            else:
                print(f"  {key}: {value}")

        # Expected return hesaplama kontrolü
        confluence_score = signal_data.get('confluence', {}).get('confluence_score', 0)
        baseline = 0.26

        print(f"\n💰 EXPECTED RETURN HESAPLAMA:")
        print(f"  Baseline: {baseline:.3f}%")
        print(f"  Confluence Score: {confluence_score:.1f}%")

        if confluence_score >= 75:
            boost = confluence_score / 100 * 0.75
            quality = 'YUKSEK'
            print(f"  Boost (>=75): {confluence_score}/100 * 0.75 = {boost:.3f}")
        elif confluence_score >= 50:
            boost = confluence_score / 100 * 0.35
            quality = 'ORTA'
            print(f"  Boost (>=50): {confluence_score}/100 * 0.35 = {boost:.3f}")
        else:
            boost = 0
            quality = 'DUSUK'
            print(f"  Boost (<50): 0")

        expected_return = baseline + boost
        print(f"  Expected Return: {baseline:.3f} + {boost:.3f} = {expected_return:.3f}%")
        print(f"  Quality: {quality}")

        # Raw indicator kontrolleri
        print(f"\n🔧 RAW İNDİKATÖR KONTROL:")
        from src.data_fetcher import DataFetcher
        data_fetcher = DataFetcher()

        # Veriyi çek
        df = data_fetcher.fetch_data(symbol)
        if df is not None and not df.empty:
            print(f"  DataFrame shape: {df.shape}")
            print(f"  Son 3 veri:")
            print(df[['close', 'volume']].tail(3))

            # Manuel indicator hesaplama
            calc = IndicatorCalculator()
            indicators = calc.calculate_all(df)

            print(f"\n  Son RSI değerleri:")
            print(f"    RSI[-1]: {indicators['rsi'].iloc[-1]:.2f}")
            print(f"    RSI[-2]: {indicators['rsi'].iloc[-2]:.2f}")
            print(f"    RSI[-3]: {indicators['rsi'].iloc[-3]:.2f}")

            print(f"\n  MACD değerleri:")
            print(f"    MACD[-1]: {indicators['macd'].iloc[-1]:.6f}")
            print(f"    MACD Signal[-1]: {indicators['macd_signal'].iloc[-1]:.6f}")
            print(f"    MACD Hist[-1]: {indicators['macd_histogram'].iloc[-1]:.6f}")

        else:
            print("  ❌ DataFrame alınamadı")

    except Exception as e:
        print(f"❌ Hata: {e}")
        import traceback
        traceback.print_exc()

def debug_confluence_calculation():
    """Confluence hesaplama mantığını test et"""

    print("\n🧮 CONFLUENCE HESAPLAMA MANTIK TESTİ")
    print("="*60)

    # Test coinlerinin confluence skorları
    test_symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']

    for symbol in test_symbols[:2]:  # İlk 2 coin detaylı
        debug_single_coin_calculation(symbol)

    print(f"\n🎯 SONUÇ ANALİZİ:")
    print("1. Confluence skorları aynı çıkıyor mu? (82.3%)")
    print("2. Expected return hesaplaması doğru mu?")
    print("3. Baseline 0.26% + boost mantıklı mı?")
    print("4. RSI/MACD/BB sinyalleri tutarlı mı?")

if __name__ == "__main__":
    debug_confluence_calculation()
