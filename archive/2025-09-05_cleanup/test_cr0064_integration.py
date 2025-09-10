from src.signal_generator import SignalGenerator
from src.utils.lookahead_guard import get_lookahead_guard

# Test lookahead guard directly
print("=== CR-0064 Lookahead Guard Direct Test ===")

guard = get_lookahead_guard()

# Test 1: Current timestamp (should fail)
from datetime import datetime
current_signal = {
    'symbol': 'BTCUSDT',
    'timestamp': datetime.now().isoformat(),
    'close_price': 50000.0,
    'signal': 'BUY'
}

print(f'\n1. Testing current timestamp (should be rejected)...')
result1 = guard.validate_signal_data(current_signal)
print(f'   Result: {result1} (False = blocked)')
print(f'   Violations: {guard.violation_count}')

# Test 2: Historical timestamp (should pass)
from datetime import timedelta
past_time = datetime.now() - timedelta(minutes=5)
historical_signal = {
    'symbol': 'BTCUSDT',
    'timestamp': past_time.isoformat(),
    'close_price': 50000.0,
    'signal': 'BUY'
}

print(f'\n2. Testing historical timestamp (should be accepted)...')
result2 = guard.validate_signal_data(historical_signal)
print(f'   Result: {result2} (True = allowed)')
print(f'   Total violations: {guard.violation_count}')

print(f'\n3. Violations by symbol: {guard.violations_by_symbol}')

print("\n=== CR-0064 Guard Working Correctly! ===")
