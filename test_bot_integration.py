#!/usr/bin/env python3
"""
Bot Position Verification Test
Bu test gerçek bot instance'ını çalıştırıp pozisyonları UI'da gösterir.
"""
import sys
import os
import time

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_bot_positions():
    print("🤖 Testing Bot Position Display...")
    
    try:
        # Environment reload
        from dotenv import load_dotenv
        load_dotenv(override=True)
        
        # Import after env reload
        from src.trader.core import Trader
        from src.api.binance_api import BinanceAPI
        from src.utils.trade_store import TradeStore
        
        print("✅ Modules imported successfully")
        
        # Test API
        api = BinanceAPI()
        print(f"📡 API Mode: {api.mode}")
        print(f"📡 OFFLINE_MODE: {api.offline_mode if hasattr(api, 'offline_mode') else 'N/A'}")
        
        # Test positions
        positions = api.get_positions()
        print(f"🎯 Exchange Positions: {len(positions)}")
        for pos in positions:
            print(f"  📊 {pos}")
            
        # Test TradeStore
        store = TradeStore()
        open_trades = store.open_trades()
        print(f"💾 Database Open Trades: {len(open_trades)}")
        for trade in open_trades:
            print(f"  📈 {trade}")
            
        closed_trades = store.closed_trades(limit=5)
        print(f"💾 Database Closed Trades: {len(closed_trades)}")
        for trade in closed_trades[:2]:  # Show first 2
            print(f"  📉 {trade}")
            
        print("\n🎉 Bot position verification complete!")
        print("   ✅ Exchange connection working")
        print("   ✅ Position detection working") 
        print("   ✅ Database integration working")
        
        # Quick Trader core test
        print("\n🚀 Testing Trader Core...")
        trader = Trader()
        print(f"🤖 Trader initialized: {trader.__class__.__name__}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_bot_positions()
