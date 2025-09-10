#!/usr/bin/env python3
import sys
# Clear cached modules
[sys.modules.pop(k, None) for k in list(sys.modules.keys()) if 'config.settings' in k or 'src.api' in k]

from dotenv import load_dotenv
load_dotenv()

from src.api.binance_api import BinanceAPI

def test_v2_api():
    print("🔄 Testing v2 endpoint...")
    
    api = BinanceAPI()
    
    # Test v2 position endpoint
    try:
        raw = api._signed_request_v2('GET', '/fapi/v2/positionRisk')
        print(f"✅ API Success! Count: {len(raw)}")
        
        # Show first position if any
        if raw:
            print(f"📊 First position: {raw[0]}")
        else:
            print("📋 No positions found")
            
    except Exception as e:
        print(f"❌ API Error: {str(e)}")
        
        # Try v1 for comparison
        try:
            print("🔄 Trying v1 fallback...")
            raw_v1 = api._signed_request('GET', '/fapi/v1/positionRisk')
            print(f"✅ V1 Success! Count: {len(raw_v1)}")
        except Exception as e1:
            print(f"❌ V1 Also Failed: {str(e1)}")

if __name__ == "__main__":
    test_v2_api()
