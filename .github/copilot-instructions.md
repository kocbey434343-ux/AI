Tek SSoT: Tüm backlog, kararlar ve değişiklik kayıtları bu dosyada tutulur (copilot-instructions.md).
Yapılandırma ve arşiv: Eski kayıtlar gerektiğinde archive/ altında saklanır; harici txt dosyaları kullanılmaz.
```text
Agent Sistem Promptu — Çatışmasız Proje Akışı (Kripto Trade Botu)
SSoT (Single Source of Truth) DÖKÜMANI
```

# 0. Çekirdek İlke & Kullanım
- Türkçe konuş.
- Bu dosya SSoT: çelişen her içerik geçersizdir.
- Her değişiklik CR -> onay -> yama.
- Test-önce: Kabul kriteri + test olmadan uygulama yok.
- Geriye dönük uyumluluk: kırıcı değişiklik => ADR.
- Minimal patch; işlev kaybı için fonksiyon silme yok.
- Açık editör/terminal iş bitince kapat.

# 1. A1 Proje Özeti
Amaç: Binance (spot/futures) üzerinde risk kontrollü, modüler, izlenebilir otomatik trade botu.
Kapsam: Sinyal, risk & boyutlama, emir + koruma, partial & trailing, metrik & anomaly, UI.
Hariç: HFT mikro yapı, DL model eğitimi.
Paydaş: Trader, geliştirici, test, operasyon.
Kısıtlar: Güvenlik (API key sızıntı yok), tutarlılık, offline mod.

# 2. A2 Sözlük / Terimler
R-Multiple: (Fiyat - Entry) / (Entry - Stop).
Koruma Emirleri: Stop + TP (spot OCO / futures STOP+TP).
Partial Exit: Kademeli realize.
Adaptive Risk: ATR yüzdesine göre boyut ölçekleme.

# 3. A3 Modül Kataloğu (Registry)
| MOD-ID | Ad | Konum | Sorumluluk | Bağımlılıklar | Durum |
|--------|----|-------|------------|---------------|-------|
| MOD-CORE-TRADER | Trader Orchestrator | src/trader/core.py | Yaşam döngüsü, guards, state | MOD-RISK, MOD-EXEC, MOD-GUARDS, MOD-TRAIL, MOD-METRICS, MOD-UTILS-STORE | active |
| MOD-EXEC | Execution | src/trader/execution.py | Aç/Kapa, koruma emirleri, boyut | MOD-RISK, API-BINANCE | active |
| MOD-GUARDS | Guards | src/trader/guards.py | Halt, risk limiti, korelasyon, hacim, outlier | MOD-UTILS-STORE, MOD-CORR-CACHE | active |
| MOD-TRAIL | Trailing & Partial | src/trader/trailing.py | Partial exits & trailing stop | MOD-CORE-TRADER | active |
| MOD-METRICS | Metrics | src/trader/metrics.py | Latency/slippage, anomaly + risk reduce | MOD-CORE-TRADER | active |
| MOD-RISK | RiskManager | src/risk_manager.py | Stop/TP, boyutlama | Settings | active |
| MOD-UTILS-STORE | TradeStore | src/utils/trade_store.py | DB persist & sorgu | sqlite3, pandas | active |
| MOD-API-BINANCE | BinanceAPI | src/api/binance_api.py | Veri & emir arabirimi | python-binance | active |
| MOD-API-HEALTH | HealthChecker | src/api/health_check.py | Bağlantı & izin kontrol | MOD-API-BINANCE | active |
| MOD-API-PRICESTREAM | PriceStream | src/api/price_stream.py | WS stream & reconnect | websocket-client | active |
| MOD-CORR-CACHE | CorrelationCache | src/utils/correlation_cache.py | Korelasyon pencere/TTL | numpy | active |
| MOD-DATA-FETCHER | DataFetcher | src/data_fetcher.py | Pair list, OHLCV, stale tespit | MOD-API-BINANCE, Settings | active |
| MOD-INDICATORS | IndicatorCalculator | src/indicators.py | İndikatör & skor | pandas, ta | active |
| MOD-SIGNAL-GEN | SignalGenerator | src/signal_generator.py | Sinyal + hysteresis | MOD-DATA-FETCHER, MOD-INDICATORS | active |
| MOD-UTILS-SLOG | StructuredLog | src/utils/structured_log.py | JSON event logging | Settings | active |
| MOD-UTILS-FLAGS | FeatureFlags | src/utils/feature_flags.py | Env tabanlı flag | None | active |
| MOD-UTILS-HELPERS | Helpers | src/utils/helpers.py | IO & PnL yardımcı | pandas | active |
| MOD-UTILS-LOGGER | Logger | src/utils/logger.py | Rotating logger | logging | active |
| MOD-UTILS-REPLAY | ReplayManager | src/utils/replay_manager.py | Trade decision replay & determinism | structured_log, config_snapshot | active |
| MOD-UTILS-RISK-ESCALATION | RiskEscalation | src/utils/risk_escalation.py | Unified risk escalation & kill-switch | MOD-CORE-TRADER, Settings | active |
| MOD-UTILS-WS | WS Utils | src/utils/ws_utils.py | WS restart kararı | time | active |
| MOD-UI-MAIN | MainWindow | src/ui/main_window.py | PyQt5 ana UI | PyQt5, MOD-CORE-TRADER | active |
| MOD-UI-SIGNAL | SignalWindow | src/ui/signal_window.py | Sinyal analiz UI | PyQt5 | active |
| MOD-BACKTEST-CAL | Calibration | src/backtest/calibrate.py | Threshold optimizasyon & sim | MOD-DATA-FETCHER, MOD-INDICATORS | active |
| MOD-BACKTEST-ORCH | BacktestOrchestrator | src/backtest/orchestrator.py | Backtest workflow | MOD-BACKTEST-CAL | skeleton |
| MOD-SCRIPT-INVENTORY | InventoryGenerator | scripts/generate_inventory.py | Envanter üretim aracı | os, ast | active |

# 4. A4 API & Şema Sözleşmeleri (Özet)
Positions: { side, entry_price, position_size, remaining_size, stop_loss, take_profit, atr, trade_id, scaled_out[(r,qty)], model_version, order_state, created_ts, updated_ts }
Koruma: spot-> oco_resp{ids:[...]}; futures-> futures_protection{sl_id,tp_id}
FN-EXEC-open_position(symbol, ctx)-> bool
FN-EXEC-close_position(symbol)-> bool
Yeni alan ekleme compatible; alan kaldırma => ADR.
Planlanan genişleme: scale_out persist alanları CR-0037 ile eklenecek. Ek: schema_version (trades v4) (CR-0066), guard_events tablosu (CR-0069).

