#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.signal_generator import SignalGenerator
import json

def test_confluence_performance():
    """
    Quick confluence performance assessment
    """
    print("🚀 CONFLUENCE PERFORMANCE TEST")
    print("=" * 50)

    signal_gen = SignalGenerator()

    # Test symbols
    symbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'XRPUSDT',
               'SOLUSDT', 'DOTUSDT', 'MATICUSDT', 'AVAXUSDT', 'LTCUSDT']

    total_signals = 0
    confluence_signals = 0
    confluence_scores = []

    print("📊 TESTING 10 SYMBOLS:")
    print("-" * 30)

    for symbol in symbols:
        try:
            signal_data = signal_gen.generate_pair_signal(symbol)

            if signal_data and signal_data.get('signal') in ['AL', 'SAT']:
                total_signals += 1

                confluence = signal_data.get('confluence', {})
                confluence_score = confluence.get('confluence_score', 0)
                confluence_scores.append(confluence_score)

                if confluence_score > 50:
                    confluence_signals += 1
                    print(f"  ✅ {symbol}: {signal_data['signal']} (Confluence: {confluence_score:.1f})")
                else:
                    print(f"  📊 {symbol}: {signal_data['signal']} (Confluence: {confluence_score:.1f})")
            else:
                print(f"  ⏸️ {symbol}: No trade signal")

        except Exception as e:
            print(f"  ❌ {symbol}: Error - {e}")

    print(f"\n🎯 PERFORMANCE SUMMARY:")
    print("-" * 30)
    print(f"Total Signals: {total_signals}")
    print(f"Confluence Signals: {confluence_signals}")

    if total_signals > 0:
        confluence_rate = (confluence_signals / total_signals) * 100
        print(f"Confluence Rate: {confluence_rate:.1f}%")

        if confluence_scores:
            avg_confluence = sum(confluence_scores) / len(confluence_scores)
            max_confluence = max(confluence_scores)
            min_confluence = min(confluence_scores)

            print(f"Average Confluence Score: {avg_confluence:.1f}")
            print(f"Max Confluence Score: {max_confluence:.1f}")
            print(f"Min Confluence Score: {min_confluence:.1f}")

    # Monthly projection
    daily_trades = total_signals
    monthly_trades = daily_trades * 30
    confluence_monthly = confluence_signals * 30

    print(f"\n📈 MONTHLY PROJECTION:")
    print(f"  Total Monthly Trades: ~{monthly_trades}")
    print(f"  Confluence Monthly Trades: ~{confluence_monthly}")

    target_achieved = monthly_trades >= 40
    print(f"  Target Status: {'✅ ACHIEVED' if target_achieved else '❌ NEEDS IMPROVEMENT'}")

    # Estimate expectancy boost from confluence
    if confluence_rate > 0:
        # Confluence signals typically have higher win rate
        baseline_expectancy = 0.26  # Current baseline
        confluence_boost = confluence_rate / 100 * 0.5  # 50% boost from confluence
        estimated_expectancy = baseline_expectancy + confluence_boost

        print(f"\n🎯 EXPECTANCY ESTIMATE:")
        print(f"  Baseline Expectancy: {baseline_expectancy:.3f}%")
        print(f"  Confluence Boost: +{confluence_boost:.3f}%")
        print(f"  Estimated Expectancy: {estimated_expectancy:.3f}%")

        expectancy_target = estimated_expectancy >= 1.0
        print(f"  Target Status: {'✅ ACHIEVED' if expectancy_target else '❌ NEEDS IMPROVEMENT'}")

        if target_achieved and expectancy_target:
            print(f"\n🏆 SUCCESS: Strategy targets achieved!")
        else:
            print(f"\n⚠️ NEEDS WORK: Some targets not met")

if __name__ == "__main__":
    test_confluence_performance()
