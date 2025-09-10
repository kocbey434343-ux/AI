# ŞEMA YÖNETİMİ VE MİGRASYON PLANLARI

## A10. Şema & Tablo Genişlemeleri Planı

| Tablo | Yeni Alan | Tip | CR | Açıklama |
|-------|-----------|-----|----|----------|
| trades | schema_version | INTEGER | 0066 | Satır şema rev referansı |
| trades | created_ts | TEXT | 0066 | ISO açılış zaman damgası |
| trades | updated_ts | TEXT | 0066 | Son güncelleme |
| trades | param_snapshot | TEXT | 0071 | Konfig hash (JSON or hex) |
| guard_events (yeni) | guard, symbol, reason, extra | Çeşitli | 0069 | Guard telemetri |
| executions | exec_type=trailing_update genişleme | TEXT | (mevcut) | Trailing audit |
| executions | dedup_key | TEXT | 0087 | Idempotent execution kayıtları; UNIQUE index `idx_exec_dedup` |

## A11. İzlenebilirlik & Metrik Sözleşmesi

Structured Log Event Temel Alanları: ts, event, symbol?, trade_id?, severity?, payload.

Zorunlu Eventler: app_start, trade_open, trade_close, partial_exit, trailing_update, reconciliation, auto_heal_attempt/success/fail, anomaly_latency/slippage, daily_risk_reset, shutdown_snapshot.

Metrik Örnekleri (Prometheus plan):
- bot_open_latency_ms_bucket / _sum / _count
- bot_entry_slippage_bps_histogram
- bot_guard_block_total{guard="daily_loss"}
- bot_positions_open_gauge
- bot_reconciliation_orphans_total{type="exchange_position"}

## A12. Determinism Hash

Uygulandı (CR-0072): SHA256(
  strategy_version + "|" +
  join(";", sort_by_key(config_items)) + "|" +
  join(";", map(ts, signals_closed_bar_order)) + "|" +
  join(";", map(e -> f"{e.ts}:{e.from}->{e.to}", order_state_transitions))
)

Notlar:
- Timestamp normalizasyonu: saniyeye yuvarlama (floor).
- Sadece kapanmış mum sinyalleri dahil (CR-0064 lookahead guard ile uyumlu).
- State transition feed: executions.exec_type in {state_transition, scale_out, trailing_update} kaynaklı olaylar.
- Replay Manager entegrasyonu: run başında snapshot, sonunda hash kaydı (CR-0072).

## A13. OrderState FSM (CR-0063)

Amaç: Emir & pozisyon durumlarının deterministik ve izlenebilir hale getirilmesi; reconciliation & determinism hash için kaynak oluşturmak.

Durumlar (state enum önerisi):
- INIT (hazırlık, context oluşturuldu henüz borsa emri yok)
- SUBMITTING (REST order gönderildi, yanıt bekleniyor)
- OPEN_PENDING (exchange accepted; fill bekliyor / kısmi fill olabilir)
- PARTIAL (kısmi dolum; remaining_size > 0)
- OPEN (tam dolum; remaining_size == position_size, scale-out öncesi tam boy)
- ACTIVE (OPEN veya PARTIAL sonrası koruma emirleri yerleşti ve izleniyor)
- SCALING_OUT (partial exit emri gönderildi / işlendi)
- TRAILING_ADJUST (trailing stop güncelleme işlemi snapshot anı)
- CLOSING (kapatma emri gönderildi, fill bekliyor)
- CLOSED (tam kapandı; realized PnL hesaplandı)
- CANCEL_PENDING (iptal denemesi yapıldı, sonuç bekleniyor)
- CANCELLED (başarılı iptal; pozisyon açılmadı veya kalan miktar iptal edildi)
- ERROR (terminal hata; manuel müdahale gerekebilir)

İzinli Geçişler (özet):
INIT -> SUBMITTING -> OPEN_PENDING -> (PARTIAL | OPEN)
PARTIAL -> (PARTIAL | OPEN | SCALING_OUT | CLOSING)
OPEN -> (ACTIVE | SCALING_OUT | CLOSING | TRAILING_ADJUST)
ACTIVE -> (SCALING_OUT | TRAILING_ADJUST | CLOSING)
SCALING_OUT -> (ACTIVE | SCALING_OUT | CLOSING)
TRAILING_ADJUST -> (ACTIVE | CLOSING)
OPEN_PENDING -> CANCEL_PENDING -> CANCELLED
SUBMITTING -> CANCEL_PENDING -> CANCELLED
Herhangi -> ERROR (hata yakalandığında)
ERROR -> (CLOSING | CANCEL_PENDING) (manuel / auto-heal girişimi)
CLOSING -> CLOSED