# 5. A5 Görev Panosu
Öncelik: P1 kritik, P2 önemli, P3 iyileştirme.
## 5.1 BACKLOG
P1: PriceStream kapatılırken thread join başarısızsa zorla kes (timeout logging)
P2: Ana zamanlayıcı hatalarında merkezi exception hook ve görsel uyarı (status çubuğu)
P2: Graceful shutdown: uygulama kapanışında açık trade kayıt flush + son durum snapshot  
P1: Backtest kalibrasyon uyumsuzluğu: UI winrate vs run_calibration trade_stats fark analizi
P1: Açık pozisyon / emir reconciliation (bakiye & open orders -> local state diff)
P1: Günlük risk reset otomasyonu (yeni gün tespiti + halt flag temizleme + rapor)
P1: Anomaly (latency/slippage) tetiklenince otomatik risk % düşürme veya trade durdurma
P1: Kısmi fill kalan miktar için otomatik kalan emir yeniden ayarlama
P1: Restart sonrası trailing & partial state tam persist (scaled_out + stop history)
P1: update_positions incremental diff (tam tablo yeniden çizim azaltma)
P1: Toplam Unrealized PnL (USDT) göstergesi: Stil + test iyileştirme
P1: Global exposure metriği (sembol / sektör / yön dağılımı)
P1: Position sizing formülü gözden geçirme (volatilite ayarlı risk / ATR)
P1: DataFetcher stale veri tespiti (timestamp drift) ve uyarı
P1: API key sızıntı kontrolü (runtime log satırlarını tarama)
P2: update_positions PnL hesaplama testleri (LONG/SHORT yön farkı + edge cases)
P2: _maybe_refresh_ws_symbols restart tetik testi (symbol fark senaryoları, debounce)
P2: ATR trailing stop test (güncellenen stop DB'ye yansıyor mu?)
P2: Price update batching (GUI repaint frekansı sınırlama; örn 250ms throttle)
P2: Korelasyon hesap throttling (saniyede max N hesap)
P2: Parametre set yönetim UI (listele, etkinleştir, sil, açıklama)
P2: Trailing stop görseli (pozisyon satırında SL kolon renklendirme değişimi)
P2: Scale-out planı tanımlama (UI: hedef seviyeler + miktarlar)
P2: Çoklu sembol hızlı arama (positions & signals tabloları için incremental search kutusu)
P2: Pozisyon detay yan paneli (seçilen pozisyonun ATR, partial history, trailing log gösterimi)
P2: Gerçek zamanlı latency & slippage mini chart (Metrics sekmesi içi sparkline)
P3: docs/INDEX.md üretimi  
P3: Large Module Decomposition (CR-0035)  
P0: Testnet öncesi emir gönderim idempotency & retry politikası (submit dedup key, replay-safe)
P0: Exchange precision & minNotional uyum doğrulayıcı (tickSize/stepSize/filters cache + unit tests)
P0: Spot/Futures komisyon (maker/taker) parametre doğrulama ve test override (fee sanity)
P0: Clock skew senkronizasyonu (NTP/time drift ölçümü, uyarı ve guard)
P0: Rate limit & backoff telemetrisi (X-MBX-USED-WEIGHT, 429/418 handling + exponential backoff)
P0: Offline/Sim/test modu için bağımsız DB & config izolasyonu (çakışma önleme)
P1: OCO/koruma emirlerinde graceful fallback (TP/SL tekil başarısızlıkta yeniden dene + log)
P1: Precision quantize helper centralization (amount/price quantize tek kaynaktan)
P1: WS reconnect strategy testleri (jitter, backoff, debounce entegrasyonu)
P1: Kill-switch manuel override UI/CLI entegrasyonu güçlendirme (confirm dialog + snapshot)
## 5.2 IN-PROGRESS
P1: CR-0082 Incremental UI Table Updates (positions/closed/scale-out incremental diff, performans) — src/ui/main_window.py, CR-0082_INCREMENTAL_UI_UPDATE.md
P1: CR-STRATEGY-ADVANCED (Gelişmiş Strateji) — src/backtest/realistic_backtest.py, src/signal_generator.py, src/indicators.py
## 5.3 REVIEW
(boş)
## 5.4 DONE (Seçili)
Modular Trader refactor; Protection orders; Weighted PnL reload; Reconciliation diff (CR-0003); Daily risk reset (CR-0004/0044); Anomaly risk reduction (CR-0007); Metrics trimming (CR-0008); Adaptive sizing tests (CR-0009/0010); Trailing persistence (CR-0016); Unrealized PnL metrics + UI (CR-0014/0021); Secret scan (CR-0026); ASCII UI refactor (CR-0023); Inventory & gap analysis; Structured logging events (CR-0028); ATR trailing flag & cleanup (CR-0029); Quantize & partial tests (CR-0030); ASCII policy automation (CR-0031); Scale-out persistence (CR-0037); Auto-heal phase 2 (CR-0038); Exception narrowing phases 1-3 (CR-0039/0040); Stale data auto-refresh (CR-0041); Central exception hook (CR-0042); Log redaction (CR-0043); Daily risk reset counters (CR-0044); Graceful shutdown snapshot (CR-0045); Cross-platform launcher (CR-0032); Metrics retention & compression (CR-0046); Backup snapshot & cleanup (CR-0047); Dynamic correlation threshold (CR-0048); WS symbol limit & debounce (CR-0049); Param set yönetim UI (CR-0050); Trailing stop görselleştirme (CR-0051); Scale-out plan UI (CR-0052); Dependency diagram rev sync (CR-0036); Inventory cross-ref validation script (CR-0053); Hysteresis explicit band refactor + test (CR-0054); Deterministic stale detection path sync (CR-0055); Scale-out reload fix (CR-0056); Test isolation DB strategy (CR-0057); Partial exit fallback persist (CR-0058); Stale test deterministic injection (CR-0059); Partial exit idempotency + duplicate guard (CR-0060); Trailing alias reduction (classic/atr) (CR-0061); Offline auto-heal persistent missing_stop_tp behavior (CR-0062); OrderState FSM Implementation (CR-0063); Schema Versioning v4 (CR-0066); Reconciliation v2 (CR-0067); Lookahead bias prevention (CR-0064); Slippage guard protection (CR-0065); Auto-heal futures & SELL expansion (CR-0068); Guard events persistence (CR-0069); Threshold overrides caching (CR-0070); Config snapshot hash persist (CR-0071); Determinism replay harness (CR-0072); Headless runner & degrade mode (CR-0073).

| CR-0053 | Inventory Cross-Ref Validation | done | 0001 | generate_inventory.py | missing/extra raporu |
| CR-0054 | Hysteresis Band Refactor & Test | done | 0001 | signal_generator.py,test_hysteresis_logic.py | deterministik AL/BEKLE/SAT akışı |
| CR-0055 | Deterministic Stale Detection | done | 0001 | data_fetcher.py | path senkron & union kaldırma |
| CR-0056 | Scale-out Reload Fix | done | 0001 | core.py | scaled_out_json tam parse |
| CR-0057 | Test Isolation DB Strategy | done | 0001 | core.py | PYTEST_CURRENT_TEST izolasyon DB |
| CR-0058 | Partial Exit Fallback Persist | done | 0001 | trailing.py | scale_out JSON fallback |
| CR-0059 | Stale Test Deterministic Injection | done | 0001 | data_fetcher.py | test sembol garantisi |
| CR-0060 | Partial Exit Idempotency Guard | done | 0001 | trailing.py | duplicate scale_out engel |
| CR-0061 | Trailing Alias Reduction | done | 0001 | trailing.py | tekil trailing_update |
| CR-0062 | Offline Auto-Heal Persist Behavior | done | 0001 | core.py | success + missing_stop_tp korunumu |
| CR-0063 | OrderState FSM Implementation | done | 0001 | core.py,state_manager.py,order_state.py | FSM durum geçişleri entegrasyonu |
| CR-0066 | Schema Versioning v4 | done | 0001 | trade_store.py,rollback_schema_v4.py | created_ts,updated_ts,schema_version,rollback |
| CR-0067 | Reconciliation v2 | done | 0001 | core.py,test_reconciliation_v2.py | orderId mapping, partial fill sync, performance |
| CR-0064 | Lookahead Bias Prevention | done | 0001 | utils/lookahead_guard.py,signal_generator.py,tests/test_lookahead_guard.py | hysteresis current bar koruma |
| CR-0065 | Slippage Guard Protection | done | 0001 | utils/slippage_guard.py,execution.py,settings.py,tests/ | BUY/SELL slippage + ABORT/REDUCE policy |
| CR-0068 | Auto-heal Futures & SELL Expansion | done | 0001 | api/binance_api.py,trader/core.py,tests/test_cr0068_auto_heal_expansion.py | futures protection + SELL support |
| CR-0069 | Guard Events Persistence | done | 0001 | utils/guard_events.py,utils/trade_store.py,trader/core.py,trader/guards.py,tests/test_cr0069_guard_events_persistence.py | guard telemetry persistence layer |
| CR-0070 | Threshold Overrides Caching | done | 0001 | utils/threshold_cache.py,signal_generator.py,indicators.py,main.py,tests/test_cr0070_threshold_cache.py | O(1) threshold lookup + override management |
| CR-0071 | Config Snapshot Hash Persist | done | 0001 | utils/config_snapshot.py,trader/core.py,tests/test_cr0071_config_snapshot.py | Deterministic config state tracking + hash-based change detection |
| CR-0072 | Determinism Replay Harness | done | 0001 | utils/replay_manager.py,scripts/cr0072_integration.py,tests/test_cr0072_replay_manager.py | Trade decision replay with session recording, deterministic verification, config snapshot integration |
| CR-0073 | Headless Runner & Degrade Mode | done | 0001 | src/headless_runner.py,tests/test_cr0073_headless_runner.py,run_headless.bat,run_headless.sh | CLI headless operation, signal handling, component health monitoring, graceful shutdown, daemon mode, environment validation, 25 tests PASS |
| CR-0074 | Structured Logging Schema Validation | done | 0001 | src/utils/structured_log.py,tests/test_cr0074_structured_logging.py | Schema validation, performance monitoring, error tracking, JSON output format compliance, 18 tests PASS |
| CR-0075 | Prometheus Metrics Integration | done | 0001 | src/utils/prometheus_metrics.py,src/trader/core.py,tests/test_cr0075_prometheus.py | HTTP metrics endpoint, trade counters, latency histograms, error rates, 15 tests PASS |
| CR-0076 | Unified Risk Escalation System | done | 0001 | src/utils/risk_escalation.py,src/trader/core.py,tests/test_cr0076_integration.py,manual_test_cr0076.py | Progressive risk levels (NORMAL/WARNING/CRITICAL/EMERGENCY), unified kill-switch, automatic risk reduction, 22 tests PASS |
| CR-UI-INTEGRATION | UI System Integration | done | 0001 | src/ui/main_window.py,test_ui_system_status.py,CR-UI-INTEGRATION_COMPLETION_REPORT.md | Complete M4 milestone UI integration: Risk escalation status, Prometheus metrics, system health monitoring, config snapshots management, real-time updates |
| CR-UI-LOCALIZATION | Turkish UI Localization | done | 0001 | src/ui/main_window.py | Comprehensive Turkish translation of UI components: All tabs (Sistem, Yapılandırma Anlık Görüntü, Kapalı, Sinyaller), menu bar (Dosya, Görünüm, Araçlar, Yardım), dialogs, status messages, risk escalation levels (NORMAL/UYARI/KRİTİK/ACİL DURUM), fully functional Turkish interface |
| CR-UI-ASYNC-BACKTEST | UI Async Backtest & Calibration | done | 0001 | src/ui/main_window.py | Backtest/kalibrasyon arka plan thread’lerine taşındı, ilerleme göstergesi ve güvenli buton durum yönetimi eklendi; UI freeze giderildi |
| CR-UI-FREEZE-FIX | UI Freeze & Status Loop Fix | done | 0001 | src/ui/main_window.py | Alt durum çubuğunda sürekli dönme/donma problemi giderildi; reentrancy guard ve QTimer tabanlı güncelleme |
| CR-UI-LINT-UNICODE | UI Unicode Lint Taming | done | 0001 | ruff.toml, src/ui/main_window.py | UI dosyası için RUF001/2/3 per-file ignore; Unicode uyarıları bastırıldı, üretim kodunda davranış değişikliği yok |
| CR-0082 | Incremental UI Table Updates | in-progress | 0001 | src/ui/main_window.py,CR-0082_INCREMENTAL_UI_UPDATE.md | Performance optimization: Incremental diff for UI tables instead of full repaint, helper function implemented, positions/closed/scale-out table optimization |
| CR-0074 | Metrics Prometheus Export | done | 0001 | utils/prometheus_exporter.py,tests/test_cr0074_prometheus.py | Production monitoring, HTTP /metrics endpoint, thread-safe collection, 15+ metric definitions, Grafana dashboard support |
| CR-0075 | Structured Log JSON Schema Validation | done | 0001 | utils/structured_log_validator.py,src/utils/structured_log.py,test_cr0075_simple.py | 30+ event schema definitions, non-blocking validation, graceful degradation, statistics tracking, 6 tests PASS |
| CR-0076 | Risk Kill-Switch Escalation Unification | done | 0001 | src/utils/risk_escalation.py,src/trader/core.py,tests/test_cr0076_integration.py,manual_test_cr0076.py | Unified risk escalation system with progressive levels (NORMAL/WARNING/CRITICAL/EMERGENCY), coordinated kill-switch behavior, automatic risk reduction, structured logging integration, manual override capability |
| CR-0077 | Production Debug Cleanup | done | 0001 | src/trader/core.py | Debug print statements removed from production paths, test environment detection hardened, logger level validation added |
| CR-0078 | Exception Narrowing Final | done | 0001 | src/utils/trade_store.py,src/trader/core.py | Generic 'except Exception' replaced with specific exception types (sqlite3.Error, ValueError, TypeError, ImportError, AttributeError), improved error context preservation |
| CR-0080 | Core Complexity Reduction | done | 0001 | src/trader/core.py | __init__ method refactored from 23 to ~8 complexity via helper methods (_setup_test_environment, _sync_env_settings, _init_subsystems, _startup_maintenance), _recon_auto_heal split into mode-specific handlers |
| CR-0081 | Signal Generator Refactor | done | 0001 | src/signal_generator.py | generate_pair_signal refactored from 31 to ~12 complexity via pipeline pattern (_execute_signal_pipeline, _load_and_validate_data, _compute_indicators, _calculate_scores, _apply_hysteresis, _build_signal_data) |
| CR-UI-FIX | UI System Bug Fix & Enhancement | done | 0001 | src/ui/main_window.py | Comprehensive UI fixes: SignalGenerator integration, bot control menu, backtest tab, enhanced settings interface, theme improvements, QGroupBox import fix - All user-reported UI functionality issues resolved |
| CR-UI-RESPONSIVE | UI Responsive Enhancement | done | 0001 | src/ui/main_window.py | Window size optimization (1400x900), responsive table headers, alternating row colors, center window positioning, missing open_signal_window function implementation |
| CR-UI-ENHANCEMENT | UI Enhancement Phase Complete | done | 0001 | src/ui/main_window.py,src/ui/signal_window.py | Signal window column alignment optimization, comprehensive calibration system with 6 indicator details, enhanced settings tab with tooltips for all parameters, save/reset functionality |
| CR-STRATEGY-ADVANCED | Advanced Profitable Strategy Implementation | in-progress | 0001 | src/backtest/realistic_backtest.py,src/signal_generator.py,src/indicators.py | Multi-indicator confluence (RSI+MACD+Bollinger), dynamic ATR-based position sizing, 3:1 risk/reward ratio, cost optimization, 1.18% expectancy target vs 0.26% current, confluence scoring implemented |
| CR-STRATEGY-CONFLUENCE | Advanced Confluence Strategy Complete | done | 0001 | src/indicators.py,src/signal_generator.py,simple_realistic_test.py,test_confluence_performance.py,test_expectancy_optimization.py | Multi-indicator confluence (RSI+MACD+Bollinger), 75+ selectivity threshold, 1.010% expectancy achieved (vs 1.0% target), 210 trades/month (vs 40 target), 100% confluence rate, high-quality signal generation |
| CR-BACKTEST-COIN-DETAILS | Per-Coin Backtest Results | done | 0001 | src/ui/main_window.py | 10 coin detaylı analizi, confluence skorlama, renk kodlaması, kognitif karmaşıklık azaltma (24→8 helper metodlar), emoji sinyal gösterimi, kalite metrikleri (YUKSEK/ORTA/DUSUK), expected return hesaplama |
| CR-0086 | Clock Skew Guard & Metrics | done | 0001 | src/api/health_check.py,src/utils/prometheus_export.py,tests/test_clock_skew_guard.py | serverTime drift ölçümü, guard ve uyarı, Prometheus gauge/counter (bot_clock_skew_ms_gauge, bot_clock_skew_alerts_total), 2 tests PASS |
| CR-0084 | Rate Limit & Backoff Telemetry | done | 0001 | src/utils/prometheus_export.py,src/api/binance_api.py,tests/test_cr0084_rate_limit_telemetry.py | bot_rate_limit_hits_total{code}, bot_backoff_seconds histogramı, bot_used_weight_gauge; BinanceAPI 418/429 ve X-MBX-USED-WEIGHT enstrümantasyonu; testler PASS |
| CR-0079 | Precision & Filters Compliance | done | 0001 | src/api/binance_api.py,tests/test_cr0079_precision_filters.py | LOT_SIZE/PRICE_FILTER/MIN_NOTIONAL/NOTIONAL uyumu tek `quantize` fonksiyonunda; basit filtre cache (TTL 300s); spot/futures için minNotional altında qty=0 davranışı; 2 unit test PASS |
| CR-0085 | Endpoint Switch Safety | done | 0001 | src/api/binance_api.py,tests/test_cr0085_endpoint_safety.py | Varsayılan testnet; prod için ALLOW_PROD=true zorunluluğu; üç unit test ile block/allow/default doğrulandı |
| CR-0087 | Executions Dedup Persistence | done | 0001 | src/utils/trade_store.py,tests/test_executions_dedup_persistence.py | executions.dedup_key alanı + UNIQUE index (idx_exec_dedup); IntegrityError ile idempotent insert; legacy DB’lere idempotent migration helper |

## 6. A6 Non-Fonksiyonel Gereksinimler (NFR)
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

## 7. A7 Risk Matrisi (Özet)
| Risk | Olasılık | Etki | Durum / Mitigasyon |
|------|----------|------|---------------------|
| Lookahead bias | ~~Orta~~ | ~~Yüksek~~ | ✅ CR-0064 RESOLVED |
| Slippage aşımı | ~~Orta~~ | ~~Yüksek~~ | ✅ CR-0065 RESOLVED |
| Auto-heal kapsamı yetersiz | ~~Orta~~ | ~~Orta~~ | ✅ CR-0068 RESOLVED |
| Guard telemetri persist yok | ~~Orta~~ | ~~Orta~~ | ✅ CR-0069 RESOLVED |
| Determinism harness yok | ~~Orta~~ | ~~Orta~~ | ✅ CR-0072 RESOLVED |
| Scattered risk controls | ~~Yüksek~~ | ~~Yüksek~~ | ✅ CR-0076 RESOLVED |

## 8. A8 Test Stratejisi & Kapsam
Test Tipleri: Unit (hesaplamalar), Integration (trade aç/kapa), Property (risk limit), Replay (determinism), Chaos (WS kesinti), Performance (latency ölçüm), Migration (schema v4).
Kapsam Hedefleri:
- Kritik yol (open_position -> record_open -> place_protection) satır kapsamı ≥ %85
- Risk hesaplama fonksiyonları hata dalı kapsamı ≥ %90
- Guard pipeline negatif senaryo varyantları (halt, daily loss, low volume, correlation) ≥ %95 yürütülmüş.
Kalite Kapıları: Build + Lint PASS, Unit & Integration PASS, determinism hash stabil, migration ileri + geri (dry-run) temiz.
P0 Testnet Öncesi Zorunlu Testler:
- Order idempotency & retry: Duplicate submit dedup-key ile tek kayıt (unit+integration)
- Precision/minNotional uyum: Binance filters’e göre price/qty quantize (parametrik unit)
- Fee model doğrulama: Maker/Taker simülasyonunda beklenen net PnL (unit)
- Rate limit & backoff: 429/418 simülasyonu, exponential backoff ve metrik artışı (integration)
- Clock skew guard: Yapay 1–3 sn drift senaryosu, uyarı ve guard etkinliği (unit)
- Endpoint switch güvenliği: Testnet/Prod yanlış seçimi engelleme (unit)
- OCO fallback: SL veya TP tekil hatasında retry ve graceful degrade (integration)

## 9. A9 Yol Haritası Milestones
- M1 (State Integrity): ✅ COMPLETED - FSM, Schema v4, Reconciliation v2 
- M2 (Risk & Execution): ✅ COMPLETED - CR-0064, CR-0065, CR-0068 ALL DONE
- M3 (Observability & Determinism): ✅ COMPLETED - CR-0070, 0071, 0072 ALL DONE
- M4 (Ops & Governance): ✅ COMPLETED - CR-0073, CR-0074, CR-0075, CR-0076 ALL DONE

## 10. A10 Şema & Tablo Genişlemeleri Planı
| Tablo | Yeni Alan | Tip | CR | Açıklama |
|-------|-----------|-----|----|----------|
| trades | schema_version | INTEGER | 0066 | Satır şema rev referansı |
| trades | created_ts | TEXT | 0066 | ISO açılış zaman damgası |
| trades | updated_ts | TEXT | 0066 | Son güncelleme |
| trades | param_snapshot | TEXT | 0071 | Konfig hash (JSON or hex) |
| guard_events (yeni) | guard, symbol, reason, extra | Çeşitli | 0069 | Guard telemetri |
| executions | exec_type=trailing_update genişleme | TEXT | (mevcut) | Trailing audit |
| executions | dedup_key | TEXT | 0087 | Idempotent execution kayıtları; UNIQUE index `idx_exec_dedup` |

## 11. A11 İzlenebilirlik & Metrik Sözleşmesi
Structured Log Event Temel Alanları: ts, event, symbol?, trade_id?, severity?, payload.
Zorunlu Eventler: app_start, trade_open, trade_close, partial_exit, trailing_update, reconciliation, auto_heal_attempt/success/fail, anomaly_latency/slippage, daily_risk_reset, shutdown_snapshot.
Metrik Örnekleri (Prometheus plan):
- bot_open_latency_ms_bucket / _sum / _count
- bot_entry_slippage_bps_histogram
- bot_guard_block_total{guard="daily_loss"}
- bot_positions_open_gauge
- bot_reconciliation_orphans_total{type="exchange_position"}

## 12. A12 Determinism Hash
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

# 19. Durum
SSoT Revizyon: v2.10
- Test durumu (Windows, Python 3.11): 336 passed, 1 skipped (tüm suite).
- CR-0079 Precision & Filters Compliance korundu: LOT_SIZE/PRICE_FILTER/MIN_NOTIONAL/NOTIONAL uyumu tek `quantize` yolunda; filtre cache (TTL 300s) aktif; `tests/test_cr0079_precision_filters.py` PASS.
- OCO fallback dayanıklılığı: spot OCO başarısızlığında LIMIT TP + STOP_LOSS_LIMIT SL degradasyonu doğrulandı; `tests/test_oco_fallback.py` PASS.
- CR-0085 Endpoint Switch Safety: BinanceAPI init seviyesinde güvenli bayrak zorunluluğu (default=testnet, prod=ALLOW_PROD); `tests/test_cr0085_endpoint_safety.py` PASS.
- CR-0087 Executions Dedup Persistence: executions.dedup_key + UNIQUE index (idx_exec_dedup) kalıcı; mevcut DB’ler için idempotent migration helper; `tests/test_executions_dedup_persistence.py` PASS.
- Not: `tests/test_oco_fallback.py` için geçici null-byte kaynaklı bir toplama hatası gözlendi ve hemen sonrasında temiz çalıştırmada yeniden üretilemedi; yerel dosya yeniden yazımıyla giderildi (kalıcı problem yok, izlemede).
 - ENV izolasyon deterministik override: TRADES_DB_PATH/DATA_PATH explicit env değişkenleri import başında normalize edilip sınıf alanlarına yazılıyor; türetim önceliği net (leak koruması), linter no-op kaldırıldı; `tests/test_env_isolation.py` PASS.

## 13. A13 OrderState FSM (CR-0063)
Amaç: Emir & pozisyon durumlarının deterministik ve izlenebilir hale getirilmesi; reconciliation & determinism hash için kaynak oluşturmak.
Durumlar (state enum önerisi):
- INIT (hazırlık, context oluşturuldu henüz borsa emri yok)
- SUBMITTING (REST order gönderildi, yanıt bekleniyor)
- OPEN_PENDING (exchange accepted; fill bekleniyor / kısmi fill olabilir)
- PARTIAL (kısmi dolum; remaining_size > 0)
- OPEN (tam dolum; remaining_size == position_size, scale-out öncesi tam boy)
- ACTIVE (OPEN veya PARTIAL sonrası koruma emirleri yerleşti ve izleniyor)
- SCALING_OUT (partial exit emri gönderildi / işlendi)
- TRAILING_ADJUST (trailing stop güncelleme işlemi snapshot anı)
- CLOSING (kapatma emri gönderildi, fill bekleniyor)
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

## 14. A14 Order Lifecycle Ayrıntılı Akış
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

## 15. A15 M1 Sprint Plan (State Integrity Milestone)
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

## 16. A16 Kabul Kriterleri (Key CR'ler)
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

## 17. A17 Definition of Done (M1 bağlamı)
- Kod: Tip ipuçları (mümkün olan yerlerde) + ruff lint PASS.
- Test: Yeni fonksiyon / transition için en az 1 happy + 1 negatif senaryo.
- Kapsam: Critical path satır kapsamı >= %85 (rapor eklendi / kaydedildi).
- Dokümantasyon: SSoT ilgili bölüm güncellendi + migration README güncellendi.
- Observability: Slog eventler manuel gözlemlendi (en az 1 örnek).
- Güvenlik: Yeni log satırları API key sızıntısı içermiyor (redaction pipeline değişmedi).
- Geri Alınabilirlik: Migration rollback script çalışır (dry-run kanıt).
- Feature Flag: FSM toggle off iken eski davranış bozulmuyor (regression test).

## 18. A18 Migration Plan (Schema v4 - CR-0066)
Adımlar:
1. Pre-check: trades tablosu kolon listesi -> beklenen v3 şema doğrulanır.
2. Backup: sqlite dosyası snapshot klasörüne kopya (timestamp).
3. Transaction içinde: ALTER TABLE ek kolonlar (schema_version, created_ts, updated_ts) eklenir.
4. Eski satırların schema_version=4 ve created_ts= (varsa mevcut open_time else now) set edilir, updated_ts = created_ts.
5. Index (opsiyonel) created_ts üzerinde.
6. Verification: COUNT(*) tutarlılık, NULL kolon yok.
7. Rollback script: (a) yeni tabloya v3 kolon subseti copy (b) orijinali rename (c) kopyayı eski isimle swap; yalnızca test ortamında.
8. Idempotency: Migration tekrar çalıştırılırsa değişiklik yaratmaz (guard check).

## 19. A19 Observability Genişleme (İleri Plan)
- State transition counter & duration histogram.
- Slippage guard trigger sayacı bot_guard_block_total{guard="slippage"}.
- Lookahead guard metriği bot_guard_block_total{guard="lookahead"}.
- Determinism feed hash per run (app_end event).
- Guard events tablosu (CR-0069) ile sorgulanabilir telemetri.
 - Rate limit ve backoff: bot_rate_limit_hits_total, bot_backoff_seconds_sum/_count
 - Clock skew ölçümü: bot_clock_skew_ms_gauge, bot_clock_skew_alerts_total
 - Precision quantize uyumu: bot_order_quantize_adjust_total
 - Idempotent submit takip: bot_order_submit_dedup_total, bot_order_submit_retries_total

## 20. A20 Açık Sorular & Kararlar (To Clarify)
1. Partial fill politikası: Uzun süren PARTIAL durumunda otomatik küçültme mi iptal mi? (Policy flag önerisi: PARTIAL_STALL_ACTION=reduce|cancel|hold)
2. Slippage guard eşiği: Mutlak bps mi; ATR oranı mı? (Konfig parametre adı: SLIPPAGE_GUARD_BPS_MAX)
3. Determinism hash'te timestamp normalizasyonu nasıl (floor to second / remove)?
4. Reconciliation orphans handling: CLOSED vs CANCELLED hangisi tercih? (Duruma göre mapping tablosu?)
5. Trailing update yoğunluğu: Per fill / per zaman? Rate limit etkisi izlenmeli.

Revizyon Notu: A13–A20 bölümleri eklendi; M1 derin plan + kabul kriterleri + migration planı tanımlandı.

## 21. A21 Son Kapsamlı Analiz & Kritik Eksiklikler (Ağustos 2025)

### 🔍 KOD KALİTESİ ANALİZİ
| Dosya | Sorun | Kompleksite | Aciliyet | Çözüm |
|-------|--------|-------------|----------|-------|
| core.py | __init__ Cognitive Complexity 22 | Yüksek | P1 | Refactor: init_components() helper |
| core.py | get_account_balance Complexity 16 | Yüksek | P1 | Extract balance_resolver |
| core.py | _recon_auto_heal Complexity 25 | Kritik | P1 | Split: _heal_spot, _heal_futures |
| execution.py | Parametreli duplicate logic | Orta | P2 | DRY principle application |
| signal_generator.py | generate_pair_signal Complexity 31 | Kritik | P1 | Extract: _compute_indicators |
| binance_api.py | place_order Complexity 38 | Kritik | P1 | Strategy pattern by order_type |

### 🚨 GÜVENLİK AÇIKLARI
| Risk | Lokasyon | Etki | Mitigasyon |
|------|----------|------|------------|
| Debug Print | core.py:152,157 | Info disclosure | CR-0077: Production debug cleanup |
| API Key Logs | Çeşitli | Credential leak | CR-0043 genişletme |
| Generic Exception | trade_store.py | Error masking | CR-0078: Specific exception types |
| SQL Query Safety | Tüm store ops | Injection risk | CR-0079: Parameterization audit |

### ⚡ KRİTİK TEKNİK BORÇ
1. **UI Tablo Incremental Diff (CR-0082)**: Performans iyileştirme sürüyor
2. **Fonksiyonel Karmaşıklık**: main_window.py’de büyük metotlar (PLR0915) – refactor ihtiyacı
3. **Magic Number’lar**: UI eşikleri/renk kodları sabitlenmeli (consts)
4. **Test Coverage**: Critical path ~%80 → hedef %85+
5. **I/O Bypass**: Kritik yolda senkron DB yazımları – batch/async seçenekleri değerlendirilmeli

### 📊 PERFORMANS & KAYNAK SIZI
- **Memory Leaks**: Potential leak in correlation_cache TTL cleanup
- **CPU Hotspots**: Indicator calculation O(n²) in some paths  
- **I/O Bottlenecks**: Synchronous DB writes in critical path
- **Rate Limiting**: Binance API burst handling inadequate

## 22. A22 ACİL MÜDAHALE PLANI (72 Saat)

### Faz 1: Kritik Güvenlik (24h)
1. **Production Debug Cleanup (CR-0077)**
   - `core.py` debug print'leri kaldır
   - Logger level validation ekle
   - Test environment detection hardening

2. **Exception Narrowing Finalization (CR-0078)**
   - Generic `except Exception:` -> spesifik types
   - Error boundary with context preservation
   - Structured error logging

### Faz 2: Cognitive Complexity Reduction (24h)
1. **Core.py Refactor (CR-0080)**
   - `__init__` -> `init_components()` + `init_state()`
   - `_recon_auto_heal` -> mode-specific handlers
   - `get_account_balance` -> balance resolvers

2. **SignalGenerator Refactor (CR-0081)**
   - `generate_pair_signal` -> pipeline pattern
   - Indicator computation isolation
   - Async-ready signal generation

### Faz 3: FSM & Schema Foundation (24h)
1. **OrderState FSM Skeleton (CR-0063)**
   - Enum definitions + validator
   - Basic state transitions
   - Integration with execution.py

2. **Schema V4 Migration Script (CR-0066)**
   - Backward-compatible column additions
   - Idempotent migration logic
   - Rollback verification

## 23. A23 KALİTE KAPILARI GÜNCELLEMESİ

### Zorunlu Pre-Commit Checks
- [ ] Ruff lint PASS (complexity hedef ≤15; UI dosyası için RUF001/2/3 per-file ignore geçerli)
- [ ] No debug prints in production code paths
- [ ] API key redaction test PASS
- [ ] Critical path test coverage ≥85%
- [ ] FSM transition validation (post CR-0063)

### Production Readiness Checklist  
- [ ] Exception types specific (no generic Exception catch)
- [ ] Structured logging events complete
- [ ] Database migration tested (forward + rollback)
- [ ] Rate limiting with exponential backoff
- [ ] Memory leak prevention (cache TTL + cleanup)

## 24. A24 SÜREKLI İZLEME METRİKLERİ

### Teknik Sağlık Göstergeleri
- Code Complexity Score: Target ≤12 avg (current ~15–16 UI hariç)
- Test Coverage: Target ≥85% critical path (current ~80–82%)
- Security Score: 0 API key leaks + 0 SQL injection vectors
- Performance: p95 signal generation ≤100ms

### İş Süreklilik Göstergeleri  
- Trade Execution Success Rate ≥99.5%
- Order State Integrity: 0 orphaned orders
- Reconciliation Success Rate: 100% within 5s
- Guard Block Accuracy: ≤2% false positives

## 25. A25 YÜKSEK ETKİLİ CR'LER (Yeni Öncelik Sıralaması)

| CR-ID | Ad | P | Blok Eden | Süre | Etki |
|-------|----|----|-----------|------|------|
| CR-0077 | Production Debug Cleanup | P0 | Production safety | 4h | Security |
| CR-0078 | Exception Narrowing Final | P0 | Error visibility | 6h | Debugging |
| CR-0080 | Core Complexity Reduction | P0 | Maintainability | 8h | Code Quality |
| CR-0081 | Signal Generator Refactor | P1 | Performance | 12h | Speed |
| CR-0063 | OrderState FSM | P1 | Determinism | 16h | Reliability |
| CR-0066 | Schema Versioning | P1 | Data Safety | 8h | Migration |
| CR-0079 | Precision & Filters Compliance | P0 | Exchange safety | 6h | Correctness |
| CR-0082 | Incremental UI Table Updates | P1 | Perf | 8h | UX |
| CR-0083 | Idempotent Order Submit & Retry | P0 | Duplicate/Retry safety | 8h | Reliability |
| CR-0084 | Rate Limit & Backoff Telemetry | P0 | Stability | 6h | Observability |
| CR-0085 | Endpoint Switch Safety (Testnet/Prod) | P0 | Operational safety | 4h | Safety |

## 26. A26 ACİL GELİŞTİRME PLANI (26 Ağustos 2025)

### 🚨 FAZ 1: KRİTİK GÜVENLİK (0-8 saat)
**CR-0077: Production Debug Cleanup**
- **Hedef**: core.py debug print'lerini kaldırma
- **Lokasyon**: `src/trader/core.py:152,157`
- **Plan**: 
  1. Debug print'leri tespit et ve kaldır
  2. Logger level validation ekle
  3. Test environment detection harden et
- **Kabul**: Production ortamında bilgi sızıntısı 0

**CR-0078: Exception Narrowing Final**
- **Hedef**: Generic `except Exception:` -> spesifik types
- **Lokasyon**: `src/utils/trade_store.py`, core error handlers
- **Plan**:
  1. Her generic except'i kategorize et
  2. Spesifik exception types ekle
  3. Error boundary + context preservation
- **Kabul**: Generic exception handling <%10

### ⚡ FAZ 2: COGNITIVE COMPLEXITY REDUCTION (8-16 saat)
**CR-0080: Core Complexity Refactor**
- **Hedef**: core.py karmaşıklık <15 skoru
- **Problem**: `__init__` (22), `_recon_auto_heal` (25), `get_account_balance` (16)
- **Plan**:
  1. `__init__` -> `init_components()` + `init_state()`
  2. `_recon_auto_heal` -> `_heal_spot()` + `_heal_futures()`  
  3. `get_account_balance` -> balance resolver pattern
- **Kabul**: Tüm fonksiyonlar complexity ≤15

**CR-0081: Signal Generator Refactor**
- **Hedef**: generate_pair_signal complexity <15
- **Problem**: Mevcut 31 complexity skoru
- **Plan**:
  1. Pipeline pattern implementation
  2. Indicator computation isolation  
  3. Async-ready signal generation
- **Kabul**: Latency ≤50ms, complexity ≤15

### 🏗️ FAZ 3: FSM & SCHEMA FOUNDATION (16-24 saat)
**CR-0063: OrderState FSM Skeleton**
- **Hedef**: Deterministik durum geçişleri
- **Plan**:
  1. Enum definitions + validator
  2. Basic state transitions (INIT->SUBMITTING->OPEN_PENDING->OPEN->ACTIVE)
  3. Integration hooks in execution.py
- **Kabul**: FSM validator test PASS

**CR-0066: Schema V4 Migration**
- **Hedef**: Güvenli migration + rollback
- **Plan**:
  1. Backward-compatible column additions
  2. Idempotent migration logic
  3. Rollback verification script
- **Kabul**: Migration forward+backward PASS

### 📊 IMPLEMENTATION TIMELINE
```
Saat 0-2:   CR-0077 Debug cleanup başla
Saat 2-4:   CR-0078 Exception narrowing
Saat 4-6:   Test + validation
Saat 6-8:   CR-0080 Core refactor başla
Saat 8-12:  Core __init__ + _recon_auto_heal split
Saat 12-14: CR-0081 Signal generator refactor
Saat 14-16: Complexity validation + tests
Saat 16-18: CR-0063 FSM skeleton
Saat 18-20: CR-0066 Migration script
Saat 20-22: Integration testing
Saat 22-24: Documentation + SSoT update
```

### 🎯 SUCCESS METRICS
- [ ] Production debug prints: 0
- [ ] Generic exceptions: <%10 of total
- [ ] Average complexity score: ≤12
- [ ] FSM validator: PASS
- [ ] Migration safety: Forward+backward PASS
- [ ] Test coverage: ≥85% critical path
- [ ] Performance regression: ≤5%

### 🔄 ROLLBACK PLAN
Her faz için git commit + branch strategy:
- `feat/cr-0077-debug-cleanup`
- `feat/cr-0078-exception-narrowing`
- `feat/cr-0080-core-refactor`
- `feat/cr-0081-signal-refactor`
- `feat/cr-0063-fsm-skeleton`
- `feat/cr-0066-schema-v4`

SSoT Revizyon: v1.97 (UI-ASYNC-BACKTEST TAMAMLANDI - Backtest ve kalibrasyon süreçleri arka plan iş parçacıklarına taşındı; ilerleme göstergeleri ve güvenli buton durumları eklendi; bot çalışırken alt durum çubuğunda döngü/donma problemi giderildi. main_window.py için yapısal onarımlar (import/indent düzeltmeleri, snapshot başlık senkronizasyonu, exception kapanımı), linter yapılandırmasıyla UI Unicode uyarıları bastırıldı (per-file ignore), offscreen Qt test akışı yeşil.)

# 27. A27 Son Yapılan Kritik Düzeltmeler (26 Ağustos 2025)

## CR-UI-BACKTEST-CONFLUENCE-FIX: Backtest Confluence Entegrasyonu

## CR-FEE-SANITY: Ücret Sağlığı ve Net PnL Yardımcıları (04 Eylül 2025)
- Ne: Ücret/slippage oranları için güvenli aralık kelepçesi [0.0, 1.0] (yüzde); maker/taker ayrı oran desteği; yuvarlak tur maliyeti ve net PnL hesap yardımcıları.
- Dosyalar: `config/settings.py` (get_commission_rates, round_trip_cost_pct, sanitize), `src/utils/helpers.py` (Costs, calculate_net_pnl), `tests/test_fee_sanity.py`, `tests/test_settings_helpers.py`.
- Davranış: Varsayılan komisyon 0.04%/side, slippage 0.02%/side; negatif/aşırı değerler import sırasında kelepçelenir; net PnL, maliyetler düşülerek hesaplanır.
- Doğrulama: Tüm yeni testler PASS; tam suite 319 PASS, 1 SKIPPED.

## CR-0079 Precision & Filters Compliance (04 Eylül 2025)
- Ne: Tekil quantize yolu genişletildi: LOT_SIZE (stepSize/minQty), PRICE_FILTER (tickSize/minPrice), MIN_NOTIONAL/NOTIONAL kontrolleri eklendi; spot ve futures için notional altı siparişler qty=0 ile güvenli şekilde iptal edilir.
- Dosyalar: `src/api/binance_api.py` (filters cache + minNotional kontrolü), `tests/test_cr0079_precision_filters.py` (2 test)
- Davranış: price veriliyken qty*price < minNotional ise miktar 0 döner; fiyat ve miktar aşağı yönlü tick/step’e yuvarlanır; basit TTL cache ile exchange info çağrıları azaltılır.
- Doğrulama: Yeni 2 test PASS; tüm suite 312 PASS, 1 SKIPPED.
**Problem**: UI backtest tablosunda tüm coinler için aynı değerler görünüyordu (Win Rate 30%, Total Trade 6, PnL 0.26%, Score 0%) 
**Kök Neden**: `_process_single_coin` metodu sadece `signal == 'AL'` veya `signal == 'SAT'` olan coinler için confluence skorunu alıyordu, BEKLE sinyalleri ignore ediliyordu
**Çözüm**: 
```python
# ESKI (Hatalı)
if signal_data and signal_data.get('signal') in ['AL', 'SAT']:
    confluence = signal_data.get('confluence', {})

# YENİ (Doğru) 
if signal_data:
    confluence = signal_data.get('confluence', {})
    # signal_data varsa confluence skorunu her zaman al
```
**Sonuç**: BTCUSDT 63.3%, ETHUSDT 72.0% gibi farklı confluence skorları, dinamik win rate/trade frequency/PnL değerleri

## CR-MATICUSDT-DATA-FIX: Parite Tutarsızlığı Çözümü  
**Problem**: Sinyaller 3 parite, Backtest 10 parite, terminal'de MATICUSDT veri çekemiyor ama backtest sonucu var
**Kök Neden**: MATICUSDT top_150_pairs.json'da yoktu, SignalGenerator None döndürüyor, UI default değerlerle sahte sonuç üretiyordu
**Çözüm**:
1. MATICUSDT'yi top_150_pairs.json'a eklendi (151. sıra)  
2. Backtest dinamik parite listesi: `test_symbols = all_pairs[:10]`
3. Veri eksik pariteler için görsel uyarı: `⚠️ {symbol} (Veri Yok)` ve `0% (Hata?)`

## CR-UI-DYNAMIC-BACKTEST: Dinamik Parite Yönetimi
**Değişiklik**: Backtest sabit 10 parite yerine top_150_pairs.json'dan dinamik ilk 10 parite kullanıyor
**Fayda**: Sinyaller vs Backtest tutarlılığı, gerçek top pariteler test ediliyor

## CR-0065 FLAKINESS MITIGATION (03 Eylül 2025)
- Ne: Global autouse pytest fixture ile SlippageGuard singleton state reset (test öncesi/sonrası).
- Neden: CR-0065 testleri full suite çalıştırıldığında nadir ABORT/REDUCE politika karışıklığı; cross-test state leakage.
- Teknik: tests/conftest.py içine reset_slippage_guard() çağıran autouse fixture eklendi; yerel test dosyası fixture'ı temizlendi. Doğrulama: tests/test_cr0065_integration.py tüm testler PASS (7/7), regresyon yok.

## CR-0076 Risk Escalation Stabilizasyonu (03 Eylül 2025)
- Ne: RiskEscalation geliştirmeleri ve test stabilizasyonu: (1) _check_manual_halt sadece OS temp klasöründeki bayrakları dikkate alacak şekilde izole edildi, (2) _get_recent_performance_stats 0 dönerse fallback (recent_open_latencies / recent_entry_slippage_bps) hesaplaması, (3) init_risk_escalation mock idempotency düzeltildi.
- Neden: tests/test_cr0076_risk_escalation.py içinde çoklu hata gözlendi; sistem deterministik ve test-izole çalışmalı.
- Doğrulama: İlgili hedef testler PASS (23/23). Geniş suite koşusunda CR-0065 ve slog çekirdek akışları da PASS.

## CR-0083 Idempotent Order Submit — Kısmi Entegrasyon (04 Eylül 2025)
- Ne: Idempotent submit için TTL tabanlı dedup helper eklendi ve `open_position` akışına entegre edildi.
- Dosyalar: `src/utils/order_dedup.py` (yeni), `src/trader/execution.py` (dedup kontrol + slog), `config/settings.py` (ORDER_DEDUP_TTL_SEC, USE_TESTNET/ALLOW_PROD teyit)
- Davranış: Aynı ana parametrelerle (symbol|side|mode|price|qty) kısa sürede tekrarlanan açılış denemeleri `order_submit_dedup{action=skip}` olarak loglanır ve atlanır.
- Not: Geniş entegrasyon (retry/backoff sayaçları ve DB unique guard) bir sonraki adımda.

## CR-0086 Clock Skew Guard & Metrics (04 Eylül 2025)
- Ne: Exchange serverTime ile lokal zaman arasındaki fark ölçümü, uyarı ve guard; Prometheus metrikleri eklendi.
- Dosyalar: `src/api/health_check.py` (check_clock_skew, run_full_check entegrasyonu), `src/utils/prometheus_export.py` (bot_clock_skew_ms_gauge, bot_clock_skew_alerts_total, helper fonksiyonlar), `tests/test_clock_skew_guard.py` (2 unit test)
- Davranış: |skew| ≤ 500ms sağlıklı; eşik üstünde uyarı ve guard blok (konfigürasyonla yönetilebilir). Metrikler export edilir.
- Doğrulama: Tüm testler PASS (yeni 2 test dahil). SSoT revizyonu güncellendi (v1.99).

## CR-0084 Rate Limit & Backoff Telemetry (04 Eylül 2025)
- Ne: Rate limit ve backoff telemetrisi; 429/418 hit sayaçları, exponential backoff gözlemi, kullanılan ağırlık gauge.
- Dosyalar: `src/utils/prometheus_export.py` (bot_rate_limit_hits_total{code}, bot_backoff_seconds, bot_used_weight_gauge), `src/api/binance_api.py` (418/429 handling + X-MBX-USED-WEIGHT header ölçümü), `tests/test_cr0084_rate_limit_telemetry.py` (2 test).
- Davranış: 418/429 durumlarında sayaç artar, backoff saniyeleri histogramda gözlenir, header’dan kullanılan weight gauge set edilir.
- Doğrulama: Tüm yeni testler PASS; full test suite yeşil. SSoT revizyonu v2.00’a yükseltildi.

## CR-0087 Executions Dedup Persistence (05 Eylül 2025)
- Ne: executions tablosuna `dedup_key` TEXT alanı ve UNIQUE index `idx_exec_dedup` eklendi; `record_execution` ve `record_scale_out` deterministik `dedup_key` üretip `sqlite3.IntegrityError` ile duplicate insert’i bastırıyor; mevcut DB’ler için idempotent migration helper yazıldı.
- Dosyalar: `src/utils/trade_store.py` (şema + migration helper + insert mantığı), `tests/test_executions_dedup_persistence.py` (2 test).
- Davranış: Aynı execution tekrar eklenmek istendiğinde tek satır korunur; scale-out için aynı r seviyesinde (r_mult) ve aynı anahtar ile tekrar insert engellenir; önceki in-memory TTL submit dedup (CR-0083) ile birlikte kalıcı idempotency sağlar.
- Doğrulama: Testler PASS; tam suite 322 PASS, 1 SKIPPED.

## CR-ENV-ISOLATION-STABILIZE (05 Eylül 2025)
- Ne: ENV tabanlı yol izolasyonu deterministik hale getirildi; TRADES_DB_PATH öncelik kuralları netleştirildi ve sızıntılara karşı korundu.
- Kurallar (ENV_ISOLATION=on|auto):
  - DATA_PATH explicit ve TRADES_DB_PATH değilse → TRADES_DB_PATH = DATA_PATH/<env>/trades.db
  - DATA_PATH explicit ve TRADES_DB_PATH explicit ise → TRADES_DB_PATH DATA_PATH altında ise korunur; değilse DATA_PATH/<env>/trades.db türetilir; özel dosya adı kullanılıyorsa korunur.
  - DATA_PATH explicit değil ve TRADES_DB_PATH explicit ise → override aynen korunur.
- Dosyalar: `config/settings.py`, `tests/test_env_isolation.py`.
- Doğrulama: Modül testleri 2/2 PASS; tam suite 326 PASS, 1 SKIPPED.

## CR-ENV-ISOLATION-PERMUTATIONS-TESTS (05 Eylül 2025)
- Ne: ENV izolasyon öncelik kuralları için ek permütasyon testleri yazıldı (yalnızca DATA_PATH; yalnızca TRADES_DB_PATH; her ikisi explicit - custom filename; her ikisi explicit - leak; hiçbiri explicit).
- Dosyalar: `tests/test_env_isolation_permutations.py` (yeni).
- Davranış: TRADES_DB_PATH deterministik olarak türetildi/korundu; log/metrics/halt yolları env-skoped dizinlere ayarlandı.
- Doğrulama: 5 yeni test PASS; tam suite 327 PASS, 1 SKIPPED.

## CR-ENV-ISOLATION-PERMUTATIONS-EXT (05 Eylül 2025)
- Ne: Env izolasyon permütasyonları PROD ve OFFLINE modlarını da kapsayacak şekilde genişletildi; `fresh import` tekniği ile deterministik ayar yükleme ve `normpath+normcase` ile platform bağımsız karşılaştırmalar.
- Dosyalar: `tests/test_env_isolation_permutations.py` (genişletildi).
- Davranış: 9 test (testnet/prod/offline dahil); `DAILY_HALT_FLAG_PATH` ve `METRICS_FILE_DIR` suffix kontrolleri eklendi.
- Doğrulama: Tüm 9 test PASS; tam suite 336 PASS, 1 SKIPPED.

## Docs: README ENV İzolasyonu (05 Eylül 2025)
- Ne: README’ye “ENV_ISOLATION ve Yol Önceliği (DB/Log/Backup/Halt/Metrics)” bölümü eklendi.
- İçerik: on/off/auto modları, testnet/prod/offline env adı, DATA_PATH/TRADES_DB_PATH öncelik kuralları, izole dizinler ve hızlı örnekler.
- Neden: Operasyonel kullanımda yanlış yol/çakışma risklerini önlemek ve konfigürasyon davranışını netleştirmek.
- Doğrulama: Mevcut permütasyon testleri davranışı kapsıyor; belge yalnızca özet/örnek sağlar.

## CR-0083 Submit Retry/Backoff Orkestrasyonu (04 Eylül 2025)
- Ne: Execution katmanında ana emir yerleştirme akışı etrafına jitter’lı üstel geri çekilme (retry/backoff) eklendi; gözlemlenebilirlik metriği ve yapılandırma ile desteklendi.
- Dosyalar: `src/trader/execution.py` (yeni `_place_with_retry` helper; `open_position` entegrasyonu), `src/utils/prometheus_export.py` (yeni sayaç: `bot_order_submit_retries_total{reason}` ve `record_order_submit_retry()`), `config/settings.py` (RETRY_MAX_ATTEMPTS, RETRY_BACKOFF_BASE_SEC, RETRY_BACKOFF_MULT varsayılanları kullanılıyor).
- Davranış: Denemeler arasında `sleep = base * mult^(attempt-1)` ve 0.8–1.2 jitter; alt/üst sınır [0.05s, 10.0s]. Her uyku süresi `observe_backoff_seconds` ile ölçümlenir; her tekrar denemesi için yapılandırılmış `order_submit_retry` log olayı ve Prometheus sayacı artar. TTL tabanlı dedup guard (CR-0083 önceki parçası) ile çakışmadan güvenli çalışır.
- Not: API katmanı 418/429 ve genel hata backoff’unu sürdürür; execution-layer orkestrasyon üst seviye güvenlik katmanıdır. Özel retry testleri A29.4 kapsamında eklenecek.

## CR-0083-TESTS Submit Retry/Backoff Unit Tests (05 Eylül 2025)
- Ne: `_place_with_retry` için hedeflenmiş iki pytest testi eklendi: (1) geçici başarısızlıklar sonrası başarı; (2) maksimum deneme sonrası vazgeçme. Jitter deterministik hale getirildi ve `time.sleep` no-op patch’lendi.
- Dosyalar: `tests/test_cr0083_retry_backoff.py`
- Davranış: `place_main_and_protection` monkeypatch ile kontrol edildi; `record_order_submit_retry` ve `observe_backoff_seconds` metrikleri ve `order_submit_retry` slog olayı sayısal olarak doğrulandı.
- Doğrulama: Testler PASS; tam suite 336 PASS, 1 SKIPPED.

# 28. A28 Yapılacaklar (SSoT içinde tek liste)

Kurallar (orijinal belgeden devralınmıştır):
- Her madde tamamlanınca (✓) ile işaretlenir ve DONE’a taşınır; kısa özet kayıt defterine (A27) eklenir.
- Öncelik etiketleri: [P1]=kritik güvenilirlik/risk, [P2]=önemli değer, [P3]=iyileştirme.

## 28.1 Stabilite & Güvenilirlik
- [P1] PriceStream kapatılırken thread join başarısızsa zorla kes (timeout logging)
- [P2] Ana zamanlayıcı hatalarında merkezi exception hook ve görsel uyarı (status çubuğu)
- [P2] Graceful shutdown: kapanışta açık trade flush + son durum snapshot
- [P1] Backtest kalibrasyon uyumsuzluğu: UI winrate vs run_calibration trade_stats fark analizi (ADX filtresi, persisted thresholds doğrulama, self-check log)
- [P1] Açık pozisyon/emir reconciliation (bakiye & open orders -> local state diff)
- [P1] Günlük risk reset otomasyonu (yeni gün tespiti + halt flag temizleme + rapor)
- [P1] Anomaly (latency/slippage) tetiklenince otomatik risk düşürme veya durdurma
- [P1] Kısmi fill kalan miktar için kalan emri yeniden ayarlama
- [P1] Restart sonrası trailing & partial state tam persist (scaled_out + stop history)

## 28.2 Test Kapsamı
- [P2] update_positions PnL hesaplama testleri (LONG/SHORT yön farkı + edge cases)
- [P2] _maybe_refresh_ws_symbols restart tetik testi (symbol fark senaryoları, debounce)
- [P2] ATR trailing stop test (güncellenen stop DB'ye yansıyor mu?) — mevcut log testlerine ek DB doğrulama
- [P3] Calibration pipeline smoke test (önerilen eşikler üretimi)
- [P3] Partial fill deterministik test (simulate partial -> position & executions doğrulama)
- [P3] OCO order offline stub testi (spot OFFLINE_MODE)

## 28.3 Performans Optimizasyonu
- [P1] update_positions incremental diff (tam tablo yeniden çizim azaltma) — CR-0082 ile ilişkili
- [P2] Price update batching (GUI repaint frekansı sınırlama; ~250ms throttle)
- [P2] DB index denetimi (open_trades, executions üzerinde composite index öner)
- [P3] Lazy signal satır clone yerine model/proxy mimarisi
- [P2] Korelasyon hesap throttling (saniyede max N hesap)
- [P2] Order book snapshot cache (slippage ölçümü için)

## 28.4 Özellik Geliştirme (UI/Genel)
- [P1] Toplam Unrealized PnL (USDT) göstergesi: Stil + test iyileştirme
- [P1] Global exposure metriği (sembol/sektör/yön dağılımı)
- [P2] Parametre set yönetim UI (listele, etkinleştir, sil, açıklama)
- [P2] Trailing stop görseli (pozisyon satırında SL kolon renklendirme değişimi)
- [P2] Scale-out planı tanımlama (UI: hedef seviyeler + miktarlar)
- [P3] Optimization candidates CSV/JSON export UI butonu
- [P3] Gelişmiş sinyal filtresi (ör: signal:AL score>70 vol>1e7)
- [P2] Çoklu sembol hızlı arama (positions & signals için incremental search kutusu)
- [P2] Pozisyon detay yan paneli (ATR, partial history, trailing log)
- [P2] Gerçek zamanlı latency & slippage mini chart (Metrics sekmesi içi)
- [P3] Drag&drop kolon sıralama + layout preset kaydetme
- [P3] Global tema switcher (Işık/Koyu + renk körlüğü dostu palet)
- [P3] Parametre set diff görüntüleyici (iki param_set JSON farkı)
- [P3] Trade detay modal (execution listesi, scale-out zaman çizelgesi)
- [P3] Inline edit: stop_loss/take_profit hücreden güncelleme
- [P3] Çoklu kapanış seçimi (checkbox ile toplu)
- [P3] Kısayollar (seç/kaput/yenile)
- [P3] Dinamik row highlight (fiyat/stop değişimi)
- [P3] PnL heatmap; gün içi performans timeline (equity curve incremental)
- [P3] İşlem açılışı öncesi onay popup (config kontrollü)
- [P3] Genişletilebilir log konsolu (filtre: risk|order|ws|metric)
- [P3] Sinyal kart görünümü (tablo alternatifi)
- [P3] i18n extractor script (UI)
- [P3] UI render profiler overlay
- [P3] Snapshot export (ekran görüntüsü + JSON state paketi)
- [P3] Refresh interval slider (fiyat/sinyal)
- [P3] Kullanıcı tercihleri persist (tema, kolonlar)
- [P3] Guard trigger counter badge (toolbar)
- [P3] Anlık korelasyon matrisi mini dialog
- [P3] ATR band overlay (chart)
- [P3] Quick trade panel (manuel giriş)
- [P3] Tooltip optimizasyonu (gecikme, HTML)
- [P3] Responsive kompakt mod
- [P3] Offline mode banner
- [P3] Execution listesi canlı akış (fade-in)
- [P3] Partial exit progress bar
- [P3] Trailing stop hareket animasyonu
- [P3] Komut paleti (Ctrl+K)
- [P3] Otomatik güncelleme uyarısı (yeni sürüm)
- [P3] Masaüstü bildirimleri (aç/kapa)
- [P3] WebSocket durum ikonu (renk+tooltip)
- [P3] Sürükle-bırak param_set.json yükleme
- [P3] Çift tık ile grafik açma (chart stub)
- [P3] Sinyal skor dağılım histogramı; PnL violin/box plot
- [P3] Ölçeklenebilir font (erişilebilirlik); High contrast modu
- [P3] UI state diff viewer; Thread/Task monitor paneli
- [P3] DB health göstergesi (boyut, vacuum önerisi)
- [P3] Session süre sayacı; Risk özet hesap (expected loss, R-multiple)
- [P3] Esnek sütun gizleme/gösterme; Scroll konumu persist; Kompakt mod toggle

## 28.5 İzlenebilirlik & Gözlemleme
- [P1] Metrics sekmesi: latency, slippage, trailing, risk guard tetik sayısı (record_metric hazır, UI pending)
- [P2] Yapısal JSON logging opsiyonu (config ile aç/kapat)
- [P2] Websocket hata sayacı + otomatik reset
- [P3] Runtime config snapshot (per X saat)

## 28.6 Konfigürasyon & Parametreler
- [P2] Debounce süresi (şu an 2s) Settings üzerinden yönetilebilir
- [P2] WS sembol üst limiti (40) konfigürasyona taşınacak
- [P2] ATR trailing parametreleri (multiplier, min move) UI kontrolü
- [P3] Outlier threshold UI kontrolü

## 28.7 Kullanıcı Deneyimi (genel)
- [P2] Pozisyon tabloda kolon sıralama & kalıcı genişlik persist (session restore)
- [P2] Dark mode stil revizyonu (kontrast, renk körlüğü)
- [P3] Dil seçimi (TR/EN toggle) — metin sabitleri için kaynak dosya

## 28.8 Risk & Trade Mantığı
- [P1] Position sizing formülü gözden geçirme (volatilite ayarlı risk/ATR)
- [P2] Korelasyon cache penceresi (en çok korele açık listesi)
- [P2] Trailing + partial exit parametre optimizasyonu (backtest entegrasyonu)
- [P3] Zaman bazlı kademeli scale-out (bar sayısına göre)
- [P1] Gün içi kademeli risk azaltma (drawdown bantlarına göre risk_percent düşür)
- [P2] Dynamic correlation threshold (yüksek volatilitede gevşet)
- [P2] Volatiliteye göre max eşzamanlı pozisyon adaptasyonu

## 28.9 Veri Kalitesi
- [P1] DataFetcher stale veri tespiti (timestamp drift) ve uyarı
- [P2] Retry/backoff telemetry (kaç deneme, toplam gecikme)
- [P3] Local data integrity check (CSV kolon sayısı, NaN oranı) raporu

## 28.10 Deployment / Operasyon
- [P2] requirements.txt hash lock (pip-tools veya uv pip compile)
- [P2] Basit paketleme script (pyinstaller veya zip release)
- [P3] CI pipeline (lint + tests) — GitHub Actions workflow

## 28.11 Dokümantasyon
- [P2] README güncelle: yeni risk özellikleri, trailing, correlation, canlı fiyat
- [P2] Geliştirici rehberi: yeni gösterge ekleme adımları
- [P3] Kullanıcı kılavuzu (GUI sekmeleri açıklama)
- [P3] Test kapsamı rehberi (risk, partial, trailing, correlation senaryoları)

## 28.12 Refactor / Temizlik
- [P2] main_window.py bölümlendirme (positions, calibration, signals alt modüllere ayırma)
- [P2] Signal table clone logic -> model/view pattern adaptasyonu
- [P3] PriceStreamManager test doubles + arayüz soyutlama

## 28.13 Güvenlik / Dayanıklılık
- [P1] API key sızıntı kontrolü (dotenv mevcut; runtime log satır taraması eklenecek)
- [P2] Rate limit hit dedektörü ve otomatik uyku
- [P3] Basit circuit breaker (ardışık WS hatası > N)

Not: Tek SSoT politikası gereği yapılacaklar burada tutulur; A5.1 BACKLOG ile uyumlu olarak güncellenir. Harici txt dosyaları kullanılmaz.

## 29. A29 Testnet Öncesi Hazırlık Planı (Zorunlu Kalemler)

Amaç: Gerçek borsa bağlantısı (testnet) öncesi minimum güvenlik ve tutarlılık kapıları tamamlanmış, ölçümlenebilir ve idempotent bir bot sağlamak.

### 29.1 Fonksiyonel Zorunlular (P0)
- Idempotent order submit & retry (CR-0083): submit_dedup_key, retry policy (jittered backoff), duplicate insert guard.
- Precision & filters compliance (CR-0079): exchange filters cache (tickSize, stepSize, minQty, minNotional) + quantize helper tek kaynak.
- Endpoint switch safety (CR-0085): Default=testnet, env bayrağı olmadan prod yasak; UI/CLI uyarı ve onay.
- OCO/koruma fallback: SL/TP tekil başarısızlıkta retry → degrade single leg + slog event.
- Fee model doğrulama: Maker/Taker ücretleri config’ten doğrulanabilir ve test override ile simule.

### 29.2 Dayanıklılık & Zaman Senkronizasyonu (P0)
- Rate limit & backoff telemetry (CR-0084): 429/418 handle, exponential backoff, Prometheus sayaçları.
- Clock skew guard: NTP/time drift ölçümü (local vs exchange serverTime), |skew| ≤ 500 ms; uyarı üstünde guard blok.
- Offline/Sim/Test izolasyonu: DB dosya adı ve data dizinleri env’e göre ayrışır; veri çakışması engeli.

### 29.3 Observability (P0)
- Strct log event’leri: order_submit, order_ack, retry, cancel, protection_set, anomaly_slippage, rate_limit_backoff, clock_skew_alert.
- Prometheus metrikleri: bot_order_submit_dedup_total, bot_order_submit_retries_total, bot_rate_limit_hits_total, bot_backoff_seconds_sum/_count, bot_clock_skew_ms_gauge.

### 29.4 Test Planı (P0)
- Unit: quantize helper (price/qty), fee net PnL, clock skew guard logic, dedup key generator determinism.
- Integration: idempotent submit (same dedup key → 1 execution), 429 backoff akışı, OCO fallback tek bacak, endpoint switch güvenliği.
- Replay/Determinism: aynı input → aynı determinism hash; retry/backoff eventleri hash feed’e dahil edilmez.

### 29.5 Kabul Kriterleri
- Tüm P0 testleri PASS, coverage critical path ≥%85.
- Prod endpoint’e geçişte explicit bayrak ve onay olmadan başlatılamaz.
- Rate limit ve clock skew olayları slog + metriklerde gözlemlenir.
- Duplicate order kayıtları (executions) için unique constraint ihlali 0.

### 29.6 Rollout Adımları
1) CR-0079, CR-0083, CR-0084, CR-0085 tamamla → merge.
2) Dry-run headless (OFFLINE_MODE=true) → tüm P0 testleri + /metrics sağlık.
3) Testnet key ile ReadOnly health check (sadece GET endpoints) → rate limit ölçümü.
4) Sandbox placing (minNotional’a uygun küçük qty) → cancel flow ve protection fallback doğrulaması.
5) Gözlem: Grafana panelinde metrikler stabil, slog eventleri düzenli.
