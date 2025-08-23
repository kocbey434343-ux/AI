# Trader Modulu Mimari Ozeti

Bu belge yeni moduler Trader yapisinin ana bilesenlerini ve akisini aciklar.

## Modul Parcalari

| Dosya | Gorev |
|-------|-------|
| `trader/core.py` | Orkestrasyon, dis API (execute_trade, process_price_update, close_*) |
| `trader/guards.py` | Sinyal oncesi guard zinciri (halt, gunluk zarar, consecutif kayip, outlier, hacim, korelasyon) |
| `trader/execution.py` | ATR tabanli SL/TP hesaplama, adaptif boyut, emir gonderme, acilis kaydi |
| `trader/trailing.py` | Kismi cikis (R seviyeleri) + klasik step trailing + ATR trailing |
| `trader/metrics.py` | Latency & slippage ring buffer, periyodik flush, anomaly tespiti |

## Akis (Sinyal -> Pozisyon)
1. `execute_trade(signal)`
2. `pre_trade_pipeline` guard kontrolu (ilk fail -> son)
3. ATR, SL, TP, pozisyon boyutu, korelasyon tekrar
4. Emir MARKET (offline ise sentetik)
5. Fill -> pozisyon state + TradeStore open kaydi

## Fiyat Guncelleme Akisi
`process_price_update(symbol, last_price)`:
1. R multiple hesap
2. Kismi cikis kosullari
3. Trailing güncelleme (step + ATR cooldown)
4. Metrik flush & anomaly

## Veritabani (TradeStore)
- `trades`: open/close, weighted PnL (scale out hesaba katma)
- `executions`: scale_out ve diger olaylar
- `metrics`: ileride DB metrikleri (su an JSONL flush ayrik)

## Guard Zinciri Ayrintisi
Siralama: halt flag -> gunluk risk limitleri -> outlier bar -> hacim / max pozisyon -> korelasyon (final execution icinde de kontrol). Her guard kendi sayaç anahtarini `guard_counters` icinde artirir.

## Kismi Cikis & Trailing
- R seviye listesi Settings'ten (TP1/TP2) okunur.
- Ilk kismi cikis sonrasi stop BE'ye cekilir (fiyata gore).
- Trailing aktivasyon R >= `TRAILING_ACTIVATE_R_MULT`.
- ATR trailing cooldown -> `ATR_TRAILING_COOLDOWN_SEC`.

## Metrikler
- Listeler: open_latency_ms, close_latency_ms, entry_slip_bps, exit_slip_bps.
- Flush araligi: `METRICS_FLUSH_INTERVAL_SEC` -> JSONL (time bucket minute). 
- Anomaly: ortalama open latency > `LATENCY_ANOMALY_MS` veya entry slippage > `SLIPPAGE_ANOMALY_BPS`.

## Gelistirme Notlari / Yapilabilecekler
- Gercek bakiye entegrasyonu (account info) -> `get_account_balance`.
- OCO/stop-limit ekleme spot icin.
- Futures hedge/isolated mod parametreleri.
- Daha detayli korelasyon matris onbellekleme / simetrik azaltma.
- Param set versionlama ve kalibrasyon pipeline baglantisi.

## Test Stratejisi
- guard zinciri unit test (her engel icin ayrik senaryo)
- execution boyutlama & sl quantize test
- partial exit progression (TP1 -> TP2) + weighted pnl recompute
- trailing stop hareket validasyon (step + ATR)
- anomaly tetik/geri donus

Bu belge modul gelistikce guncellenecektir.