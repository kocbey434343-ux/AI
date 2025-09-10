# API ŞEMASİ VE SÖZLEŞMELER

## Positions Şeması (Detaylı)

```python
position_schema = {
    "side": "BUY|SELL",           # Pozisyon yönü
    "entry_price": float,         # Giriş fiyatı
    "position_size": float,       # Toplam pozisyon boyutu
    "remaining_size": float,      # Kalan pozisyon boyutu (partial exit sonrası)
    "stop_loss": float,           # Stop loss fiyatı
    "take_profit": float,         # Take profit fiyatı
    "atr": float,                 # ATR değeri (risk hesaplama için)
    "trade_id": str,              # Unique trade identifier
    "scaled_out": [               # Partial exit kayıtları
        {"r_multiple": float, "quantity": float}
    ],
    "model_version": str,         # Strateji versiyonu
    "order_state": str,           # FSM state (INIT, OPEN, ACTIVE, CLOSED, etc.)
    "created_ts": str,            # ISO 8601 timestamp
    "updated_ts": str,            # Son güncelleme timestamp
    "symbol": str,                # Trading pair (BTCUSDT, etc.)
    "order_type": str,            # MARKET, LIMIT, etc.
    "oco_resp": dict,             # OCO response (spot için)
    "futures_protection": dict    # Futures protection orders
}
```

## Koruma Emirleri Şeması

### Spot OCO Response
```python
oco_resp = {
    "orderListId": int,
    "contingencyType": "OCO",
    "listStatusType": "EXEC_STARTED",
    "listOrderStatus": "EXECUTING",
    "orders": [
        {
            "symbol": str,
            "orderId": int,
            "side": "BUY|SELL",
            "type": "LIMIT_MAKER|STOP_LOSS_LIMIT",
            "status": "NEW"
        }
    ]
}
```

### Futures Protection
```python
futures_protection = {
    "sl_id": int,     # Stop Loss order ID
    "tp_id": int,     # Take Profit order ID
    "sl_status": str, # Order status
    "tp_status": str  # Order status
}
```

## Executions Şeması

```python
execution_schema = {
    "exec_id": str,               # Unique execution ID
    "trade_id": str,              # Trade reference
    "symbol": str,                # Trading pair
    "exec_type": str,             # order_fill, partial_exit, trailing_update, state_transition
    "side": "BUY|SELL",           # Execution side
    "quantity": float,            # Executed quantity
    "price": float,               # Execution price
    "commission": float,          # Fee paid
    "timestamp": str,             # ISO 8601 timestamp
    "order_id": int,              # Exchange order ID
    "dedup_key": str,             # Idempotency key (UNIQUE)
    "r_multiple": float,          # R-multiple at execution
    "pnl": float,                 # Realized PnL (if applicable)
    "state_from": str,            # FSM transition from (optional)
    "state_to": str               # FSM transition to (optional)
}
```

## Guard Events Şeması

```python
guard_event_schema = {
    "event_id": str,              # Unique event ID
    "guard": str,                 # daily_loss, correlation, volume, spread, etc.
    "symbol": str,                # Affected symbol (can be null for global)
    "reason": str,                # Human readable reason
    "extra": str,                 # JSON encoded additional data
    "severity": str,              # INFO, WARNING, ERROR, CRITICAL
    "timestamp": str,             # ISO 8601 timestamp
    "action_taken": str           # BLOCK, REDUCE, ALERT, etc.
}
```

## Ana Fonksiyon Sözleşmeleri

### Execution Functions
```python
def open_position(trader_instance, symbol: str, context: dict) -> bool:
    """
    Pozisyon açma fonksiyonu
    
    Args:
        trader_instance: Trader core instance
        symbol: Trading pair
        context: Signal context (side, confidence, atr, etc.)
    
    Returns:
        bool: True if successful, False otherwise
    
    Side Effects:
        - Database'e trade kaydı
        - Koruma emirleri yerleştirme
        - State transition logging
    """

def close_position(trader_instance, symbol: str, reason: str = "manual") -> bool:
    """
    Pozisyon kapatma fonksiyonu
    
    Args:
        trader_instance: Trader core instance
        symbol: Trading pair to close
        reason: Closure reason (manual, stop_hit, take_profit, time_stop)
    
    Returns:
        bool: True if successful, False otherwise
    
    Side Effects:
        - Market order placement
        - PnL calculation
        - Database update
        - Metrics recording
    """
```

### Risk Manager Functions
```python
def calculate_position_size(symbol: str, context: dict) -> float:
    """
    Pozisyon boyutu hesaplama
    
    Args:
        symbol: Trading pair
        context: Risk context (atr, confidence, balance)
    
    Returns:
        float: Position size in base currency
    
    Constraints:
        - MAX_POSITION_PCT compliance
        - MIN_NOTIONAL compliance
        - Risk per trade limits
    """

def validate_risk_limits(symbol: str, size: float) -> bool:
    """
    Risk limit validasyonu
    
    Args:
        symbol: Trading pair
        size: Proposed position size
    
    Returns:
        bool: True if within limits
    
    Checks:
        - Daily loss limits
        - Correlation limits
        - Position concentration
        - Leverage limits (futures)
    """
```

## API Rate Limiting & Error Handling

### Rate Limit Response
```python
rate_limit_error = {
    "code": -1003,
    "msg": "Too much request weight used; IP banned until..."
}

# Exponential backoff: 1s, 2s, 4s, 8s, 16s
# Max retry: 5 attempts
# Circuit breaker: 10 consecutive failures = 5 min pause
```

### Error Response Format
```python
api_error_response = {
    "code": int,                  # Binance error code
    "msg": str,                   # Error message
    "context": {                  # Additional context
        "symbol": str,
        "operation": str,
        "timestamp": str
    }
}
```

## WebSocket Message Formats

### Price Stream
```python
price_update = {
    "e": "24hrTicker",           # Event type
    "E": int,                    # Event time
    "s": str,                    # Symbol
    "c": str,                    # Close price
    "o": str,                    # Open price
    "h": str,                    # High price
    "l": str,                    # Low price
    "v": str,                    # Volume
    "q": str                     # Quote volume
}
```

### User Data Stream
```python
execution_report = {
    "e": "executionReport",      # Event type
    "E": int,                    # Event time
    "s": str,                    # Symbol
    "S": str,                    # Side
    "o": str,                    # Order type
    "q": str,                    # Quantity
    "p": str,                    # Price
    "X": str,                    # Current execution type
    "i": int,                    # Order ID
    "z": str,                    # Cumulative filled quantity
    "Z": str,                    # Cumulative quote qty
    "n": str,                    # Commission amount
    "N": str                     # Commission asset
}
```

## Database Constraints

### Unique Constraints
- `trades.trade_id` (PRIMARY KEY)
- `executions.dedup_key` (UNIQUE INDEX)
- `guard_events.event_id` (PRIMARY KEY)

### Foreign Key Constraints
- `executions.trade_id` → `trades.trade_id`
- `guard_events.trade_id` → `trades.trade_id` (nullable)

### Check Constraints
- `trades.position_size > 0`
- `trades.remaining_size >= 0`
- `trades.remaining_size <= position_size`
- `executions.quantity > 0`
- `executions.price > 0`
