#!/usr/bin/env python3
"""
Simplified Realistic Backtest - Focus on trade frequency
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from src.signal_generator import SignalGenerator
from config.settings import Settings

def run_simple_realistic_test():
    """Run simplified realistic backtest with confluence"""

    print("🎯 SIMPLIFIED REALISTIC BACKTEST")
    print("=" * 60)
    print("Focus: Trade frequency with confluence scoring")
    print("")

    # Initialize components
    signal_gen = SignalGenerator()

    # Test symbols
    symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'XRPUSDT']

    total_trades = 0
    total_signals = 0
    confluence_signals = 0

    results = {
        'symbols': {},
        'total_trades': 0,
        'confluence_trades': 0,
        'signal_breakdown': {}
    }

    print("📊 TESTING SIGNAL GENERATION:")
    print("-" * 40)

    for symbol in symbols:
        print(f"\n🔍 {symbol}:")

        # Generate signal
        signal_data = signal_gen.generate_pair_signal(symbol)
        total_signals += 1

        if signal_data:
            signal = signal_data.get('signal', 'BEKLE')
            total_score = signal_data.get('total_score', 0)

            # Check confluence data - FIXED: direct access to confluence key
            confluence = signal_data.get('confluence', {})
            confluence_score = confluence.get('confluence_score', 0)

            print(f"  Signal: {signal} (Score: {total_score:.1f})")
            print(f"  Confluence: {confluence_score:.1f}")

            # Count tradeable signals
            if signal in ['AL', 'SAT']:
                total_trades += 1

                if confluence_score > 50:  # Any confluence
                    confluence_signals += 1
                    print(f"  ✅ CONFLUENCE TRADE!")

                    # Show component breakdown
                    components = confluence.get('component_signals', {})
                    for comp_name, comp_data in components.items():
                        comp_signal = comp_data.get('signal', 'N/A')
                        comp_value = comp_data.get('value', 0)
                        print(f"    {comp_name}: {comp_signal} ({comp_value:.1f})")
                else:
                    print(f"  📊 Regular trade")
            else:
                print(f"  ⏸️ No trade signal")

            results['symbols'][symbol] = {
                'signal': signal,
                'total_score': total_score,
                'confluence_score': confluence_score,
                'tradeable': signal in ['AL', 'SAT']
            }
        else:
            print(f"  ❌ No signal data")
            results['symbols'][symbol] = {
                'signal': 'ERROR',
                'total_score': 0,
                'confluence_score': 0,
                'tradeable': False
            }

    # Final results
    results['total_trades'] = total_trades
    results['confluence_trades'] = confluence_signals

    print(f"\n🎯 SIMPLIFIED BACKTEST RESULTS:")
    print("=" * 50)
    print(f"📊 Total Signals Generated: {total_signals}")
    print(f"🎪 Tradeable Signals: {total_trades}")
    print(f"🔥 Confluence Signals: {confluence_signals}")

    if total_signals > 0:
        trade_rate = (total_trades / total_signals) * 100
        confluence_rate = (confluence_signals / total_signals) * 100
        print(f"📈 Trade Generation Rate: {trade_rate:.1f}%")
        print(f"🎭 Confluence Rate: {confluence_rate:.1f}%")

    # Projection to monthly volume
    daily_signals = total_signals  # for 5 symbols
    monthly_projection = daily_signals * 30
    monthly_trades = total_trades * 30

    print(f"\n📈 MONTHLY PROJECTION:")
    print(f"  Daily signals: {daily_signals} (from {len(symbols)} symbols)")
    print(f"  Monthly signals: ~{monthly_projection}")
    print(f"  Monthly trades: ~{monthly_trades}")

    if monthly_trades >= 40:
        print(f"  ✅ TARGET ACHIEVED: {monthly_trades} >= 40 trades/month")
    else:
        print(f"  🔴 NEEDS MORE: {monthly_trades} < 40 trades/month")
        needed_symbols = int(40 / max(total_trades * 30 / len(symbols), 1))
        print(f"  💡 Suggestion: Test with ~{needed_symbols} symbols")

    # Save results
    with open('simple_realistic_results.json', 'w') as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\n💾 Results saved to simple_realistic_results.json")
    return results

if __name__ == "__main__":
    run_simple_realistic_test()
