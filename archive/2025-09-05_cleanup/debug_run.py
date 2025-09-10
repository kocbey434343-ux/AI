"""Offline debug script: generate synthetic signals and attempt trades.
Run with:
  powershell> $env:OFFLINE_MODE="true"; $env:QT_QPA_PLATFORM="offscreen"; python debug_run.py
"""
from config.settings import Settings
from src.signal_generator import SignalGenerator
from src.trader import Trader
import json, os, time

def ensure_top_pairs(pairs):
    os.makedirs(Settings.DATA_PATH, exist_ok=True)
    path = f"{Settings.DATA_PATH}/top_150_pairs.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(pairs, f)
    return path

pairs = ["BTCUSDT","ETHUSDT","XRPUSDT"]
ensure_top_pairs(pairs)
print("Top pairs file prepared.")

gen = SignalGenerator()
print("Generating signals...")
signals = gen.generate_signals(pairs)
print(f"Generated {len(signals)} signals")
for sym, s in signals.items():
    print(f"  {sym}: signal={s['signal']} score={s['total_score']:.2f} close={s['close_price']}")

tr = Trader()
print("Executing trades...")
results = {}
for sym, s in signals.items():
    payload = {
        'symbol': sym,
        'signal': s['signal'],
        'close_price': s['close_price'],
        'prev_close': s['close_price'] * 0.995,
        'volume_24h': s['volume_24h'],
        'total_score': s['total_score'],
        'indicators': s['indicators']
    }
    ok = tr.execute_trade(payload)
    results[sym] = ok
print("Trade execution results:")
for sym, ok in results.items():
    print(f"  {sym}: {'OPENED' if ok else 'SKIPPED'}")
print("Open positions:", list(tr.open_positions.keys()))
print("Risk status:", tr.risk_status())

print("Done.")
