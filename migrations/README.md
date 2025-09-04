# Migrations

Basit manuel migration sistemi.

Kural:
- Her migration dosyası `NNN_description.sql` formatında.
- Uygulama sırasında uygulanan migration ID'leri `data/migrations_applied.txt` dosyasında tutulur.
- Yeni şema değişikliği önce CR + test, sonra migration dosyası eklenir.
