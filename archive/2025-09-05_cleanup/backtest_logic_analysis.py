#!/usr/bin/env python3
"""
Backtest Logic Analysis
======================
Backtest hesaplama mantığını analiz eder ve gerçek sonuçları kontrol eder.
"""

import sys
sys.path.append('src')

from src.signal_generator import SignalGenerator
from src.indicators import IndicatorCalculator
from src.data_fetcher import DataFetcher

def analyze_backtest_logic():
    print("BACKTEST LOGIC ANALYSIS")
    print("=" * 50)

    signal_gen = SignalGenerator()
    calc = IndicatorCalculator()
    data_fetcher = DataFetcher()

    coins = ['BTCUSDT', 'ETHUSDT']

    for symbol in coins:
        print(f"\n📊 {symbol} Analysis:")

        try:
            df = data_fetcher.get_pair_data(symbol, '1h')
            if df is None or df.empty:
                print("  ❌ No data")
                continue

            # Test confluence score
            confluence_result = calc.calculate_confluence_score(df)
            score = confluence_result.get('confluence_score', 0)
            direction = confluence_result.get('signal_direction', 'BEKLE')

            print(f"  Confluence Score: {score:.2f}%")
            print(f"  Signal Direction: {direction}")

            # Expected return formula (from UI)
            expected_return = 0.26 + (score/100 * 0.75)
            print(f"  Expected Return: {expected_return:.3f}%")

            # Simulate simple backtest metrics
            # Win rate approximation based on confluence score
            if score >= 80:
                win_rate = 75.0 + (score - 80) * 0.5  # High confidence
            elif score >= 60:
                win_rate = 60.0 + (score - 60)  # Medium confidence
            elif score >= 40:
                win_rate = 45.0 + (score - 40) * 0.75  # Low confidence
            else:
                win_rate = 35.0 + score * 0.25  # Very low confidence

            win_rate = min(95, max(25, win_rate))  # Clamp realistic range

            print(f"  Estimated Win Rate: {win_rate:.1f}%")

            # PnL simulation based on confluence and win rate
            avg_win = expected_return * 2  # Typical 2:1 risk/reward
            avg_loss = -expected_return     # Stop loss at -expected return

            expected_pnl = (win_rate/100) * avg_win + ((100-win_rate)/100) * avg_loss
            print(f"  Expected PnL per trade: {expected_pnl:.3f}%")

            # Best buy/sell price simulation
            last_close = df['close'].iloc[-1]
            best_buy = last_close * (1 - expected_return/100)
            best_sell = last_close * (1 + expected_return/100)

            print(f"  Last Close: ${last_close:.2f}")
            print(f"  Best Buy: ${best_buy:.2f}")
            print(f"  Best Sell: ${best_sell:.2f}")

        except Exception as e:
            print(f"  ❌ Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    analyze_backtest_logic()
