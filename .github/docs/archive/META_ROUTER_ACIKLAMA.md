# 🧠 Meta-Router Sistemi - Kapsamlı Açıklama

## 🎯 Meta-Router Nedir?

Meta-Router, **4 farklı uzman stratejiyi koordine eden akıllı ensemble sistemi**dir. Her uzman farklı market koşullarında uzmanlaşır ve sistem, hangi uzmanın ne zaman aktif olacağına karar verir.

## 🏗️ Sistem Mimarisi

```
┌─────────────────────────────────────────────────────────────┐
│                     META-ROUTER SİSTEMİ                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │    Market   │    │   Uzman     │    │     MWU     │     │
│  │   Rejim     │───▶│  Seçimi     │───▶│   Öğrenme   │     │
│  │  Analizi    │    │ (Gating)    │    │ Algoritması │     │
│  └─────────────┘    └─────────────┘    └─────────────┘     │
│         │                   │                   │          │
│         ▼                   ▼                   ▼          │
│  ┌─────────────────────────────────────────────────────┐   │
│  │             ENSEMBLE KARAR SİSTEMİ              │   │
│  │                                                     │   │
│  │  ┌───────┐  ┌───────┐  ┌───────┐  ┌───────┐     │   │
│  │  │  S1   │  │  S2   │  │  S3   │  │  S4   │     │   │
│  │  │Trend  │  │Range  │  │Volume │  │XSect  │     │   │
│  │  │PB/BO  │  │  MR   │  │Breakout│ │ Mom   │     │   │
│  │  └───────┘  └───────┘  └───────┘  └───────┘     │   │
│  └─────────────────────────────────────────────────────┘   │
│                           │                                 │
│                           ▼                                 │
│                   FINAL TRADING SIGNAL                      │
│                    (AL/SAT/BEKLE)                           │
└─────────────────────────────────────────────────────────────┘
```

## 🤖 4 Uzman Strateji

### S1: Trend Pullback/Breakout (Trend PB/BO)
- **Amaç**: Güçlü trend durumlarında pullback ve breakout fırsatları yakalar
- **Aktif Olma Koşulu**: `TrendScore≥0.35 && (SqueezeScore≥0.5 || ADX≥18)`
- **Çalışma Mantığı**: RSI + MACD + Bollinger Bands confluence scoring
- **Uzmanlaştığı Market**: Trendy piyasalar, momentum durumları

### S2: Range Mean-Reversion (Range MR)
- **Amaç**: Yatay piyasalarda aşırı alım/satım seviyelerinden dönüş yakalar
- **Aktif Olma Koşulu**: `TrendScore≤0.25 && ChopScore≥0.6`
- **Çalışma Mantığı**: BB bantlarına dokunma + RSI aşırılık (≤35 / ≥65)
- **Uzmanlaştığı Market**: Range-bound, yatay konsolidasyon

### S3: Volume Breakout (Vol BO)
- **Amaç**: Donchian kanalı kırılımları + yüksek hacim onayı
- **Aktif Olma Koşulu**: `SqueezeScore≥0.6 && Volume≥1.2×median`
- **Çalışma Mantığı**: Donchian(20) + ATR≥median×1.1 + volume teyidi
- **Uzmanlaştığı Market**: Sıkışma sonrası patlama, squeeze breakout

### S4: Cross-Sectional Momentum (XSect Mom)
- **Amaç**: Kripto evreni içinde güçlü momentum gösteren coinleri yakalar
- **Aktif Olma Koşulu**: Sadece günlük rebalance saatinde (00:00 UTC)
- **Çalışma Mantığı**: 3h/6h/12h composite momentum ranking, Top150 içinde percentile
- **Uzmanlaştığı Market**: Sektör rotasyonu, momentum shifts

## 🎚️ Gating Sistemi (Kapı Kuralları)

Market rejim analizi ile hangi uzmanın aktif olacağını belirler:

