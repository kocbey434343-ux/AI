#!/usr/bin/env python3
"""
Testnet mock/dummy data temizleme scripti
Sadece gerçek testnet pozisyonlarını bırakır, mock verileri siler
"""

import sqlite3
from src.utils.trade_store import TradeStore
from src.api.binance_api import BinanceAPI
from dotenv import load_dotenv

def main():
    # .env yükle
    load_dotenv(override=True)
    
    # Gerçek testnet pozisyonlarını al
    print("=== GERÇEK TESTNET POZİSYONLARI KONTROL EDİLİYOR ===")
    api = BinanceAPI()
    real_positions = api.get_positions()
    
    real_symbols = {pos['symbol'] for pos in real_positions}
    print(f"Gerçek testnet sembolleri: {real_symbols}")
    
    # Veritabanı bağlantısı
    db_path = 'data/testnet/trades.db'
    ts = TradeStore(db_path)
    
    print(f"\n=== VERİTABANI TEMİZLENİYOR: {db_path} ===")
    
    # Mevcut durumu göster
    open_trades = ts.open_trades()
    closed_trades = ts.closed_trades()
    
    print(f"Açık trades: {len(open_trades)}")
    print(f"Kapalı trades: {len(closed_trades)}")
    
    # Mock sembolleri tespit et
    mock_symbols = set()
    for trade in open_trades + closed_trades:
        symbol = trade['symbol']
        if symbol not in real_symbols:
            mock_symbols.add(symbol)
    
    print(f"Mock/dummy semboller: {sorted(mock_symbols)}")
    
    if not mock_symbols:
        print("Temizlenecek mock data yok!")
        return
    
    # SQL connection direkt al
    conn = sqlite3.connect(db_path)
    
    try:
        # Mock trade'leri sil
        for symbol in mock_symbols:
            print(f"Temizleniyor: {symbol}")
            
            # trades tablosundan sil
            conn.execute("DELETE FROM trades WHERE symbol = ?", (symbol,))
            
            # executions tablosundan sil
            conn.execute("DELETE FROM executions WHERE symbol = ?", (symbol,))
        
        # Değişiklikleri kaydet
        conn.commit()
        print(f"✅ {len(mock_symbols)} mock sembol temizlendi!")
        
        # Son durumu kontrol et
        ts_new = TradeStore(db_path)
        new_open = ts_new.open_trades()
        new_closed = ts_new.closed_trades()
        
        print(f"\n=== TEMİZLEME SONRASI ===")
        print(f"Açık trades: {len(new_open)}")
        print(f"Kapalı trades: {len(new_closed)}")
        
        if new_open:
            print("Kalan açık trades:")
            for trade in new_open:
                print(f"  {trade['symbol']}: {trade['side']} {trade['size']}")
        
        if new_closed:
            print("Kalan kapalı trades:")
            for trade in new_closed[:5]:  # İlk 5'ini göster
                print(f"  {trade['symbol']}: {trade['side']} {trade.get('size', 'N/A')}")
    
    finally:
        conn.close()

if __name__ == "__main__":
    main()
