### 2025-08-20 Histerezis & Eşik İyileştirmeleri
- Kalibrasyon artık trade simülasyonu yaparak global ve sembol bazında winrate, expectancy, max_consec_losses metriklerini üretir.
- Grid search tabanlı basit threshold optimizasyonu (expectancy öncelikli) eklendi; ilk adaylar tooltip olarak UI’da.
- Kalibrasyon sonucu sembol bazlı trade istatistiklerini açan yeni pencere: "Kalibrasyon Trade İstatistikleri" butonu.

- Runtime threshold dosyası `config/runtime_thresholds.json` artık çıkış (histerezis) eşiklerini de (buy_exit, sell_exit) saklıyor.
- Yükleme (`load_runtime_thresholds`) exit eşiklerini de uygular hale getirildi.
- Kalibrasyon (`run_calibration`) önerilen exit eşikleri (suggested_buy_exit_threshold, suggested_sell_exit_threshold) üretir.
- UI Control tabına manuel histerezis exit eşikleri için spinbox'lar eklendi; değişiklikler anında persist edilir.
- Kalibrasyon sonucu uygulandığında exit eşikleri de güncellenip kaydedilir.
- Dinamik skor renklendirme artık Settings.BUY/SELL_SIGNAL_THRESHOLD değerlerini ve exit zonlarını dikkate alıyor (yakın bölgeler soft renk tonları).
- Tooltip'lere aktif ve exit eşikleri eklendi.
- `_format_current_thresholds` metni exit eşiklerini gösteriyor.

# Session Summary (2025-08-19)

## Amaç ve Son Durum
Bu oturumda göstergenin (indikator) puanlama sistemi geliştirildi, ADX ve histerezis eklendi, dinamik pozisyon boyutu ve kalibrasyon istatistikleri genişletildi. Ardından PyQt5 arayüzüne (MainWindow) otomatik kalibrasyon zamanlayıcısı, yeni kontrol bileşenleri, sinyal tablosunda katkı (contributions) ve raw vs. final sinyal tooltip'leri eklendi. `main_window.py` içindeki girinti bozulmaları tamamen düzeltildi ve şu an sözdizimi hatası yok.

## Ana Değişiklikler
- Histerezis eşikleri: `Settings.BUY_EXIT_THRESHOLD`, `Settings.SELL_EXIT_THRESHOLD` (henüz SignalGenerator'da explicit kullanılmıyor; mantık var ama exit eşikleri açık entegrasyon yapılabilir).
- ADX entegrasyonu ve adaptif ağırlıklandırma.
- ATR stop-loss extraction bug fix.
- Dinamik position sizing (toplam skora göre ölçek).
- Kalibrasyon çıktılarına ADX ve ATR risk percentilleri eklendi (`backtest/calibrate.py`).
- Sinyal üretiminde: `signal_raw`, `contributions` alanları, histerezis state `_prev_signals`.
- UI: Kontrol sekmesi yeniden yazıldı, otomatik kalibrasyon checkbox + saat aralığı spin, sonuç ve ek istatistik label'ları, tablo tooltip'leri.
- `main_window.py` baş kısmı tamamen yeniden düzenlenip hatasız hale getirildi.

## Dosya Durumları (Öne Çıkanlar)
- `src/indicators.py`: Refaktör + contributions + ADX/ATR uyarlamaları (temiz).
- `src/signal_generator.py`: Histerezis (raw vs final) + contributions.
- `src/trader.py`: ATR fix + dinamik pozisyon boyutu.
- `src/backtest/calibrate.py`: Percentil ekleri.
- `src/ui/main_window.py`: Girinti sorunları çözüldü; otomatik kalibrasyon bileşenleri eklendi.

## Henüz Yapılabilecek / Açık Maddeler
1. Histerezis çıkış eşiklerini (BUY_EXIT_THRESHOLD / SELL_EXIT_THRESHOLD) SignalGenerator içinde net if/elif bloklarıyla kullanmak (şu an genel mantık var, parametreler tam devrede değilse ekle).
2. Otomatik kalibrasyon tetiklendiğinde (timer tick) sonuç uygulama opsiyonu: auto_apply aktifse direkt eşikleri güncelle.
3. Kalibrasyon sonrası eşiklerin kalıcı (persist) yazılması için settings dosyasına veya ayrı bir runtime json'a kaydetme.
4. Sinyal tablosuna bir ikon/badge ekleyerek raw != final durumunu görsel vurgulama (şu an sadece tooltip).
5. Test genişletme: ADX ağırlık adaptasyonu, histerezis scenario testleri.
6. UI'da eşik değerlerini gösteren mini panel (güncel AL/SAT ve önerilenler).

## Hızlı Devam Notları
- Otomatik kalibrasyon için toggle: `self.auto_calib_checkbox`; interval spin: `self.auto_calib_hours`.
- Timer callback: `_auto_calibration_tick()` -> `start_calibration()` guard içeriyor.
- Kalibrasyon sonuç label'ları: `self.calib_result_label`, ek istatistik: `self.calib_stats_label`.
- Contributions tooltip kolonu: skor (kolon 4). Raw vs final: sinyal kolonu (kolon 3) tooltip.

## Bir Sonraki Mantıklı Adım
Histerezis exit eşiklerinin açık uygulanması ve kalibrasyon sonrası otomatik persist. Sonrasında küçük bir test ekleyip (pytest) doğrulamak.

## Kısa Özet Tek Satır
"ADX + histerezis + dinamik risk + zengin kalibrasyon + UI otomatik kalibrasyon entegre edildi; main_window.py girinti sorunları düzeltildi; exit histerezis ve persist adımları sırada."  

---
Bu dosyayı tekrar açarak kaldığımız yeri hızla hatırlayabilirsin.