### Market Rejim Skorları
```python
# 1. Trend Score (ADX bazlı)
trend_score = (ADX - 10) / (40 - 10)  # 0-1 aralığı

# 2. Squeeze Score (BB bandwidth)
squeeze_score = 1 - BB_bandwidth_percentile  # Düşük BW = yüksek squeeze

# 3. Chop Score (RSI osillasyon)
chop_score = 1 - |RSI - 50| / 50  # RSI 50'ye yakın = chop

# 4. Volume Score
volume_score = current_volume / median_volume_20

# 5. Autocorrelation (momentum persistence)
autocorr_1h = corr(return_t, return_t-1)
```

### Gating Logic Örnekleri:
```
TREND MARKET (ADX>25, strong directional move):
✅ S1 (Trend PB/BO) → Aktif
❌ S2 (Range MR) → Pasif
❌ S3 (Vol BO) → Pasif
❌ S4 (XSect) → Sadece rebalance saatinde

RANGE MARKET (ADX<20, chopy price action):
❌ S1 (Trend PB/BO) → Pasif
✅ S2 (Range MR) → Aktif
❌ S3 (Vol BO) → Pasif
❌ S4 (XSect) → Sadece rebalance saatinde

SQUEEZE BREAKOUT (Low BB BW + Volume spike):
❌ S1 (Trend PB/BO) → Potansiyel aktif
❌ S2 (Range MR) → Pasif
✅ S3 (Vol BO) → Aktif
❌ S4 (XSect) → Sadece rebalance saatinde
```

## 🧮 MWU (Multiplicative Weight Update) Öğrenme

### Algoritma Mantığı:
1. **Başlangıç**: Her uzman eşit ağırlık (0.25 = 25%)
2. **Performans Takibi**: Her trade sonrası R-multiple hesaplama
3. **Ağırlık Güncelleme**: `w_{t+1} = w_t × exp(η × r_t)`
   - `η = 0.10` (learning rate)
   - `r_t = R-multiple` (kazanç/zarar oranı)
4. **Normalizasyon**: Toplam ağırlık = 1.0
5. **Sınır Kontrolü**: Min 0.10, Max 0.60

### Örnek Ağırlık Evrimi:
```
Başlangıç: S1:0.25, S2:0.25, S3:0.25, S4:0.25

S1 başarılı trade (+1.5R) sonrası:
S1: 0.25 × exp(0.10 × 1.5) = 0.29
→ Normalize → S1:0.32, S2:0.23, S3:0.23, S4:0.22

S2 kaybettirici trade (-1.0R) sonrası:
S2: 0.23 × exp(0.10 × -1.0) = 0.21
→ Normalize → S1:0.34, S2:0.19, S3:0.24, S4:0.23

6 ay sonra örnek durum:
S1:0.45, S2:0.15, S3:0.25, S4:0.15
(S1 en başarılı, S2 ve S4 düşük performans)
```

## 🎯 Ensemble Karar Verme

### Ağırlıklı Voting Sistemi:
```python
# 1. Aktif uzmanlardan sinyal al
specialist_signals = {
    "S1": SpecialistSignal("AL", confidence=0.8),
    "S3": SpecialistSignal("AL", confidence=0.6)
}

# 2. Mevcut ağırlıkları uygula
weights = {"S1": 0.45, "S3": 0.25}

# 3. Ağırlıklı oylama
signal_scores = {
    "AL": 0.45 × 0.8 + 0.25 × 0.6 = 0.51,
    "SAT": 0.0,
    "BEKLE": 0.0
}

# 4. En yüksek skor = FINAL SIGNAL
final_signal = "AL"
final_confidence = 0.51 / (0.45 + 0.25) = 0.73
```

## 🛡️ OOS (Out-of-Sample) Guard

Kötü performans gösteren uzmanları koruma altına alır:

```python
# Son 14 gün içinde:
if uzman.profit_factor < 1.10 and uzman.trade_count >= 5:
    uzman.weight = min_weight  # 0.10'a sabitle
    logger.warning(f"OOS guard: {uzman_id} minimize edildi")
```

## 📊 Gerçek Dünya Örneği

