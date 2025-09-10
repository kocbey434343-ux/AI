#!/usr/bin/env python3
from src.api.binance_api import BinanceAPI

def debug_positions():
    print("🔍 Debugging positions...")
    
    api = BinanceAPI()
    
    try:
        raw = api._signed_request_v2('GET', '/fapi/v2/positionRisk')
        
        for p in raw:
            amt = float(p.get('positionAmt') or 0.0)
            if abs(amt) > 0:  # Any non-zero
                print(f"🔍 Debug: {p.get('symbol')} amt={amt} abs={abs(amt)} threshold_check={abs(amt) < 1e-12}")
                entry_price = float(p.get('entryPrice') or 0.0)
                symbol = p.get('symbol')
                side = 'BUY' if amt > 0 else 'SELL'
                print(f"   Would add: {{'symbol': '{symbol}', 'side': '{side}', 'size': {abs(amt)}, 'entry_price': {entry_price}}}")
                
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    debug_positions()
