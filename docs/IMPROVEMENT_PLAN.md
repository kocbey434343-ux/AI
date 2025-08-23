# Geliştirme ve İyileştirme Planı

Bu plan mevcut proje durumunun analizi ve yüklü VS Code eklentilerinin verimli kullanımını esas alır. Önceliklendirme: (P0 Kritik) > (P1 Yüksek) > (P2 Orta) > (P3 İsteğe bağlı).

---
## Özet Durum
- Testler: Mevcut test suite (11+ test) PASS, 1 skip (gözlem). Kapsam sınırlı: risk, ws yardımcıları, bazı indikatörler.
- Hata Yönetimi: Çok sayıda geniş `except Exception` (200+ match). Silikleştirilmiş hata teşhisi & olası sessiz başarısızlık.
- Risk/Trade Döngüsü: Quantize ve slippage iyileştirmeleri eklendi; partial fills sonrası RR yeniden kalibrasyonu eksik.
- Observability: Log var ancak yapılandırılmış (JSON) ve metrik toplama/panel yok.
- Mimarî: Binance API sarıcı + Trader monolitik; backtest ve canlı mantık ayrımı kısmen karışık.
- Performans: İndikatör hesapları tek-thread, uygun ancak ileride paralellik fırsatı var.
- Güvenlik: API key yönetimi `.env` varsayımı; gizli konfig doğrulaması yok.

---
## 1. Güvenilirlik & Hata Yönetimi (P0)
| Görev | Açıklama | Araç/Eklenti |
|-------|----------|--------------|
| Targeted Exception Refactor | Kritik akışlarda (order, trade close, data fetch) geniş `except` -> spesifik (ConnectionError, JSONDecodeError, sqlite3.Error) | SonarLint, GitLens blame |
| Error Classification | `utils/logger` içine `log_exception(exc, ctx:dict)` yardımı ile tür bazlı sınıflandırma | Ruff (unused vars) |
| Retry Strategy | Geçici network hataları için (örn. 429, timeout) exponential backoff decorator | SonarLint |
| Health Check Genişletme | `api/health_check.py` endpoint'leri: WS latency, DB write test | SonarLint |

## 2. Risk Yönetimi Doğruluğu (P0)
| Görev | Açıklama | Araç |
|-------|----------|------|
| Partial Fill Recalc | Kısmi gerçekleşmede SL/TP'yi kalan boyuta göre RR koruyarak yeniden hesapla | Pytest, Todo Tree |
| Dynamic ATR Sizing | ATR volatilite yükselince risk yüzdesi dinamik azalt | Data Wrangler (analiz) |
| Daily Loss Lock Audit | Günlük kilit aç/kapa mantığına test (flag dosya senaryoları) | Pytest |

## 3. Emir & Durum Tutarlılığı (P1)
| Görev | Açıklama | Araç |
|-------|----------|------|
| Order State Machine | OPENING -> OPEN -> SCALING -> CLOSING -> CLOSED enum | Ruff (naming) |
| Reconcile Enhancement | `sync_open_positions` gerçek borsa poz + trade_store delta diff raporu | GitLens |
| OCO Simulation Consistency | Spot OCO stub: DB'ye sanal protective emirleri kaydet | Todo Tree |

## 4. Test Kapsamı ve Kalite (P1)
| Görev | Açıklama | Araç |
|-------|----------|------|
| Unit: quantize edge | minQty altı -> 0, stepSize yuvarlama | Pytest |
| Unit: partial exit logic | r_mult geçişleri & stop breakeven | Pytest |
| Unit: correlation guard | threshold varyasyon | Pytest |
| Integration: trade lifecycle | Sinyal -> açık poz -> partial -> close | Pytest, Data Preview (log inceleme) |
| Snapshot: indicator weights | Belirli candle setinde skor deterministik | Data Wrangler |

## 5. Performans & Kaynak (P2)
| Görev | Açıklama | Araç |
|-------|----------|------|
| Profil Tick Path | `process_price_update` CPU profili (cProfile) | Python, GitLens |
| Caching Indicators | Aynı sembol için yakın zamanda hesaplanmış gösterge cache | Ruff |
| Async Price Stream | `price_stream` için asyncio + queue -> Trader tüketici | SonarLint |

