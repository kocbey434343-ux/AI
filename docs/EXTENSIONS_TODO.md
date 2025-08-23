# VS Code Extensions Reference

Bu dosya otomatik oluşturuldu. Projede kurulu ve önerilen eklentiler listesi ve amaçları:

## Kurulu / Başarılı
- Python, Pylance, Debugpy: Python geliştirme, dil zekası, debug
- Black Formatter: Kod formatı
- Ruff, isort: Lint + import sıralama
- Jupyter, Jupyter Keymap: Notebook çalıştırma
- Data Wrangler: Pandas veri keşfi
- GitLens: Gelişmiş git geçmişi
- GitHub Pull Requests and Issues: PR & Issue yönetimi
- Code Spell Checker: Yazım kontrolü
- Todo Tree: TODO/FIXME takibi
- SonarLint: Ek statik analiz
- Excel Viewer: CSV/Excel hızlı görünüm
- Data Preview: Veri önizleme (CSV/JSON/parquet)
- SQLite: (Kurulum denendi: HATA - ms-vscode.vscode-sqlite) -> Alternatif: "qwtel.sqlite-viewer" veya DB Browser harici araç
- EditorConfig: Tutarlı format
- Error Lens: Hataları satır üstünde göster
- Rainbow CSV: CSV renklendirme
- Output Colorizer: Log renklendirme
- PowerShell: PowerShell script geliştirme
- Qt for Python: PyQt/Pyside tooling
- IntelliJ IDEA Keybindings: Kısayol konforu

## Kurulumda Başarısız (manuel tekrar denenebilir)
- ms-vscode.vscode-sqlite (bir kez daha yüklendi ama hata döndü mü? İlk deneme başarısız olarak kaydedildi)
- snyk-security.vscode-vuln-cost
- trailofbits.codelingo
- benewagner.quicktypegen

## Notlar
- Güvenlik analizi için alternatif: Snyk (snyk-security.snyk-vulnerability-scanner) veya GitHub Advanced Security entegrasyonu.
- SQLite inceleme için: "cweijan.vscode-database-client2" zaten yüklü (Database Client 2) -> trades.db açmak için kullan.
- JSON -> Python model üretimi gerekirse çevrim içi quicktype veya pydantic model generator script yazılabilir.

## Yapılacaklar
- [ ] Başarısız eklenti kurulumlarını uygun alternatiflerle değerlendir
- [ ] SonarLint + Ruff birlikte kuralları çakışanları gözden geçir (ör: format vs stil)
- [ ] trades.db için sık sorgulara küçük snippet'lar ekle (gelecek adım)
- [ ] Güvenlik/bağımlılık taraması pipeline adımı ekle

Bu liste tercihini hatırlamak içindir; yeni ihtiyaç çıktıkça güncelle.
