#!/usr/bin/env python3
from src.api.binance_api import BinanceAPI

def test_account_and_positions():
    print("🔄 Testing account info and positions...")
    
    api = BinanceAPI()
    
    # Test account balance
    try:
        balance = api.get_account_balance()
        print(f"💰 Account balance: {balance}")
    except Exception as e:
        print(f"❌ Balance error: {e}")
        
    # Test raw positions to see all data
    try:
        raw = api._signed_request_v2('GET', '/fapi/v2/positionRisk')
        print(f"📊 Total positions in API: {len(raw)}")
        
        # Show positions with non-zero amounts
        non_zero = [p for p in raw if float(p.get('positionAmt', 0)) != 0]
        print(f"📈 Non-zero positions: {len(non_zero)}")
        
        for pos in non_zero[:5]:  # Show first 5
            amt = pos.get('positionAmt')
            symbol = pos.get('symbol')
            entry = pos.get('entryPrice')
            pnl = pos.get('unRealizedProfit')
            print(f"  🎯 {symbol}: {amt} @ {entry} (PnL: {pnl})")
            
    except Exception as e:
        print(f"❌ Positions error: {e}")

if __name__ == "__main__":
    test_account_and_positions()
