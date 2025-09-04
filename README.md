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

## Hızlı Başlangıç (Headless + Metrics)
Windows PowerShell ile başlatma ve metrik doğrulama:

```powershell
# Ortamı etkinleştir (opsiyonel)
./activate_env.bat

# Headless çalıştır (testnet varsayılan)
./run_headless.bat

# Ayrı bir PowerShell penceresinde sağlık ve metrik kontrolü
curl http://localhost:8080/health
curl http://localhost:8080/metrics | Select-Object -First 20
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

## Sipariş Gönderimi Retry/Backoff (CR-0083)
Emir gönderimi geçici hatalarda jitter’lı üstel geri çekilme ile yeniden denenir. Her deneme arasında süre: `sleep = base * mult^(attempt-1) * jitter(0.8–1.2)`; alt/üst sınır `[0.05s, 10.0s]`.

- Ayarlar (config.settings.Settings):
	- `RETRY_MAX_ATTEMPTS` (varsayılan 3)
	- `RETRY_BACKOFF_BASE_SEC` (varsayılan 0.5)
	- `RETRY_BACKOFF_MULT` (varsayılan 2.0)
- Gözlemlenebilirlik:
	- Prometheus sayaç: `bot_order_submit_retries_total{reason}`
	- Prometheus histogram: `bot_backoff_seconds`
	- Yapısal log olayı: `order_submit_retry` (payload: attempt, max_attempts, sleep_sec)
- Güvenlik:
	- TTL tabanlı idempotent submit guard ile çakışmadan çalışır (aynı ana parametreler kısa sürede tekrar edilirse atlanır).

## Çalışma Zamanı Maliyet Persisti
`config/runtime_costs.json` dosyasına komisyon, kayma ve next‑bar ayarı yazılır / okunur (`config/runtime_costs.py`).

## Logging
`src/utils/logger.py` RotatingFileHandler (5MB * 3) + singleton cache. Log dizini: `data/logs` (env ile değiştirilebilir).

## ENV_ISOLATION ve Yol Önceliği (DB/Log/Backup/Halt/Metrics)
Çalışma dosyaları (SQLite DB, loglar, yedekler, halt bayrağı, metrics) ortam-temelli (testnet/prod/offline) dizinlere izole edilebilir.

- Modlar:
	- ENV_ISOLATION=on: Her şey `DATA_PATH/<env>/...` altında tutulur.
	- ENV_ISOLATION=off: Klasik davranış, mevcut yollar korunur (izolasyon yok).
	- ENV_ISOLATION=auto: Test/CI veya headless modda otomatik `on` davranışı; aksi halde proje varsayılanları.

- Ortam adı (<env>):
	- USE_TESTNET=true → `testnet`
	- USE_TESTNET=false → `prod`
	- OFFLINE_MODE=true → `offline` (USE_TESTNET geçersiz kılar)

- Yol önceliği (özet):
	1) DATA_PATH explicit ve TRADES_DB_PATH explicit değilse → TRADES_DB_PATH = `DATA_PATH/<env>/trades.db`
	2) DATA_PATH explicit ve TRADES_DB_PATH explicit ise →
		 - TRADES_DB_PATH, DATA_PATH altında ise: Olduğu gibi kullanılır.
		 - TRADES_DB_PATH, DATA_PATH dışında ve adı varsayılan `trades.db` ise: Sızıntı önlenir, `DATA_PATH/<env>/trades.db` türetilir.
		 - TRADES_DB_PATH özel dosya adını (ör. `my.db`) kullanıyorsa: Olduğu gibi korunur (konum dışarıda olsa bile).
	3) DATA_PATH explicit değil ve TRADES_DB_PATH explicit ise → TRADES_DB_PATH aynen korunur.
	4) Her ikisi de explicit değil → TRADES_DB_PATH = `./data/<env>/trades.db`.

- Diğer yollar (izole dizinler):
	- Loglar: `DATA_PATH/<env>/logs`
	- Yedekler: `DATA_PATH/<env>/backups`
	- Halt bayrağı: `DATA_PATH/<env>/halt`
	- Prometheus/metrics dosyaları: `DATA_PATH/<env>/metrics`

- Hızlı örnekler:
	- Sadece DATA_PATH: `ENV_ISOLATION=on`, `DATA_PATH=D:/runs`, `USE_TESTNET=true` → DB: `D:/runs/testnet/trades.db`
	- Sadece TRADES_DB_PATH: `TRADES_DB_PATH=D:/db/custom.db` → DB: `D:/db/custom.db` (korunur)
	- İkisi de explicit, sızıntı: `DATA_PATH=D:/runs`, `TRADES_DB_PATH=C:/tmp/trades.db`, `USE_TESTNET=false` → DB: `D:/runs/prod/trades.db`
	- Hiçbiri explicit değil (offline): `OFFLINE_MODE=true` → DB: `./data/offline/trades.db`

Not: Bu davranışlar kapsamlı testlerle doğrulanmıştır (ENV izolasyon permütasyonları). Varsayılan endpoint güvenliği nedeniyle gerçek prod’a bağlanmak için ayrıca `ALLOW_PROD=true` gerekir.

## Prometheus /metrics Uç Noktası
Yerleşik HTTP sunucu ile Prometheus formatında metrikler sunulur. Varsayılan adres `http://localhost:8080/metrics` ve sağlık kontrolü `http://localhost:8080/health`.

- Başlatma (koddan): `Trader` örneğinde `init_metrics_server(port=8080, host="localhost")` çağırın; durdurmak için `shutdown_metrics_server()`.
- İçerik: gecikme histogramları, slippage metrikleri, guard sayaçları, retry/backoff metrikleri ve çeşitli gauge’lar.
- Hızlı kontrol (PowerShell):

```powershell
curl http://localhost:8080/health
curl http://localhost:8080/metrics | Select-Object -First 20
```

### İlgili Ayarlar (Settings hızlı referans)
- `RETRY_MAX_ATTEMPTS` (vars: 3)
- `RETRY_BACKOFF_BASE_SEC` (vars: 0.5)
- `RETRY_BACKOFF_MULT` (vars: 2.0)
- `ORDER_DEDUP_TTL_SEC` (vars: projeye göre)
- `USE_TESTNET` (vars: true)
- `ALLOW_PROD` (prod’a bağlanmak için ayrıca true olmalı; aksi halde bloklanır)

### Metrik Örnekleri
```text
# Sipariş yeniden deneme sayacı (etiket: reason)
bot_order_submit_retries_total{reason="order_place_fail"} 2

# Backoff saniyeleri histogramı
bot_backoff_seconds_bucket{le="0.1"} 1
bot_backoff_seconds_sum 0.3
bot_backoff_seconds_count 2
```

## Geliştirme Yol Haritası (Kalanlar)
- Spot OCO (SL/TP) otomatik emir seti
- Gelişmiş derinlik tabanlı kayma modeli
- Paper trading & trade geçmişi (SQLite)
- Websocket canlı veri beslemesi
- Trailing ve kısmi kar realizasyonu

## Uyarı
Bu bot üretim kullanımına hazır değildir; örnek ve araştırma amacıyla sunulmuştur. Kendi API anahtarlarınızı güvenli saklayın; gerçek piyasada test etmeden önce paper / düşük bakiye ile deneyin.
