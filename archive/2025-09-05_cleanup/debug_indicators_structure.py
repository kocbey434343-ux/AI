#!/usr/bin/env python3
"""
Indicator Structure Debug
========================
Indicators dictionary yapısını detaylı analiz eder.
"""

import sys
sys.path.append('src')

from src.indicators import IndicatorCalculator
from src.data_fetcher import DataFetcher

def debug_indicators():
    print("INDICATOR STRUCTURE DEBUG")
    print("=========================")

    calc = IndicatorCalculator()
    data_fetcher = DataFetcher()

    try:
        df = data_fetcher.get_pair_data('BTCUSDT', '1h')
        print(f"DataFrame last close: {df['close'].iloc[-1]}")

        indicators = calc.calculate_all_indicators(df)

        print("\nINDICATORS KEYS:", list(indicators.keys()))

        if 'close' in indicators:
            close_data = indicators['close']
            print(f"CLOSE in indicators: {type(close_data)}")
            print(f"CLOSE last value: {close_data.iloc[-1]}")
        else:
            print("NO CLOSE in indicators!")

        # Test BB calculation directly
        print("\nDIRECT BB TEST:")
        bb_result = calc._calculate_bollinger_signal(indicators)
        print("BB Result:", bb_result)

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_indicators()
