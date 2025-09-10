#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.signal_generator import SignalGenerator
from src.data_fetcher import DataFetcher
from src.indicators import IndicatorCalculator
from config.settings import Settings
import json

def debug_signal_structure():
    print("🔍 SIGNAL STRUCTURE DEBUG")
    print("=" * 50)

    # Initialize components
    signal_gen = SignalGenerator()

    # Test with a single symbol
    symbol = "BTCUSDT"
    print(f"📊 Testing with {symbol}")

    # Generate signal
    signal_data = signal_gen.generate_pair_signal(symbol)

    if signal_data:
        print("\n📋 FULL SIGNAL DATA STRUCTURE:")
        print(json.dumps(signal_data, indent=2, default=str))

        print(f"\n🎯 KEY CONFLUENCE ACCESS:")
        print(f"  Direct confluence key: {signal_data.get('confluence', 'NOT FOUND')}")

        scores = signal_data.get('scores', {})
        print(f"  Scores.confluence: {scores.get('confluence', 'NOT FOUND')}")

        # Try other possible structures
        confluence_in_scores = signal_data.get('scores', {}).get('confluence', {})
        print(f"  Confluence in scores: {confluence_in_scores}")

        if isinstance(confluence_in_scores, dict):
            print(f"  Confluence score: {confluence_in_scores.get('confluence_score', 'NOT FOUND')}")

    else:
        print("❌ No signal data generated")

if __name__ == "__main__":
    debug_signal_structure()
