## 🎨 UI DASHBOARD DEVELOPMENT PLAN

**Hedef:** Meta-Router & Edge Hardening systemlerini görselleştiren kapsamlı dashboard

### 📊 DASHBOARD COMPONENT ÖZETİ

#### 1. **Meta-Router Control Panel**
- **Dosya:** `src/ui/meta_router_panel.py`
- **Özellikler:**
  - 4 Uzman ağırlık barları (S1-S4) real-time
  - MWU learning grafiği (ağırlık değişimi timeline)
  - Gating status rozetleri (TrendScore, SqueezeScore, ChopScore, VolumeScore)
  - Ensemble sinyal kalitesi heatmap
  - OOS guard status ve minimal weight uyarıları

#### 2. **Edge Health Monitor Dashboard**
- **Dosya:** `src/ui/edge_health_panel.py`
- **Özellikler:**
  - HOT/WARM/COLD status büyük renkli rozetler
  - Wilson CI confidence interval grafiği
  - Son 200 trade pencere expectancy trend
  - Strategy-specific edge health ayrık gösterim
  - Risk multiplier visualizations

#### 3. **4× Cost Rule Tracker**
- **Dosya:** `src/ui/cost_tracker_panel.py`
- **Özellikler:**
  - Pre-trade cost/edge oranı real-time
  - Fee structure visualization (maker/taker spread)
  - Slippage estimation vs actual
  - Market impact calculator widget
  - Trade feasibility green/red status

#### 4. **Microstructure Monitor**
- **Dosya:** `src/ui/microstructure_panel.py`
- **Özellikler:**
  - OBI (Order Book Imbalance) gauge (-1 to +1)
  - AFR (Aggressive Fill Ratio) donut chart
  - Real-time book depth visualization
  - Conflict detection alerts (OBI vs AFR)
  - Signal allowance traffic light (LONG/SHORT/WAIT)

#### 5. **System Health Overview**
- **Dosya:** `src/ui/system_health_panel.py`
- **Özellikler:**
  - Risk Escalation Level büyük status card
  - Prometheus metrics summary mini-charts
  - Feature flags status grid
  - Performance metrics (latency, slippage)
  - Component health matrix (API, DB, Streams)

### 🔧 TEKNİK IMPLEMENTATION

#### **UI Framework Strategy:**
- **Base:** Mevcut PyQt5 infrastructure genişletme
- **Layout:** QTabWidget ile organize paneller
- **Update:** QTimer ile 250ms real-time refresh
- **Performance:** Incremental updates, lazy loading

#### **Data Integration:**
- **Meta-Router:** `MetaRouter.get_status()` API
- **Edge Health:** `EdgeHealthMonitor.get_statistics()` API  
- **Cost Calculator:** `CostOfEdgeCalculator.get_current_analysis()` API
- **Microstructure:** `MicrostructureFilter.get_current_state()` API
- **Prometheus:** `/metrics` endpoint local scraping

#### **Visual Components:**
```python
# Progress Bars: Ağırlıklar (0-60%)
specialist_weights = {
    'S1_Trend_PB_BO': 0.35,
    'S2_Range_MR': 0.25, 
    'S3_Vol_Breakout': 0.15,
    'S4_XSect_Momentum': 0.25
}

# Status Cards: Edge Health
edge_status = {
    'global': 'WARM',  # HOT/WARM/COLD
    'color': '#ff8c00',  # Orange
    'expectancy': 0.05,  # 5% expectancy
    'confidence': 0.92   # Wilson CI lower bound
}

# Gauges: OBI/AFR
obi_gauge = (-0.15, -1.0, 1.0)  # Value, Min, Max
afr_donut = (0.58, "Bullish")   # AFR 58% = Bullish

# Traffic Lights: Signal Allowance
signal_lights = {
    'LONG': 'green',   # OBI+AFR allows
    'SHORT': 'red',    # Not allowed
    'WAIT': 'yellow'   # Conflict detected
}
```

### 📋 IMPLEMENTATION ROADMAP

#### **Phase 1: Foundation (1-2 hours)**
1. **Panel Structure:** Base panel classes, layout managers
2. **Data Connectors:** API integration wrappers
3. **Update Engine:** QTimer refresh mechanism
4. **Basic Styling:** Color schemes, fonts, spacing

#### **Phase 2: Core Panels (2-3 hours)**
1. **Meta-Router Panel:** Ağırlık barları + gating status
2. **Edge Health Panel:** HOT/WARM/COLD cards + CI grafiği
3. **Integration Testing:** Real data flow verification

#### **Phase 3: Advanced Panels (2-3 hours)**
1. **Cost Tracker Panel:** 4× rule visualization
2. **Microstructure Panel:** OBI/AFR gauges + conflicts
3. **System Health Panel:** Risk escalation + metrics

#### **Phase 4: Polish & Performance (1-2 hours)**
1. **Performance Optimization:** Incremental updates
2. **Error Handling:** Graceful fallbacks
3. **User Experience:** Tooltips, animations, responsiveness
4. **Integration Testing:** Full dashboard validation

### 🎯 ACCEPTANCE CRITERIA

#### **Functional Requirements:**
1. **Real-time Updates:** Dashboard refreshes ≤250ms
2. **Data Accuracy:** Metrics match backend APIs ±1%
3. **Performance:** UI response time <100ms
4. **Error Handling:** API failures don't crash dashboard
5. **Visual Quality:** Professional appearance, intuitive UX

#### **Technical Requirements:**
1. **Memory Usage:** <50MB additional for dashboard
2. **CPU Impact:** <5% additional load during updates
3. **Thread Safety:** No UI freezing during data updates
4. **Responsive Design:** Scales well 1400x900+ resolutions
5. **Feature Flags:** Panels can be disabled if features off

#### **User Experience Requirements:**
1. **Intuitive Layout:** Logical information hierarchy
2. **Color Coding:** Consistent status colors (green/yellow/red)
3. **Tooltips:** Hover explanations for all metrics
4. **Keyboard Shortcuts:** Quick panel navigation
5. **Export Capability:** Screenshot or data export options

### 🚀 NEXT STEPS

1. **Start Implementation:** Panel infrastructure + Meta-Router
2. **Iterative Development:** Phase-by-phase completion
3. **User Testing:** Real-world usage validation
4. **Performance Tuning:** Optimization based on usage patterns
5. **Production Integration:** Live environment testing

---
**Estimated Total Time:** 6-10 hours
**Priority:** P1 (Critical for production readiness)
**Dependencies:** Existing A31/A32 APIs
**Success Metric:** Full dashboard operational with real-time monitoring
