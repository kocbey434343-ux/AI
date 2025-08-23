import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # API
    BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
    BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET")
    USE_TESTNET = os.getenv("USE_TESTNET", "false").lower() == "true"
    # Offline (test / debug) mode: "true" => force, "auto" => enabled if no API key, anything else => disable
    _offline_env = os.getenv("OFFLINE_MODE", "auto").lower()
    OFFLINE_MODE = True if _offline_env == "true" else (False if _offline_env not in ("true","auto") else (BINANCE_API_KEY in (None, "") or BINANCE_API_SECRET in (None, "")))
    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    # Structured logging toggle
    STRUCTURED_LOG_ENABLED = os.getenv("STRUCTURED_LOG_ENABLED", "true").lower() == "true"

    # Relative default paths
    DATA_PATH = os.getenv("DATA_PATH", "./data")
    LOG_PATH = os.getenv("LOG_PATH", "./data/logs")
    BACKUP_PATH = os.getenv("BACKUP_PATH", "./backup")

    # Risk
    DEFAULT_RISK_PERCENT = float(os.getenv("DEFAULT_RISK_PERCENT", "1.0"))  # safer default 1%
    DEFAULT_LEVERAGE = int(os.getenv("DEFAULT_LEVERAGE", "3"))
    DEFAULT_MAX_POSITIONS = int(os.getenv("DEFAULT_MAX_POSITIONS", "3"))
    DEFAULT_MIN_VOLUME = float(os.getenv("DEFAULT_MIN_VOLUME", "50000"))

    # Signals
    # Thresholds (optimized candidate)
    BUY_SIGNAL_THRESHOLD: float = 50  # formerly 80
    SELL_SIGNAL_THRESHOLD: float = 17  # formerly 40
    # Histerezis (flip-flop engelleme) - optimize adaya gore ayarlandi
    BUY_EXIT_THRESHOLD: float = 45    # formerly 75 (BUY-5 mantigi)
    SELL_EXIT_THRESHOLD: float = 22   # formerly 45 (SELL+5 mantigi)
    # Regime filter (ADX minimum) - dusuk trend donemlerinde sinyal baskilama
    ADX_MIN_THRESHOLD = 25

    # Simulation / Trading Costs
    # DIKKAT: Bu degerler yuzde cinsinden saklanir (0.04 => %0.04 = 4 bps). Hesaplamalarda /100 yapilmalidir.
    # Round-trip tahmini maliyet ≈ 2 * (commission + slippage) (yuzde cinsinden dusunulunce /100 /100).
    # Ileride kafa karismasini azaltmak icin isimler korunuyor, fakat README'de netlestirilecek.
    COMMISSION_PCT_PER_SIDE = float(os.getenv("COMMISSION_PCT_PER_SIDE", "0.04"))  # stored as percent
    SLIPPAGE_PCT_PER_SIDE = float(os.getenv("SLIPPAGE_PCT_PER_SIDE", "0.02"))      # stored as percent
    # Gelişmiş (placeholder) dinamik kayma parametreleri
    DYNAMIC_SLIPPAGE_MULT = float(os.getenv("DYNAMIC_SLIPPAGE_MULT", "0.0"))
    SPREAD_BASIS_POINTS = float(os.getenv("SPREAD_BASIS_POINTS", "0.0"))
    TRADES_DB_PATH = os.getenv("TRADES_DB_PATH", "./data/trades.db")

    # Daily risk guardrails
    MAX_DAILY_LOSS_PCT = float(os.getenv("MAX_DAILY_LOSS_PCT", "3.0"))
    MAX_CONSECUTIVE_LOSSES = int(os.getenv("MAX_CONSECUTIVE_LOSSES", "4"))
    DAILY_HALT_FLAG_PATH = os.getenv("DAILY_HALT_FLAG_PATH", "./data/daily_halt.flag")
    # Outlier & param set
    OUTLIER_RETURN_THRESHOLD_PCT = float(os.getenv("OUTLIER_RETURN_THRESHOLD_PCT", "5.0"))
    PARAM_SET_ID = os.getenv("PARAM_SET_ID", "default")
    # Partial exit & trailing
    ENABLE_PARTIAL_EXITS = os.getenv("ENABLE_PARTIAL_EXITS", "true").lower() == "true"
    PARTIAL_TP1_R_MULT = float(os.getenv("PARTIAL_TP1_R_MULT", "1.0"))
    PARTIAL_TP1_PCT = float(os.getenv("PARTIAL_TP1_PCT", "50.0"))
    PARTIAL_TP2_R_MULT = float(os.getenv("PARTIAL_TP2_R_MULT", "1.8"))
    PARTIAL_TP2_PCT = float(os.getenv("PARTIAL_TP2_PCT", "30.0"))
    TRAILING_ACTIVATE_R_MULT = float(os.getenv("TRAILING_ACTIVATE_R_MULT", "1.2"))
    TRAILING_STEP_PCT = float(os.getenv("TRAILING_STEP_PCT", "25.0"))

    # Correlation control (stub)
    CORRELATION_WINDOW = int(os.getenv("CORRELATION_WINDOW", "50"))
    CORRELATION_THRESHOLD = float(os.getenv("CORRELATION_THRESHOLD", "0.85"))
    MAX_CORRELATED_POSITIONS = int(os.getenv("MAX_CORRELATED_POSITIONS", "2"))
    CORRELATION_TTL_SECONDS = int(os.getenv("CORRELATION_TTL_SECONDS", "900"))

    # API retry / backoff
    RETRY_MAX_ATTEMPTS = int(os.getenv("RETRY_MAX_ATTEMPTS", "3"))
    RETRY_BACKOFF_BASE_SEC = float(os.getenv("RETRY_BACKOFF_BASE_SEC", "0.5"))
    RETRY_BACKOFF_MULT = float(os.getenv("RETRY_BACKOFF_MULT", "2.0"))

    # Advanced trailing
    ATR_TRAILING_START_R = float(os.getenv("ATR_TRAILING_START_R", "1.5"))
    ATR_TRAILING_MULT = float(os.getenv("ATR_TRAILING_MULT", "1.2"))
    ATR_TRAILING_COOLDOWN_SEC = int(os.getenv("ATR_TRAILING_COOLDOWN_SEC", "60"))

    # Metrics
    METRICS_REPORT_LOOKBACK_HOURS = int(os.getenv("METRICS_REPORT_LOOKBACK_HOURS", "24"))
    METRICS_FILE_ENABLED = os.getenv("METRICS_FILE_ENABLED", "true").lower() == "true"
    METRICS_FILE_DIR = os.getenv("METRICS_FILE_DIR", "./data/processed/metrics")
    METRICS_FLUSH_INTERVAL_SEC = int(os.getenv("METRICS_FLUSH_INTERVAL_SEC", "60"))
    LATENCY_ANOMALY_MS = float(os.getenv("LATENCY_ANOMALY_MS", "1000"))  # ortalama acilis latency bu esigi gecerse uyar
    SLIPPAGE_ANOMALY_BPS = float(os.getenv("SLIPPAGE_ANOMALY_BPS", "35"))  # ortalama entry slip bps bu esigi gecerse uyar
    # Anomaly risk reduction multiplier (risk_percent *= multiplier on anomaly, restore on recovery)
    ANOMALY_RISK_MULT = float(os.getenv("ANOMALY_RISK_MULT", "0.5"))

    # Adaptive risk sizing (ATR yukseldikce risk azaltma)
    ADAPTIVE_RISK_ENABLED = os.getenv("ADAPTIVE_RISK_ENABLED", "true").lower() == "true"
    ADAPTIVE_RISK_ATR_REF_PCT = float(os.getenv("ADAPTIVE_RISK_ATR_REF_PCT", "2.5"))  # ATR% referans (ATR/price*100)
    ADAPTIVE_RISK_MIN_MULT = float(os.getenv("ADAPTIVE_RISK_MIN_MULT", "0.5"))
    ADAPTIVE_RISK_MAX_MULT = float(os.getenv("ADAPTIVE_RISK_MAX_MULT", "1.25"))

    # Backtest / Calibration behaviour
    USE_NEXT_BAR_FILL = os.getenv("USE_NEXT_BAR_FILL", "false").lower() == "true"
    CALIB_PARALLEL_WORKERS = int(os.getenv("CALIB_PARALLEL_WORKERS", "4"))

    # Indicators
    INDICATORS_CONFIG = "config/indicators.json"

    # Other
    BACKTEST_DAYS = 30
    TIMEFRAME = "1h"
    TOP_PAIRS_COUNT = 150
    # Gecici analiz limiti (gelistirme icin). 0 veya None ise tum TOP_PAIRS_COUNT kullanilir.
    ANALYSIS_PAIRS_LIMIT = int(os.getenv("ANALYSIS_PAIRS_LIMIT", "3"))  # dev limit; prod icin 0
    CONNECTION_TIMEOUT = 30  # seconds
    # Websocket stream config
    WS_BASE_BACKOFF_SEC = float(os.getenv("WS_BASE_BACKOFF_SEC", "2.0"))
    WS_MAX_BACKOFF_SEC = float(os.getenv("WS_MAX_BACKOFF_SEC", "60.0"))
    WS_TIMEOUT_SEC = float(os.getenv("WS_TIMEOUT_SEC", "25.0"))
    WS_MAX_RETRIES = os.getenv("WS_MAX_RETRIES")
    WS_MAX_RETRIES = int(WS_MAX_RETRIES) if (WS_MAX_RETRIES is not None and WS_MAX_RETRIES.strip() != "") else None
    WS_HEALTH_INTERVAL_MS = int(os.getenv("WS_HEALTH_INTERVAL_MS", "10000"))
    # WS dynamic symbol management
    WS_REFRESH_DEBOUNCE_SEC = float(os.getenv("WS_REFRESH_DEBOUNCE_SEC", "2.0"))
    WS_SYMBOL_LIMIT = int(os.getenv("WS_SYMBOL_LIMIT", "40"))
    # UI toggles
    SHOW_UNREALIZED_TOTAL = os.getenv("SHOW_UNREALIZED_TOTAL", "true").lower() == "true"

    # Market mode default
    MARKET_MODE = os.getenv("MARKET_MODE", "spot").lower()

class RuntimeConfig:
    MARKET_MODE = Settings.MARKET_MODE

    @classmethod
    def set_market_mode(cls, mode: str):
        cls.MARKET_MODE = (mode or "spot").lower()

    @classmethod
    def get_market_mode(cls) -> str:
        return cls.MARKET_MODE
