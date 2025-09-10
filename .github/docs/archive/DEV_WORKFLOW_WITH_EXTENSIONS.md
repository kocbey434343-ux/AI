# Geliştirilmiş Geliştirme Akışı (Extensions Entegre)

Aşağıdaki rehber mevcut eklentileri projede maksimum verimle kullanman için hazırlanmıştır.

## Kod Kalitesi
- Black Formatter: Kaydettiğinde otomatik format. `settings.json` içinde `"editor.formatOnSave": true` + `"python.formatting.provider": "black"` ayarla.
- Ruff: Hızlı lint. Hataları panelde gör. Gerekirse belirli kuralı devre dışı bırak: `# noqa: RUF100`.
- isort (Ruff entegre): Import sıralama Ruff tarafından otomatik düzeltilebilir.
- SonarLint: Daha geniş koku ve potansiyel bug tespiti. Sorunları GitLens blame ile birleştirip sorumlu commit'i analiz et.

## Test ve Hızlı Döngü
- Pytest + `pytest.ini` eklendi. Test dosyalarında kaydettiğinde VSCode Test Explorer ile çalıştır.
- Todo Tree: Yeni test gereksinimleri için kodda `# TODO: add partial fill test` işaretle.

## Veri Analizi
- Data Wrangler: DataFrame sonuçlarını hızlı görselleştir (örn. sinyal özellikleri tuning).
- Data Preview & Excel Viewer & Rainbow CSV: `data/processed/*.json` veya CSV loglarını hızlı incele.

## Log / Debug
- Output Colorizer + Error Lens: Log penceresinde renk ve satır içi hata.
- GitLens: Hangi değişikliğin hatayı getirdiğini blame ile izle.

## DB İnceleme
- Database Client 2: `data/trades.db` aç, basit SELECT sorguları çalıştır.
- (SQLite extension başarısız; alternatife gerek yok şimdilik.)

## GUI / Qt
- Qt for Python: Form tasarım, sinyal-slot inceleme.

## Güvenlik ve Risk
- SonarLint: Potansiyel risk desenleri.
- (Snyk kurulum başarısız; istenirse daha sonra CLI ile `snyk test` eklenebilir.)

## PowerShell
- Proje batch/script bakımı (örn. otomatik kalibrasyon çalıştırma).

## Önerilen Ayar Örneği
```jsonc
{
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.fixAll": true,
    "source.organizeImports": true,
    "source.fixAll.ruff": true
  },
  "python.formatting.provider": "black",
  "ruff.format.enabled": true,
  "ruff.lint.run": "onSave",
  "files.trimTrailingWhitespace": true,
  "files.insertFinalNewline": true
}
```

## Yapılacaklar (Extensions Odaklı)
- [ ] Partial fill ve quantize edge-case testleri ekle.
- [ ] Lint raporundan kritik 0 hataya in.
- [ ] trades.db için sık sorgular snippet oluştur.
- [ ] Snyk veya alternatif bağımlılık taraması entegre et.
- [ ] SonarLint + Ruff çakışan kuralları incele.

Bu belge yeni ihtiyaçlarda güncellenebilir.
