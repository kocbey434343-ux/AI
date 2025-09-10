# CR-0082: Incremental UI Table Updates

## Amaç
UI tablolarında tam yeniden çizim yerine incremental diff kullanarak performans optimizasyonu.

## Problem
- `update_positions` her çağrıldığında tüm tablo sıfırlanır ve yeniden doldurulur
- `setRowCount(len(data))` maliyetli operasyon
- Büyük pozisyon listelerinde UI freeze riski

## Çözüm
- Mevcut satırları korunarak sadece değişen satırları güncelle
- Yeni pozisyonlar için `insertRow()` 
- Kapanan pozisyonlar için `removeRow()`
- Mevcut pozisyonlar için sadece değişen hücreleri güncelle

## Kapsam
- `update_positions` için positions table
- `refresh_closed_trades` için closed_table  
- `refresh_scale_out_tab` için scale_out table

## Yaklaşım
1. `_incremental_table_update(table, old_data, new_data, key_func)` helper
2. Key-based diff algoritması
3. Row-level ve cell-level update
4. Performance measurement

## Test
- Büyük pozisyon listesi ile benchmark
- Add/remove/update senaryoları
- UI responsiveness kontrolü

Priority: P2 (Performance Optimization)
Estimated: 6-8 hours
