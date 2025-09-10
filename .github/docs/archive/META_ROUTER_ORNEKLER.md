# 🎬 Meta-Router Pratik Örnekler ve Senaryolar

## 📈 Senaryo 1: Bitcoin Güçlü Uptrend (S1 Dominant)

### Market Durumu:
- **BTC/USDT**: 42,000 → 48,000 (son 5 günde %14 artış)
- **ADX**: 38 (güçlü trend)
- **Volume**: 2.1x medyan
- **RSI**: 58 (nötr ama momentum var)
- **MACD**: Pozitif ve yükseliyor

### Rejim Skorları:
```python
trend_score = (38 - 10) / (40 - 10) = 0.93  # Çok güçlü trend
squeeze_score = 0.15  # BB genişledi, squeeze yok
chop_score = (1 - |58-50|/50) = 0.84  # Orta seviye
volume_score = 2.1  # Yüksek hacim
```

### Gating Sonucu:
- ✅ **S1 (Trend PB/BO)**: `trend_score≥0.35` ✓ + `squeeze_score<0.5 AMA ADX≥18` ✓
- ❌ **S2 (Range MR)**: `trend_score>0.25` ✗ 
- ❌ **S3 (Vol BO)**: `squeeze_score<0.6` ✗
- ❌ **S4 (XSect)**: Rebalance zamanı değil ✗

### S1 Analizi:
```python
# Confluence Scoring (S1)
rsi_score = 0.7     # RSI 58 - momentum olumlu
macd_score = 0.8    # MACD bullish crossover
bb_score = 0.6      # BB middle yakınında (pullback fırsatı)
confluence = (0.7 + 0.8 + 0.6) / 3 = 0.70

# S1 Sinyali
if confluence >= 0.65:  # Eşik aşıldı
    signal = "AL"
    confidence = confluence = 0.70
```

### Ensemble Karar:
```python
# Aktif sadece S1, ağırlığı 0.42 (son performansından dolayı yüksek)
weighted_score = 0.42 * 0.70 = 0.294
final_signal = "AL" 
final_confidence = 0.294 / 0.42 = 0.70
```

### Sonuç: **AL sinyali, %70 güven ile trade açılır** 🟢

---

## 📊 Senaryo 2: Ethereum Range-Bound (S2 Aktif)

### Market Durumu:
- **ETH/USDT**: 2,800-3,200 aralığında 3 hafta (% ±7)
- **ADX**: 16 (zayıf trend)
- **BB Bandwidth**: %5.2 (dar bantlar)
- **RSI**: 73 (aşırı alım)
- **Price**: BB üst bandına yakın

### Rejim Skorları:
```python
trend_score = (16 - 10) / (40 - 10) = 0.20  # Zayıf trend
squeeze_score = 0.35  # Orta seviye sıkışma
chop_score = 1 - |73-50|/50 = 0.54  # Chop var ama ideal değil
volume_score = 0.85  # Düşük hacim
```

### Gating Sonucu:
- ❌ **S1 (Trend PB/BO)**: `trend_score<0.35` ✗
- ✅ **S2 (Range MR)**: `trend_score≤0.25` ✓ + `chop_score≥0.6` ❌ 
- ❌ **S3 (Vol BO)**: `squeeze_score<0.6` ✗
- ❌ **S4 (XSect)**: Rebalance zamanı değil ✗

