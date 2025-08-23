yapılacaklar.txt listesini takip et güncelle
yapılandırmalarını kayıt defteri.txt kaydet
```text
Agent Sistem Promptu — Çatışmasız Proje Akışı (Kripto Trade Botu)
SSoT (Single Source of Truth) DÖKÜMANI
```

# 0. Çekirdek İlke & Kullanım
- Türkçe konuş.
- Bu dosya SSoT: başka yerdeki çelişen içerikler geçersizdir.
- Her değişiklik önce CR (Change Request) olarak bu dosyada teklif → onay → yama.
- Kod yamaları minimal (satır odaklı). Tam dosya overwrite sadece ilk oluşturma veya büyük refactor ADR’si ile.
- Test-Önce: Kabul kriteri + test eklenmeden uygulama yapılmaz.
- Geriye dönük uyumluluk varsayılır; kırılma = yeni major ADR.

# 1. A1 Proje Özeti
Amaç: Binance (spot/futures) üzerinde risk kontrollü, modüler, izlenebilir, otomatik kripto işlem botu.
Kapsam: Sinyal üretimi, risk yönetimi, emir yürütme (ana + koruma emirleri), trailing & partial exits, metrik kayıt, UI.
Hariç: Karmaşık HFT mikro yapı, derin öğrenme model eğitimi (ileride ADR gerekli).
Paydaş: Trader/kullanıcı, geliştirici, kalite (test), operasyon.
Kısıtlar: Güvenlik (API key sızıntı yok), düşük gecikme kritik değil ama tutarlılık önemli, offline mod zorunlu.

# 2. A2 Sözlük / Terimler
R-Multiple: (Fiyat - Entry)/Risk.
Koruma Emirleri: Stop ve Take Profit (spot OCO veya futures STOP/TPSL).
Partial Exit: Pozisyonun kademeli realize edilmesi.
Adaptive Risk: ATR yüzdesine göre boyut ölçekleme.

# 3. A3 Modül Kataloğu (Registry)
| MOD-ID | Ad | Konum | Sorumluluk | Bağımlılıklar | Durum |
|--------|----|-------|------------|---------------|-------|
| MOD-CORE-TRADER | Trader Orchestrator | src/trader/core.py | Yaşam döngüsü, guard çağrıları, state | MOD-RISK, MOD-EXEC, MOD-GUARDS, MOD-TRAIL, MOD-METRICS, MOD-UTILS-STORE | active |
| MOD-EXEC | Execution | src/trader/execution.py | Pozisyon aç/kapa, koruma emirleri, boyut | MOD-RISK, API-BINANCE | active |
| MOD-GUARDS | Guards | src/trader/guards.py | Halt, günlük risk, korelasyon, hacim, outlier | MOD-UTILS-STORE, MOD-CORE-TRADER | active |
| MOD-TRAIL | Trailing & Partial | src/trader/trailing.py | Kısmi çıkış & trailing stop | MOD-CORE-TRADER | active |
| MOD-METRICS | Metrics | src/trader/metrics.py | Latency/slippage izleme, anomaly | MOD-CORE-TRADER | active |
| MOD-RISK | RiskManager | src/risk_manager.py | Stop, TP, boyutlama | Settings | active |
| MOD-UTILS-STORE | TradeStore | src/utils/trade_store.py | DB persist & sorgular | sqlite3, pandas | active |
| MOD-API-BINANCE | BinanceAPI Wrapper | src/api/binance_api.py | Emir & veri arabirimi | python-binance | active |
| MOD-CORR-CACHE | CorrelationCache | src/utils/correlation_cache.py | Korelasyon pencere & TTL | numpy | active |

# 4. A4 API & Şema Sözleşmeleri (Özet)
FN-EXEC-open_position(symbol, signal_ctx) -> bool (yan etkiler: DB insert, self.positions[symbol]).
FN-EXEC-close_position(symbol) -> bool (yan etkiler: DB update + state silme).
Positions State Schema: { side: str, entry_price: float, position_size: float, remaining_size: float, stop_loss: float, take_profit: float, atr: float|None, trade_id: int|None, scaled_out: list[(r, qty)] }
Koruma Emir State (spot): pos['oco_resp'] {ids: [int,...]} | (futures): pos['futures_protection'] {sl_id, tp_id}.
Değişikliklerde yeni alan ekleme = backward compatible (allowed), kaldırma = ADR major.

# 5. A5 Görev Panosu (Eski yapılacaklar gömülü)
Durum sütunları: BACKLOG, IN-PROGRESS, REVIEW, DONE.
Öncelik: P1 kritik, P2 önemli, P3 iyileştirme.

