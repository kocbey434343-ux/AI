# Trade Bot

Binance verilerini çekip teknik indikatörler ile AL / SAT / BEKLE sinyali üreten ve PyQt5 arayüzü sağlayan modüler bir bot.

## Öne Çıkan Özellikler
- Dinamik kalibrasyon (eşik optimizasyonu, maliyet sonrası expectancy sıralaması)
- Histerezis (flip‑flop azaltılmış sinyaller)
- ATR tabanlı stop & parametrik Risk:Ödül oranı
- Risk bazlı pozisyon boyutu (marjin + kaldıraç uyumlu)
- Komisyon & kayma modeli (round‑trip maliyet dâhil)
- Next‑bar fill opsiyonu (daha gerçekçi backtest)
- Rotating log sistemi
- Canlı order latency & slippage metrikleri (son N ortalamaları UI'da mini etiketler)

## Kurulum
```bash
pip install -r requirements.txt
python src/main.py
```

## Risk Yönetimi
`src/risk_manager.py` ATR varsa `stop = entry ± ATR * atr_multiplier` yoksa fallback `%fallback_stop_pct` mesafe.

Pozisyon değeri hesap akışı:
1. risk_amount = balance * (risk_percent/100)
2. stop_distance_pct = |entry-stop| / entry
3. position_value = risk_amount / stop_distance_pct
4. Futures modunda marjin = position_value / leverage (marjin aşırı ise ölçeklenir)
5. position_size = position_value / entry_price

Take profit = entry ± risk_distance * `take_profit_rr`.

## Komisyon & Kayma
Settings değerleri yüzde olarak saklanır: `COMMISSION_PCT_PER_SIDE = 0.04` => %0.04 (4 bps). Hesaplarda /100 yapılır.
Round‑trip yaklaşık maliyet: `2 * (commission + slippage)` (her biri yüzde). Örn: 0.04 + 0.02 => %0.06 tek taraf, round‑trip ≈ %0.12.

Kalibrasyon simülasyonu bu maliyetleri ve opsiyonel next-bar fill bayrağını dikkate alır.

## Canlı Latency & Slippage Metrikleri
`Trader` sınıfı açılış / kapanış emir gecikmesi (ms) ve giriş / çıkış slippage (bps) örneklerini tutar (son 100). UI Positions sekmesinde her 3 sn'de bir güncellenen iki mini etiket gösterilir:

```
Latency: open=84.3ms / close=91.7ms
Slip: entry=5.2 / exit=3.1 bps
```
`recent_latency_slippage_stats(window=30)` fonksiyonu isteğe bağlı pencere ortalaması döndürür. Daha sonra genişletilecek (histogram, metrics sekmesi).

## Çalışma Zamanı Maliyet Persisti
`config/runtime_costs.json` dosyasına komisyon, kayma ve next‑bar ayarı yazılır / okunur (`config/runtime_costs.py`).

## Logging
`src/utils/logger.py` RotatingFileHandler (5MB * 3) + singleton cache. Log dizini: `data/logs` (env ile değiştirilebilir).

## Geliştirme Yol Haritası (Kalanlar)
- Spot OCO (SL/TP) otomatik emir seti
- Gelişmiş derinlik tabanlı kayma modeli
- Paper trading & trade geçmişi (SQLite)
- Websocket canlı veri beslemesi
- Trailing ve kısmi kar realizasyonu

## Uyarı
Bu bot üretim kullanımına hazır değildir; örnek ve araştırma amacıyla sunulmuştur. Kendi API anahtarlarınızı güvenli saklayın; gerçek piyasada test etmeden önce paper / düşük bakiye ile deneyin.