### Senaryo: Bitcoin Trending Up (ADX=35)
```
Market Rejim Skorları:
- trend_score: 0.83 (yüksek)
- squeeze_score: 0.25 (düşük)
- chop_score: 0.30 (düşük)
- volume_score: 1.8

Gating Sonucu:
✅ S1 (Trend PB/BO): trend_score≥0.35 ✓
❌ S2 (Range MR): trend_score>0.25 ✗
❌ S3 (Vol BO): squeeze_score<0.6 ✗
❌ S4 (XSect): Rebalance saati değil ✗

Aktif Uzman: Sadece S1
S1 Sinyali: "AL" (confidence: 0.85)
Ensemble Sonuç: "AL" (confidence: 0.85)
```

### Senaryo: Sideways Market (ADX=12)
```
Market Rejim Skorları:
- trend_score: 0.07 (çok düşük)
- squeeze_score: 0.20 (düşük)
- chop_score: 0.85 (yüksek)
- volume_score: 0.9

Gating Sonucu:
❌ S1 (Trend PB/BO): trend_score<0.35 ✗
✅ S2 (Range MR): trend_score≤0.25 ✓ && chop_score≥0.6 ✓
❌ S3 (Vol BO): squeeze_score<0.6 ✗
❌ S4 (XSect): Rebalance saati değil ✗

Aktif Uzman: Sadece S2
S2 Sinyali: "SAT" (confidence: 0.72) [RSI=78, BB üst banda yakın]
Ensemble Sonuç: "SAT" (confidence: 0.72)
```

## 🔄 Sistem Akışı (Step-by-Step)

1. **Market Data In** → OHLCV + Indicators
2. **Rejim Analizi** → 5 gating score hesaplama
3. **Uzman Seçimi** → Gating rules ile aktif uzman belirleme
4. **Sinyal Toplama** → Aktif uzmanlardan SpecialistSignal alma
5. **Ağırlık Uygulama** → MWU ağırlıkları ile scoring
6. **Ensemble Karar** → Ağırlıklı voting
7. **Final Signal** → AL/SAT/BEKLE + confidence
8. **Performance Update** → Trade kapandığında MWU güncelleme

## ⚡ Avantajları

1. **Çeşitlendirme**: 4 farklı yaklaşım, farklı market koşullarında etkin
2. **Adaptasyon**: MWU ile başarılı stratejilere daha fazla ağırlık
3. **Risk Yönetimi**: OOS guard ile kötü performans koruması
4. **Rejim Farkındalığı**: Market koşullarına göre otomatik strateji seçimi
5. **Modülerlik**: Her uzman bağımsız geliştirilebilir/test edilebilir

## 🎛️ Konfigürasyon

```python
# Meta-Router Ayarları
META_ROUTER_ENABLED = True/False
META_ROUTER_MODE = "mwu"

# MWU Parametreleri
MWU_ETA = 0.10              # Learning rate
MWU_MIN_WEIGHT = 0.10       # Minimum ağırlık
MWU_MAX_WEIGHT = 0.60       # Maximum ağırlık
MWU_WINDOW_BARS = 24        # Güncelleme penceresi
OOS_WINDOW_DAYS = 14        # OOS guard penceresi
OOS_MIN_PF = 1.10          # Minimum profit factor
```

## 🏆 Sonuç

Meta-Router, **geleneksel tek-strateji yaklaşımının ötesinde**, market koşullarına uyum sağlayan, kendini sürekli optimize eden, **akıllı ensemble trading sistemi**dir. 

Sistem, her uzmanın güçlü olduğu alanlarda onları devreye sokarak, **risk-ayarlı getiri optimizasyonu** sağlar ve piyasa değişikliklerine **dinamik adaptasyon** gösterir.

Bu sayede:
- **Trending marketlerde** S1 ile momentum yakalar
- **Range marketlerde** S2 ile mean-reversion uygular  
- **Breakout anlarında** S3 ile volatilite artışını değerlendirir
- **Sector rotation dönemlerinde** S4 ile güçlü momentum yakalar

**Meta-Router = Tek stratejinin limitlerini aşan, çok boyutlu trading intelligence! 🚀**