FSM Eventleri (transition kaydı): order_submit, order_ack, fill_partial, fill_full, protection_set, scale_out, trail_update, close_submit, close_fill, cancel_submit, cancel_ack, error_detected, auto_heal_attempt.

Persist Alanları:
- trades.order_state (TEXT)
- executions.state_from, state_to (opsiyonel genişleme - CR-0063 ek opsiyon)
- executions.exec_type değerlerine: state_transition, scale_out, trailing_update

İzleme Metrikleri (Prometheus plan):
- bot_order_state_transition_total{from="",to=""}
- bot_order_state_duration_seconds_bucket{state=""}

Guard Kuralları:
- SUBMITTING süresi > X sn => error_detected
- OPEN_PENDING süresi > Y sn => reconciliation trigger
- PARTIAL süresi > Z sn ve fill ilerlemiyor => risk reduce veya kapat denemesi

Test Kapsam Gereksinimi:
- Her transition için en az 1 unit test + invalid transition raise testi.

## A14. Order Lifecycle Ayrıntılı Akış

1. Signal ACCEPT -> Risk hesap -> FSM INIT
2. Order submit -> SUBMITTING (timestamp t0 kaydı)
3. Ack alınır -> OPEN_PENDING (ack_latency = now - t0 kaydı)
4. Fill event(ler)i -> PARTIAL veya OPEN
5. Koruma emirleri -> ACTIVE
6. Partial exit tetik -> SCALING_OUT -> (fill sonrası) ACTIVE
7. Trailing update -> TRAILING_ADJUST -> ACTIVE
8. Kapatma kararı -> CLOSING -> CLOSED (PnL finalize, metrics + slog)
9. Hata / iptal durumlarında CANCEL_* veya ERROR dalları.

Lifecycle Telemetri Kaydı Zorunlu Alanlar:
{ts, trade_id, event, state_from, state_to, symbol, qty, remaining, reason?}

## A15. M1 Sprint Plan (State Integrity Milestone)

Sprint Hedefi: "Deterministik durum yönetimi + versiyonlandırılmış şema ile reconcile güvenilirliği".

Kapsam (M1):
- CR-0063 FSM implement & test
- CR-0066 Schema versioning (trades v4: schema_version, created_ts, updated_ts; positions alanları senkron)
- CR-0067 Reconciliation v2 (orderId eşleşme + partial fill sync)
- Temel determinism hash iskeleti (CR-0072 ön hazırlık: state transition feed)

Görev Ayrımı:
1. Migration v4 taslağı & dry-run test (idempotent) (CR-0066)
2. FSM enum + transition validator + invalid transition testleri (CR-0063)
3. Execution / core entegrasyonu (state set & slog event) (CR-0063)
4. Reconciliation v2: borsa order list -> lokal state diff (CR-0067)
5. Partial fill merge algoritması & test (CR-0067)
6. Determinism feed collector (yalnızca transition append) (prep CR-0072)
7. Prometheus exporter taslak skeleton (yalnızca in-memory sayaç) (hazırlık CR-0074, opsiyonel)

Riskler & Mitigasyon:
- Migration yanlış veri: Önce backup snapshot + dry-run doğrulama.
- FSM entegre edilmemiş eski path: Feature flag (FEATURE_FSM_ENABLED) ile toggle.
- Reconciliation rate limit baskısı: Paginasyon + exponential backoff.

## A16. Kabul Kriterleri (Key CR'ler)

CR-0063 (FSM):
- Geçersiz transition denemesi ValueError fırlatır ve test ile kanıtlı.
- trade_open, partial_exit, trailing_update, trade_close eventlerinde executions tablosuna en az 1 state_transition veya ilgili exec satırı eklenir.
- bot_order_state_transition_total metriği en az 5 farklı transition için artar (test stub).

CR-0064 (Lookahead Kapalı Mum):
- Sinyal üretiminde current bar kapanmadan trade açılmaz; testte artificially değişen son bar verisi trade tetiklemez.
- Hysteresis testleri kapanmış mum datası ile deterministik.
- Lookahead guard violation log severity=WARNING ve guard block metriği artar.