## 5.1 BACKLOG (Aktif)
P1: Açık pozisyon/emir reconciliation (open orders vs local) → CR planlanacak.
P1: Günlük risk reset otomasyonu.
P1: Anomaly tetiklenince risk azaltma / durdurma. (CR-0007)
P1: Kısmi fill kalan miktar için koruma emir revizyonu.
P1: Restart sonrası trailing & partial state tam persist (scaled_out + stop history).
P1: update_positions incremental diff.
P1: Toplam Unrealized PnL göstergesi UI entegrasyonu.
P1: Gün içi kademeli risk azaltma.
P1: DataFetcher stale veri tespiti.
P1: API key log sızıntı taraması.
P2: Central exception hook + görsel uyarı.
P2: Graceful shutdown snapshot.
P2: Korelasyon throttling, dynamic threshold.
P2: WS sembol limit & debounce konfigüre edilebilirlik.
P2: Parametre set yönetim UI.
P2: Trailing stop görselleştirme.
P2: Scale-out plan UI.
P2: Yapısal JSON logging toggle.
P2: Dark mode kontrast revizyonu.
... (kalan P2/P3 maddeleri önceki dosyadan içe alındı; kesik listesi arşiv bölümünde)

## 5.2 IN-PROGRESS
(boş)

## 5.3 REVIEW
— (boş)

## 5.4 DONE (Örnek Geçmiş)
P1: Modular Trader refactor.
P1: Koruma emir yerleştirme (spot OCO / futures STOP+TP).
P1: Weighted PnL backfill & reload open positions.
P1: Reconciliation döngüsü (open orders vs local diff logları) (CR-0003)
P1: Günlük Risk Reset Otomasyonu (CR-0004)
P1: Anomaly Risk Reduction (CR-0007)

# 6. A6 ADR Defteri
| ADR-ID | Başlık | Durum | Kısa Karar | Etki |
|--------|--------|-------|------------|------|
| ADR-0001 | Sözleşme-Öncelik & Patch Disiplini | accepted | API şemaları kırılmaz; CR+ADR olmadan major değişmez | Sürdürülebilir refactor |

### ADR-0001 (Özet)
Bağlam: Hızlı iterasyon sırasında bozulma ve tekrar riskini azaltmak.
Karar: Her yapısal değişiklik önce CR; küçük ek alan backwards-compatible serbest; test-önce.
Sonuç: İzlenebilirlik ↑, hız ilk an düşük ama orta vadede hata maliyeti ↓.

# 7. A7 CR Defteri
| CR-ID | Başlık | Durum | İlgili ADR | Kapsam | AC (özet) |
|-------|--------|-------|-----------|--------|-----------|
| CR-0001 | Modül Kataloğu iskeleti + Risk Motoru çerçevesi | done | ADR-0001 | A3 oluşturma | AC1 katalog tablo; AC2 risk modülü tanımlı |
| CR-0002 | Koruma Emir Entegrasyonu | done | ADR-0001 | open_position sonrası gerçek OCO/STOP | AC1 spot OCO; AC2 futures STOP+TP |
| CR-0003 | Reconciliation Döngüsü | done | ADR-0001 | Açık emir / pozisyon senk | AC1 fonksiyon iskeleti; AC2 log diff |
| CR-0004 | Günlük Risk Reset Otomasyonu | done | ADR-0001 | Halt flag & guard sayaç reset | AC1 tarih değişiminde flag sil; AC2 reset log; AC3 sayaçlar sıfır |
| CR-0005 | Test Çalıştırma Venv Aktivasyon Notu | done | ADR-0001 | Dokümana venv aktivasyon hatırlatma ekleme | AC1 A9'a not; AC2 Revizyon numarası artışı |
| CR-0006 | Pytest Öncesi Otomatik Venv Doğrulama Kuralı | done | ADR-0001 | Ajan davranış kurallarına zorunlu doğrulama maddesi | AC1 Section 17'e kural; AC2 revizyon artışı |
| CR-0007 | Anomaly Risk Reduction | done | ADR-0001 | Anomali sırasında dinamik risk azaltma | AC1 anomaly tetikte risk% *= ANOMALY_RISK_MULT; AC2 recovery sonrası orijinal risk% restore; AC3 test |
> CR-0003 AC Detay: AC1 _reconcile_open_orders fonksiyonu exchange open_orders + positions alıp local state ile diff üretir (hiçbiri kırılmadan). AC2: Her start() çağrısında tespit edilen farklar INFO log satırıyla 'RECON:' prefix'i ile listelenir (eksik koruma emri, fazla local pozisyon, çıplak exchange pozisyonu). Test: offline mock override ile sentetik listeler -> diff çıktısı doğrulama.

# 8. A8 Risk & Varsayım Kaydı
| Risk-ID | Tanım | Olası*Etki | Azaltım | Durum |
|---------|------|-----------|---------|-------|
| R-001 | Koruma emirleri yeniden kurulamazsa çıplak pozisyon | M*Y | Reconciliation döngüsü, periyodik doğrulama | açık |
| R-002 | Günlük risk reset atlanır | M*M | Tarih değişim tetikleyici, otomatik flag temizleme | açık |
| R-003 | Anomaly uyarısı aksiyonsuz | M*M | Otomatik risk reduce logic (gelecek CR) | açık |
| R-004 | Partial fill senaryosu tam test edilmedi | D*M | Simüle test + emir revizyon kodu | açık |

