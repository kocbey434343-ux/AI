import os
from dotenv import load_dotenv

load_dotenv()

def _sanitize_cost_percent(name: str, value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """Yuzde degeri mantikli sinirlara kirmadan sigdir (clamp) ve asiri degerleri uyar.
    Degerler yuzde olarak saklanir (0.04 => %0.04). max_val default=1.0 (%1.00) konservatif ust sinir.
    Not: settings import sirasinda logger kullanmamak icin basit print ile uyarilir.
    """
    try:
        v = float(value)
    except (TypeError, ValueError):
        v = 0.0
    if v < min_val:
        print(f"[Settings] WARN: {name} < {min_val} ise {min_val}'a cekildi (was={value})")
        return min_val
    if v > max_val:
        print(f"[Settings] WARN: {name} > {max_val} ise {max_val}'a cekildi (was={value})")
        return max_val
    return v

class Settings:
    # API
    BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
    BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET")
    # Varsayilan: testnet (operasyonel guvenlik). Prod icin ALLOW_PROD=true gerekir.
    USE_TESTNET = os.getenv("USE_TESTNET", "true").lower() == "true"
    ALLOW_PROD = os.getenv("ALLOW_PROD", "false").lower() == "true"
    # Offline (test / debug) mode: "true" => force, "auto" => enabled if no API key, anything else => disable
    _offline_env = os.getenv("OFFLINE_MODE", "auto").lower()
    if _offline_env == "true":
        OFFLINE_MODE = True
    elif _offline_env == "auto":
        OFFLINE_MODE = (BINANCE_API_KEY in (None, "") or BINANCE_API_SECRET in (None, ""))
    else:
        OFFLINE_MODE = False
    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    # Structured logging toggle
    STRUCTURED_LOG_ENABLED = os.getenv("STRUCTURED_LOG_ENABLED", "true").lower() == "true"
    # Structured log JSON schema validation (CR-0075)
    STRUCTURED_LOG_VALIDATION = os.getenv("STRUCTURED_LOG_VALIDATION", "true").lower() == "true"

    # Env-aware path isolation flag (off|on|auto). Default: off (geriye donuk uyum)
    ENV_ISOLATION = os.getenv("ENV_ISOLATION", "off").lower()

    # Relative default paths (klasik varsayilanlar; izolasyon sonradan uygulanir)
    DATA_PATH = os.getenv("DATA_PATH", "./data")
    LOG_PATH = os.getenv("LOG_PATH", "./data/logs")
    BACKUP_PATH = os.getenv("BACKUP_PATH", "./backup")

    # Risk - Personal use optimization: more conservative settings
    DEFAULT_RISK_PERCENT = float(os.getenv("DEFAULT_RISK_PERCENT", "0.75"))  # Personal use: 1.0% → 0.75% (extra safety)
    DEFAULT_LEVERAGE = int(os.getenv("DEFAULT_LEVERAGE", "3"))
    DEFAULT_MAX_POSITIONS = int(os.getenv("DEFAULT_MAX_POSITIONS", "2"))  # Personal use: 3 → 2 (better focus)
    DEFAULT_MIN_VOLUME = float(os.getenv("DEFAULT_MIN_VOLUME", "50000"))

    # Signals - Personal use optimization: fine-tuned for personal trading style
    # Thresholds (personal use optimized)
    BUY_SIGNAL_THRESHOLD: float = 45  # Personal use: 50 → 45 (slightly more signals)
    SELL_SIGNAL_THRESHOLD: float = 20  # Personal use: 17 → 20 (more conservative exits)
    # Histerezis (flip-flop engelleme) - personal use optimization
    BUY_EXIT_THRESHOLD: float = 40    # Personal use: 45 → 40 (BUY-5 logic maintained)
    SELL_EXIT_THRESHOLD: float = 25   # Personal use: 22 → 25 (SELL+5 logic maintained)
    # Regime filter (ADX minimum) - dusuk trend donemlerinde sinyal baskilama
    ADX_MIN_THRESHOLD = 25

    # Simulation / Trading Costs
    # DIKKAT: Bu degerler yuzde cinsinden saklanir (0.04 => %0.04 = 4 bps). Hesaplamalarda /100 yapilmalidir.
    # Round-trip tahmini maliyet ≈ 2 * (commission + slippage) (yuzde cinsinden dusunulunce /100 /100).
    # Ileride kafa karismasini azaltmak icin isimlar korunuyor, fakat README'de netlestirilecek.
    # Not: MAKER/TAKER opsiyoneldir; set edilmezse COMMISSION_PCT_PER_SIDE kullanilir (geriye donuk uyum).

    COMMISSION_PCT_PER_SIDE = _sanitize_cost_percent(
        "COMMISSION_PCT_PER_SIDE", float(os.getenv("COMMISSION_PCT_PER_SIDE", "0.04"))
    )  # stored as percent
    SLIPPAGE_PCT_PER_SIDE = _sanitize_cost_percent(
        "SLIPPAGE_PCT_PER_SIDE", float(os.getenv("SLIPPAGE_PCT_PER_SIDE", "0.02"))
    )  # stored as percent

    # Opsiyonel maker/taker ayri parametreleri; belirtilmezse COMMISSION_PCT_PER_SIDE kullanilir
    MAKER_COMMISSION_PCT_PER_SIDE = _sanitize_cost_percent(
        "MAKER_COMMISSION_PCT_PER_SIDE",
        float(os.getenv("MAKER_COMMISSION_PCT_PER_SIDE", str(COMMISSION_PCT_PER_SIDE)))
    )
    TAKER_COMMISSION_PCT_PER_SIDE = _sanitize_cost_percent(
        "TAKER_COMMISSION_PCT_PER_SIDE",
        float(os.getenv("TAKER_COMMISSION_PCT_PER_SIDE", str(COMMISSION_PCT_PER_SIDE)))
    )
    # Gelişmiş (placeholder) dinamik kayma parametreleri
    DYNAMIC_SLIPPAGE_MULT = float(os.getenv("DYNAMIC_SLIPPAGE_MULT", "0.0"))
    SPREAD_BASIS_POINTS = float(os.getenv("SPREAD_BASIS_POINTS", "0.0"))
    TRADES_DB_PATH = os.getenv("TRADES_DB_PATH", "./data/trades.db")

    # Daily risk guardrails - Personal use: tighter controls
    MAX_DAILY_LOSS_PCT = float(os.getenv("MAX_DAILY_LOSS_PCT", "2.0"))  # Personal use: 3.0% → 2.0% (tighter control)
    MAX_CONSECUTIVE_LOSSES = int(os.getenv("MAX_CONSECUTIVE_LOSSES", "3"))  # Personal use: 4 → 3 (faster halt)
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
    CORRELATION_DYNAMIC_ENABLED = os.getenv("CORRELATION_DYNAMIC_ENABLED", "true").lower() == "true"  # CR-0048
    CORRELATION_MIN_THRESHOLD = float(os.getenv("CORRELATION_MIN_THRESHOLD", "0.70"))  # CR-0048
    CORRELATION_MAX_THRESHOLD = float(os.getenv("CORRELATION_MAX_THRESHOLD", "0.92"))  # CR-0048
    CORRELATION_LATENCY_TARGET_MS = float(os.getenv("CORRELATION_LATENCY_TARGET_MS", "400"))  # CR-0048
    CORRELATION_ADJ_STEP = float(os.getenv("CORRELATION_ADJ_STEP", "0.01"))  # CR-0048

    # API retry / backoff
    RETRY_MAX_ATTEMPTS = int(os.getenv("RETRY_MAX_ATTEMPTS", "3"))
    RETRY_BACKOFF_BASE_SEC = float(os.getenv("RETRY_BACKOFF_BASE_SEC", "0.5"))
    RETRY_BACKOFF_MULT = float(os.getenv("RETRY_BACKOFF_MULT", "2.0"))
    # Order submit idempotency
    ORDER_DEDUP_TTL_SEC = float(os.getenv("ORDER_DEDUP_TTL_SEC", "5.0"))

    # Advanced trailing
    ATR_TRAILING_ENABLED = os.getenv("ATR_TRAILING_ENABLED", "true").lower() == "true"
    ATR_TRAILING_START_R = float(os.getenv("ATR_TRAILING_START_R", "1.2"))
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

    # Backtest / Calibration behaviour - Personal use: performance optimized
    USE_NEXT_BAR_FILL = os.getenv("USE_NEXT_BAR_FILL", "false").lower() == "true"
    CALIB_PARALLEL_WORKERS = int(os.getenv("CALIB_PARALLEL_WORKERS", "2"))  # Personal use: 4 → 2 (resource friendly)

    # Indicators
    INDICATORS_CONFIG = "config/indicators.json"

    # Other
    BACKTEST_DAYS = 30
    TIMEFRAME = "1h"
    TOP_PAIRS_COUNT = 50  # Personal use optimization: 150 → 50 (better performance)
    # Personal use optimization: slightly more pairs but still manageable
    ANALYSIS_PAIRS_LIMIT = int(os.getenv("ANALYSIS_PAIRS_LIMIT", "5"))  # Personal use: 3 → 5
    CONNECTION_TIMEOUT = 30  # seconds
    # Websocket stream config - Personal use: optimized intervals
    WS_BASE_BACKOFF_SEC = float(os.getenv("WS_BASE_BACKOFF_SEC", "2.0"))
    WS_MAX_BACKOFF_SEC = float(os.getenv("WS_MAX_BACKOFF_SEC", "60.0"))
    WS_TIMEOUT_SEC = float(os.getenv("WS_TIMEOUT_SEC", "25.0"))
    WS_MAX_RETRIES = os.getenv("WS_MAX_RETRIES")
    WS_MAX_RETRIES = int(WS_MAX_RETRIES) if (WS_MAX_RETRIES is not None and WS_MAX_RETRIES.strip() != "") else None
    WS_HEALTH_INTERVAL_MS = int(os.getenv("WS_HEALTH_INTERVAL_MS", "10000"))
    # WS dynamic symbol management - Personal use: reduced symbol limit
    WS_REFRESH_DEBOUNCE_SEC = float(os.getenv("WS_REFRESH_DEBOUNCE_SEC", "2.0"))
    WS_SYMBOL_LIMIT = int(os.getenv("WS_SYMBOL_LIMIT", "25"))  # Personal use: 40 → 25 (performance boost)
    # UI toggles
    SHOW_UNREALIZED_TOTAL = os.getenv("SHOW_UNREALIZED_TOTAL", "true").lower() == "true"

    # Market mode default
    MARKET_MODE = os.getenv("MARKET_MODE", "spot").lower()

    # Metrics retention settings
    METRICS_RETENTION_HOURS = int(os.getenv("METRICS_RETENTION_HOURS", "48"))  # CR-0046
    METRICS_RETENTION_COMPRESS = os.getenv("METRICS_RETENTION_COMPRESS", "true").lower() == "true"

    # Backup settings
    BACKUP_MAX_SNAPSHOTS = int(os.getenv("BACKUP_MAX_SNAPSHOTS", "10"))  # CR-0047
    BACKUP_RETENTION_DAYS = int(os.getenv("BACKUP_RETENTION_DAYS", "14"))  # CR-0047

    # Param set override
    PARAM_OVERRIDE_PATH = os.getenv("PARAM_OVERRIDE_PATH", "./data/param_overrides.json")  # CR-0050

    # CR-0065: Slippage Guard Configuration
    MAX_SLIPPAGE_BPS = float(os.getenv("MAX_SLIPPAGE_BPS", "50.0"))  # 0.5% = 50 basis points
    SLIPPAGE_GUARD_POLICY = os.getenv("SLIPPAGE_GUARD_POLICY", "ABORT")  # ABORT or REDUCE
    SLIPPAGE_REDUCTION_FACTOR = float(os.getenv("SLIPPAGE_REDUCTION_FACTOR", "0.5"))  # 50% reduction
    # Clock skew guard
    CLOCK_SKEW_WARN_MS = float(os.getenv("CLOCK_SKEW_WARN_MS", "500"))
    CLOCK_SKEW_GUARD_ENABLED = os.getenv("CLOCK_SKEW_GUARD_ENABLED", "true").lower() == "true"

    # --- RBP-LS v1.3.1 PoR: Geriye uyumlu konfig genislemeleri ---
    # Strateji surum bilgisi (telemetri/determinism icin bilgi amacli)
    STRATEGY_VERSION = os.getenv("STRATEGY_VERSION", "RBP-LS-1.3.1")
    # HTF EMA filtresi (kapali baslar; davranis degisikligi yok)
    HTF_FILTER_ENABLED = os.getenv("HTF_FILTER_ENABLED", "false").lower() == "true"
    HTF_EMA_TIMEFRAME = os.getenv("HTF_EMA_TIMEFRAME", "4h")
    HTF_EMA_LENGTH = int(os.getenv("HTF_EMA_LENGTH", "200"))
    # Giris modlari (mevcut sinyallerle uyumlu; her ikisi acik kalir)
    ENABLE_BREAKOUT = os.getenv("ENABLE_BREAKOUT", "true").lower() == "true"
    ENABLE_PULLBACK = os.getenv("ENABLE_PULLBACK", "true").lower() == "true"
    # Hedef RR (mevcut RiskManager default'unu bozmaz; 2.2 korunur)
    DEFAULT_TAKE_PROFIT_RR = float(os.getenv("DEFAULT_TAKE_PROFIT_RR", "2.2"))
    # Zaman durdurma (kapali baslar)
    TIME_STOP_ENABLED = os.getenv("TIME_STOP_ENABLED", "false").lower() == "true"
    TIME_STOP_BARS = int(os.getenv("TIME_STOP_BARS", "24"))
    # Spread guard (kapali baslar)
    SPREAD_GUARD_ENABLED = os.getenv("SPREAD_GUARD_ENABLED", "false").lower() == "true"
    SPREAD_MAX_BPS = float(os.getenv("SPREAD_MAX_BPS", "10.0"))
    # Koruma watchdog (aktif; mevcut retry/backoff ile uyumlu limitler)
    PROTECTION_WATCHDOG_ENABLED = os.getenv("PROTECTION_WATCHDOG_ENABLED", "true").lower() == "true"
    PROTECTION_RETRY_MAX = int(os.getenv("PROTECTION_RETRY_MAX", "3"))
    # Meta-router (personal use: disabled for single strategy focus)
    META_ROUTER_ENABLED = os.getenv("META_ROUTER_ENABLED", "false").lower() == "true"
    META_ROUTER_MODE = os.getenv("META_ROUTER_MODE", "mwu")

    # --- Smart Execution (TWAP/VWAP) ---
    # Personal use: disabled for simplicity (single market orders preferred)
    SMART_EXECUTION_ENABLED = os.getenv("SMART_EXECUTION_ENABLED", "false").lower() == "true"
    SMART_EXECUTION_MODE = os.getenv("SMART_EXECUTION_MODE", "twap")  # twap|vwap|auto
    TWAP_SLICES = int(os.getenv("TWAP_SLICES", "4"))
    TWAP_INTERVAL_SEC = float(os.getenv("TWAP_INTERVAL_SEC", "0.5"))  # prod icin arttirilabilir
    VWAP_WINDOW_BARS = int(os.getenv("VWAP_WINDOW_BARS", "20"))
    MAX_PARTICIPATION_RATE = float(os.getenv("MAX_PARTICIPATION_RATE", "0.2"))  # 20% (placeholder)
    MIN_SLICE_NOTIONAL_USDT = float(os.getenv("MIN_SLICE_NOTIONAL_USDT", "10.0"))
    MIN_SLICE_QTY = float(os.getenv("MIN_SLICE_QTY", "0.0"))  # 0 = quantize min auto
    SMART_EXECUTION_SLEEP_SEC = float(os.getenv("SMART_EXECUTION_SLEEP_SEC", "0.0"))  # tests icin 0

    # --- Helpers ---
    @classmethod
    def get_commission_rates(cls) -> tuple[float, float]:
        """(maker, taker) yuzde değerlerini döndür (0.04 => %0.04)."""
        return (cls.MAKER_COMMISSION_PCT_PER_SIDE, cls.TAKER_COMMISSION_PCT_PER_SIDE)

    @classmethod
    def round_trip_cost_pct(cls) -> float:
        """Round-trip tahmini maliyet (yuzde biriminde): 2 * (commission + slippage).
        Geriye donuk uyum icin tekil COMMISSION_PCT_PER_SIDE kullanilir.
        """
        return 2.0 * (cls.COMMISSION_PCT_PER_SIDE + cls.SLIPPAGE_PCT_PER_SIDE)

    # ================== SCALP MODE CONFIGURATION ==================
    # Scalp mode: Fast 5-minute trading with aggressive parameters
    SCALP_MODE_ENABLED = os.getenv("SCALP_MODE_ENABLED", "false").lower() == "true"

    # Scalp timeframes (faster than normal)
    SCALP_TIMEFRAME = os.getenv("SCALP_TIMEFRAME", "5m")  # 5-minute bars
    SCALP_UPDATE_INTERVAL = int(os.getenv("SCALP_UPDATE_INTERVAL", "2000"))  # 2 seconds (vs 5s normal)

    # Scalp signal thresholds (more aggressive)
    SCALP_BUY_SIGNAL_THRESHOLD = float(os.getenv("SCALP_BUY_SIGNAL_THRESHOLD", "60"))  # vs 50 normal
    SCALP_SELL_SIGNAL_THRESHOLD = float(os.getenv("SCALP_SELL_SIGNAL_THRESHOLD", "20"))  # vs 17 normal
    SCALP_BUY_EXIT_THRESHOLD = float(os.getenv("SCALP_BUY_EXIT_THRESHOLD", "55"))  # vs 45 normal
    SCALP_SELL_EXIT_THRESHOLD = float(os.getenv("SCALP_SELL_EXIT_THRESHOLD", "25"))  # vs 22 normal

    # Scalp risk management (tighter stops, smaller targets)
    SCALP_PROFIT_TARGET_PCT = float(os.getenv("SCALP_PROFIT_TARGET_PCT", "0.8"))  # 0.8% target (vs 2% normal)
    SCALP_STOP_LOSS_PCT = float(os.getenv("SCALP_STOP_LOSS_PCT", "0.4"))  # 0.4% stop (vs 1% normal)
    SCALP_MAX_HOLD_MINUTES = int(os.getenv("SCALP_MAX_HOLD_MINUTES", "15"))  # 15 min max hold

    # Scalp position sizing (smaller positions for faster turnover)
    SCALP_RISK_PERCENT = float(os.getenv("SCALP_RISK_PERCENT", "0.5"))  # 0.5% risk (vs 1% normal)
    SCALP_MAX_POSITIONS = int(os.getenv("SCALP_MAX_POSITIONS", "2"))  # Max 2 positions (vs 3 normal)

    # Scalp exit conditions (more aggressive exits)
    SCALP_PARTIAL_EXIT_ENABLED = os.getenv("SCALP_PARTIAL_EXIT_ENABLED", "true").lower() == "true"
    SCALP_PARTIAL_EXIT_PCT = float(os.getenv("SCALP_PARTIAL_EXIT_PCT", "50"))  # 50% at 0.4% profit
    SCALP_TRAILING_STOP_PCT = float(os.getenv("SCALP_TRAILING_STOP_PCT", "0.2"))  # 0.2% trailing

class RuntimeConfig:
    MARKET_MODE = Settings.MARKET_MODE

    @classmethod
    def set_market_mode(cls, mode: str):
        cls.MARKET_MODE = (mode or "spot").lower()

    @classmethod
    def get_market_mode(cls) -> str:
        return cls.MARKET_MODE

# --- Environment-based path scoping (optional) ---
# Not: Env override (ENV var) mevcutsa kullanici tercihi korunur.
def _detect_env_name() -> str:
    """Environment name detection - reads directly from env vars to support dynamic reloading"""
    try:
        # Read directly from environment to support test reloading scenarios
        offline_env = os.getenv("OFFLINE_MODE", "auto").lower()
        use_testnet_env = os.getenv("USE_TESTNET", "true").lower() == "true"

        # OFFLINE_MODE precedence logic (same as in Settings class)
        if offline_env == "true":
            offline_mode = True
        elif offline_env == "auto":
            api_key = os.getenv("BINANCE_API_KEY")
            api_secret = os.getenv("BINANCE_API_SECRET")
            offline_mode = (api_key in (None, "") or api_secret in (None, ""))
        else:
            offline_mode = False

        if offline_mode:
            return "offline"
        if use_testnet_env:
            return "testnet"
        return "prod"
    except Exception:
        return "prod"

def _join(*parts: str) -> str:
    return os.path.normpath(os.path.join(*parts))

_env_iso = os.getenv("ENV_ISOLATION", Settings.ENV_ISOLATION).lower()
if _env_iso in ("on", "auto"):
    # Constants for file/folder names to avoid magic strings
    DB_FILE_NAME = "trades.db"
    _env = _detect_env_name()
    _data_explicit = ("DATA_PATH" in os.environ)
    _db_explicit = ("TRADES_DB_PATH" in os.environ)
    _log_explicit = ("LOG_PATH" in os.environ)
    _bkp_explicit = ("BACKUP_PATH" in os.environ)
    _halt_explicit = ("DAILY_HALT_FLAG_PATH" in os.environ)
    _metrics_explicit = ("METRICS_FILE_DIR" in os.environ)

    # Normalize explicit overrides early to avoid being overwritten by derivation below
    # This ensures determinism when tests mutate environment variables before import.
    if _data_explicit:
        Settings.DATA_PATH = os.environ.get("DATA_PATH", Settings.DATA_PATH)
    if _db_explicit:
        Settings.TRADES_DB_PATH = os.environ.get("TRADES_DB_PATH", Settings.TRADES_DB_PATH)

    # TRADES_DB_PATH precedence (deterministic):
    # 1) If TRADES_DB_PATH is explicit (real override) -> respect.
    # 2) If DATA_PATH is explicit and TRADES_DB_PATH is not -> derive DATA_PATH/<env>/trades.db.
    # 3) If both are explicit:
    #    - If TRADES_DB_PATH has a custom filename (not trades.db) -> respect explicit override.
    #    - Else if TRADES_DB_PATH is not under DATA_PATH (probable leak) -> derive under DATA_PATH.
    def _norm(p: str) -> str:
        return os.path.normcase(os.path.normpath(p))

    if _db_explicit and not _data_explicit:
        # Saf override senaryosu — explicit TRADES_DB_PATH korunur ve normalize edilir
        Settings.TRADES_DB_PATH = os.path.normpath(Settings.TRADES_DB_PATH)
    elif _data_explicit and not _db_explicit:
        Settings.TRADES_DB_PATH = _join(Settings.DATA_PATH, _env, DB_FILE_NAME)
    elif _data_explicit and _db_explicit:
        try:
            env_db = _norm(os.environ.get("TRADES_DB_PATH", ""))
            # If custom filename is used, always respect explicit override (normalize path)
            if os.path.basename(env_db).lower() != DB_FILE_NAME:
                Settings.TRADES_DB_PATH = os.path.normpath(Settings.TRADES_DB_PATH)
            else:
                data_root = _norm(Settings.DATA_PATH)
                if not env_db.startswith(data_root + os.path.sep) and env_db != data_root:
                    # Probable leak: TRADES_DB_PATH is not under the provided DATA_PATH
                    Settings.TRADES_DB_PATH = _join(Settings.DATA_PATH, _env, DB_FILE_NAME)
        except Exception:
            # Güvenli tarafta kal: türet
            Settings.TRADES_DB_PATH = _join(Settings.DATA_PATH, _env, DB_FILE_NAME)
    elif not _db_explicit:
        # Neither DATA_PATH nor TRADES_DB_PATH explicit -> derive from default DATA_PATH
        Settings.TRADES_DB_PATH = _join(Settings.DATA_PATH, _env, DB_FILE_NAME)

    # LOG_PATH
    if _data_explicit or not _log_explicit:
        Settings.LOG_PATH = _join(Settings.DATA_PATH, "logs", _env)

    # BACKUP_PATH (DATA_PATH'tan bagimsiz dizin yapisi)
    if not _bkp_explicit:
        Settings.BACKUP_PATH = _join("backup", _env)

    # DAILY_HALT_FLAG_PATH
    if _data_explicit or not _halt_explicit:
        Settings.DAILY_HALT_FLAG_PATH = _join(Settings.DATA_PATH, _env, "daily_halt.flag")

    # METRICS_FILE_DIR
    if _data_explicit or not _metrics_explicit:
        Settings.METRICS_FILE_DIR = _join(Settings.DATA_PATH, "processed", "metrics", _env)

    # ======================= A32 EDGE HARDENING CONFIGURATION =======================
    # Edge Hardening System (personal use: disabled for simplicity)
    A32_EDGE_HARDENING_ENABLED = os.getenv("A32_EDGE_HARDENING_ENABLED", "false").lower() == "true"

    # Edge Health Monitor Settings
    EDGE_HEALTH_WINDOW_TRADES = int(os.getenv("EDGE_HEALTH_WINDOW_TRADES", "200"))
    EDGE_HEALTH_MIN_TRADES = int(os.getenv("EDGE_HEALTH_MIN_TRADES", "50"))
    EDGE_HEALTH_CONFIDENCE_INTERVAL = float(os.getenv("EDGE_HEALTH_CONFIDENCE_INTERVAL", "0.95"))
    EDGE_HEALTH_HOT_THRESHOLD = float(os.getenv("EDGE_HEALTH_HOT_THRESHOLD", "0.10"))  # >0.1R
    EDGE_HEALTH_WARM_THRESHOLD = float(os.getenv("EDGE_HEALTH_WARM_THRESHOLD", "0.0"))  # >0R

    # 4x Cost-of-Edge Rule Settings
    COST_OF_EDGE_MULTIPLIER = float(os.getenv("COST_OF_EDGE_MULTIPLIER", "4.0"))  # 4x rule
    COST_FEE_MODEL = os.getenv("COST_FEE_MODEL", "tiered")  # flat|tiered|dynamic
    COST_SLIPPAGE_MODEL = os.getenv("COST_SLIPPAGE_MODEL", "dynamic")  # static|dynamic|spread_based

    # Microstructure Filter Settings
    MICROSTRUCTURE_ENABLED = os.getenv("MICROSTRUCTURE_ENABLED", "false").lower() == "true"
    MICROSTRUCTURE_OBI_LEVELS = int(os.getenv("MICROSTRUCTURE_OBI_LEVELS", "5"))
    MICROSTRUCTURE_OBI_LONG_MIN = float(os.getenv("MICROSTRUCTURE_OBI_LONG_MIN", "0.20"))
    MICROSTRUCTURE_OBI_SHORT_MAX = float(os.getenv("MICROSTRUCTURE_OBI_SHORT_MAX", "-0.20"))
    MICROSTRUCTURE_AFR_WINDOW_TRADES = int(os.getenv("MICROSTRUCTURE_AFR_WINDOW_TRADES", "80"))
    MICROSTRUCTURE_AFR_LONG_MIN = float(os.getenv("MICROSTRUCTURE_AFR_LONG_MIN", "0.55"))
    MICROSTRUCTURE_AFR_SHORT_MAX = float(os.getenv("MICROSTRUCTURE_AFR_SHORT_MAX", "0.45"))
    MICROSTRUCTURE_CONFLICT_ACTION = os.getenv("MICROSTRUCTURE_CONFLICT_ACTION", "wait")  # wait|abort

    # Kelly Fraction Settings (for future integration)
    KELLY_ENABLED = os.getenv("KELLY_ENABLED", "false").lower() == "true"
    KELLY_CONSERVATIVE_MULT = float(os.getenv("KELLY_CONSERVATIVE_MULT", "0.25"))
    KELLY_MAX_FRACTION = float(os.getenv("KELLY_MAX_FRACTION", "0.005"))  # 0.5% max

    # Dead Zone Settings
    DEAD_ZONE_ENABLED = os.getenv("DEAD_ZONE_ENABLED", "false").lower() == "true"
    DEAD_ZONE_EPS_THRESHOLD = float(os.getenv("DEAD_ZONE_EPS_THRESHOLD", "0.05"))  # [-0.05, +0.05] no trade
