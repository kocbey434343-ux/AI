# STRATEJİ İMPLEMENTASYONLARI VE İLERİ ÖZELLİKLER

## A30. RBP-LS v1.3.1 — REAL IMPLEMENTATION (In-Place Upgrade) PoR

Amaç: Mevcut strateji/riske/uygulama iskeletini bozmayıp minimal-diff yaklaşımıyla RBP-LS v1.3.1'i devreye almak. Bu bölüm, yapıtaşlarını, geri uyumlu konfig genişlemelerini, telemetri/SSoT sözleşmelerini ve kabul kriterlerini tanımlar.

### 30.1 Strateji Mantığı (Özet)
- Zaman Çerçevesi: Ana TF 1h; HTF doğrulama: 4h EMA200 trend filtresi (yukarıda -> long-only bias; aşağıda -> short-only bias; flat -> kısıtlı risk).
- Rejim Filtresi: ADX min eşiği (varsayılan 25) ile trend gücü kontrolü; zayıf trendte mean-reversion bileşenlerinin ağırlığı artar (mevcut indicators.py ağırlık adaptasyonu korunur).
- Giriş Modları: PB/BO (Pullback/Breakout) çift mod. BB/Keltner/Donchian bantları ile bağlam; mevcut BB tabanlı sinyal korunur, Donchian/Keltner ileride eklenmek üzere feature flag ile tanımlanır (kapalı başlar).
- Confluence: RSI + MACD + Bollinger skorlaması mevcut; eşik default ≥75 seçicilik hedefi UI/Backtest ile hizalı. ADX ile ağırlık modülasyonu sürer.
- Çıkış Planı: Hedef RR≥3.0; kısmi realize ilk kademe ~1.5R; ATR-trailing aktivasyonu ≥1.2R, dondurma (freeze) mekanizması mevcut ATR trailing parametreleri ile uyumlu.
- Zaman Durdurma: time_stop=24 bar (1h → ~24 saat) — süre dolunca pozisyon kapatma sinyali üret.

### 30.2 Risk & Kaldıraç (Spot/Futures)
- Risk yüzde bazlı (DEFAULT_RISK_PERCENT), ATR tabanlı stop mesafesi (atr_multiplier) veya fallback %; mevcut RiskManager korunur.
- Futures: Isolated leverage (DEFAULT_LEVERAGE) — marjin limitine güvenli ölçekleme; aşırı kullanım guard (≤%90 marjin kullan).
- Günlük risk guardrail'leri (MAX_DAILY_LOSS_PCT, MAX_CONSECUTIVE_LOSSES) korunur; anomaly tetiklerinde ANOMALY_RISK_MULT devreye girer.

### 30.3 Emir Akışı & Koruma
- Maker-first fırsatları (ileride); mevcut open + koruma (OCO/tekil fallback) akışı korunur.
- Watchdog: Koruma emirleri için retry + degrade policy; structured log olayı ve metrik artışı.

### 30.4 Likidite/Spread Guard'ları
- Minimum hacim zaten mevcut (DEFAULT_MIN_VOLUME). Ek: SPREAD_MAX_BPS ile genişleyebilir guard; kapalı başlar.

### 30.5 Telemetri & İzlenebilirlik
- Prometheus: mevcut sayaçlar (open/close latency, slippage, guard_block, rate_limit/backoff, clock_skew) kullanılır.
- Yeni olaylar, mevcut generic guard_block metriği ile etiketlenir (guard="spread"/"time_stop"/"htf_filter"). Ek sayaç şart değildir.

### 30.6 UI
- Mevcut Türkçe UI korunur; Ayarlar'da ADX min eşiği zaten yönetilebilir. Yeni HTF/EMA ve time_stop/ spread guard parametreleri ileri fazda görünür yapılabilir (varsayılan kapalı/konservatif değerlerle başlar, fonksiyonel regresyon yaratmaz).