# 9. A9 Test Planı (Özet)
Smoke: Trader init, tek sinyal execute (offline).
Risk Guards: Günlük loss > eşik blok testi.
Execution: open_position ATR SL/TP varlığı.
Trailing: R-multiple geçince partial exit kaydı.
Koruma Emirleri: OFFLINE_MODE=False stub ile çağrı (gelecek mock).
Anomaly: Yapay yüksek latency listesi -> flag set.
Venv Aktivasyon Notu: Test ÇALIŞTIRMADAN ÖNCE her zaman sanal ortamı aktifleştir:
 - Windows PowerShell:  .venv\\Scripts\\Activate.ps1
 - CMD:                 .venv\\Scripts\\activate.bat
 - Pytest çağrısı örnek:  python -m pytest -vv --maxfail=1
Aktif python yolu doğrulama: python -c "import sys;print(sys.executable)" (çıktı .venv altında olmalı).

# 10. Operasyon Akışı (Oturum Açılış Rutin'i)
1. Oturum Hedefi yaz.
2. İlgili CR/ADR özetle.
3. Çakışma taraması (fonksiyon isimleri & şema).
4. Plan maddeleri (3–7 adım) -> A5 güncelle.
5. Onay sonrası patch uygula.

# 11. Görev İşleme Protokolü (Kısa)
CR -> Registry araması -> Sözleşme kontrol -> Test tasarım -> Patch taslağı -> Uygulama -> Doğrulama -> SSoT güncelle.

# 12. Şablonlar (Kısaltılmış Referans)
(S1–S5 hızlı erişim için; tam açıklama orijinal promptta)

S1 CR: CR-ID, Başlık, Gerekçe, Kapsam, Alternatifler, Etki Analizi, AC listesi, Test Plan Özeti, Durum.
S2 Modül Kartı: MOD-ID, Amaç, Bağımlılıklar, Sözleşmeler.
S3 Fonksiyon Kartı: FN-ID, İmza, Yan Etki.
S4 Test Plan: TP-ID, Senaryolar (Happy/Edge/Error), Gate.
S5 ADR: ADR-ID, Konu, Karar, Sonuçlar, Alternatifler.

# 13. Çakışma Önleme Mekanizmaları
- Registry Araması zorunlu (fonksiyon eklemeden önce A3 taranır).
- Sözleşme Kilidi: Schema kırıcı değişiklik -> yeni ADR + major increment.
- Değişmeyen Alan Seti: Oturum planında listelenmeyen dosyalar salt okunur.

# 14. Adlandırma & Versiyonlama
İsim: scope.verbNoun (örn: execution.openPosition) — Python tarafında snake_case fonksiyon, dokümanda camelCase soyut isim.
Versiyon: Şema kırılmadan alan ekleme minor (etiketlenmez, not düşülür). Kırılma -> ADR major.

# 15. Oturum Kapanış Raporu Şablonu
Oturum Hedefi / Yapılanlar / Güncellenen Artefaktlar / Açık Riskler / Sonraki Adımlar.

# 16. Arşiv (Tam Backlog Kopyası Kaynak)**
Önceki `yapılacaklar.txt` içeriği bu SSoT’a taşındı. Gerektiğinde geçmiş maddeler buradan yeniden sınıflanır.

# 17. Ajan Davranış Kuralları (Bu Dosya İçin)
- İzin sorma: Kritik dışı değişikliklerde CR onay blokunu kendin ver ve uygula.
- Yapılacaklar artık bu dosyada; `yapılacaklar.txt` kullanılmaz.
- Değişiklik sonrası: A3 / A5 / A7 / A6 ilgili satırlar güncellenmeli.
- Pytest ÇALIŞTIRMADAN ÖNCE her zaman aktif Python yolunu doğrula: `python -c "import sys;print(sys.executable)"` çıktısı `.venv` içermiyorsa PowerShell: `.venv\\Scripts\\Activate.ps1` (veya CMD: `.venv\\Scripts\\activate.bat`) komutuyla aktive ET; test komutları daima `python -m pytest` şeklinde çağrılacak.
- Ortam doğrulaması yapılmadan alınan test hataları geçersiz say ve önce ortamı düzelt.

# 18. Hızlı Kullanım Örnekleri
Yeni reconciliation döngüsü eklemek için: CR-0003 durumunu approved yap, AC test tanımla, patch uygula.

# 19. Durum
SSoT Revizyon: v1.6 (CR-0007 anomaly risk reduction testleri eklendi - risk azaltma & geri yukleme doğrulandı).

# 20. Ek Notlar
Kayıt defteri.txt değişiklik günlüğü devam edebilir; ancak yapısal kararlar bu dosyada tutulur.

---
Özet: Bu belge tüm yönetişim, backlog ve karar kayıtlarının tek kaynağıdır. Harici yapılacak listesi kaldırılmıştır.
