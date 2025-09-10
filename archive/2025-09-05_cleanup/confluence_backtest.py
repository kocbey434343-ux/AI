#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.backtest.realistic_backtest import RealisticBacktest
import json

def run_confluence_backtest():
    """
    Run full backtest with active confluence system
    Target: 1.0%+ expectancy with 40+ trades/month
    """
    print("🚀 CONFLUENCE SYSTEM BACKTEST")
    print("=" * 60)
    print("Goal: Validate 1.0%+ expectancy with 150 trades/month")
    print("System: Multi-indicator confluence (RSI+MACD+Bollinger)")
    print("=" * 60)

    # Initialize backtest
    backtest = RealisticBacktest()

    # Run comprehensive test
    try:
        results = backtest.run_comprehensive_test()

        if results:
            print(f"\n📊 CONFLUENCE BACKTEST RESULTS:")
            print("-" * 40)
            print(f"Total Trades: {results.get('total_trades', 0)}")
            print(f"Win Rate: {results.get('win_rate', 0):.1f}%")
            print(f"Expectancy: {results.get('expectancy', 0):.3f}%")
            print(f"Monthly Trade Rate: ~{results.get('monthly_trades', 0)}")

            # Performance Analysis
            expectancy = results.get('expectancy', 0)
            monthly_trades = results.get('monthly_trades', 0)

            print(f"\n🎯 TARGET ANALYSIS:")
            print(f"  Expectancy: {expectancy:.3f}% {'✅ ACHIEVED' if expectancy >= 1.0 else '❌ NEEDS IMPROVEMENT'}")
            print(f"  Monthly Trades: {monthly_trades} {'✅ ACHIEVED' if monthly_trades >= 40 else '❌ NEEDS IMPROVEMENT'}")

            if expectancy >= 1.0 and monthly_trades >= 40:
                print(f"\n🏆 SUCCESS: Profitable strategy achieved!")
                print(f"   - {expectancy:.3f}% expectancy (target: 1.0%+)")
                print(f"   - {monthly_trades} trades/month (target: 40+)")
            else:
                print(f"\n⚠️  NEEDS OPTIMIZATION:")
                if expectancy < 1.0:
                    print(f"   - Expectancy below target: {expectancy:.3f}% < 1.0%")
                if monthly_trades < 40:
                    print(f"   - Trade frequency below target: {monthly_trades} < 40")

            # Save results
            with open('confluence_backtest_results.json', 'w') as f:
                json.dump(results, f, indent=2, default=str)

            print(f"\n💾 Results saved to confluence_backtest_results.json")

        else:
            print("❌ Backtest failed to return results")

    except Exception as e:
        print(f"❌ Backtest error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_confluence_backtest()