### 30.7 Konfig Genişlemeleri (Geriye Uyumlu — Rename yok)
- STRATEGY_VERSION = "RBP-LS-1.3.1" (bilgi amaçlı)
- HTF doğrulama: HTF_EMA_TIMEFRAME="4h", HTF_EMA_LENGTH=200, HTF_FILTER_ENABLED=false (default)
- Giriş modları: ENABLE_BREAKOUT=true, ENABLE_PULLBACK=true (ikisi de açık; mevcut davranış değişmez)
- Hedef RR: DEFAULT_TAKE_PROFIT_RR=2.2 (mevcut değeri koru; 3.0'a geçiş opsiyonel)
- Kısmi realize: PARTIAL_TP1_R_MULT default mevcut değeri korur (1.0); 1.5 önerilir (opsiyonel switch)
- Zaman durdurma: TIME_STOP_BARS=24 (kapalı başlar: TIME_STOP_ENABLED=false)
- Spread guard: SPREAD_GUARD_ENABLED=false, SPREAD_MAX_BPS=10.0
- Koruma watchdog: PROTECTION_WATCHDOG_ENABLED=true, PROTECTION_RETRY_MAX=3
- Meta-router (ileri faz): META_ROUTER_ENABLED=false, META_ROUTER_MODE="mwu"

Not: Tüm anahtarlar Settings altında eklenir; mevcut isimler korunur; yeniler varsayılan olarak pasif/konservatif ayarlanır.

### 30.8 Kabul Kriterleri
- Geriye dönük uyum: Mevcut testlerin tamamı PASS; varsayılan değerlerle davranış değişmez.
- Konfig: Yeni anahtarlar import edilir, erişilebilir; UI/işlev path'larında zorunlu olmayan hiçbir yan etki yok.
- Telemetri: Yeni guard'lar tetiklenirse bot_guard_block_total etiketlenir; metriks endpoint bozulmaz.
- SSoT: Bu PoR bölümü eklendi; Migration notları oluşturuldu.

### 30.9 Rollout & Test
- PR-1: Config & Telemetry (bu PoR + Settings genişlemeleri) — minimal kod değişikliği, test çalıştır.
- PR-2..N: PB/BO çekirdek, HTF EMA filtresi, time_stop, spread guard adım adım, her adımda test/backtest.

### 30.10 Migration Notları (Özet)
- Yeni anahtarlar eklendi; hiçbir mevcut anahtarın adı değişmedi; varsayılanlar kapalı/pasif.
- RiskManager take_profit_rr başlangıç değeri Settings.DEFAULT_TAKE_PROFIT_RR ile okunur; default 2.2, dolayısıyla davranış değişmez.

## A31. RBP-LS v1.4.0 — META-ROUTER & ENSEMBLE SYSTEM PoR

Amaç: Meta-Router ensemble sistemi ile 4 uzman stratejiyi koordine etmek. Adaptif ağırlık öğrenme ve risk dağıtımı.

### 31.1 Meta-Router Çerçevesi
**Uzman Stratejiler**:
- S1: trend_pb_bo (mevcut PB/BO çekirdeği; trend + squeeze-breakout)
- S2: range_mr (yatay mean-reversion: BB bounce + RSI aşırılık)
- S3: vol_breakout (Donchian(20) kırılma + ATR≥medyan×1.1)
- S4: xsect_mom (Top150'de 3/6/12h bileşik momentum; günlük rebalance)

**Gating Skorları (0–1)**:
- TrendScore = clip((ADX−10)/(40−10),0,1)
- SqueezeScore = 1 − pct_rank(BB_bw, lookback=180)
- ChopScore = 1 − |RSI−50|/50
- Autocorr1h = corr(close_t−1, close_t)

**Kapı Kuralları**:
- S1: TrendScore≥0.35 ve (SqueezeScore≥0.5 veya ADX≥18)
- S2: TrendScore≤0.25 ve ChopScore≥0.6 (ADX<20; 4h slope≈0)
- S3: SqueezeScore≥0.6 ve hacim≥medyan×1.2
- S4: sadece daily rebalance saatinde

**Ağırlık Öğrenme (MWU)**:
- w_{t+1}(i) ∝ w_t(i) × exp(η × r_t(i)/risk_unit), η≈0.10
- Normalize; clamp [0.1, 0.6]; 24 bar pencere
- OOS-guard: son 14 gün PF<1.1 olan uzmanın ağırlığı min_weight'e sabitlenir

### 31.2 Range Mean-Reversion Uzmanı (S2)
**Giriş Koşulları**:
- LONG: close ≤ BB_lower + 0.1×ATR & RSI≤35 → çıkış: SMA20 veya 1.5R
- SHORT: close ≥ BB_upper − 0.1×ATR & RSI≥65 → çıkış: SMA20 veya 1.5R
- SL=max(1.0×ATR, band±0.5×ATR)

**Rejim Filtresi**:
- ADX<20 (trend yok), 4h EMA slope≈0 (yatay market)
- ChopScore≥0.6 (RSI 35-65 arası osillasyon)

### 31.3 Volume Breakout Uzmanı (S3)
**Donchian Breakout**:
- LONG: close > Donchian_upper(20) ve ATR≥medyan×1.1
- SHORT: close < Donchian_lower(20) ve ATR≥medyan×1.1
- SL=1.2×ATR; hedef 2R + trailing

**Hacim Teyidi**:
- Volume ≥ 20-bar medyan × 1.2
- Squeeze teyidi: BB bandwidth p80 üstünde

### 31.4 Cross-Sectional Momentum Uzmanı (S4)
**Momentum Hesaplama**:
- 3h, 6h, 12h getiri bileşik skoru
- Top150 evreni içinde percentile ranking
- Günlük 00:00 UTC rebalance

**Risk Parite**:
- Her sembol için volatilite ayarlı ağırlık
- Pay tavanı toplam riskin %10'u
- Dinamik korelasyon kısıtları

### 31.5 Konfigürasyon Şeması (Meta-Router)
```yaml
meta_router:
  enabled: false  # A31'de aktif edilecek
  specialists: ["trend_pb_bo", "range_mr", "vol_breakout", "xsect_mom"]
  rebalance_bars: 24
  learner:
    algorithm: "mwu"  # multiplicative weights update
    eta: 0.10
    min_weight: 0.10
    max_weight: 0.60
    window_bars: 24
  oos_guard:
    window_days: 14
    min_profit_factor: 1.10
  gating:
    trend_min_threshold: 0.35
    squeeze_min_threshold: 0.5
    chop_min_threshold: 0.6
    volume_min_mult: 1.2

range_mr:
  enabled: false
  rsi_oversold: 35
  rsi_overbought: 65
  bb_touch_atr_mult: 0.1
  target_r: 1.5
  sl_atr_mult: 1.0

vol_breakout:
  enabled: false
  donchian_periods: 20
  atr_min_mult: 1.1
  target_r: 2.0
  sl_atr_mult: 1.2
  volume_min_mult: 1.2

xsect_mom:
  enabled: false
  lookback_hours: [3, 6, 12]
  rebalance_hour: 0  # UTC
  max_position_pct: 0.10
  risk_parity: true
```

### 31.6 Implementation Roadmap (A31)
**Phase 1**: Meta-Router infrastructure
- Uzman interface & factory pattern
- Gating score computation engine
- MWU ağırlık güncelleme motoru

**Phase 2**: S2 & S3 uzmanları
- Range MR: BB + RSI mean reversion
- Vol BO: Donchian + ATR/volume breakout

**Phase 3**: S4 & orchestration
- Cross-sectional momentum engine
- Risk parite allocation
- Ensemble coordination

**Phase 4**: UI & monitoring
- Meta-Router panel (ağırlık barları)
- Uzman performance kartları
- Gating status rozetleri

### 31.7 Kabul Kriterleri (A31)
- 4 uzman ayrı ayrı test edilebilir
- MWU ağırlık güncelleme deterministik
- Gating skorları doğru hesaplanır
- Risk dağıtımı %100 toplamı yapar
- OOS guard düşük performans uzmanları durdurur

## A32. RBP-LS v1.5.0 — ELMAS MANTIK (Edge Hardening) PoR

Amaç: Trading edge'lerini korumak için gelişmiş filtreleme ve adaptasyon sistemleri.

### 32.1 Edge Health Monitor (EHM)
**Sağlık Metrikleri**:
- Expectancy-R: E[R] = Σ(win_rate × avg_win_R − loss_rate × avg_loss_R)
- Wilson alt sınır: confidence interval lower bound
- 200 trade kayan pencere, minimum 50 trade

**Edge Durumları**:
- HOT: LB > 0.1R (güçlü edge)
- WARM: 0 < LB ≤ 0.1R (zayıf ama pozitif)
- COLD: LB ≤ 0 (edge yok/negatif)

**Edge Politikası**:
- COLD edge'ler NO-GO (yalnızca paper/testnet'te re-qualify)
- WARM edge'ler risk azaltılır (%50)
- HOT edge'ler normal risk

### 32.2 Cost-of-Edge: 4× Kuralı
**Pre-trade EGE Hesaplama**:
- Expected Gross Edge = confluence + rejim + tetik gücü + hacim skoru
- Total Cost = fee + expected_slippage
- Kural: EGE ≥ 4 × Total Cost, değilse NO-GO

**Dinamik Cost Model**:
- Fee: maker/taker differential
- Slippage: spread & derinlik tabanlı tahmin
- Impact: order size vs book depth

### 32.3 Mikroyapı Prefiltreleri
**Order Book Imbalance (OBI)**:
- OBI = (Σbid_vol − Σask_vol) / (Σbid_vol + Σask_vol), 5-10 seviye
- LONG sadece OBI ≥ +0.20; SHORT sadece OBI ≤ −0.20
- Çelişki durumunda WAIT; 2. snapshot ile teyit

**Aggressive Fill Ratio (AFR)**:
- AFR = taker_buy_qty / total_taker_qty (son 50-100 trade)
- LONG AFR≥0.55, SHORT AFR≤0.45
- Real-time trade stream analysis

### 32.4 Adaptif Fraksiyonel Kelly
**Risk Adjustment Formula**:
- risk_per_trade = base_risk × g(DD) × h(EdgeHealth)
- g(DD): 1.0 (≤5%), 0.5 (5-10%), 0.25 (>10%)
- h(Hot)=1.0, h(Warm)=0.75, h(Cold)=0.25
- Tavan: min(..., 0.5%) (geriye uyum)

**Kelly Fraction Hesaplama**:
- f* = (bp - q) / b, burada b=avg_win/avg_loss, p=win_rate, q=1-p
- Conservative multiplier: 0.25 × f* (over-leverage koruması)

### 32.5 Dead-Zone (No-Trade Band)
**Expected Edge Score (EES)**:
- Tüm faktörlerin ağırlıklı toplamı: [-1, +1] aralığında
- Dead zone: -0.05 ≤ EES ≤ +0.05 ise trade yok
- Chop market'ta deneme azaltma

### 32.6 Carry Fallback (Opsiyonel)
**Funding Arbitraj**:
- Rejim belirsiz ve |funding|≥0.03%/8h
- Spot cüzdan varsa: delta-nötr (spot long + perp short)
- Funding saatinde [-5,+2] dk sessiz pencere

### 32.7 Konfigürasyon (A32)
```yaml
edge_health:
  enabled: false  # A32'de aktif
  window_trades: 200
  min_trades: 50
  confidence_interval: "wilson"
  hot_threshold: 0.10
  warm_threshold: 0.0
  cold_action: "no_go"  # no_go|reduce|paper_only

cost_of_edge:
  enabled: false
  k_multiple: 4.0
  fee_model: "tiered"  # flat|tiered
  slippage_model: "dynamic"  # static|dynamic

microstructure:
  enabled: false
  obi_levels: 5
  obi_long_min: 0.20
  obi_short_max: -0.20
  afr_window_trades: 80
  afr_long_min: 0.55
  afr_short_max: 0.45
  conflict_action: "wait"  # wait|abort

kelly:
  enabled: false
  base_risk: 0.005
  conservative_mult: 0.25
  dd_adjustment: true
  edge_adjustment: true
  max_fraction: 0.005

dead_zone:
  enabled: false
  eps_threshold: 0.05
  chop_reduction: true

carry_fallback:
  enabled: false
  funding_threshold_8h: 0.0003
  require_spot_wallet: true
  quiet_window_minutes: [-5, 2]
```

### 32.8 Implementation Priority (A32)
**P1**: Edge Health Monitor + COLD/WARM/HOT classification
**P1**: 4× Cost rule + pre-trade gate
**P2**: OBI/AFR mikroyapı filtreleri
**P2**: Kelly fraksiyonu + risk scaling
**P3**: Dead-zone + carry fallback

### 32.9 Kabul Kriterleri (A32)
- EHM 200 trade pencerede doğru LB hesaplar
- 4× cost kuralı fee+slip'i doğru tahmin eder
- OBI/AFR real-time hesaplama 100ms altında
- Kelly fraction DD ve edge health'e uygun scale eder
- Dead-zone EES hesaplama deterministik
