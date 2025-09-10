#!/usr/bin/env python3
"""
Basit Confluence Test
====================
"""

import sys
import os
sys.path.append('src')

from src.signal_generator import SignalGenerator

def simple_confluence_test():
    print("CONFLUENCE TEST")
    print("===============")

    signal_gen = SignalGenerator()

    # BTC test
    print("\n1. BTC Test:")
    signal_data = signal_gen.generate_pair_signal('BTCUSDT')
    if signal_data:
        conf = signal_data.get('confluence', {})
        print(f"  Confluence Score: {conf.get('confluence_score', 0):.2f}")
        print(f"  Signal Direction: {conf.get('signal_direction', 'N/A')}")

        # Component signals
        comp = conf.get('component_signals', {})
        if comp:
            print("  Component Signals:")
            for name, data in comp.items():
                print(f"    {name}: value={data.get('value', 'N/A')} signal={data.get('signal', 'N/A')}")

    # ETH test
    print("\n2. ETH Test:")
    signal_data = signal_gen.generate_pair_signal('ETHUSDT')
    if signal_data:
        conf = signal_data.get('confluence', {})
        print(f"  Confluence Score: {conf.get('confluence_score', 0):.2f}")
        print(f"  Signal Direction: {conf.get('signal_direction', 'N/A')}")

        # Component signals
        comp = conf.get('component_signals', {})
        if comp:
            print("  Component Signals:")
            for name, data in comp.items():
                print(f"    {name}: value={data.get('value', 'N/A')} signal={data.get('signal', 'N/A')}")

    print("\nTEST ANALIZI:")
    print("- Confluence skorları aynı mi?")
    print("- Component signal değerleri farklı mı?")
    print("- BB hesaplaması hala exception mu?")

if __name__ == "__main__":
    simple_confluence_test()
