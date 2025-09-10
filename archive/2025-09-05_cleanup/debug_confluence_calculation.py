#!/usr/bin/env python3
"""
Confluence Hesaplama Testi
==========================

Bu script confluence skorlarının neden aynı çıktığını test eder.
"""

import sys
import os
sys.path.append('src')

from src.indicators import IndicatorCalculator
import pandas as pd
import numpy as np

def test_confluence_calculation():
    """Confluence hesaplama mantığını test et"""

    print("🔍 CONFLUENCE HESAPLAMA TEST")
    print("="*40)

    calc = IndicatorCalculator()

    # Test 1: Farklı RSI değerleri ile mock data
    mock_scenarios = [
        {
            'name': 'BTC-like (RSI=50, MACD pos)',
            'rsi': 50,
            'macd': 10,
            'macd_signal': 5,
            'bb_position': 'middle'
        },
        {
            'name': 'ETH-like (RSI=61, MACD pos)',
            'rsi': 61,
            'macd': 13,
            'macd_signal': 4,
            'bb_position': 'middle'
        },
        {
            'name': 'High RSI scenario',
            'rsi': 75,
            'macd': -5,
            'macd_signal': -8,
            'bb_position': 'upper'
        }
    ]

    for scenario in mock_scenarios:
        print(f"\n📊 {scenario['name']}:")

        # Mock RSI signal
        rsi = scenario['rsi']
        if rsi > 70:
            rsi_value = 85
            rsi_signal = 'STRONG_BUY'
        elif rsi > 55:
            rsi_value = 75
            rsi_signal = 'BUY'
        elif rsi < 30:
            rsi_value = 15
            rsi_signal = 'STRONG_SELL'
        elif rsi < 45:
            rsi_value = 25
            rsi_signal = 'SELL'
        else:
            rsi_value = 50
            rsi_signal = 'NEUTRAL'

        # Mock MACD signal
        macd = scenario['macd']
        macd_sig = scenario['macd_signal']
        histogram = macd - macd_sig

        if histogram > 0 and macd > 0:
            macd_value = 75
            macd_signal = 'BUY'
        elif histogram > 0 and macd < 0:
            macd_value = 60
            macd_signal = 'WEAK_BUY'
        elif histogram < 0 and macd < 0:
            macd_value = 25
            macd_signal = 'SELL'
        else:
            macd_value = 50
            macd_signal = 'NEUTRAL'

        # Mock BB signal (always 50 for simplicity)
        bb_value = 50
        bb_signal = 'NEUTRAL'

        # Manual confluence calculation
        signal_values = [rsi_value, macd_value, bb_value]
        avg_signal = np.mean(signal_values)
        signal_std = np.std(signal_values)

        if avg_signal > 55:
            direction = 'BUY'
        elif avg_signal < 45:
            direction = 'SELL'
        else:
            direction = 'NEUTRAL'

        confluence_score = max(0, 100 - signal_std * 1.5)
        signal_consistency = 100 - signal_std

        print(f"  RSI: {rsi:.1f} -> value={rsi_value} ({rsi_signal})")
        print(f"  MACD: {macd:.1f} hist={histogram:.1f} -> value={macd_value} ({macd_signal})")
        print(f"  BB: {bb_value} ({bb_signal})")
        print(f"  Signal Values: {signal_values}")
        print(f"  Avg Signal: {avg_signal:.2f}")
        print(f"  Signal Std: {signal_std:.2f}")
        print(f"  Confluence Score: {confluence_score:.2f}")
        print(f"  Signal Consistency: {signal_consistency:.2f}")
        print(f"  Direction: {direction}")

        # Problem analizi
        print(f"  🔍 PROBLEM: Signal std sabit mi?")

    print(f"\n❗ SORUN TESPİTİ:")
    print("1. Standard deviation formülü doğru çalışıyor mu?")
    print("2. Signal values array'i her zaman aynı mı?")
    print("3. BB sinyal hesaplaması sabit mi?")

if __name__ == "__main__":
    test_confluence_calculation()
