#!/usr/bin/env python3
"""
BB (Bollinger Bands) Debug Script
=================================
BB sinyal hesaplamasindaki sorunu tespit eder.
"""

import sys
sys.path.append('src')

from src.indicators import IndicatorCalculator
from src.data_fetcher import DataFetcher
import pandas as pd

def debug_bb_signal():
    print("BB SIGNAL DEBUG")
    print("===============")

    calc = IndicatorCalculator()
    data_fetcher = DataFetcher()

    # BTC verisi al
    try:
        print("\n1. BTC Data Fetch:")
        df = data_fetcher.get_pair_data('BTCUSDT', '1h')

        if df is None or df.empty:
            print("  ERROR: DataFrame bos veya None")
            return

        print(f"  DataFrame shape: {df.shape}")
        print(f"  Columns: {list(df.columns)}")
        print(f"  Last 3 rows:")
        print(df[['close', 'volume']].tail(3))

        print("\n2. All Indicators Calculate:")
        indicators = calc.calculate_all_indicators(df)
        print(f"  Indicators keys: {list(indicators.keys())}")

        print("\n3. BB Data Check:")
        if 'Bollinger Bands' in indicators:
            bb = indicators['Bollinger Bands']
            print(f"  BB type: {type(bb)}")
            print(f"  BB keys: {list(bb.keys()) if isinstance(bb, dict) else 'Not dict'}")

            if isinstance(bb, dict):
                for key, value in bb.items():
                    print(f"    {key}: type={type(value)}, shape={getattr(value, 'shape', 'No shape')}")
                    if hasattr(value, 'iloc'):
                        print(f"      Last value: {value.iloc[-1]}")
                    else:
                        print(f"      Value: {value}")
        else:
            print("  ERROR: No Bollinger Bands in indicators!")

        print("\n4. Manual BB Signal Test:")
        bb_signal = calc._calculate_bollinger_signal(indicators)
        print(f"  BB Signal Result: {bb_signal}")

        print("\n5. Direct BB Calculation Test:")
        try:
            # Manual BB hesaplama
            close = df['close']
            rolling_mean = close.rolling(window=20).mean()
            rolling_std = close.rolling(window=20).std()
            upper_band = rolling_mean + (rolling_std * 2)
            lower_band = rolling_mean - (rolling_std * 2)

            last_close = close.iloc[-1]
            last_upper = upper_band.iloc[-1]
            last_lower = lower_band.iloc[-1]
            last_middle = rolling_mean.iloc[-1]

            print(f"  Manual Calculation:")
            print(f"    Close: {last_close:.2f}")
            print(f"    Upper: {last_upper:.2f}")
            print(f"    Middle: {last_middle:.2f}")
            print(f"    Lower: {last_lower:.2f}")

            band_width = last_upper - last_lower
            position = (last_close - last_lower) / band_width if band_width > 0 else 0.5
            print(f"    Band Width: {band_width:.2f}")
            print(f"    Position: {position:.3f}")

        except Exception as e:
            print(f"  Manual calculation error: {e}")
            import traceback
            traceback.print_exc()

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_bb_signal()
