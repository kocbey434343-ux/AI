import sys
import os

# Python path'e proje dizinini ekle
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Output'u dosyaya yaz
output_file = "test_output.txt"

def log_output(message):
    print(message)
    with open(output_file, "a", encoding="utf-8") as f:
        f.write(message + "\n")

# Dosyayı temizle
with open(output_file, "w") as f:
    f.write("")

log_output("Starting API test...")

try:
    from config.settings import Settings
    log_output(f"Settings loaded - API Key: {Settings.BINANCE_API_KEY[:10]}...")
    log_output(f"Testnet: {Settings.USE_TESTNET}")
    
    from binance import Client
    log_output("Binance client imported successfully")
    
    client = Client(
        api_key=Settings.BINANCE_API_KEY,
        api_secret=Settings.BINANCE_API_SECRET,
        testnet=Settings.USE_TESTNET
    )
    log_output("Client created successfully")
    
    # Test basic connection
    server_time = client.get_server_time()
    log_output(f"✓ Server time: {server_time}")
    
    # Test ticker
    tickers = client.get_ticker()
    log_output(f"✓ Got {len(tickers)} tickers")
    if tickers:
        log_output(f"First ticker: {tickers[0]}")
    
except Exception as e:
    log_output(f"✗ Error: {e}")
    import traceback
    log_output(traceback.format_exc())
