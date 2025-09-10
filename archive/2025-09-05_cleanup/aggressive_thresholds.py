#!/usr/bin/env python3
"""Aggressive threshold override for more trades"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import json

from src.utils.threshold_cache import get_cached_threshold

def apply_aggressive_thresholds():
    """Apply very aggressive thresholds for maximum trade generation"""

    aggressive_thresholds = {
        'BUY_SIGNAL_THRESHOLD': 35.0,    # Very low for more BUY signals
        'SELL_SIGNAL_THRESHOLD': 30.0,   # Higher for more SELL signals
        'BUY_EXIT_THRESHOLD': 30.0,      # Lower exit threshold
        'SELL_EXIT_THRESHOLD': 35.0,     # Higher exit threshold
    }

    print("🔥 APPLYING AGGRESSIVE THRESHOLDS")
    print("=" * 50)

    # Update param_overrides.json
    with open("data/param_overrides.json", "w") as f:
        json.dump(aggressive_thresholds, f, indent=2)
    print("📄 Updated param_overrides.json")

    # Force cache refresh
    print("🔄 Override file updated, cache will refresh on next use")

    # Verify new values (will be applied on next threshold access)
    print("\n✅ AGGRESSIVE THRESHOLDS APPLIED:")
    for name, expected in aggressive_thresholds.items():
        print(f"  📊 {name}: {expected}")

    print("\n🚀 Ready for aggressive trading strategy!")
    return aggressive_thresholds

if __name__ == "__main__":
    apply_aggressive_thresholds()
