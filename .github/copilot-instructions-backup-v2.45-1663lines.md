# CORE AGENT PRINCIPLES & OPERATIONAL GUIDELINES

## Primary Directives
1. **TURKISH COMMUNICATION**: Always respond in Turkish language
2. **SSoT AUTHORITY**: This document is Single Source of Truth - any conflicting content is invalid
3. **CR WORKFLOW**: Every change requires CR → approval → patch process
4. **TEST-FIRST**: No implementation without acceptance criteria + tests
5. **BACKWARD COMPATIBILITY**: Breaking changes require ADR (Architecture Decision Record)
6. **CLEAN WORKSPACE**: Close open editors/terminals when work is complete
7. **REAL DATA ONLY**: Use actual data - never mock/dummy/simulation data. Replace any existing mock implementations with real data
8. **ZERO ERROR TOLERANCE**: Never ignore simple errors - they compound and can cause system collapse
9. **STRICT DISCIPLINE**: Always follow file organization, schema connections, module logic, coding standards, testing, documentation, version control, code review, and CR processes

## Operational Behavior
- Proactively identify and fix errors immediately
- Maintain code quality and architectural integrity
- Document all changes in SSoT format
- Preserve existing functionality while enhancing
- Use comprehensive testing strategies
- Follow established patterns and conventions
- Maintain traceability through CR system

## Quality Gates
- All code changes must have corresponding tests
- Real-time data integration over database fallbacks where applicable
- Consistent error handling and logging
- Performance optimization without breaking changes
- Security considerations (no API key leaks)
- UI/UX consistency and responsiveness
# PROJE YAPISI VE ANA BİLEŞENLER

## A1. Proje Özeti
**Amaç**: Binance (spot/futures) üzerinde risk kontrollü, modüler, izlenebilir otomatik trade botu.
**Kapsam**: Sinyal üretimi, risk yönetimi & boyutlama, emir yerleştirme & koruma, partial & trailing çıkış, metrik & anomaly tespiti, kullanıcı arayüzü.
**Hariç Tutulanlar**: HFT mikro yapı analizi, Deep Learning model eğitimi.
**Paydaşlar**: Trader, geliştirici, test ekibi, operasyon.
**Kısıtlar**: Güvenlik (API key sızıntı yok), tutarlılık, offline mod desteği.

## A2. Terimler Sözlüğü
- **R-Multiple**: (Fiyat - Entry) / (Entry - Stop) - Risk bazlı getiri ölçümü
- **Koruma Emirleri**: Stop Loss + Take Profit (spot OCO / futures STOP+TP)
- **Partial Exit**: Kademeli kar realizasyonu
- **Adaptive Risk**: ATR yüzdesine göre pozisyon boyutu ölçeklendirme
- **HTF Filter**: Higher Timeframe trend filtresi (4h EMA200)
- **Meta-Router**: 4 uzman stratejiyi koordine eden ensemble sistem
- **Edge Health**: Trading edge'lerinin sağlık durumu (HOT/WARM/COLD)

## A3. Modül Kataloğu (Registry)

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
| MOD-API-PRICESTREAM | PriceStream | src/api/price_stream.py | WebSocket stream & reconnect | websocket-client | active |
| MOD-SIGNAL-GEN | SignalGenerator | src/signal_generator.py | Sinyal + hysteresis | MOD-DATA-FETCHER, MOD-INDICATORS | active |
| MOD-UI-MAIN | MainWindow | src/ui/main_window.py | PyQt5 ana UI + Bot Control Center | PyQt5, MOD-CORE-TRADER | active |
| MOD-A31-META-ROUTER | MetaRouter | src/strategy/meta_router.py | 4 specialist coordination, MWU weight learning | MOD-SIGNAL-GEN | active |
| MOD-A32-EDGE-HEALTH | EdgeHealthMonitor | src/utils/edge_health.py | Trading edge health monitoring | MOD-UTILS-STORE | active |
| MOD-AUTOMATION-SCHEDULER | BotScheduler | src/utils/scheduler.py | Task scheduler, market hours automation | datetime, threading | active |

*Tam modül listesi için: [Detaylı Modül Kataloğu](.github/docs/module-registry.md)*

## A4. API & Şema Sözleşmeleri (Özet)

**Positions Şeması**:
```
{
  side, entry_price, position_size, remaining_size, 
  stop_loss, take_profit, atr, trade_id, 
  scaled_out[(r,qty)], model_version, order_state, 
  created_ts, updated_ts
}
```

**Koruma Emirleri**:
- Spot: oco_resp{ids:[...]}
- Futures: futures_protection{sl_id,tp_id}

**Ana Fonksiyonlar**:
- `FN-EXEC-open_position(symbol, ctx) -> bool`
- `FN-EXEC-close_position(symbol) -> bool`

*Detaylı API sözleşmeleri için: [API Şema Referansı](.github/docs/api-contracts.md)*

## DURUM ÖZET (v2.45)
- **Test Durumu**: 677 tests collected, 663 PASS + 1 SKIPPED (%98+ başarı oranı)
- **Kritik Sorunlar Tespit Edildi**: 13 failed tests - partial exit DB operasyonları, FSM geçişleri, structured logging
- **A35 MODULAR DEBUG PLAN ACTIVE**: Systematic debugging gerekli - partial exit DB context manager hatası yaygın
- **SSoT Modüler Organizasyon COMPLETED**: Ana dokümantasyon 8 ayrı dosyaya organize edildi
- **Bot Control Center COMPLETED**: All phases operational
- **A30-A32 Strategy Implementations COMPLETED**: HTF Filter, Meta-Router, Edge Hardening systems
- **ANALİZ GEREKLİ**: Partial exit DB operation failures - 'NoneType' object context manager protocol

# DETAYLI DOKÜMANTASYON REFERANSLARİ

Bu ana dokümantasyon, aşağıdaki detaylı belgelerle desteklenmektedir:

## Görev Yönetimi
- [Görev Panosu ve Yol Haritası](.github/docs/task-management.md)
- [Proje Milestone'ları](.github/docs/task-management.md#a9-yol-haritası-milestones)

## Teknik Gereksinimler
- [NFR ve Risk Matrisi](.github/docs/technical-requirements.md)
- [Test Stratejisi](.github/docs/technical-requirements.md#a8-test-stratejisi--kapsam)

## Şema ve Veri Yönetimi
- [Şema Planları ve Migration](.github/docs/schema-management.md)
- [Observability ve Metrikler](.github/docs/schema-management.md#a11-i̇zlenebilirlik--metrik-sözleşmesi)

## Strateji İmplementasyonları
- [A30-A32 Strateji Detayları](.github/docs/strategy-implementations.md)
- [Meta-Router ve Edge Hardening](.github/docs/strategy-implementations.md#a31-rbp-ls-v140--meta-router--ensemble-system-por)

## İleri Özellikler
- [Bot Control Center](.github/docs/advanced-features.md#a33-bot-kontrol-merkezi̇-geli̇şti̇rme-plani)
- [A35 Deep Logic Debugging](.github/docs/advanced-features.md#a35-deep-logic-debugging--production-readiness-assessment-por)

## Change Request Kayıtları
- [Major CR Tablosu](.github/docs/cr-records.md)
- [CR-0053 to CR-0087 Detayları](.github/docs/cr-records.md#cr-0053---cr-0087-detaylı-kayıtlar)

---
**SSoT Versiyon**: v2.45
**Son Güncelleme**: Test failure analysis - 13 kritik test failure tespit edildi, systematic debugging needed
**Dokümantasyon Yapısı**: Modüler, referans tabanlı, sürdürülebilir
**ANALİZ DURUMU**: Partial exit DB operations context manager protocol failures widespread - immediate investigation required

## Major CR Kayıtları

| CR-ID | Açıklama | Durum | Versiyon | Dosyalar | Notlar |
|-------|----------|-------|----------|----------|--------|
| CR-TRADESTORE-API-METHOD-MISMATCH-FIX | TradeStore API Method Mismatch Fix | done | 0001 | src/ui/main_window.py | Performance dashboard'taki "API Yok" hatası çözüldü. UI fonksiyonları yanlış TradeStore metodlarını çağırıyordu: `get_closed_trades()` → `closed_trades(limit=N)`, `get_open_positions()` → `open_trades()`. DataFrame tabanlı kod List tabanlı kod ile değiştirildi, tüm data calculation fonksiyonları güncellendi |
| CR-EMERGENCY-STOP-METHOD-NAME-FIX | Emergency Stop Method Name Fix | done | 0001 | src/ui/main_window.py | Emergency stop butonundaki "emergency_shutdown" method not found hatası düzeltildi. `trader.emergency_shutdown()` yerine mevcut `trader.close_all_positions()` metoduna geçildi, fallback olarak `trader.stop()` eklendi |
| CR-BOT-CONTROL-PERFORMANCE-DASHBOARD-FIX | Bot Control Performance Dashboard Fix | done | 0001 | src/ui/main_window.py | Performans özeti bölümündeki grid layout overlap sorunları düzeltildi (label ve değerler aynı column'a eklenmişti), değerler column 3'e taşındı. Tüm data calculation fonksiyonlarında defensive programming: trader/trade_store None kontrolü, DataFrame column kontrolü, type-safe conversion, enhanced exception handling. `_calculate_daily_pnl`, `_count_active_positions`, `_get_last_trade_time`, `_check_api_status`, `_calculate_max_drawdown` güvenli hale getirildi |
| CR-BOT-STATUS-SYNC-FIX | Bot Status Display Synchronization Fix | done | 0001 | src/ui/main_window.py | Bot kontrol tabında "Detaylı Durum" butonu ile bot başlatma durumu arasındaki tutarsızlık çözüldü. `_show_bot_status` `self._bot_core` kontrol ediyordu ama bot başlatma `self.trader` kullanıyordu. `_start_bot()` artık `self._bot_core = self.trader` ile sync ediyor, `_stop_bot()` `self._bot_core = None` ile temizliyor, `__init__()` da doğru initialize ediyor |
| CR-SCALP-MODE-SETTINGS-INTEGRATION | Scalp Mode Settings Class Integration | done | 0001 | config/settings.py, src/ui/main_window.py | Scalp mode ayarları Settings class'ına taşındı, duplicate tanımlar kaldırıldı, "Settings has no attribute SCALP_RISK_PERCENT" hatası çözüldü, trading mode switching operational |
| CR-EMERGENCY-STOP-DUAL-IMPLEMENTATION | Emergency Stop Button Dual Implementation | done | 0001 | src/ui/main_window.py | ACİL KAPAT butonu hem ana sayfa pozisyonlar bölümünde hem de Bot Control tabında eklendi, emergency_stop_btn_control instance oluşturuldu, comprehensive emergency shutdown functionality |
| CR-0085 | Endpoint Switch Safety | done | 0001 | src/api/binance_api.py,tests/test_cr0085_endpoint_safety.py | Varsayılan testnet; prod için ALLOW_PROD=true zorunluluğu; üç unit test ile block/allow/default doğrulandı |
| CR-API-V2-MIGRATION | Binance API V2 Endpoint Migration | done | 0001 | src/api/binance_api.py | python-binance deprecated /fapi/v1/positionRisk endpoint migration to /fapi/v2/positionRisk. Monkey patch implementation with _patch_client_for_v2_endpoints(), automatic V2 switching + V1 fallback, manual _signed_request_v2() for modern Binance Futures API v2 support |
| CR-0087 | Executions Dedup Persistence | done | 0001 | src/utils/trade_store.py,tests/test_executions_dedup_persistence.py | executions.dedup_key alanı + UNIQUE index (idx_exec_dedup); IntegrityError ile idempotent insert; legacy DB'lere idempotent migration helper |
| CR-UI-BOT-CONTROL-RISK-SPINBOX-FIX | UI Bot Control Risk Spinbox Fix | done | 0001 | src/ui/main_window.py | MainWindow'da duplicate risk_spinbox tanımları düzeltildi - Bot Control tab'ında risk ayarları grubu eklendi, "MainWindow' object has no attribute 'risk_spinbox'" hatası çözüldü. Deprecated unified interface kodları temizlendi, sadece _build_ui() metodu kullanılıyor |
| CR-TRADESTORE-API-METHOD-MISMATCH-FIX | TradeStore API Method Mismatch Fix | done | 0001 | src/ui/main_window.py | Performance dashboard'taki "API Yok" hatası çözüldü. UI fonksiyonları yanlış TradeStore metodlarını çağırıyordu: `get_closed_trades()` → `closed_trades(limit=N)`, `get_open_positions()` → `open_trades()`. DataFrame tabanlı kod List tabanlı kod ile değiştirildi, tüm data calculation fonksiyonları güncellendi |
| CR-EMERGENCY-STOP-METHOD-NAME-FIX | Emergency Stop Method Name Fix | done | 0001 | src/ui/main_window.py | Emergency stop butonundaki "emergency_shutdown" method not found hatası düzeltildi. `trader.emergency_shutdown()` yerine mevcut `trader.close_all_positions()` metoduna geçildi, fallback olarak `trader.stop()` eklendi |
| CR-BOT-CONTROL-PERFORMANCE-DASHBOARD-FIX | Bot Control Performance Dashboard Fix | done | 0001 | src/ui/main_window.py | Performans özeti bölümündeki grid layout overlap sorunları düzeltildi (label ve değerler aynı column'a eklenmişti), değerler column 3'e taşındı. Tüm data calculation fonksiyonlarında defensive programming: trader/trade_store None kontrolü, DataFrame column kontrolü, type-safe conversion, enhanced exception handling. `_calculate_daily_pnl`, `_count_active_positions`, `_get_last_trade_time`, `_check_api_status`, `_calculate_max_drawdown` güvenli hale getirildi |
| CR-BOT-STATUS-SYNC-FIX | Bot Status Display Synchronization Fix | done | 0001 | src/ui/main_window.py | Bot kontrol tabında "Detaylı Durum" butonu ile bot başlatma durumu arasındaki tutarsızlık çözüldü. `_show_bot_status` `self._bot_core` kontrol ediyordu ama bot başlatma `self.trader` kullanıyordu. `_start_bot()` artık `self._bot_core = self.trader` ile sync ediyor, `_stop_bot()` `self._bot_core = None` ile temizliyor, `__init__()` da doğru initialize ediyor |
| CR-SCALP-MODE-SETTINGS-INTEGRATION | Scalp Mode Settings Class Integration | done | 0001 | config/settings.py, src/ui/main_window.py | Scalp mode ayarları Settings class'ına taşındı, duplicate tanımlar kaldırıldı, "Settings has no attribute SCALP_RISK_PERCENT" hatası çözüldü, trading mode switching operational |
| CR-EMERGENCY-STOP-DUAL-IMPLEMENTATION | Emergency Stop Button Dual Implementation | done | 0001 | src/ui/main_window.py | ACİL KAPAT butonu hem ana sayfa pozisyonlar bölümünde hem de Bot Control tabında eklendi, emergency_stop_btn_control instance oluşturuldu, comprehensive emergency shutdown functionality |
| CR-A31-META-ROUTER | A31 Meta-Router & Ensemble System | done | 0001 | src/strategy/ (specialist_interface.py, meta_router.py, trend_pb_bo.py, range_mr.py, vol_breakout.py, xsect_momentum.py, __init__.py), test_a31_integration.py | 4 uzman stratejisi (S1: Trend PB/BO, S2: Range MR, S3: Vol Breakout, S4: XSect Momentum), MWU ağırlık öğrenme, gating sistem, ensemble sinyal üretimi, specialist interface pattern, registry yönetimi, integration test PASS |
| CR-A32-EDGE-HARDENING | A32 Edge Hardening System | done | 0001 | src/utils/ (edge_health.py, cost_calculator.py, microstructure.py), tests/test_a32_integration.py | Edge Health Monitor (Wilson CI + 200 trade window), 4× Cost-of-Edge calculator, OBI/AFR mikroyapı filtreleri, comprehensive testing framework, 9/9 integration tests PASS |
| CR-ADVANCED-ML-PIPELINE | Advanced ML Pipeline Framework | done | 0001 | src/ml/advanced_ml_pipeline.py, tests/test_advanced_ml_pipeline.py | Next-generation ML system: AdvancedFeatureEngineer (50+ features: multi-timeframe technical, volatility regimes, cross-asset correlation, microstructure OBI/AFR, calendar seasonality), AdvancedMLPipeline (XGBoost/LightGBM/RF ensemble models, direction/volatility/returns prediction, real-time inference <100ms), sophisticated feature caching, model drift detection, A/B testing framework, 874 lines production-ready implementation |
| CR-A32-PROD-INTEGRATION | A32 Production Integration | done | 0001 | src/trader/core.py, src/signal_generator.py, config/settings.py | A32 Edge Hardening sistemini production trade flow'una entegre edildi: pre-trade 4× cost kuralı, edge health monitoring, OBI/AFR microstructure filtreleri, SignalGenerator pipeline integration, Trader Core initialization, comprehensive configuration parameters |

## 9. A9 Yol Haritası Milestones
- M1 (State Integrity): ✅ COMPLETED - FSM, Schema v4, Reconciliation v2
- M2 (Risk & Execution): ✅ COMPLETED - CR-0064, CR-0065, CR-0068 ALL DONE
- M3 (Observability & Determinism): ✅ COMPLETED - CR-0070, 0071, 0072 ALL DONE
- M4 (Ops & Governance): ✅ COMPLETED - CR-0073, CR-0074, CR-0075, CR-0076 ALL DONE
- A30 (RBP-LS v1.3.1 Real Implementation): ✅ COMPLETED - HTF Filter, Time Stop, Spread Guard ALL DONE
- A31 (Meta-Router & Ensemble): ✅ COMPLETED - 4 Specialist strategies, MWU learning, gating logic, registry system ALL DONE
- A32 (Edge Hardening): ✅ COMPLETED - Edge Health Monitor, 4× cost rule, OBI/AFR filters, Production Integration ALL DONE
- **A33 (Bot Control Center Enhancement): ✅ ALL PHASES COMPLETED** - Foundation ✅, Real-time Telemetry ✅, Advanced Settings ✅, Performance Dashboard ✅, **Automation Pipeline ✅**; comprehensive bot control center with full automation capabilities including scheduler engine, daily scheduling, market hours automation, maintenance windows, auto risk reduction, active task management - ALL PHASES COMPLETED
- **SMART EXECUTION STRATEGIES: ✅ COMPLETED** - TWAPExecutor, VWAPExecutor, SmartRouter optimization, execution planning, market impact integration, cost estimation framework, 450+ lines production-ready implementation, 5 unit tests PASS
- **ADVANCED ML PIPELINE: ✅ COMPLETED** - AdvancedFeatureEngineer (50+ features), AdvancedMLPipeline (XGBoost/LightGBM/RF ensemble models), real-time inference <100ms, model drift detection, A/B testing framework, 874 lines production-ready implementation
- **A35 (Deep Logic Debugging & Production Readiness): 🔄 IN-PROGRESS** - Comprehensive logic error detection, real-world scenario testing, error injection framework, state consistency validation, E2E flow analysis, production hardening - critical for deployment readiness despite 100% test coverage

### A30 Implementation Details (PoR COMPLETED):
- HTF Filter stabilizasyonu: Settings import cache sorunu çözüldi; HTF testleri artık tam suite'de kararlı çalışıyor; deterministik bias hesaplama ile tutarlılık sağlandı.
- Time Stop: TIME_STOP_ENABLED/TIME_STOP_BARS parametreli pozisyon yaş limiti; check_time_stop metodu ile 24 bar sonrası otomatik kapanış tetikleme.
- Spread Guard: SPREAD_GUARD_ENABLED/SPREAD_MAX_BPS parametreli spread koruması; get_ticker ile real-time bid/ask spread hesaplaması; 10 BPS eşik aşımında graceful fallback.
- Backward Compatibility: Tüm A30 özellikleri default kapalı/konservatif; mevcut davranışta değişiklik yok; production-ready implementation.

## Major CR Kayıtları

| CR-ID | Açıklama | Durum | Versiyon | Dosyalar | Notlar |
|-------|----------|-------|----------|----------|--------|
| CR-0085 | Endpoint Switch Safety | done | 0001 | src/api/binance_api.py,tests/test_cr0085_endpoint_safety.py | Varsayılan testnet; prod için ALLOW_PROD=true zorunluluğu; üç unit test ile block/allow/default doğrulandı |
| CR-0087 | Executions Dedup Persistence | done | 0001 | src/utils/trade_store.py,tests/test_executions_dedup_persistence.py | executions.dedup_key alanı + UNIQUE index (idx_exec_dedup); IntegrityError ile idempotent insert; legacy DB'lere idempotent migration helper |
| CR-BOT-CONTROL-FOUNDATION | Bot Control Center Foundation | done | 0001 | src/ui/main_window.py | Modern bot control center UI tab creation, menu cleanup, basic controls (start/stop/status), risk settings (risk%, max positions), real-time status display, UI integration complete |
| CR-BOT-CONTROL-TELEMETRY | Real-time Telemetry Integration | done | 0001 | src/ui/main_window.py | Real-time bot metrics (uptime, PnL, success rate, active positions), telemetry threading, performance monitoring, risk escalation status display, 2-second update cycle |
| CR-BOT-CONTROL-SETTINGS | Advanced Settings Management | done | 0001 | src/ui/main_window.py, config/settings.py | Strategy switcher (A30/A31/A32), Meta-Router toggle, Edge Health settings, HTF/Time Stop/Spread Guard/Kelly Fraction toggles, hot-reload configuration, advanced risk parameters, comprehensive settings UI |
| CR-BOT-CONTROL-DASHBOARD | Performance Dashboard | done | 0001 | src/ui/main_window.py | Performance mini dashboard: günlük PnL, aktif pozisyon sayısı, risk seviyesi, son işlem zamanı, API durumu, max drawdown real-time metrics, advanced telemetry integration, color-coded status indicators |
| CR-BOT-CONTROL-AUTOMATION | Scheduler & Automation | done | 0001 | src/utils/scheduler.py, src/ui/main_window.py | BotScheduler engine, time-based bot scheduling, market hours automation, maintenance windows, auto risk reduction, scheduled tasks, daily schedule management, UI automation panel, comprehensive task management |
| CR-A31-META-ROUTER | A31 Meta-Router & Ensemble System | done | 0001 | src/strategy/ (specialist_interface.py, meta_router.py, trend_pb_bo.py, range_mr.py, vol_breakout.py, xsect_momentum.py, __init__.py), test_a31_integration.py | 4 uzman stratejisi (S1: Trend PB/BO, S2: Range MR, S3: Vol Breakout, S4: XSect Momentum), MWU ağırlık öğrenme, gating sistem, ensemble sinyal üretimi, specialist interface pattern, registry yönetimi, integration test PASS |
| CR-A32-EDGE-HARDENING | A32 Edge Hardening System | done | 0001 | src/utils/ (edge_health.py, cost_calculator.py, microstructure.py), tests/test_a32_integration.py | Edge Health Monitor (Wilson CI + 200 trade window), 4× Cost-of-Edge calculator, OBI/AFR mikroyapı filtreleri, comprehensive testing framework, 9/9 integration tests PASS |
| CR-A32-PROD-INTEGRATION | A32 Production Integration | done | 0001 | src/trader/core.py, src/signal_generator.py, config/settings.py | A32 Edge Hardening sistemini production trade flow'una entegre edildi: pre-trade 4× cost kuralı, edge health monitoring, OBI/AFR microstructure filtreleri, SignalGenerator pipeline integration, Trader Core initialization, comprehensive configuration parameters |
| CR-ADVANCED-ML-PIPELINE | Advanced ML Pipeline Framework | done | 0001 | src/ml/advanced_ml_pipeline.py, tests/test_advanced_ml_pipeline.py | Next-generation ML system: AdvancedFeatureEngineer (50+ features: multi-timeframe technical, volatility regimes, cross-asset correlation, microstructure OBI/AFR, calendar seasonality), AdvancedMLPipeline (XGBoost/LightGBM/RF ensemble models, direction/volatility/returns prediction, real-time inference <100ms), sophisticated feature caching, model drift detection, A/B testing framework, 874 lines production-ready implementation |
| A30-HTF-FILTER | HTF EMA(200, 4h) Filter Implementation | done | 0001 | src/signal_generator.py,config/settings.py,tests/test_htf_filter.py | HTF EMA(200) trend bias filtresi, deterministik hesaplama, Settings cache fix, test stabilizasyonu |
| A30-TIME-STOP | Position Time Stop (24 bars) | done | 0001 | src/trader/core.py,config/settings.py | Pozisyon yaş limiti kontrolü, TIME_STOP_ENABLED/TIME_STOP_BARS parametreleri, structured logging |
| A30-SPREAD-GUARD | Spread Guard Protection (10 BPS) | done | 0001 | src/trader/execution.py,src/api/binance_api.py,config/settings.py | Bid/ask spread koruması, SPREAD_GUARD_ENABLED/SPREAD_MAX_BPS, graceful fallback, ticker desteği |
```text
Agent Sistem Promptu — Çatışmasız Proje Akışı (Kripto Trade Botu)
SSoT (Single Source of Truth) DÖKÜMANI
```

# 0. Çekirdek İlke & Kullanım

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

# 3. A3 Modül Kataloğu (Özet)
**Ana Modüller**: 40+ modül active durumda (Core Trader, Execution, Risk Manager, Signal Generator, UI, API, Strategy, ML)

*Detaylı modül registrisi için: [Modül Kataloğu](.github/docs/module-registry.md)*

**Kritik Modüller**:
- **MOD-CORE-TRADER**: Trade orchestrator & yaşam döngüsü
- **MOD-EXEC**: Emir açma/kapama & koruma emirleri  
- **MOD-RISK**: Risk yönetimi & pozisyon boyutlama
- **MOD-SIGNAL-GEN**: Sinyal üretimi & hysteresis
- **MOD-UI-MAIN**: Ana PyQt5 kullanıcı arayüzü
- **MOD-API-BINANCE**: Binance API integration

# 4. A4 API & Şema Sözleşmeleri (Özet)
**Positions**: `{side, entry_price, position_size, remaining_size, stop_loss, take_profit, atr, trade_id, scaled_out, model_version, order_state, created_ts, updated_ts}`

**Koruma Emirleri**: 
- Spot: `oco_resp{ids:[...]}`
- Futures: `futures_protection{sl_id,tp_id}`

**Ana Fonksiyonlar**:
- `FN-EXEC-open_position(symbol, ctx) -> bool`
- `FN-EXEC-close_position(symbol) -> bool`

*Detaylı API sözleşmeleri için: [API Şema Referansı](.github/docs/schema-management.md)*

# 5. A5 Görev Panosu
Öncelik: P1 kritik, P2 önemli, P3 iyileştirme.
## 5.1 BACKLOG (Post-A32)
P1: **Deep Logic Debugging & Production Readiness Assessment (A35)** — Kapsamlı mantık hata ayıklama, real-world scenario testing, error injection framework, state consistency validation, E2E flow analysis, production hardening; %100 test coverage'a rağmen gerçek kullanım mantık hatalarını tespit ve düzeltme
P1: Advanced Strategy Enhancements (Post A32)
P1: Bot Control Center Advanced Features — Real-time telemetry, advanced settings, scheduler
P1: Multi-asset portfolio correlation matrix ve risk-adjusted position sizing
P1: ✅ COMPLETED: Smart Routing + TWAP/VWAP Strategies — Advanced execution algorithms using market impact models, time-weighted and volume-weighted execution plans, smart routing optimization, cost estimation, 5 unit tests PASS
P1: Liquidity-aware order execution (depth analysis + smart routing)
P1: Dynamic volatility regime detection ve strategy adaptation
P1: Cross-exchange arbitrage detection (Binance vs diğer CEX'ler)
P1: Advanced backtesting: Monte Carlo simulation, walk-forward analysis
P1: Real-time sentiment analysis integration (Twitter/Reddit/News feeds)
P1: Machine learning feature engineering pipeline (technical + fundamental)
P1: Advanced risk management: Value-at-Risk (VaR), Expected Shortfall (ES)
P1: Performance attribution analysis (strategy vs market vs alpha)
P1: Options trading integration (covered calls, protective puts)
P2: AI-powered market regime classification
P2: Advanced order types: TWAP, VWAP, Iceberg orders
P2: Inter-market spread trading (spot vs futures basis trading)
P2: Cryptocurrency-specific indicators (on-chain metrics, funding rates)
P2: Real-time order book analysis ve market microstructure insights
P2: Smart contract interaction for DeFi yield farming
P2: Cross-chain bridge monitoring ve arbitrage opportunities
P2: Social trading platform integration (copy trading functionality)
P2: Advanced visualization: 3D market analysis, heat maps
P2: Mobile app development for remote monitoring
P3: Plugin architecture for custom strategy development
P3: API marketplace for third-party indicators
P3: Cloud-based backtesting infrastructure
P3: Integration with professional trading platforms (TradingView, Bloomberg)
--- LEGACY ITEMS (Lower Priority) ---
P2: PriceStream kapatılırken thread join başarısızsa zorla kes (timeout logging)
P2: Ana zamanlayıcı hatalarında merkezi exception hook ve görsel uyarı (status çubuğu)
P2: Graceful shutdown: uygulama kapanışında açık trade kayıt flush + son durum snapshot
## 5.2 IN-PROGRESS
P1: Cross-exchange arbitrage detection — Multi-CEX price difference analysis
## 5.3 REVIEW
(boş)
## 5.4 DONE (Seçili)
✅ **TradeStore API Method Mismatch Fix:** Performance dashboard'taki "API Yok" hatası çözüldü - UI fonksiyonları yanlış TradeStore metodlarını çağırıyordu (`get_closed_trades` → `closed_trades`, `get_open_positions` → `open_trades`), DataFrame tabanlı kod List tabanlı kod ile değiştirildi, tüm data calculation fonksiyonları güncellendi
✅ **Emergency Stop Method Name Fix:** Emergency stop butonundaki "emergency_shutdown" method not found hatası düzeltildi - `trader.emergency_shutdown()` yerine mevcut `trader.close_all_positions()` metoduna geçildi, fallback olarak `trader.stop()` eklendi
✅ **Bot Control Performance Dashboard Fix:** Bot kontrol tabındaki performans özeti bölümündeki data ve layout sorunları düzeltildi; grid layout overlap çözüldü, tüm data calculation fonksiyonlarında defensive programming uygulandı
✅ **Bot Status Display Synchronization Fix:** Bot kontrol tabındaki "Detaylı Durum" butonu ile bot başlatma durumu arasındaki tutarsızlık çözüldü; `_show_bot_status` ve `_start_bot/_stop_bot` fonksiyonları artık `_bot_core` referansı üzerinden senkronize çalışıyor
✅ **Emergency Stop Button Dual Implementation:** ACİL KAPAT butonu hem ana sayfa pozisyonlar bölümünde hem de Bot Control tabında eklendi, comprehensive emergency shutdown functionality
✅ **Trading Mode Switching Operational:** Scalp Mode (5m timeframe, 2000ms update) ve Normal Mode (15m timeframe, 5000ms update) arasında real-time geçiş
Modular Trader refactor; Protection orders; Weighted PnL reload; Reconciliation diff (CR-0003); Daily risk reset (CR-0004/0044); Anomaly risk reduction (CR-0007); Metrics trimming (CR-0008); Adaptive sizing tests (CR-0009/0010); Trailing persistence (CR-0016); Unrealized PnL metrics + UI (CR-0014/0021); Secret scan (CR-0026); ASCII UI refactor (CR-0023); Inventory & gap analysis; Structured logging events (CR-0028); ATR trailing flag & cleanup (CR-0029); Quantize & partial tests (CR-0030); ASCII policy automation (CR-0031); Scale-out persistence (CR-0037); Auto-heal phase 2 (CR-0038); Exception narrowing phases 1-3 (CR-0039/0040); Stale data auto-refresh (CR-0041); Central exception hook (CR-0042); Log redaction (CR-0043); Daily risk reset counters (CR-0044); Graceful shutdown snapshot (CR-0045); Cross-platform launcher (CR-0032); Metrics retention & compression (CR-0046); Backup snapshot & cleanup (CR-0047); Dynamic correlation threshold (CR-0048); WS symbol limit & debounce (CR-0049); Param set yönetim UI (CR-0050); Trailing stop görselleştirme (CR-0051); Scale-out plan UI (CR-0052); Dependency diagram rev sync (CR-0036); Inventory cross-ref validation script (CR-0053); Hysteresis explicit band refactor + test (CR-0054); Deterministic stale detection path sync (CR-0055); Scale-out reload fix (CR-0056); Test isolation DB strategy (CR-0057); Partial exit fallback persist (CR-0058); Stale test deterministic injection (CR-0059); Partial exit idempotency + duplicate guard (CR-0060); Trailing alias reduction (classic/atr) (CR-0061); Offline auto-heal persistent missing_stop_tp behavior (CR-0062); OrderState FSM Implementation (CR-0063); Schema Versioning v4 (CR-0066); Reconciliation v2 (CR-0067); Lookahead bias prevention (CR-0064); Slippage guard protection (CR-0065); Auto-heal futures & SELL expansion (CR-0068); Guard events persistence (CR-0069); Threshold overrides caching (CR-0070); Config snapshot hash persist (CR-0071); Determinism replay harness (CR-0072); Headless runner & degrade mode (CR-0073); UI Dashboard Phase 1 (CR-UI-DASHBOARD-PHASE1); Meta-Router control panel with real-time monitoring complete; Portfolio Analysis System (CR-PORTFOLIO-ANALYSIS): Multi-asset correlation analysis, risk metrics (VaR, Expected Shortfall), Wilson confidence intervals, UI integration COMPLETED; Machine Learning Pipeline (CR-ML-PIPELINE): SimpleFeatureEngineer framework, RuleBasedRegimeDetector, feature engineering (price returns, volume ratios, volatility, basic technicals), market regime detection (trending/ranging/squeeze), 12 unit tests PASS; Dynamic Volatility Regime Detection (CR-VOLATILITY-REGIME): 6 regime types (TRENDING_UP/DOWN, RANGING, VOLATILE, SQUEEZE, BREAKOUT), sophisticated market analysis (trend strength, volatility percentiles, range efficiency, autocorrelation, volume alignment), Wilson confidence intervals, real-time regime classification, 34 tests PASS (27 unit + 7 integration); Advanced Market Impact Models (CR-ADVANCED-IMPACT): 5 sophisticated impact models (Linear, Square-root Almgren-Chriss, Kyle's lambda, Power-law, Concave), Implementation shortfall calculation, optimal participation rate optimization, Wilson confidence intervals, risk penalty assessment, model calibration system, singleton architecture, 7 integration tests PASS; Smart Execution Strategies (CR-SMART-EXECUTION): TWAPExecutor ve VWAPExecutor advanced execution algorithms, SmartRouter optimization engine, execution plan generation, market impact integration, cost estimation framework; 450+ lines production-ready implementation, 5 unit tests PASS; optimal slice calculation, volume profiling, execution timing, strategy selection logic tamamen operasyonel; Bot Control Center Foundation (CR-BOT-CONTROL-FOUNDATION): Modern bot control center 🤖 Bot Kontrol tabı olarak UI'ya entegre edildi; menü çubuğundan bot kontrol menüsü kaldırıldı; temel kontroller (başlat/durdur/durum), risk ayarları (risk%, max positions), real-time durum göstergeleri, modern UI tasarım ile tüm bot yönetimi tek merkezde toplandı.

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
| CR-UI-DASHBOARD-PHASE1 | UI Dashboard Meta-Router Panel | done | 0001 | src/ui/meta_router_panel.py,src/ui/main_window.py,test_meta_router_panel.py,UI_DASHBOARD_PHASE1_COMPLETION_REPORT.md | Complete Meta-Router control panel: 4 specialist weight bars, gating status display, ensemble decision monitoring, real-time updates (500ms), enable/disable toggle, color-coded indicators, main UI tab integration, standalone/integrated testing passed |
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
- A30 (RBP-LS v1.3.1 Real Implementation): ✅ COMPLETED - HTF Filter, Time Stop, Spread Guard ALL DONE
- A31 (Meta-Router & Ensemble): ✅ COMPLETED - 4 Specialist strategies, MWU learning, gating logic, registry system ALL DONE
- A32 (Edge Hardening): ✅ COMPLETED - Edge Health Monitor, 4× cost rule, OBI/AFR filters, Production Integration ALL DONE

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
SSoT Revizyon: v2.28
- Test durumu (Windows, Python 3.11): 500+ passed, 1 skipped (tüm suite stabilize).
- Portfolio Analysis System COMPLETED: Multi-asset correlation analysis, risk metrics (VaR, Expected Shortfall), Wilson confidence intervals, diversification ratios tam implementasyon tamamlandı.
- UI Integration COMPLETED: Portfolio Analysis Panel ana UI'ya entegre edildi; Genel Bakış, Risk Analizi tabları, real-time metrics, pozisyon tablosu, korelasyon analizi, optimizasyon önerileri tam operasyonel.
- Performance Monitor Panel timestamp fix: src/ui/performance_monitor_panel.py'de float timestamp formatı sorunu çözüldü; isinstance() check + datetime.fromtimestamp() conversion ile AttributeError giderildi.
- A30 PoR COMPLETED: HTF EMA(200, 4h) filter + time_stop (24 bars) + spread_guard (10 BPS) implementation + Settings cache fix tam tamamlandı.
- A31 META-ROUTER COMPLETED: 4 Specialist strategies (S1: Trend PB/BO, S2: Range MR, S3: Vol Breakout, S4: XSect Momentum), MWU ağırlık öğrenme, gating sistem, ensemble sinyal üretimi, specialist interface pattern, registry yönetimi tamamlandı.
- A32 EDGE HARDENING COMPLETED: Edge Health Monitor (Wilson CI + 200 trade window), 4× Cost-of-Edge calculator, OBI/AFR mikroyapı filtreleri, SignalGenerator pipeline integration, Trader Core initialization, production integration tamamlandı.
- **A33 BOT CONTROL CENTER COMPLETED**: 4 Phase comprehensive implementation - Foundation ✅, Real-time Telemetry ✅, Advanced Settings ✅, Performance Dashboard ✅, **Automation Pipeline ✅**; BotScheduler engine, cron-like task scheduling, market hours automation, maintenance windows, auto risk reduction, daily scheduling, split-panel UI design, comprehensive task management, callback integration - ALL PHASES FULLY OPERATIONAL
- **SMART EXECUTION STRATEGIES COMPLETED**: TWAPExecutor ve VWAPExecutor advanced execution algorithms, SmartRouter optimization engine, execution plan generation, market impact integration, cost estimation framework; 450+ lines production-ready implementation, 5 unit tests PASS; optimal slice calculation, volume profiling, execution timing, strategy selection logic tamamen operasyonel.
- Advanced Strategy Framework: Smart Execution Strategies milestone COMPLETED; next priority: Cross-exchange arbitrage detection + Liquidity-aware execution + Real-time market microstructure analysis + Advanced ML Pipeline expansion.
- Advanced Strategy Framework: A32 Edge Hardening milestone COMPLETED; next priority: Bot Control Center Enhancement + Advanced ML Pipeline expansion + Liquidity-aware execution + Cross-exchange arbitrage detection.
- A30/PR-1: Config genişlemeleri eklendi (HTF/EMA, time_stop, spread guard, meta-router, protection watchdog, strategy_version); tümü default pasif/konservatif, davranış değişikliği yok.
- A30/PR-2 (kısmen): HTF EMA(200, 4h) filtresi `src/signal_generator.py` içine feature flag (HTF_FILTER_ENABLED) ile entegre edildi; long/short bias’a aykırı sinyaller BEKLE’ye çevrilir; `structured_log` ile `signal_blocked` (guard="htf_filter") olayı yazılır; default=false olduğundan mevcut test davranışı değişmedi.
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

## 30. A30 RBP-LS v1.3.1 — REAL IMPLEMENTATION (In-Place Upgrade) PoR

Amaç: Mevcut strateji/riske/uygulama iskeletini bozmayıp minimal-diff yaklaşımıyla RBP-LS v1.3.1’i devreye almak. Bu bölüm, yapıtaşlarını, geri uyumlu konfig genişlemelerini, telemetri/SSoT sözleşmelerini ve kabul kriterlerini tanımlar.

### 30.1 Strateji Mantığı (Özet)
- Zaman Çerçevesi: Ana TF 1h; HTF doğrulama: 4h EMA200 trend filtresi (yukarıda -> long-only bias; aşağıda -> short-only bias; flat -> kısıtlı risk).
- Rejim Filtresi: ADX min eşiği (varsayılan 25) ile trend gücü kontrolü; zayıf trendte mean-reversion bileşenlerinin ağırlığı artar (mevcut indicators.py ağırlık adaptasyonu korunur).
- Giriş Modları: PB/BO (Pullback/Breakout) çift mod. BB/Keltner/Donchian bantları ile bağlam; mevcut BB tabanlı sinyal korunur, Donchian/Keltner ileride eklenmek üzere feature flag ile tanımlanır (kapalı başlar).
- Confluence: RSI + MACD + Bollinger skorlaması mevcut; eşik default ≥75 seçicilik hedefi UI/Backtest ile hizalı. ADX ile ağırlık modülasyonu sürer.
- Çıkış Planı: Hedef RR≥3.0; kısmi realize ilk kademe ~1.5R; ATR-trailing aktivasyonu ≥1.2R, dondurma (freeze) mekanizması mevcut ATR trailing parametreleri ile uyumlu.
- Zaman Durdurma: time_stop=24 bar (1h → ~24 saat) — süre dolunca pozisyon kapatma sinyali üret.

### 30.2 Risk & Kaldıraç (Spot/Futures)
- Risk yüzde bazlı (DEFAULT_RISK_PERCENT), ATR tabanlı stop mesafesi (atr_multiplier) veya fallback %; mevcut RiskManager korunur.
- Futures: Isolated leverage (DEFAULT_LEVERAGE) — marjin limitine güvenli ölçekleme; aşırı kullanım guard (≤%90 marjin kullan).
- Günlük risk guardrail’leri (MAX_DAILY_LOSS_PCT, MAX_CONSECUTIVE_LOSSES) korunur; anomaly tetiklerinde ANOMALY_RISK_MULT devreye girer.

### 30.3 Emir Akışı & Koruma
- Maker-first fırsatları (ileride); mevcut open + koruma (OCO/tekil fallback) akışı korunur.
- Watchdog: Koruma emirleri için retry + degrade policy; structured log olayı ve metrik artışı.

### 30.4 Likidite/Spread Guard’ları
- Minimum hacim zaten mevcut (DEFAULT_MIN_VOLUME). Ek: SPREAD_MAX_BPS ile genişleyebilir guard; kapalı başlar.

### 30.5 Telemetri & İzlenebilirlik
- Prometheus: mevcut sayaçlar (open/close latency, slippage, guard_block, rate_limit/backoff, clock_skew) kullanılır.
- Yeni olaylar, mevcut generic guard_block metriği ile etiketlenir (guard="spread"/"time_stop"/"htf_filter"). Ek sayaç şart değildir.

### 30.6 UI
- Mevcut Türkçe UI korunur; Ayarlar’da ADX min eşiği zaten yönetilebilir. Yeni HTF/EMA ve time_stop/ spread guard parametreleri ileri fazda görünür yapılabilir (varsayılan kapalı/konservatif değerlerle başlar, fonksiyonel regresyon yaratmaz).

### 30.7 Konfig Genişlemeleri (Geriye Uyumlu — Rename yok)
- STRATEGY_VERSION = "RBP-LS-1.3.1" (bilgi amaçlı)
- HTF doğrulama: HTF_EMA_TIMEFRAME="4h", HTF_EMA_LENGTH=200, HTF_FILTER_ENABLED=false (default)
- Giriş modları: ENABLE_BREAKOUT=true, ENABLE_PULLBACK=true (ikisi de açık; mevcut davranış değişmez)
- Hedef RR: DEFAULT_TAKE_PROFIT_RR=2.2 (mevcut değeri koru; 3.0’a geçiş opsiyonel)
- Kısmi realize: PARTIAL_TP1_R_MULT default mevcut değeri korur (1.0); 1.5 önerilir (opsiyonel switch)
- Zaman durdurma: TIME_STOP_BARS=24 (kapalı başlar: TIME_STOP_ENABLED=false)
- Spread guard: SPREAD_GUARD_ENABLED=false, SPREAD_MAX_BPS=10.0
- Koruma watchdog: PROTECTION_WATCHDOG_ENABLED=true, PROTECTION_RETRY_MAX=3
- Meta-router (ileri faz): META_ROUTER_ENABLED=false, META_ROUTER_MODE="mwu"

Not: Tüm anahtarlar Settings altında eklenir; mevcut isimler korunur; yeniler varsayılan olarak pasif/konservatif ayarlanır.

### 30.8 Kabul Kriterleri
- Geriye dönük uyum: Mevcut testlerin tamamı PASS; varsayılan değerlerle davranış değişmez.
- Konfig: Yeni anahtarlar import edilir, erişilebilir; UI/işlev path’larında zorunlu olmayan hiçbir yan etki yok.
- Telemetri: Yeni guard’lar tetiklenirse bot_guard_block_total etiketlenir; metriks endpoint bozulmaz.
- SSoT: Bu PoR bölümü eklendi; Migration notları oluşturuldu.

### 30.9 Rollout & Test
- PR-1: Config & Telemetry (bu PoR + Settings genişlemeleri) — minimal kod değişikliği, test çalıştır.
- PR-2..N: PB/BO çekirdek, HTF EMA filtresi, time_stop, spread guard adım adım, her adımda test/backtest.

### 30.10 Migration Notları (Özet)
- Yeni anahtarlar eklendi; hiçbir mevcut anahtarın adı değişmedi; varsayılanlar kapalı/pasif.
- RiskManager take_profit_rr başlangıç değeri Settings.DEFAULT_TAKE_PROFIT_RR ile okunur; default 2.2, dolayısıyla davranış değişmez.

## 31. A31 RBP-LS v1.4.0 — META-ROUTER & ENSEMBLE SYSTEM PoR

Amaç: Meta-Router ensemble sistemi ile 4 uzman stratejiyi koordine etmek. Adaptif ağırlık öğrenme ve risk dağıtımı.

### 31.1 Meta-Router Çerçevesi
**Uzman Stratejiler**:
- S1: trend_pb_bo (mevcut PB/BO çekirdeği; trend + squeeze-breakout)
- S2: range_mr (yatay mean-reversion: BB bounce + RSI aşırılık)
- S3: vol_breakout (Donchian(20) kırılma + ATR≥medyan×1.1)
- S4: xsect_mom (Top150'de 3/6/12h bileşik momentum; günlük rebalance)

**Gating Skorları (0–1)**:
- TrendScore = clip((ADX−10)/(40−10),0,1)
- SqueezeScore = 1 − pct_rank(BB_bw, lookback=180)
- ChopScore = 1 − |RSI−50|/50
- Autocorr1h = corr(close_t−1, close_t)

**Kapı Kuralları**:
- S1: TrendScore≥0.35 ve (SqueezeScore≥0.5 veya ADX≥18)
- S2: TrendScore≤0.25 ve ChopScore≥0.6 (ADX<20; 4h slope≈0)
- S3: SqueezeScore≥0.6 ve hacim≥medyan×1.2
- S4: sadece daily rebalance saatinde

**Ağırlık Öğrenme (MWU)**:
- w_{t+1}(i) ∝ w_t(i) × exp(η × r_t(i)/risk_unit), η≈0.10
- Normalize; clamp [0.1, 0.6]; 24 bar pencere
- OOS-guard: son 14 gün PF<1.1 olan uzmanın ağırlığı min_weight'e sabitlenir

### 31.2 Range Mean-Reversion Uzmanı (S2)
**Giriş Koşulları**:
- LONG: close ≤ BB_lower + 0.1×ATR & RSI≤35 → çıkış: SMA20 veya 1.5R
- SHORT: close ≥ BB_upper − 0.1×ATR & RSI≥65 → çıkış: SMA20 veya 1.5R
- SL=max(1.0×ATR, band±0.5×ATR)

**Rejim Filtresi**:
- ADX<20 (trend yok), 4h EMA slope≈0 (yatay market)
- ChopScore≥0.6 (RSI 35-65 arası osillasyon)

### 31.3 Volume Breakout Uzmanı (S3)
**Donchian Breakout**:
- LONG: close > Donchian_upper(20) ve ATR≥medyan×1.1
- SHORT: close < Donchian_lower(20) ve ATR≥medyan×1.1
- SL=1.2×ATR; hedef 2R + trailing

**Hacim Teyidi**:
- Volume ≥ 20-bar medyan × 1.2
- Squeeze teyidi: BB bandwidth p80 üstünde

### 31.4 Cross-Sectional Momentum Uzmanı (S4)
**Momentum Hesaplama**:
- 3h, 6h, 12h getiri bileşik skoru
- Top150 evreni içinde percentile ranking
- Günlük 00:00 UTC rebalance

**Risk Parite**:
- Her sembol için volatilite ayarlı ağırlık
- Pay tavanı toplam riskin %10'u
- Dinamik korelasyon kısıtları

### 31.5 Konfigürasyon Şeması (Meta-Router)
```yaml
meta_router:
  enabled: false  # A31'de aktif edilecek
  specialists: ["trend_pb_bo", "range_mr", "vol_breakout", "xsect_mom"]
  rebalance_bars: 24
  learner:
    algorithm: "mwu"  # multiplicative weights update
    eta: 0.10
    min_weight: 0.10
    max_weight: 0.60
    window_bars: 24
  oos_guard:
    window_days: 14
    min_profit_factor: 1.10
  gating:
    trend_min_threshold: 0.35
    squeeze_min_threshold: 0.5
    chop_min_threshold: 0.6
    volume_min_mult: 1.2

range_mr:
  enabled: false
  rsi_oversold: 35
  rsi_overbought: 65
  bb_touch_atr_mult: 0.1
  target_r: 1.5
  sl_atr_mult: 1.0

vol_breakout:
  enabled: false
  donchian_periods: 20
  atr_min_mult: 1.1
  target_r: 2.0
  sl_atr_mult: 1.2
  volume_min_mult: 1.2

xsect_mom:
  enabled: false
  lookback_hours: [3, 6, 12]
  rebalance_hour: 0  # UTC
  max_position_pct: 0.10
  risk_parity: true
```

### 31.6 Implementation Roadmap (A31)
**Phase 1**: Meta-Router infrastructure
- Uzman interface & factory pattern
- Gating score computation engine
- MWU ağırlık güncelleme motoru

**Phase 2**: S2 & S3 uzmanları
- Range MR: BB + RSI mean reversion
- Vol BO: Donchian + ATR/volume breakout

**Phase 3**: S4 & orchestration
- Cross-sectional momentum engine
- Risk parite allocation
- Ensemble coordination

**Phase 4**: UI & monitoring
- Meta-Router panel (ağırlık barları)
- Uzman performance kartları
- Gating status rozetleri

### 31.7 Kabul Kriterleri (A31)
- 4 uzman ayrı ayrı test edilebilir
- MWU ağırlık güncelleme deterministik
- Gating skorları doğru hesaplanır
- Risk dağıtımı %100 toplamı yapar
- OOS guard düşük performans uzmanları durdurur

## 32. A32 RBP-LS v1.5.0 — ELMAS MANTIK (Edge Hardening) PoR

Amaç: Trading edge'lerini korumak için gelişmiş filtreleme ve adaptasyon sistemleri.

### 32.1 Edge Health Monitor (EHM)
**Sağlık Metrikleri**:
- Expectancy-R: E[R] = Σ(win_rate × avg_win_R − loss_rate × avg_loss_R)
- Wilson alt sınır: confidence interval lower bound
- 200 trade kayan pencere, minimum 50 trade

**Edge Durumları**:
- HOT: LB > 0.1R (güçlü edge)
- WARM: 0 < LB ≤ 0.1R (zayıf ama pozitif)
- COLD: LB ≤ 0 (edge yok/negatif)

**Edge Politikası**:
- COLD edge'ler NO-GO (yalnızca paper/testnet'te re-qualify)
- WARM edge'ler risk azaltılır (%50)
- HOT edge'ler normal risk

### 32.2 Cost-of-Edge: 4× Kuralı
**Pre-trade EGE Hesaplama**:
- Expected Gross Edge = confluence + rejim + tetik gücü + hacim skoru
- Total Cost = fee + expected_slippage
- Kural: EGE ≥ 4 × Total Cost, değilse NO-GO

**Dinamik Cost Model**:
- Fee: maker/taker differential
- Slippage: spread & derinlik tabanlı tahmin
- Impact: order size vs book depth

### 32.3 Mikroyapı Prefiltreleri
**Order Book Imbalance (OBI)**:
- OBI = (Σbid_vol − Σask_vol) / (Σbid_vol + Σask_vol), 5-10 seviye
- LONG sadece OBI ≥ +0.20; SHORT sadece OBI ≤ −0.20
- Çelişki durumunda WAIT; 2. snapshot ile teyit

**Aggressive Fill Ratio (AFR)**:
- AFR = taker_buy_qty / total_taker_qty (son 50-100 trade)
- LONG AFR≥0.55, SHORT AFR≤0.45
- Real-time trade stream analysis

### 32.4 Adaptif Fraksiyonel Kelly
**Risk Adjustment Formula**:
- risk_per_trade = base_risk × g(DD) × h(EdgeHealth)
- g(DD): 1.0 (≤5%), 0.5 (5-10%), 0.25 (>10%)
- h(Hot)=1.0, h(Warm)=0.75, h(Cold)=0.25
- Tavan: min(..., 0.5%) (geriye uyum)

**Kelly Fraction Hesaplama**:
- f* = (bp - q) / b, burada b=avg_win/avg_loss, p=win_rate, q=1-p
- Conservative multiplier: 0.25 × f* (over-leverage koruması)

### 32.5 Dead-Zone (No-Trade Band)
**Expected Edge Score (EES)**:
- Tüm faktörlerin ağırlıklı toplamı: [-1, +1] aralığında
- Dead zone: -0.05 ≤ EES ≤ +0.05 ise trade yok
- Chop market'ta deneme azaltma

### 32.6 Carry Fallback (Opsiyonel)
**Funding Arbitraj**:
- Rejim belirsiz ve |funding|≥0.03%/8h
- Spot cüzdan varsa: delta-nötr (spot long + perp short)
- Funding saatinde [-5,+2] dk sessiz pencere

### 32.7 Konfigürasyon (A32)
```yaml
edge_health:
  enabled: false  # A32'de aktif
  window_trades: 200
  min_trades: 50
  confidence_interval: "wilson"
  hot_threshold: 0.10
  warm_threshold: 0.0
  cold_action: "no_go"  # no_go|reduce|paper_only

cost_of_edge:
  enabled: false
  k_multiple: 4.0
  fee_model: "tiered"  # flat|tiered
  slippage_model: "dynamic"  # static|dynamic

microstructure:
  enabled: false
  obi_levels: 5
  obi_long_min: 0.20
  obi_short_max: -0.20
  afr_window_trades: 80
  afr_long_min: 0.55
  afr_short_max: 0.45
  conflict_action: "wait"  # wait|abort

kelly:
  enabled: false
  base_risk: 0.005
  conservative_mult: 0.25
  dd_adjustment: true
  edge_adjustment: true
  max_fraction: 0.005

dead_zone:
  enabled: false
  eps_threshold: 0.05
  chop_reduction: true

carry_fallback:
  enabled: false
  funding_threshold_8h: 0.0003
  require_spot_wallet: true
  quiet_window_minutes: [-5, 2]
```

### 32.8 Implementation Priority (A32)
**P1**: Edge Health Monitor + COLD/WARM/HOT classification
**P1**: 4× Cost rule + pre-trade gate
**P2**: OBI/AFR mikroyapı filtreleri
**P2**: Kelly fraksiyonu + risk scaling
**P3**: Dead-zone + carry fallback

### 32.9 Kabul Kriterleri (A32)
- EHM 200 trade pencerede doğru LB hesaplar
- 4× cost kuralı fee+slip'i doğru tahmin eder
- OBI/AFR real-time hesaplama 100ms altında
- Kelly fraction DD ve edge health'e uygun scale eder
- Dead-zone EES hesaplama deterministik

## 33. A33 MODÜL REGISTRY GÜNCELLEMESİ

Yeni modüller A31-A32 implementasyonu için ekleniyor:

| MOD-ID | Ad | Konum | Sorumluluk | Bağımlılıklar | Durum |
|--------|----|-------|------------|---------------|-------|
| MOD-META-ROUTER | MetaRouter | src/strategy/meta_router.py | Uzman koordinasyon, MWU ağırlık | MOD-SIGNAL-GEN, MOD-RISK | planned |
| MOD-STRATEGY-S2 | RangeMRSpecialist | src/strategy/range_mr.py | Mean-reversion BB+RSI | MOD-INDICATORS | planned |
| MOD-STRATEGY-S3 | VolBreakoutSpecialist | src/strategy/vol_breakout.py | Donchian+volume breakout | MOD-INDICATORS | planned |
| MOD-STRATEGY-S4 | XSectMomSpecialist | src/strategy/xsect_momentum.py | Cross-sectional momentum | MOD-DATA-FETCHER | planned |
| MOD-EHM | EdgeHealthMonitor | src/utils/edge_health.py | Trading edge sağlık izleme | MOD-UTILS-STORE | planned |
| MOD-COST-EDGE | CostOfEdge | src/utils/cost_calculator.py | 4× cost kuralı hesaplama | MOD-API-BINANCE | planned |
| MOD-MICROSTRUCTURE | MicrostructureFilter | src/utils/microstructure.py | OBI/AFR real-time filtre | MOD-API-BINANCE | planned |
| MOD-KELLY | KellyCalculator | src/utils/kelly_fraction.py | Adaptif Kelly fraksiyonu | MOD-EHM | planned |
| MOD-DEAD-ZONE | DeadZoneFilter | src/utils/dead_zone.py | No-trade band mantığı | MOD-SIGNAL-GEN | planned |

## 35. A35 DEEP LOGIC DEBUGGING & PRODUCTION READINESS ASSESSMENT PoR

Amaç: %100 test coverage'a rağmen gerçek kullanımda ortaya çıkan mantık hataları, bağlantı sorunları ve state inconsistency'lerini sistematik olarak tespit etmek ve düzeltmek.

### 35.1 Problem Analizi
**Test Coverage Paradoksu**: Unit testler %100 geçse de gerçek dünyada sorunlar var çünkü:
- Unit testler izole çalışır, gerçek bağlantıları test etmez
- Integration testler sınırlı senaryoları kapsar  
- UI-backend etkileşimleri mock'lanır
- Race conditions ve timing issues gözden kaçar
- Error handling edge case'leri eksik kalır
- State management karmaşıklığı underestimate edilir

### 35.2 Deep Logic Debugging Methodology

**Phase 1: End-to-End Flow Analysis (E2E-FA)**
- Bot başlatma → sinyal üretimi → trade açma → koruma → kapatma full cycle
- UI interaction → backend processing → database persistence → UI update loop
- Real API calls + real data + real timing constraints
- Error propagation path analysis
- State transition validation at every step

**Phase 2: Real-World Scenario Testing (RWST)**
- Testnet'te 24 saat kesintisiz çalışma testi
- Network interruption simulation (Wi-Fi disconnect/reconnect)
- API rate limiting + 429 error handling under pressure
- Database lock scenarios + concurrent access
- UI freeze prevention under heavy data loads
- Memory leak detection over extended periods

**Phase 3: Error Injection & Resilience Testing (EIRT)**
- Deliberate API failures at critical moments
- Database corruption simulation
- Partial data scenarios (incomplete JSON responses)
- Timeout simulations (slow network, overloaded API)
- Invalid data injection (malformed price data, missing fields)
- State corruption testing (manual database edits during runtime)

**Phase 4: State Consistency Validation (SCV)**
- UI display vs database content comparison
- Exchange positions vs local positions reconciliation
- Trade execution state vs UI button states synchronization
- Cache coherency across components
- Event ordering validation (especially WebSocket events)
- Concurrency safety in multi-threaded operations

**Phase 5: Integration Boundary Analysis (IBA)**
- TradeStore API contract validation (closed_trades vs get_closed_trades issues)
- BinanceAPI client connection lifecycle management
- Trader core vs UI communication protocol verification
- Settings hot-reload propagation testing
- MetaRouter vs SignalGenerator coordination validation
- Risk escalation system integration points

### 35.3 Critical Flow Scenarios

**Scenario 1: Bot Startup Flow**
```
UI Start Button → Trader Init → API Connect → TradeStore Ready → SignalGen Start → UI Status Update
```
**Test Points**: Her adımda failure injection, partial completion scenarios, rollback verification

**Scenario 2: Trade Execution Flow**
```  
Signal → Risk Check → Order Submit → Fill Event → Protection Setup → Position Track → UI Update
```
**Test Points**: API timeout mid-execution, partial fills, protection order failures, UI sync delays

**Scenario 3: Emergency Stop Flow**
```
UI Emergency Button → close_all_positions() → Cancel Orders → Position Cleanup → Bot Stop → UI Update  
```
**Test Points**: Network failure during cleanup, partial position closures, state recovery

**Scenario 4: Performance Dashboard Data Flow**
```
Timer Trigger → _calculate_daily_pnl() → TradeStore Query → Data Processing → UI Widget Update
```
**Test Points**: Empty data scenarios, calculation errors, UI thread blocking, refresh rate consistency

### 35.4 Debugging Tools & Instrumentation

**Real-Time State Inspector**:
- Live dashboard showing internal state across all components
- WebSocket message flow visualization  
- Database query execution timing and results
- UI event queue status and processing delays
- Memory usage and GC pressure monitoring

**Production Logging Enhancement**:
- Structured logging with correlation IDs across components
- Performance timing logs for critical operations
- State transition logs with before/after snapshots
- Error context preservation with full stack traces
- API call/response logging with timing metrics

**Automated Health Checks**:
- Background state consistency verifiers
- API connectivity health monitors
- Database integrity checkers
- UI responsiveness validators
- Memory leak detectors

### 35.5 Implementation Roadmap

**Week 1: E2E Flow Analysis & Instrumentation**
- Implement real-time state inspector
- Add correlation ID tracking across components
- Create end-to-end test harness with real APIs
- Document all critical flow paths

**Modül ve Bileşen Tarama Planı:**

**Phase 1A: Core Trading Flow Analysis (Hafta 1-2)**
- **MOD-CORE-TRADER** (src/trader/core.py): 
  - Bot başlatma/durdurma lifecycle
  - Trade açma/kapatma decision flow
  - Risk escalation integration points
  - State management (_bot_core, trader sync)
- **MOD-EXEC** (src/trader/execution.py):
  - Order submission pipeline
  - Protection order placement
  - Error handling during execution
  - Timeout scenarios
- **MOD-SIGNAL-GEN** (src/signal_generator.py):
  - Signal generation timing
  - Data staleness detection
  - Hysteresis logic validation
  - Cache coherency issues

**Phase 1B: UI-Backend Integration (Hafta 1-2)**
- **MOD-UI-MAIN** (src/ui/main_window.py):
  - Performance dashboard data flow
  - Emergency stop button functionality
  - Bot status display synchronization
  - Real-time telemetry updates
- **MOD-UTILS-STORE** (src/utils/trade_store.py):
  - API method consistency (closed_trades vs get_closed_trades)
  - Database query performance
  - Data format inconsistencies
  - Concurrent access issues

**Phase 2A: Data Persistence & API Integration (Hafta 2-3)**
- **MOD-API-BINANCE** (src/api/binance_api.py):
  - Connection lifecycle management
  - Rate limiting handling
  - API v2 endpoint compatibility
  - Error response processing
- **MOD-API-HEALTH** (src/api/health_check.py):
  - Clock skew detection accuracy
  - Connection timeout scenarios
  - Reconnection logic validation
- **MOD-API-PRICESTREAM** (src/api/price_stream.py):
  - WebSocket connection stability
  - Message ordering validation
  - Reconnection race conditions

**Phase 2B: Risk & Guards System (Hafta 2-3)**
- **MOD-RISK** (src/risk_manager.py):
  - Position sizing calculations
  - Stop/TP price validation
  - Risk escalation triggers
- **MOD-GUARDS** (src/trader/guards.py):
  - Daily loss reset timing
  - Correlation cache TTL
  - Volume guard effectiveness
- **MOD-UTILS-RISK-ESCALATION** (src/utils/risk_escalation.py):
  - Progressive risk level transitions
  - Kill-switch activation scenarios
  - Recovery mechanisms

**Phase 3A: Advanced Components (Hafta 3-4)**
- **MOD-A31-META-ROUTER** (src/strategy/meta_router.py):
  - Specialist coordination logic
  - Weight learning convergence
  - Gating decision accuracy
- **MOD-A32-EDGE-HEALTH** (src/utils/edge_health.py):
  - Wilson CI calculations
  - Trade window management
  - Health state transitions
- **MOD-AUTOMATION-SCHEDULER** (src/utils/scheduler.py):
  - Task scheduling reliability
  - Callback execution timing
  - Error propagation

**Phase 3B: UI Responsiveness & Performance (Hafta 3-4)**
- **MOD-UI-META-ROUTER** (src/ui/meta_router_panel.py):
  - Real-time weight display
  - Update frequency optimization
  - Memory leak detection
- **MOD-UI-PORTFOLIO** (src/ui/portfolio_analysis_panel.py):
  - Correlation matrix calculations
  - Risk metrics accuracy
  - UI freeze prevention

**Week 2: Error Injection Framework**
- Build configurable failure injection system
- Create network simulation tools  
- Implement chaos testing scenarios
- Add state corruption detection

**Week 3: Real-World Testing**
- 24/7 testnet operation with monitoring
- Load testing with multiple concurrent operations
- Performance profiling under stress
- Memory leak detection over extended periods

**Week 4: Issue Resolution & Hardening**
- Fix identified logic bugs and race conditions
- Implement missing error handling
- Add defensive programming where needed
- Enhance recovery mechanisms

### 35.6 Success Metrics

**Reliability Targets**:
- 99.9% uptime over 7-day continuous operation
- <1% trade execution failures due to logic errors
- <5 second recovery time from network interruptions
- Zero UI freezes during normal operation
- <2% memory growth over 24-hour periods

**Quality Gates**:
- All critical flows pass error injection testing
- State consistency maintained across all scenarios
- UI-backend synchronization under 100ms
- Database operations complete within SLA
- Error recovery mechanisms validated

### 35.7 Risk Mitigation

**Backup & Recovery**:
- Automated database snapshots before testing
- Configuration rollback procedures
- Emergency stop procedures for testing
- Data integrity verification protocols

**Testing Safety**:
- Testnet-only for destructive testing
- Isolated environment for chaos testing  
- Automated test result validation
- Human oversight for critical scenarios

### 35.9 Phase-by-Phase Module Analysis Matrix

**Phase 1: Core Flow Integrity (Hafta 1-2)**
| Modül | Dosya | Kritik Test Noktaları | Beklenen Sorunlar |
|-------|-------|----------------------|-------------------|
| MOD-CORE-TRADER | src/trader/core.py | Bot startup sequence, _bot_core sync, reconciliation timing | State inconsistency, initialization race conditions |
| MOD-EXEC | src/trader/execution.py | Order submission, protection setup, error propagation | API timeout handling, partial fills, retry logic |
| MOD-SIGNAL-GEN | src/signal_generator.py | Signal timing, data freshness, cache hits | Stale data usage, timing race conditions |
| MOD-UI-MAIN | src/ui/main_window.py | UI updates, button states, telemetry display | Thread synchronization, data binding issues |
| MOD-UTILS-STORE | src/utils/trade_store.py | Method names, data formats, query performance | API contract mismatches, data type inconsistencies |

**Phase 2: Integration Boundaries (Hafta 2-3)**
| Modül | Dosya | Kritik Test Noktaları | Beklenen Sorunlar |
|-------|-------|----------------------|-------------------|
| MOD-API-BINANCE | src/api/binance_api.py | Connection lifecycle, rate limits, endpoint versions | V1/V2 endpoint issues, connection drops, auth failures |
| MOD-API-HEALTH | src/api/health_check.py | Clock sync, latency measurements, reconnection logic | Time drift detection, false positives |
| MOD-API-PRICESTREAM | src/api/price_stream.py | WebSocket stability, message ordering, error recovery | Connection interruptions, message loss |
| MOD-RISK | src/risk_manager.py | Position sizing, stop calculations, limit validations | Precision errors, edge case handling |
| MOD-GUARDS | src/trader/guards.py | Daily resets, correlation updates, volume checks | Timer accuracy, cache invalidation |

**Phase 3: Advanced Systems (Hafta 3-4)**
| Modül | Dosya | Kritik Test Noktaları | Beklenen Sorunlar |
|-------|-------|----------------------|-------------------|
| MOD-A31-META-ROUTER | src/strategy/meta_router.py | Weight learning, specialist gating, ensemble decisions | Convergence failures, weight drift |
| MOD-A32-EDGE-HEALTH | src/utils/edge_health.py | Wilson CI calculations, window management, state transitions | Statistical accuracy, window edge effects |
| MOD-AUTOMATION-SCHEDULER | src/utils/scheduler.py | Task execution, callback reliability, error handling | Timer precision, callback failures |
| MOD-UI-META-ROUTER | src/ui/meta_router_panel.py | Real-time updates, weight visualization, responsiveness | UI freezing, update lag |
| MOD-UI-PORTFOLIO | src/ui/portfolio_analysis_panel.py | Matrix calculations, metric accuracy, display refresh | Calculation bottlenecks, memory leaks |

### 35.10 Critical Integration Points Analysis

**Bot Startup Chain (Priority 1):**
```
main_window.py._start_bot() → 
trader/core.py.__init__() → 
api/binance_api.py.connect() → 
utils/trade_store.py.initialize() →
signal_generator.py.start() →
main_window.py._update_status()
```

**Trade Execution Chain (Priority 1):**
```
signal_generator.py.generate_signal() →
trader/core.py.process_signal() →
risk_manager.py.calculate_position_size() →
trader/execution.py.open_position() →
api/binance_api.py.place_order() →
utils/trade_store.py.record_trade() →
main_window.py.update_positions_table()
```

**Emergency Stop Chain (Priority 1):**
```
main_window.py.emergency_stop() →
trader/core.py.close_all_positions() →
trader/execution.py.close_position() →
api/binance_api.py.cancel_orders() →
utils/trade_store.py.update_status() →
main_window.py._update_status()
```

**Performance Dashboard Chain (Priority 2):**
```
QTimer.timeout() →
main_window.py._update_telemetry() →
main_window.py._calculate_daily_pnl() →
utils/trade_store.py.closed_trades() →
main_window.py._update_dashboard_widgets()
```
P1: Meta-Router factory pattern ve uzman interface tasarımı
P1: MWU ağırlık güncelleme algoritması implementation
P1: Range MR uzmanı (S2): BB bounce + RSI mean reversion
P1: Volume Breakout uzmanı (S3): Donchian + ATR/volume
P1: Edge Health Monitor: Wilson CI + 200 trade pencere
P1: 4× Cost-of-Edge pre-trade gate implementation
P2: Cross-sectional momentum uzmanı (S4): Top150 momentum ranking
P2: OBI/AFR mikroyapı filtreleri real-time
P2: Adaptif Kelly fraksiyonu: DD + edge health scaling
P2: Dead-zone no-trade band logic
P2: Meta-Router UI panel: ağırlık barları + performance kartları
P2: Edge health dashboard: HOT/WARM/COLD status rozetleri
P3: Carry fallback: funding arbitraj opportunity
P3: Advanced backtest: ensemble vs solo performance

## A35 Deep Logic Debugging Priorities

**🚨 CRITICAL REQUIREMENT: ZERO-CODE-SKIP MANDATE**
**ABSOLUTE RULE: TEK BİR SATIR KODU GÖZ ARDI ETMEMEMİZ LAZIM**

**Zero-Code-Skip Implementation Strategy:**
- **100% Line Coverage**: Her Python dosyasındaki her satır mutlaka analiz edilmeli
- **Exhaustive Path Testing**: Try-catch, if-else, loop, function çağrıları - HİÇ BİR PATH ATLANMAMALI
- **Dead Code Detection**: Kullanılmayan kod parçalarının tespit edilmesi ve temizlenmesi
- **Integration Boundary Validation**: Her modül arası geçiş noktası detaylı test edilmeli
- **Edge Case Coverage**: Normal akış dışındaki tüm durumlar (network fail, memory limit, timeout, etc.)

**Enforcement Mechanisms:**
- Code coverage tools ile %100 line/branch coverage doğrulaması
- Static analysis ile unreachable code detection
- Manual line-by-line code review ve documentation
- Automated test generation for uncovered paths
- Cross-reference validation for all component interactions

**P1: End-to-End Flow Analysis & Instrumentation**
- Real-time state inspector implementation
- Correlation ID tracking across components
- Critical flow documentation and mapping
- Live dashboard for internal state monitoring

**P1: Error Injection Framework**
- Configurable failure injection system
- Network simulation tools development
- Chaos testing scenarios implementation
- State corruption detection mechanisms

**P1: Real-World Testing**
- 24/7 testnet operation with monitoring
- Load testing with concurrent operations
- Performance profiling under stress
- Memory leak detection over extended periods

**P1: State Consistency Validation**
- UI display vs database content comparison
- Exchange positions vs local positions reconciliation
- Cache coherency across components verification
- Event ordering validation (WebSocket events)

**P1: Integration Boundary Analysis**
- TradeStore API contract validation
- BinanceAPI client connection lifecycle management
- Trader core vs UI communication protocol verification
- Settings hot-reload propagation testing

**P1: Critical Flow Scenario Testing**
- Bot startup flow with failure injection
- Trade execution flow with API timeouts
- Emergency stop flow with network failures
- Performance dashboard data flow validation

**P1: Production Hardening**
- Enhanced error handling implementation
- Improved state management and synchronization
- Robust API integration with retry logic
- Better UI responsiveness under load

**P1: Monitoring & Alerting**
- Production-ready health monitoring dashboard
- Automated alerting for critical failures
- Performance metrics collection and analysis
- Proactive issue detection capabilities

### A35.8 Test Execution Order & Dependencies

**🚨 ZERO-CODE-SKIP VALIDATION AT EACH PHASE**

**Phase 1A-1B: Foundation Testing (Parallel)**
```
Day 1-3: MOD-CORE-TRADER + MOD-UI-MAIN (startup/shutdown flows)
         → %100 line coverage verification REQUIRED
Day 4-7: MOD-EXEC + MOD-SIGNAL-GEN (signal-to-execution pipeline)  
         → All code paths tested, no exceptions
Day 8-10: MOD-UTILS-STORE (data persistence integrity)
          → Every database operation validated
```

**Phase 2A-2B: Integration Testing (Sequential)**
```
Day 11-14: MOD-API-* modules (external connectivity)
           → Every API call scenario covered
Day 15-17: MOD-RISK + MOD-GUARDS (internal logic validation)
           → All risk conditions and guard triggers tested
Day 18-21: Cross-component communication testing
           → Every inter-module communication path validated
```

**Phase 3A-3B: Advanced Systems (Conditional)**
```
Day 22-24: MOD-A31/A32 advanced features (if Phase 1-2 stable)
           → Complete feature functionality verification
Day 25-28: UI panels performance testing
           → Every UI component and interaction tested
Day 29-30: End-to-end system validation
           → Final comprehensive system-wide validation
```

**Quality Gates - Zero-Skip Enforcement:**
- **Phase Completion Criteria**: 100% code coverage + manual review completion
- **Go/No-Go Checkpoints**: Code analysis reports + static analysis clean
- **Production Readiness**: No single line of code left unanalyzed

**Risk Mitigation Strategy:**
- Each phase has Go/No-Go checkpoints
- Critical issues in Phase 1 block Phase 2 progression
- Rollback plan for each phase
- Isolated testing environments per phase

### 34.2 COMPLETED (A30)
✅ HTF EMA(200, 4h) filter implementation ve test stabilizasyonu
✅ Time stop (24 bars) position timeout functionality
✅ Spread guard: bid/ask spread protection + graceful fallback
✅ A30 PoR configuration parameters + backward compatibility
✅ Structured logging integration for new features
✅ Prometheus metrics extension for guards & filters

## 35. A35 TEST STRATEJİSİ GÜNCELLEMESİ

### 35.1 A31 Test Kapsam
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

### 35.2 A32 Test Kapsam
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

### 35.3 End-to-End Scenarios
**Ensemble vs Solo**: Meta-Router ON/OFF performance karşılaştırması
**Market Regime**: Trend/range/squeeze koşullarında uzman seçimi
**Risk Escalation**: COLD edge + Kelly reduction + dead-zone integration

## 36. A36 BOT KONTROL MERKEZİ GELİŞTİRME PLANI

### 36.1 Mevcut Durum (v2.24)
- ✅ **Temel Bot Kontrol Tabı**: 🤖 Bot Kontrol tabı UI'ya entegre edildi
- ✅ **Menü Temizleme**: Üst menüden bot kontrol menüsü kaldırıldı
- ✅ **Durum Göstergeleri**: 🔴/🟢 real-time bot durumu
- ✅ **Temel Kontroller**: Başlat/Durdur/Durum butonları
- ✅ **Risk Ayarları**: Risk yüzdesi ve max pozisyon spinbox'ları

### 36.2 Geliştirilecek Özellikler (Priority Matrix)

**📊 Real-time Telemetry & Monitoring (P1)**:
- Bot çalışma süresi (uptime) real-time güncelleme
- Güncel PnL ve günlük performans metrikleri
- Aktif pozisyon sayısı ve toplam exposure
- Son işlem bilgisi ve başarı oranı
- Risk escalation seviyesi göstergesi (NORMAL/WARNING/CRITICAL/EMERGENCY)
- API bağlantı durumu ve sağlık göstergeleri

**⚙️ Advanced Settings & Configuration (P1)**:
- Strategy seçici (A30/A31/A32 stratejiler arası geçiş)
- Meta-Router enable/disable toggle
- Edge Health Monitor ayarları
- Time stop ve spread guard parametreleri
- Advanced risk settings (Kelly fraction, VaR limits)
- Hot-reload configuration support

**📅 Scheduler & Automation (P2)**:
- Zamanlı bot başlatma/durdurma
- Market saatleri tabanlı otomatik mod
- Bakım penceresi tanımlama
- Otomatik risk azaltma tetikleyicileri
- Scheduled backtest runs

**🔔 Alerts & Notifications (P2)**:
- Critical event push notifications
- Performance threshold alerts
- Risk limit breach warnings
- System health monitoring alarms
- Custom alert rule engine

**📈 Performance Dashboard (P2)**:
- Mini charts: PnL trend, drawdown, R-multiple dağılımı
- Strategy performance comparison
- Correlation with market indices
- Live order flow visualization
- Recent trades summary table

**🛠️ Diagnostic Tools (P3)**:
- Log viewer with filtering
- Debug mode toggle
- System resource monitoring
- Network latency checker
- Database integrity tools

### 36.3 Implementation Roadmap

**Phase 1: Real-time Telemetry (CR-BOT-CONTROL-TELEMETRY)**
- Integration: MOD-CORE-TRADER, MOD-METRICS, MOD-UTILS-RISK-ESCALATION
- Real-time data binding ile sürekli güncelleme
- QTimer tabanlı telemetry refresh (1-5 sn aralıklarla)
- Performance metrics threading ile UI blocking önleme

**Phase 2: Advanced Settings (CR-BOT-CONTROL-SETTINGS)**
- Integration: MOD-SIGNAL-GEN, MOD-RISK, Settings
- Dynamic configuration loading/saving
- Strategy switcher UI component
- Parameter validation ve hot-reload

**Phase 3: Dashboard & Charts (CR-BOT-CONTROL-DASHBOARD)**
- Integration: matplotlib/pyqtgraph embedded charts
- Mini performance visualization
- Real-time data streaming to charts

**Phase 4: Automation & Scheduling (CR-BOT-CONTROL-AUTOMATION)**
- Scheduler engine implementation
- Cron-like task management
- Event-driven automation triggers

### 36.4 Technical Architecture

**Data Flow**:
```
Trader Core → Bot Control Center ← UI Thread
     ↓              ↑                 ↓
Telemetry ← QTimer Update → Display Components
```

**Key Components**:
- `BotTelemetryManager`: Real-time data collection
- `BotConfigManager`: Settings management
- `BotScheduler`: Automation engine
- `BotAlertEngine`: Notification system

**Performance Requirements**:
- Telemetry update latency: <100ms
- UI responsiveness: Non-blocking updates
- Memory footprint: <50MB incremental
- CPU overhead: <5% during normal operation

### 36.5 Testing Strategy

**Unit Tests**:
- Telemetry data accuracy
- Configuration validation
- Alert rule evaluation
- Scheduler job execution

**Integration Tests**:
- UI ↔ Core communication
- Real-time update pipeline
- Cross-component data consistency

**UI Tests**:
- User interaction scenarios
- Visual regression testing
- Performance profiling

### 36.6 Success Metrics

**Functionality**:
- 100% real-time telemetry accuracy
- <1s configuration change propagation
- Zero data loss during UI updates

**Usability**:
- Single-click bot management
- Intuitive control layout
- Visual feedback for all actions

**Performance**:
- <2% CPU overhead
- <100ms telemetry refresh
- Responsive UI (>30 FPS)

### 36.7 Risk Mitigation

**UI Freeze Prevention**:
- Separate telemetry thread
- Non-blocking data updates
- Graceful degradation on data unavailability

**Data Consistency**:
- Thread-safe data access
- Atomic configuration updates
- Rollback capability for failed changes

**Error Handling**:
- Graceful error recovery
- User-friendly error messages
- Automatic retry mechanisms