**Özel Durum**: S2 için `chop_score` 0.54 (eşik 0.6'ın altında) ama `trend_score` çok düşük ve RSI aşırı alım seviyesinde. **Esnek gating** devreye girer:

```python
# S2 Esnek Gating
if trend_score <= 0.25 and (chop_score >= 0.5 or rsi >= 70):
    s2_active = True  # Range MR aktif
```

### S2 Analizi:
```python
# Range MR Logic
price_to_bb_upper = (current_price - bb_upper) / atr = -0.05  # BB üst banda çok yakın
rsi_overbought = rsi >= 65  # True (RSI=73)

if price_to_bb_upper >= -0.1 and rsi_overbought:
    signal = "SAT"  # Short signal
    confidence = min(rsi_excess / 30, 1.0) = (73-65)/30 = 0.27
```

### Ensemble Karar:
```python
# S2 ağırlığı 0.28 (orta seviye performans)
weighted_score = 0.28 * 0.27 = 0.076
final_signal = "SAT"
final_confidence = 0.076 / 0.28 = 0.27
```

### Sonuç: **Düşük güvenle SAT sinyali - minimum pozisyon boyutu** 🟡

---

## 💥 Senaryo 3: Squeeze Breakout - Multi-Specialist (S1+S3)

### Market Durumu:
- **BNB/USDT**: 2 hafta 580-620 dar range
- **BB Bandwidth**: %2.1 (çok düşük - tight squeeze)
- **Volume**: Son 4 saatte 3.2x artış
- **Price**: Donchian(20) üst seviyesini kırdı (625)
- **ATR**: Medyan'ın 1.4x üstünde

### Rejim Skorları:
```python
trend_score = 0.45  # Breakout sonrası trend oluşmaya başladı
squeeze_score = 1 - 0.02 = 0.98  # Çok yüksek squeeze (düşük BW)
chop_score = 0.30  # Directional move başladı
volume_score = 3.2  # Anormal yüksek hacim
```

### Gating Sonucu:
- ✅ **S1 (Trend PB/BO)**: `trend_score≥0.35` ✓ + `squeeze_score≥0.5` ✓
- ❌ **S2 (Range MR)**: `trend_score>0.25` ✗
- ✅ **S3 (Vol BO)**: `squeeze_score≥0.6` ✓ + `volume≥1.2x` ✓
- ❌ **S4 (XSect)**: Rebalance zamanı değil ✗

### Multi-Specialist Analiz:

#### S1 (Trend PB/BO):
```python
# Confluence scoring
rsi_score = 0.75    # RSI 62 - momentum güçlü
macd_score = 0.85   # MACD güçlü bullish
bb_score = 0.90     # BB breakout confirmed
confluence_s1 = (0.75 + 0.85 + 0.90) / 3 = 0.83

signal_s1 = "AL"
confidence_s1 = 0.83
```

#### S3 (Volume Breakout):
```python
# Volume breakout logic
donchian_breakout = price > donchian_upper_20  # True
atr_condition = current_atr >= median_atr * 1.1  # True (1.4x)
volume_condition = volume >= median_volume * 1.2  # True (3.2x)

if all([donchian_breakout, atr_condition, volume_condition]):
    signal_s3 = "AL"
    confidence_s3 = min(volume_score / 3.0, 1.0) = min(3.2/3.0, 1.0) = 1.0
```

### Ensemble Karar:
```python
# İki aktif uzman ağırlıkları
weights = {"S1": 0.45, "S3": 0.22}  # S1 son dönemde daha başarılı

# Ağırlıklı scoring
signal_scores = {
    "AL": 0.45 * 0.83 + 0.22 * 1.0 = 0.594,
    "SAT": 0.0,
    "BEKLE": 0.0
}

total_weight = 0.45 + 0.22 = 0.67
final_confidence = 0.594 / 0.67 = 0.887  # Çok yüksek güven!
```

### Sonuç: **Güçlü AL sinyali (%88.7 güven) - maximum pozisyon boyutu** 🟢🟢

---

## 🔄 Senaryo 4: Cross-Sectional Momentum Rebalance (S4)

### Market Durumu:
- **Zaman**: 00:00 UTC (günlük rebalance)
- **Top 10 Performance (24h)**:
  1. SOL: +8.3%
  2. AVAX: +6.7%
  3. MATIC: +5.2%
  4. ADA: +4.8%
  5. DOT: +3.9%

### S4 Cross-Sectional Analysis:

#### Momentum Skorları:
```python
# 3h, 6h, 12h composite returns
momentum_scores = {
    "SOL": {
        "3h": +2.1%, "6h": +4.2%, "12h": +7.8%,
        "composite": (2.1 + 4.2 + 7.8) / 3 = 4.7%,
        "percentile": 98  # Top150 içinde 98. percentile
    },
    "AVAX": {
        "3h": +1.8%, "6h": +3.1%, "12h": +6.4%,
        "composite": 3.8%,
        "percentile": 94
    },
    "BTC": {
        "3h": +0.3%, "6h": +0.8%, "12h": +1.2%,
        "composite": 0.8%,
        "percentile": 62
    }
}
```

#### Risk Parite Allocation:
```python
# Volatility-adjusted weights
volatilities = {
    "SOL": 0.085,   # 8.5% günlük vol
    "AVAX": 0.078,  # 7.8% günlük vol
    "BTC": 0.045    # 4.5% günlük vol (daha stabil)
}

# Risk parite: weight = 1/vol (normalize edilir)
risk_weights = {
    "SOL": 1/0.085 = 11.76,
    "AVAX": 1/0.078 = 12.82,
    "BTC": 1/0.045 = 22.22
}

# Normalize (toplam = 1.0)
total = 11.76 + 12.82 + 22.22 = 46.8
final_weights = {
    "SOL": 11.76/46.8 = 0.251 (25.1%),
    "AVAX": 12.82/46.8 = 0.274 (27.4%),
    "BTC": 22.22/46.8 = 0.475 (47.5%)
}
```

#### S4 Portfolio Signals:
```python
# Sadece top momentum + reasonable risk
selected_coins = []
for coin, data in momentum_scores.items():
    if data["percentile"] >= 85 and risk_weights[coin] <= 0.30:
        selected_coins.append({
            "symbol": coin,
            "signal": "AL",
            "confidence": data["percentile"] / 100,
            "weight": risk_weights[coin],
            "max_position": 0.10  # Portfolio'nun max %10'u
        })

# Sonuç
s4_signals = [
    {"symbol": "SOL", "signal": "AL", "confidence": 0.98, "weight": 0.251},
    {"symbol": "AVAX", "signal": "AL", "confidence": 0.94, "weight": 0.274}
]
```

### Ensemble Karar (S4 için):
```python
# S4 ağırlığı düşük (0.18) - yeni uzman, henüz kanıtlanmamış
for signal in s4_signals:
    weighted_confidence = 0.18 * signal["confidence"]
    
    if weighted_confidence >= 0.15:  # Minimum eşik
        final_signals.append({
            "symbol": signal["symbol"],
            "action": "AL",
            "confidence": weighted_confidence,
            "position_size": 0.18 * signal["weight"] * 0.10  # S4 weight × risk weight × max pos
        })
```

### Sonuç: **SOL ve AVAX için küçük pozisyonlar açılır** 🟡

---

## 📊 Ağırlık Evrimi Örneği (6 Aylık)

### Başlangıç (Ocak):
```
S1: 0.25 (25%) - Trend PB/BO
S2: 0.25 (25%) - Range MR  
S3: 0.25 (25%) - Vol BO
S4: 0.25 (25%) - XSect Mom
```

### Mart (Bull market):
```python
# S1 çok başarılı (+15R toplam), S2 kötü (-8R), S3 orta (+3R), S4 iyi (+7R)
S1: 0.45 (45%) ⬆️ # Trend following başarılı
S2: 0.15 (15%) ⬇️ # Range MR bull'da kötü
S3: 0.22 (22%) ⬇️ # Orta performans
S4: 0.18 (18%) ⬇️ # İyi ama S1 kadar değil
```

### Haziran (Sideways/Range):
```python
# Market koşulları değişti, S2 toparlandı, S1 kötüleşti
S1: 0.28 (28%) ⬇️ # Trend stratejisi sideways'te kötü
S2: 0.35 (35%) ⬆️ # Range MR toparlandı
S3: 0.20 (20%) ⬇️ # Az breakout fırsatı
S4: 0.17 (17%) ⬇️ # Momentum azaldı
```

### MWU Hesaplama Örneği:
```python
# S2 başarılı trade (+2.1R) sonrası güncelleme
old_weight_s2 = 0.35
r_multiple = 2.1
eta = 0.10

new_weight_s2 = 0.35 * exp(0.10 * 2.1) = 0.35 * exp(0.21) = 0.35 * 1.234 = 0.432

# Diğer uzmanlar değişmediği için normalize
total_before = 0.28 + 0.35 + 0.20 + 0.17 = 1.00
total_after = 0.28 + 0.432 + 0.20 + 0.17 = 1.092

# Normalize
S1: 0.28 / 1.092 = 0.256 (25.6%)
S2: 0.432 / 1.092 = 0.396 (39.6%) ⬆️
S3: 0.20 / 1.092 = 0.183 (18.3%)
S4: 0.17 / 1.092 = 0.156 (15.6%)
```

## 🎯 Ana Avantajlar - Özet

1. **Adaptif Öğrenme**: Başarılı stratejilere otomatik ağırlık artırır
2. **Rejim Farkındalığı**: Market koşullarına göre uygun uzman seçer
3. **Risk Diversifikasyonu**: Tek strategiye bağımlılık azaltır
4. **Performance İzleme**: OOS guard ile kötü performansı durdurur
5. **Modüler Gelişim**: Her uzman bağımsız geliştirilebilir

**Meta-Router sayesinde bot, market koşulları ne olursa olsun en uygun stratejiyi otomatik olarak devreye alır! 🚀**
