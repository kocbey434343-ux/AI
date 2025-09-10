"""
KARLI STRATEJİ GELİŞTİRME PLANI - CRITICAL IMPLEMENTATION
======================================================

TARGET: 0.26% -> 1.18%+ EXPECTANCY (4.5X İYİLEŞTİRME)
STATUS: P0 CRITICAL - EN ÖNCELİKLİ GÖREV

## 1. MEVCUT DURUM ANALİZİ
❌ Sorunlar:
- Sadece 8 trade/test period (çok az)
- 0.26% expectancy (maliyetler sonrası)
- Tek indikatör yaklaşımı (RSI veya basic signals)
- Static risk management
- Market timing yok

✅ Güçlü yönler:
- 62.5% win rate (iyi temel)
- Temel risk yönetimi mevcut
- UI sistemi hazır
- Backtest framework çalışıyor

## 2. GELİŞMİŞ STRATEJİ HEDEFLERİ
🎯 Primary Target:
- 40+ trade/month (vs 8 total)
- 65%+ win rate (vs 62.5%)
- 1.0%+ expectancy (vs 0.26%)
- 2.0+ Sharpe ratio
- <5% max drawdown

## 3. UYGULAMA YOL HARİTASI

### PHASE 1: MULTI-INDICATOR CONFLUENCE (24h)
1.1 RSI + MACD + Bollinger Confluence
   - File: src/indicators.py - add confluence_score()
   - Logic: Tüm 3 indikatör aynı yönde sinyal = trade
   - Test: Confluence threshold optimization

1.2 Signal Generator Update  
   - File: src/signal_generator.py
   - Add: multi_indicator_signal()
   - Remove: Single indicator reliance

### PHASE 2: DYNAMIC RISK MANAGEMENT (24h)
2.1 ATR-Based Position Sizing
   - File: src/risk_manager.py
   - Add: calculate_atr_position_size()
   - Formula: risk_amount / (entry - stop_loss)

2.2 Dynamic Stop Loss/Take Profit
   - Stop: 1.5x ATR below entry
   - TP: 3.0x ATR above entry (3:1 ratio)
   - Trailing: ATR-based adjustment

### PHASE 3: MARKET TIMING FILTERS (24h)
3.1 Volatility Filter
   - High volatility hours: 13:00-17:00 UTC
   - Avoid: Asian low-volume hours
   - Add: volatility_filter() in signal_generator

3.2 Trend Strength Filter
   - ADX > 25 for strong trend
   - Avoid sideways markets (ADX < 20)
   - Add: trend_strength_filter()

### PHASE 4: COST OPTIMIZATION (12h)
4.1 Spread-Aware Entry
   - Check bid-ask spread < 0.02%
   - Time-based spread optimization
   - Add: spread_filter()

4.2 Liquidity Filter
   - Minimum volume: 24h volume > $100M
   - Order book depth check
   - Add: liquidity_filter()

## 4. TECHNICAL IMPLEMENTATION

### 4.1 Enhanced Indicators Class
```python
class AdvancedIndicators:
    def confluence_score(self, df):
        rsi_signal = self.rsi_signal(df)
        macd_signal = self.macd_signal(df) 
        bb_signal = self.bollinger_signal(df)
        return (rsi_signal + macd_signal + bb_signal) / 3
        
    def market_regime(self, df):
        # Trend/Range detection
        adx = self.calculate_adx(df)
        return 'trending' if adx > 25 else 'ranging'
```

### 4.2 Dynamic Risk Manager
```python
def calculate_dynamic_position_size(self, symbol, entry_price, atr):
    risk_amount = self.account_balance * self.risk_per_trade_pct
    stop_distance = atr * 1.5
    position_size = risk_amount / stop_distance
    return min(position_size, self.max_position_size)
```

### 4.3 Advanced Signal Generator
```python
def generate_advanced_signal(self, symbol, df):
    # Multi-indicator confluence
    confluence = self.indicators.confluence_score(df)
    if confluence < 0.7:  # Need strong confluence
        return None
        
    # Market timing filters
    if not self.volatility_filter(df):
        return None
        
    if not self.trend_filter(df):
        return None
        
    # Cost filters  
    if not self.spread_filter(symbol):
        return None
        
    return self.build_signal(symbol, df)
```

## 5. BACKTEST VALIDATION PLAN

### 5.1 A/B Testing
- Current Strategy: 8 trades, 0.26% expectancy
- Advanced Strategy: Target 40+ trades, 1.0%+ expectancy
- Metrics: Sharpe, win rate, max drawdown

### 5.2 Walk-Forward Analysis
- Train: 60 days data
- Test: 30 days forward
- Re-optimize: Rolling window

### 5.3 Stress Testing
- Bear market periods
- High volatility events
- Low liquidity conditions

## 6. IMPLEMENTATION SCHEDULE

Week 1:
- Day 1-2: Multi-indicator confluence
- Day 3-4: Dynamic risk management  
- Day 5-6: Market timing filters
- Day 7: Integration testing

Week 2:
- Day 1-2: Cost optimization
- Day 3-4: Backtest validation
- Day 5-6: Parameter optimization  
- Day 7: Live testing preparation

## 7. SUCCESS CRITERIA
✅ Minimum 30 trades/month
✅ 1.0%+ expectancy after all costs
✅ 65%+ win rate maintained
✅ Sharpe ratio > 2.0
✅ Max drawdown < 5%
✅ Profit factor > 2.0

## 8. RISK MITIGATION
- Conservative position sizing (1-2% risk/trade)
- Maximum 3 concurrent positions
- Daily loss limit: 5%
- Emergency stop: 10% total drawdown

## 9. FILES TO MODIFY
Priority files for immediate work:
1. src/indicators.py - Add confluence scoring
2. src/signal_generator.py - Multi-indicator logic
3. src/risk_manager.py - Dynamic position sizing
4. src/backtest/calibrate.py - Enhanced backtesting
5. src/backtest/realistic_backtest.py - Fix imports

## 10. NEXT IMMEDIATE ACTIONS
1. Fix realistic_backtest.py import issues
2. Add confluence_score to indicators.py
3. Test multi-indicator signal generation
4. Compare results with current strategy
5. Implement dynamic position sizing

TARGET COMPLETION: 7 DAYS
EXPECTED RESULT: 4X+ KARLILLIK ARTIŞI (0.26% -> 1.18%)
"""
