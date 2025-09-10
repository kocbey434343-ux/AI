# MODÜL REGISTRY - DETAYLI KATALOG

## Tam Modül Listesi

| MOD-ID | Ad | Konum | Sorumluluk | Bağımlılıklar | Durum |
|--------|----|-------|------------|---------------|-------|
| MOD-CORE-TRADER | Trader Orchestrator | src/trader/core.py | Yaşam döngüsü, guards, state | MOD-RISK, MOD-EXEC, MOD-GUARDS, MOD-TRAIL, MOD-METRICS, MOD-UTILS-STORE | active |
| MOD-EXEC | Execution | src/trader/execution.py | Aç/Kapa, koruma emirleri, boyut | MOD-RISK, API-BINANCE | active |
| MOD-GUARDS | Guards | src/trader/guards.py | Halt, risk limiti, korelasyon, hacim, outlier | MOD-UTILS-STORE, MOD-CORR-CACHE | active |
| MOD-TRAIL | Trailing & Partial | src/trader/trailing.py | Partial exits & trailing stop | MOD-CORE-TRADER | active |
| MOD-METRICS | Metrics | src/trader/metrics.py | Latency/slippage, anomaly + risk reduce | MOD-CORE-TRADER | active |
| MOD-RISK | RiskManager | src/risk_manager.py | Stop/TP, boyutlama | Settings | active |
| MOD-UTILS-STORE | TradeStore | src/utils/trade_store.py | DB persist & sorgu | sqlite3, pandas | active |
| MOD-API-BINANCE | BinanceAPI | src/api/binance_api.py | Veri & emir arabirimi | python-binance | active |
| MOD-API-HEALTH | HealthChecker | src/api/health_check.py | Bağlantı & izin kontrol | MOD-API-BINANCE | active |
| MOD-API-PRICESTREAM | PriceStream | src/api/price_stream.py | WS stream & reconnect | websocket-client | active |
| MOD-CORR-CACHE | CorrelationCache | src/utils/correlation_cache.py | Korelasyon pencere/TTL | numpy | active |
| MOD-DATA-FETCHER | DataFetcher | src/data_fetcher.py | Pair list, OHLCV, stale tespit | MOD-API-BINANCE, Settings | active |
| MOD-INDICATORS | IndicatorCalculator | src/indicators.py | İndikatör & skor | pandas, ta | active |
| MOD-SIGNAL-GEN | SignalGenerator | src/signal_generator.py | Sinyal + hysteresis | MOD-DATA-FETCHER, MOD-INDICATORS | active |
| MOD-UTILS-SLOG | StructuredLog | src/utils/structured_log.py | JSON event logging | Settings | active |
| MOD-UTILS-FLAGS | FeatureFlags | src/utils/feature_flags.py | Env tabanlı flag | None | active |
| MOD-UTILS-HELPERS | Helpers | src/utils/helpers.py | IO & PnL yardımcı | pandas | active |
| MOD-UTILS-LOGGER | Logger | src/utils/logger.py | Rotating logger | logging | active |
| MOD-UTILS-REPLAY | ReplayManager | src/utils/replay_manager.py | Trade decision replay & determinism | structured_log, config_snapshot | active |
| MOD-UTILS-RISK-ESCALATION | RiskEscalation | src/utils/risk_escalation.py | Unified risk escalation & kill-switch | MOD-CORE-TRADER, Settings | active |
| MOD-UTILS-WS | WS Utils | src/utils/ws_utils.py | WS restart kararı | time | active |
| MOD-UI-MAIN | MainWindow | src/ui/main_window.py | PyQt5 ana UI + Meta-Router tab + Portfolio tab + Bot Control Center | PyQt5, MOD-CORE-TRADER, MOD-UI-META-ROUTER, MOD-UI-PORTFOLIO, MOD-UI-BOT-CONTROL | active |
| MOD-UI-SIGNAL | SignalWindow | src/ui/signal_window.py | Sinyal analiz UI | PyQt5 | active |
| MOD-UI-META-ROUTER | MetaRouterPanel | src/ui/meta_router_panel.py | Meta-Router real-time kontrol paneli | PyQt5, QTimer | active |
| MOD-UI-PORTFOLIO | PortfolioAnalysisPanel | src/ui/portfolio_analysis_panel.py | Portfolio analiz paneli: korelasyon, risk metrikleri, optimizasyon | PyQt5, MOD-PORTFOLIO-ANALYZER | active |
| MOD-AUTOMATION-SCHEDULER | BotScheduler | src/utils/scheduler.py | Advanced task scheduler, cron-like functionality, market hours automation | datetime, threading | active |
| MOD-UI-AUTOMATION | AutomationPanel | src/ui/main_window.py (_add_automation_panel) | Automation UI panel: scheduler control, daily scheduling, maintenance windows | PyQt5, MOD-AUTOMATION-SCHEDULER | active |
| MOD-BACKTEST-CAL | Calibration | src/backtest/calibrate.py | Threshold optimizasyon & sim | MOD-DATA-FETCHER, MOD-INDICATORS | active |
| MOD-BACKTEST-ORCH | BacktestOrchestrator | src/backtest/orchestrator.py | Backtest workflow | MOD-BACKTEST-CAL | skeleton |
| MOD-SCRIPT-INVENTORY | InventoryGenerator | scripts/generate_inventory.py | Envanter üretim aracı | os, ast | active |
| MOD-PORTFOLIO-CORR | CorrelationMatrix | src/portfolio/correlation_matrix.py | Multi-asset korelasyon analizi, eigenvalue decomposition | pandas, numpy | active |
| MOD-PORTFOLIO-RISK | RiskMetrics | src/portfolio/risk_metrics.py | VaR calculator, portfolio risk metrics | pandas, numpy, scipy | active |
| MOD-PORTFOLIO-ANALYZER | PortfolioAnalyzer | src/portfolio/portfolio_analyzer.py | Ana portfolio analiz motoru, snapshot yönetimi | MOD-PORTFOLIO-CORR, MOD-PORTFOLIO-RISK | active |
| MOD-ML-FEATURE-ENG | SimpleFeatureEngineer | src/ml/simple_ml_pipeline.py | Feature engineering pipeline, technical indicators | pandas, numpy | active |
| MOD-ML-REGIME-DET | RuleBasedRegimeDetector | src/ml/simple_ml_pipeline.py | Market regime classification (trending/ranging/squeeze) | pandas, numpy | active |
| MOD-VOLATILITY-REGIME | VolatilityRegimeDetector | src/regime/volatility_detector.py | Dynamic market regime detection, volatility analysis | numpy, logging | active |
| MOD-ADVANCED-IMPACT | AdvancedMarketImpactCalculator | src/execution/advanced_impact_models.py | Advanced market impact modeling, 5 sophisticated models (Linear, Square-root, Kyle's lambda, Power-law, Concave), Implementation shortfall, optimization | numpy, scipy, typing | active |
| MOD-SMART-EXECUTION | SmartExecutionStrategies | src/execution/smart_execution_strategies.py | TWAP/VWAP execution algorithms, smart routing optimization, execution planning, cost estimation, market condition analysis | MOD-ADVANCED-IMPACT, MOD-LIQUIDITY-ANALYZER | active |
| MOD-ADVANCED-ML | AdvancedMLPipeline | src/ml/advanced_ml_pipeline.py | Next-generation ML system: 50+ features, ensemble models (XGBoost/LightGBM/RF), real-time inference <100ms, model drift detection, A/B testing | pandas, numpy, xgboost, lightgbm | active |
| MOD-A31-META-ROUTER | MetaRouter | src/strategy/meta_router.py | 4 specialist coordination, MWU weight learning, gating system, ensemble signal generation | MOD-SIGNAL-GEN, MOD-STRATEGY-SPECIALISTS | active |
| MOD-A31-TREND-PB-BO | TrendPBBOSpecialist | src/strategy/trend_pb_bo.py | Trend pullback/breakout specialist strategy | MOD-INDICATORS, MOD-SPECIALIST-INTERFACE | active |
| MOD-A31-RANGE-MR | RangeMRSpecialist | src/strategy/range_mr.py | Range mean-reversion specialist strategy | MOD-INDICATORS, MOD-SPECIALIST-INTERFACE | active |
| MOD-A31-VOL-BREAKOUT | VolBreakoutSpecialist | src/strategy/vol_breakout.py | Volume breakout specialist strategy | MOD-INDICATORS, MOD-SPECIALIST-INTERFACE | active |
| MOD-A31-XSECT-MOM | XSectMomSpecialist | src/strategy/xsect_momentum.py | Cross-sectional momentum specialist strategy | MOD-DATA-FETCHER, MOD-SPECIALIST-INTERFACE | active |
| MOD-A32-EDGE-HEALTH | EdgeHealthMonitor | src/utils/edge_health.py | Trading edge health monitoring, Wilson CI, 200 trade window | MOD-UTILS-STORE, numpy, scipy | active |
| MOD-A32-COST-CALC | CostOfEdgeCalculator | src/utils/cost_calculator.py | 4× cost-of-edge rule, fee/slippage estimation | MOD-API-BINANCE | active |
| MOD-A32-MICROSTRUCTURE | MicrostructureFilter | src/utils/microstructure.py | OBI/AFR real-time filters, order book analysis | MOD-API-BINANCE | active |

## Modül Durumları
- **active**: Operasyonel ve test edilmiş
- **skeleton**: Temel yapı mevcut, implementasyon devam ediyor
- **planned**: Tasarım aşamasında, implementasyon bekliyor
- **deprecated**: Kullanımdan kaldırılmış veya kaldırılacak

## Modül Bağımlılık Haritası
- **Tier 1 (Core)**: MOD-CORE-TRADER, MOD-UTILS-STORE, MOD-API-BINANCE
- **Tier 2 (Logic)**: MOD-EXEC, MOD-RISK, MOD-SIGNAL-GEN, MOD-GUARDS
- **Tier 3 (Features)**: MOD-TRAIL, MOD-METRICS, MOD-UI-MAIN
- **Tier 4 (Advanced)**: MOD-A31-META-ROUTER, MOD-A32-EDGE-HEALTH, MOD-ADVANCED-ML
