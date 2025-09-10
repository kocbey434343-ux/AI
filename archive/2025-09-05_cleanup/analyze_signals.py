#!/usr/bin/env python3
"""Son sinyal dosyasını analiz et"""
import json
import os

def analyze_signals():
    signal_file = "data/processed/signals_20250823_180416.json"

    if os.path.exists(signal_file):
        with open(signal_file, 'r') as f:
            signals = json.load(f)

        print(f"Signal dosyasi: {signal_file}")
        print(f"Toplam sembol: {len(signals)}")
        print("\nSemboller:")

        al_signals = []
        sat_signals = []
        bekle_signals = []

        for symbol, data in signals.items():
            signal = data.get('signal', 'UNKNOWN')
            score = data.get('total_score', 0)
            print(f"{symbol}: {signal} (Score: {score:.2f})")

            if signal == 'AL':
                al_signals.append(symbol)
            elif signal == 'SAT':
                sat_signals.append(symbol)
            else:
                bekle_signals.append(symbol)

        print(f"\nÖzet:")
        print(f"AL sinyali: {len(al_signals)} sembol")
        print(f"SAT sinyali: {len(sat_signals)} sembol")
        print(f"BEKLE: {len(bekle_signals)} sembol")

        if al_signals:
            print(f"\nAL sinyalleri: {', '.join(al_signals[:10])}")
        if sat_signals:
            print(f"SAT sinyalleri: {', '.join(sat_signals[:10])}")

    else:
        print(f"Sinyal dosyasi bulunamadi: {signal_file}")

if __name__ == "__main__":
    analyze_signals()
