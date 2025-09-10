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

## A3. Modül Kataloğu (Özet)
**Ana Modüller**: 40+ modül active durumda (Core Trader, Execution, Risk Manager, Signal Generator, UI, API, Strategy, ML)

*Detaylı modül registrisi için: [Modül Kataloğu](.github/docs/module-registry.md)*

**Kritik Modüller**:
- **MOD-CORE-TRADER**: Trade orchestrator & yaşam döngüsü
- **MOD-EXEC**: Emir açma/kapama & koruma emirleri  
- **MOD-RISK**: Risk yönetimi & pozisyon boyutlama
- **MOD-SIGNAL-GEN**: Sinyal üretimi & hysteresis
- **MOD-UI-MAIN**: Ana PyQt5 kullanıcı arayüzü
- **MOD-API-BINANCE**: Binance API integration

## A4. API & Şema Sözleşmeleri (Özet)
**Positions**: `{side, entry_price, position_size, remaining_size, stop_loss, take_profit, atr, trade_id, scaled_out, model_version, order_state, created_ts, updated_ts}`

**Koruma Emirleri**: 
- Spot: `oco_resp{ids:[...]}`
- Futures: `futures_protection{sl_id,tp_id}`

**Ana Fonksiyonlar**:
- `FN-EXEC-open_position(symbol, ctx) -> bool`
- `FN-EXEC-close_position(symbol) -> bool`

*Detaylı API sözleşmeleri için: [API Şema Referansı](.github/docs/schema-management.md)*

## A5. Görev Panosu (Özet)
**Öncelik**: P1 kritik, P2 önemli, P3 iyileştirme

### BACKLOG (Kritik)
- **P1: Deep Logic Debugging & Production Readiness Assessment (A35)** — %100 test coverage'a rağmen gerçek kullanım mantık hatalarını tespit ve düzeltme
- **P1: Advanced Strategy Enhancements** — Cross-exchange arbitrage, liquidity-aware execution
- **P1: Multi-asset portfolio correlation** — Risk-adjusted position sizing
- **P1: Advanced ML Pipeline** — Real-time sentiment analysis, machine learning features

### IN-PROGRESS
- **P1: Cross-exchange arbitrage detection** — Multi-CEX price difference analysis

### COMPLETED (Son Başarılar)
- ✅ **TradeStore API Method Mismatch Fix** — Performance dashboard API hatası çözüldü
- ✅ **Emergency Stop Method Implementation** — Dual emergency stop functionality
- ✅ **Bot Control Center Enhancement** — Real-time telemetry, automation, dashboard
- ✅ **A30-A32 Strategy Implementations** — HTF Filter, Meta-Router, Edge Hardening ALL COMPLETED

*Detaylı görev yönetimi için: [Görev Panosu ve Yol Haritası](.github/docs/task-management.md)*

## A6. Non-Fonksiyonel Gereksinimler (Özet)
| Kategori | Hedef |
|----------|-------|
| Performans | Sinyal < 50ms, Emir < 800ms |
| Güvenilirlik | %100 determinism, 0 API leak |
| Observability | p95 latency < 5dk |
| Recovery | Reconciliation < 5sn |

*Detaylı NFR için: [Teknik Gereksinimler](.github/docs/technical-requirements.md)*

## A7. Yol Haritası Milestones (Özet)
- ✅ **M1-M4**: State Integrity, Risk & Execution, Observability, Ops & Governance ALL COMPLETED
- ✅ **A30**: HTF Filter, Time Stop, Spread Guard ALL COMPLETED
- ✅ **A31**: Meta-Router & Ensemble System ALL COMPLETED
- ✅ **A32**: Edge Hardening System ALL COMPLETED
- ✅ **A33**: Bot Control Center ALL PHASES COMPLETED
- 🔄 **A35**: Deep Logic Debugging & Production Readiness IN-PROGRESS

*Detaylı milestone planları için: [Proje Milestone'ları](.github/docs/task-management.md#a9-yol-haritası-milestones)*

## A8. Major CR Kayıtları (Özet)
**Son Kritik CR'ler**:
- ✅ **CR-0085**: Endpoint Switch Safety (testnet default, prod explicit)
- ✅ **CR-0087**: Executions Dedup Persistence (idempotent operations)
- ✅ **CR-BOT-CONTROL-***: Bot Control Center comprehensive implementation
- ✅ **CR-A31-META-ROUTER**: 4 specialist strategies coordination
- ✅ **CR-A32-EDGE-HARDENING**: Edge health monitoring & cost rules

*Detaylı CR kayıtları için: [Change Request Kayıtları](.github/docs/cr-records.md)*

# DURUM ÖZET (v2.45)
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
