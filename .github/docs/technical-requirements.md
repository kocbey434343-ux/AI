# TEKNİK GEREKSİNİMLER VE TEST STRATEJİSİ

## A6. Non-Fonksiyonel Gereksinimler (NFR)

| Kategori | Gereksinim | Hedef |
|----------|------------|-------|
| Performans | Sinyal üretimi latency | < 50 ms / sembol (offline test) |
| Performans | Emir açılış round-trip | < 800 ms (spot) ortalama |
| Güvenilirlik | Günlük risk reset determinism | %100 (log + slog event) |
| Güvenlik | API anahtar log sızıntısı | 0 (redaction zorunlu) |
| Gözlemlenebilirlik | p95 open_latency_ms raporu | 5 dk içinde güncel |
| Tutarlılık | Replay determinism hash | Aynı giriş = aynı hash |
| Kurtarma | Reconciliation çalıştırma başında | < 5 sn tamam |
| Dayanıklılık | Rate limit burst | Exponential backoff + log |
| Güvenilirlik | Emir idempotency | Duplicate olmayan kayıt, unique key PASS |
| Tutarlılık | Exchange precision uyumu | Tüm emirlerde quantize PASS (unit) |
| Zaman | Clock skew | |skew| ≤ 500 ms, uyarı > 500 ms |
| Operasyon | Endpoint güvenliği | Testnet/Prod switch explicit, default=Testnet |

## A7. Risk Matrisi (Özet)

| Risk | Olasılık | Etki | Durum / Mitigasyon |
|------|----------|------|---------------------|
| Lookahead bias | ~~Orta~~ | ~~Yüksek~~ | ✅ CR-0064 RESOLVED |
| Slippage aşımı | ~~Orta~~ | ~~Yüksek~~ | ✅ CR-0065 RESOLVED |
| Auto-heal kapsamı yetersiz | ~~Orta~~ | ~~Orta~~ | ✅ CR-0068 RESOLVED |
| Guard telemetri persist yok | ~~Orta~~ | ~~Orta~~ | ✅ CR-0069 RESOLVED |
| Determinism harness yok | ~~Orta~~ | ~~Orta~~ | ✅ CR-0072 RESOLVED |
| Scattered risk controls | ~~Yüksek~~ | ~~Yüksek~~ | ✅ CR-0076 RESOLVED |

## A8. Test Stratejisi & Kapsam

Test Tipleri: Unit (hesaplamalar), Integration (trade aç/kapa), Property (risk limit), Replay (determinism), Chaos (WS kesinti), Performance (latency ölçüm), Migration (schema v4).

Kapsam Hedefleri:
- Kritik yol (open_position -> record_open -> place_protection) satır kapsamı ≥ %85
- Risk hesaplama fonksiyonları hata dalı kapsamı ≥ %90
- Guard pipeline negatif senaryo varyantları (halt, daily loss, low volume, correlation) ≥ %95 yürütülmüş.

Kalite Kapıları: Build + Lint PASS, Unit & Integration PASS, determinism hash stabil, migration ileri + geri (dry-run) temiz.

P0 Testnet Öncesi Zorunlu Testler:
- Order idempotency & retry: Duplicate submit dedup-key ile tek kayıt (unit+integration)
- Precision/minNotional uyum: Binance filters'e göre price/qty quantize (parametrik unit)
- Fee model doğrulama: Maker/Taker simülasyonunda beklenen net PnL (unit)
- Rate limit & backoff: 429/418 simülasyonu, exponential backoff ve metrik artışı (integration)
- Clock skew guard: Yapay 1–3 sn drift senaryosu, uyarı ve guard etkinliği (unit)
- Endpoint switch güvenliği: Testnet/Prod yanlış seçimi engelleme (unit)
- OCO fallback: SL veya TP tekil hatasında retry ve graceful degrade (integration)

### A35 Test Stratejisi Güncellenmesi

#### 35.1 A31 Test Kapsam
**Meta-Router Tests**:
- Unit: MWU ağırlık güncellemesi (deterministik)
- Unit: Gating skor hesaplama (TrendScore, SqueezeScore, etc.)
- Integration: 4 uzman senkronizasyonu
- Property: Ağırlık toplamı ≡ 1.0, clamp [0.1, 0.6]

**Uzman Tests**:
- Unit: S2 range MR sinyal üretimi (BB+RSI)
- Unit: S3 volume BO sinyal üretimi (Donchian+ATR)
- Unit: S4 momentum scoring (3h/6h/12h composite)
- Integration: Risk dağıtımı + position sizing

#### 35.2 A32 Test Kapsam
**Edge Hardening Tests**:
- Unit: Wilson CI hesaplama (200 trade pencere)
- Unit: 4× cost rule fee+slip estimation
- Unit: OBI/AFR mikroyapı hesaplama
- Property: Kelly fraction [0, max_fraction] aralığında
- Integration: EHM COLD edge NO-GO policy

**Performance Tests**:
- Latency: OBI real-time <100ms
- Memory: EHM 200 trade buffer management
- Throughput: Dead-zone filtering pipeline

#### 35.3 End-to-End Scenarios
**Ensemble vs Solo**: Meta-Router ON/OFF performance karşılaştırması
**Market Regime**: Trend/range/squeeze koşullarında uzman seçimi
**Risk Escalation**: COLD edge + Kelly reduction + dead-zone integration
