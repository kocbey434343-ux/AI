#!/usr/bin/env python3
import sys
import os

# Python path'e proje dizinini ekle
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.api.binance_api import BinanceAPI
from config.settings import Settings

def test_binance_api():
    print("Testing Binance API connection...")
    print(f"API Key: {Settings.BINANCE_API_KEY[:10]}...")
    print(f"Use Testnet: {Settings.USE_TESTNET}")
    
    try:
        api = BinanceAPI()
        print("✓ BinanceAPI initialized successfully")
        
        # Test ticker
        print("Testing get_ticker_24hr...")
        tickers = api.get_ticker_24hr()
        print(f"✓ Got {len(tickers)} tickers")
        
        # Test top pairs
        print("Testing get_top_pairs...")
        top_pairs = api.get_top_pairs(10)  # sadece 10 tane test için
        print(f"✓ Got {len(top_pairs)} top pairs: {top_pairs[:5]}...")
        
        print("✓ All tests passed!")
        return True
        
    except Exception as e:
        print(f"✗ Error: {str(e)}")
        print(f"Error type: {type(e).__name__}")
        return False

if __name__ == "__main__":
    success = test_binance_api()
    sys.exit(0 if success else 1)
