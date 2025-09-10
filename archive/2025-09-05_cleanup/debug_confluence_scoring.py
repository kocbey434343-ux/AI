#!/usr/bin/env python3
"""Debug confluence scoring issue"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.signal_generator import SignalGenerator
from src.indicators import IndicatorCalculator
from src.data_fetcher import DataFetcher

def debug_confluence_scoring():
    """Debug why confluence scoring returns 0"""

    print("🔍 CONFLUENCE SCORING DEBUG")
    print("=" * 50)

    # Test single symbol
    symbol = 'BTCUSDT'

    # Initialize components
    data_fetcher = DataFetcher()
    indicators = IndicatorCalculator()

    # Get data
    df = data_fetcher.get_pair_data(symbol, '1h')
    if df is None or df.empty:
        print("❌ No data available")
        return

    print(f"📊 Data shape: {df.shape}")
    print(f"📅 Date range: {df.index[0]} to {df.index[-1]}")

    # Test confluence scoring directly
    try:
        confluence = indicators.calculate_confluence_score(df)
        print(f"\n🎯 CONFLUENCE RESULT:")
        print(f"  Score: {confluence.get('confluence_score', 'N/A')}")
        print(f"  Direction: {confluence.get('signal_direction', 'N/A')}")
        print(f"  Components: {len(confluence.get('component_signals', {}))}")

        # Component breakdown
        components = confluence.get('component_signals', {})
        for name, data in components.items():
            print(f"  {name.upper()}: {data.get('signal', 'N/A')} (value: {data.get('value', 'N/A')})")

        # Show error if exists
        if 'error' in confluence:
            print(f"  ❌ Error: {confluence['error']}")

    except Exception as e:
        print(f"❌ Confluence scoring failed: {e}")
        import traceback
        traceback.print_exc()

    # Test via signal generator
    print(f"\n🔧 SIGNAL GENERATOR TEST:")
    signal_gen = SignalGenerator()

    try:
        result = signal_gen._calculate_confluence_scores(df)
        print(f"  Via SignalGen: {result.get('confluence_score', 'N/A')}")

    except Exception as e:
        print(f"  ❌ SignalGen confluence failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_confluence_scoring()
