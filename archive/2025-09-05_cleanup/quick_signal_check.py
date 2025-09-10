import json

with open("data/processed/signals_20250823_180416.json", "r") as f:
    signals = json.load(f)

print(f"Toplam sembol: {len(signals)}")

al_count = 0
sat_count = 0
bekle_count = 0

for symbol, data in signals.items():
    signal = data.get('signal', 'BEKLE')
    if signal == 'AL':
        al_count += 1
    elif signal == 'SAT':
        sat_count += 1
    else:
        bekle_count += 1

print(f"AL: {al_count}, SAT: {sat_count}, BEKLE: {bekle_count}")

# İlk 10 sinyali göster
count = 0
for symbol, data in signals.items():
    if count >= 10:
        break
    signal = data.get('signal', 'BEKLE')
    score = data.get('total_score', 0)
    print(f"{symbol}: {signal} (Score: {score:.1f})")
    count += 1