CR-0065 (Slippage Guard):
- Açılış slippage bps > threshold ise order iptal veya küçültme yapılır (policy configurable) ve slog event anomaly_slippage üretilir.
- Test: Yapay fill_price sapması ile guard tetiklenir ve trade açılmaz.

CR-0066 (Schema Versioning v4):
- trades tablosu schema_version değeri 4 alır; eski satırlar migration sonrası 4 set edilmiş.
- created_ts, updated_ts tutulur; update operasyonu updated_ts'i değiştirir (test patch update doğrular).
- Migration ileri + geri (rollback script) dry-run PASS.

CR-0067 (Reconciliation v2):
- Başlangıçta reconciliation süresi < 5 sn (test time bound mock ile ölçer).
- Exchange'de olup localde olmayan order -> orphan_log event + corrective action (insert CLOSED veya CANCELLED?).
- Localde olup exchange kapalı -> auto-close reconcile event.
- Partial fill farkı -> remaining_size güncellemesi + state transition PARTIAL->ACTIVE.

## A17. Definition of Done (M1 bağlamı)

- Kod: Tip ipuçları (mümkün olan yerlerde) + ruff lint PASS.
- Test: Yeni fonksiyon / transition için en az 1 happy + 1 negatif senaryo.
- Kapsam: Critical path satır kapsamı >= %85 (rapor eklendi / kaydedildi).
- Dokümantasyon: SSoT ilgili bölüm güncellendi + migration README güncellendi.
- Observability: Slog eventler manuel gözlemlendi (en az 1 örnek).
- Güvenlik: Yeni log satırları API key sızıntısı içermiyor (redaction pipeline değişmedi).
- Geri Alınabilirlik: Migration rollback script çalışır (dry-run kanıt).
- Feature Flag: FSM toggle off iken eski davranış bozulmuyor (regression test).

## A18. Migration Plan (Schema v4 - CR-0066)

Adımlar:
1. Pre-check: trades tablosu kolon listesi -> beklenen v3 şema doğrulanır.
2. Backup: sqlite dosyası snapshot klasörüne kopya (timestamp).
3. Transaction içinde: ALTER TABLE ek kolonlar (schema_version, created_ts, updated_ts) eklenir.
4. Eski satırların schema_version=4 ve created_ts= (varsa mevcut open_time else now) set edilir, updated_ts = created_ts.
5. Index (opsiyonel) created_ts üzerinde.
6. Verification: COUNT(*) tutarlılık, NULL kolon yok.
7. Rollback script: (a) yeni tabloya v3 kolon subseti copy (b) orijinali rename (c) kopyayı eski isimle swap; yalnızca test ortamında.
8. Idempotency: Migration tekrar çalıştırılırsa değişiklik yaratmaz (guard check).

## A19. Observability Genişleme (İleri Plan)

- State transition counter & duration histogram.
- Slippage guard trigger sayacı bot_guard_block_total{guard="slippage"}.
- Lookahead guard metriği bot_guard_block_total{guard="lookahead"}.
- Determinism feed hash per run (app_end event).
- Guard events tablosu (CR-0069) ile sorgulanabilir telemetri.
- Rate limit ve backoff: bot_rate_limit_hits_total, bot_backoff_seconds_sum/_count
- Clock skew ölçümü: bot_clock_skew_ms_gauge, bot_clock_skew_alerts_total
- Precision quantize uyumu: bot_order_quantize_adjust_total
- Idempotent submit takip: bot_order_submit_dedup_total, bot_order_submit_retries_total

## A20. Açık Sorular & Kararlar (To Clarify)

1. Partial fill politikası: Uzun süren PARTIAL durumunda otomatik küçültme mi iptal mi? (Policy flag önerisi: PARTIAL_STALL_ACTION=reduce|cancel|hold)
2. Slippage guard eşiği: Mutlak bps mi; ATR oranı mı? (Konfig parametre adı: SLIPPAGE_GUARD_BPS_MAX)
3. Determinism hash'te timestamp normalizasyonu nasıl (floor to second / remove)?
4. Reconciliation orphans handling: CLOSED vs CANCELLED hangisi tercih? (Duruma göre mapping tablosu?)
5. Trailing update yoğunluğu: Per fill / per zaman? Rate limit etkisi izlenmeli.

Revizyon Notu: A13–A20 bölümleri eklendi; M1 derin plan + kabul kriterleri + migration planı tanımlandı.