## 6. Mimarî Ayrıştırma (P2)
| Görev | Açıklama | Araç |
|-------|----------|------|
| Exchange Interface | `IExchange` protokol -> BinanceAPI implementasyonu | Ruff (typing) |
| Strategy Plug-ins | Signal generator modular pipeline (preprocess, indicators, scoring) | Todo Tree |
| Backtest Isolation | Backtest modüllerini `backtest/` altına saf bağımlılıklarla izole | GitLens |

## 7. Gözlemlenebilirlik & Metrikler (P1)
| Görev | Açıklama | Araç |
|-------|----------|------|
| Structured Logging | JSON satır + context (trace_id, symbol) | Output Colorizer |
| Metrics Store | `metrics` tablosu (key, val, ts) + API raporu | Database Client 2 |
| Latency Histogram | Order latency bucket kaydı | Data Preview |
| PnL Attribution | ATR yüksek/düşük dönem PnL karşılaştırma script | Data Wrangler |

## 8. Veri & Analiz (P2)
| Görev | Açıklama | Araç |
|-------|----------|------|
| Feature Export | İşlem öncesi özellikleri CSV/Parquet dump | Data Wrangler |
| Hyperparam Grid Log | Kalibrasyon çıktılarında param-set id -> config mapping | Excel Viewer |

## 9. Güvenlik & Uyumluluk (P1)
| Görev | Açıklama | Araç |
|-------|----------|------|
| Secrets Validation | Startup'ta gerekli env var mı; eksik log uyarı | SonarLint |
| Key Rotation Reminder | Otomatik TODO oluştur (date diff) | Todo Tree |
| Dependency Scan (Opsiyonel) | Snyk CLI pipeline entegrasyonu (extension başarısız) | — |

## 10. Developer Experience (P1)
| Görev | Açıklama | Araç |
|-------|----------|------|
| Pre-commit Hooks | black + ruff + isort otomatik | Ruff, Black |
| Template Tests | Yeni strateji test şablon dosyası | GitLens |
| Docs Live Update | README metrik snippet üretim script | Data Preview |

---
## Öncelikli İlk 7 Görev (Sprint 1 Önerisi)
1. Targeted exception refactor (order & trade path) [P0]
2. Partial fill risk recalculation & test [P0]
3. Quantize edge test + correlation guard test [P1]
4. Structured logging format (JSON) [P1]
5. Metrics table + latency histogram [P1]
6. Order state machine enum + usage [P1]
7. Pre-commit hook + CI lint gate [P1]

---
## Geniş `except` Azaltma Yaklaşımı
- Desen sınıfları: Network (requests.Timeout, ConnectionError), API (BinanceAPIException), Parse (ValueError, JSONDecodeError), DB (sqlite3.Error).
- Wrapper decorator: `@handle_errors(map={...})` -> log + rethrow / fallback.

---
## Structured Log Örneği
```json
{
  "ts": "2025-08-23T12:34:56.789Z",
  "level": "INFO",
  "component": "Trader",
  "event": "order_open",
  "symbol": "BTCUSDT",
  "side": "BUY",
  "size": 0.0025,
  "entry": 64000.5,
  "sl": 63200.0,
  "tp": 65600.0,
  "latency_ms": 84.3
}
```

---
## Test Genişletme Planı
- `tests/test_quantize.py`: minQty, stepSize, precision.
- `tests/test_partial_exit.py`: r_mult geçişleri.
- `tests/test_correlation_guard.py`: sentetik korelasyon veri seti.
- `tests/test_trade_lifecycle.py`: tam giriş -> partial -> trailing -> kapanış.

---
## Metodik Uygulama Sırası
1. (Refactor) Exception daraltma + logging altyapı güncelle.
2. (Logic) Partial fill & RR recalculation.
3. (Test) Yeni birim testleri ekle; CI lokal koş.
4. (Observability) JSON log + metrics tablosu.
5. (DX) Pre-commit, Ruff hatalarını sıfırla.
6. (Architecture) State machine & exchange interface.
7. (Optimization) Profil + caching.

---
## Eklenti Kullanım Bağlantıları
- Ruff / Black / isort: Kod tutarlılığı; pre-commit script.
- SonarLint: Potansiyel bug & kod kokusu baseline.
- Todo Tree: Her görev için `# TODO[P1]: ...` etiketi.
- GitLens: Refactor commit izlenebilirliği.
- Data Wrangler / Data Preview: PnL & feature analizi.
- Database Client 2: metrics & trades sorguları.
- Error Lens: Anında satır içi hata.

---
## Takip
Bu dosya per sprint güncellenecek. Tamamlanan görevler işaretlenecek.

