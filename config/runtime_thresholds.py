import json
from datetime import datetime
from pathlib import Path
from config.settings import Settings
from src.utils.logger import get_logger

LOGGER = get_logger("RuntimeThresholds")
RUNTIME_FILE = Path("config/runtime_thresholds.json")

SANITY_RULES = {
    "min_gap": 5.0,
    "min_buy": 20.0,
    "max_buy": 99.0,
    "min_sell": 1.0,
    "max_sell": 80.0,
    # Exit (histerezis) constraints are relative; we still keep broad absolute guards
    "min_buy_exit_delta": 1.0,   # buy_exit en az 1 puan altında olmalı
    "min_sell_exit_delta": 1.0   # sell_exit en az 1 puan üstünde olmalı
}

def load_runtime_thresholds():
    """Load persisted thresholds if file exists & sane.

    Supports optional hysteresis exit thresholds (buy_exit, sell_exit).
    """
    if not RUNTIME_FILE.exists():
        return False
    try:
        data = json.loads(RUNTIME_FILE.read_text(encoding='utf-8'))
        buy = float(data.get('buy'))
        sell = float(data.get('sell'))
        buy_exit = data.get('buy_exit')
        sell_exit = data.get('sell_exit')
        if not _is_sane(buy, sell, buy_exit, sell_exit):
            LOGGER.warning(f"Persisted thresholds not sane (buy={buy}, sell={sell}), ignoring file")
            return False
        Settings.BUY_SIGNAL_THRESHOLD = buy
        Settings.SELL_SIGNAL_THRESHOLD = sell
        if buy_exit is not None:
            try:
                Settings.BUY_EXIT_THRESHOLD = float(buy_exit)
            except Exception:
                pass
        if sell_exit is not None:
            try:
                Settings.SELL_EXIT_THRESHOLD = float(sell_exit)
            except Exception:
                pass
        LOGGER.info(f"Loaded runtime thresholds buy={buy} sell={sell} buy_exit={getattr(Settings,'BUY_EXIT_THRESHOLD',None)} sell_exit={getattr(Settings,'SELL_EXIT_THRESHOLD',None)} from {RUNTIME_FILE}")
        return True
    except Exception as e:
        LOGGER.error(f"Runtime thresholds load failed: {e}")
        return False

def persist_runtime_thresholds(buy: float, sell: float, buy_exit: float | None = None, sell_exit: float | None = None, source: str = "calibration"):
    """Persist thresholds (including optional exit hysteresis) if they are sane."""
    if not _is_sane(buy, sell, buy_exit, sell_exit):
        raise ValueError(f"Unsane thresholds buy={buy} sell={sell} buy_exit={buy_exit} sell_exit={sell_exit}")
    payload = {
        "ts": datetime.utcnow().isoformat() + "Z",
        "buy": round(buy, 4),
        "sell": round(sell, 4),
        "buy_exit": round(buy_exit, 4) if buy_exit is not None else None,
        "sell_exit": round(sell_exit, 4) if sell_exit is not None else None,
        "source": source
    }
    try:
        RUNTIME_FILE.write_text(json.dumps(payload, indent=2), encoding='utf-8')
        LOGGER.info(f"Persisted runtime thresholds: {payload}")
        return True
    except Exception as e:
        LOGGER.error(f"Persist thresholds failed: {e}")
        return False

def _is_sane(buy: float, sell: float, buy_exit: float | None = None, sell_exit: float | None = None) -> bool:
    if any(v is None for v in (buy, sell)):
        return False
    if not (SANITY_RULES['min_sell'] <= sell <= SANITY_RULES['max_sell']):
        return False
    if not (SANITY_RULES['min_buy'] <= buy <= SANITY_RULES['max_buy']):
        return False
    if not (buy - sell >= SANITY_RULES['min_gap']):
        return False
    # Histerezis ek kontrolü (opsiyonel parametreler verilmişse)
    if buy_exit is not None:
        try:
            if not (buy_exit < buy - SANITY_RULES['min_buy_exit_delta']):
                return False
        except Exception:
            return False
    if sell_exit is not None:
        try:
            if not (sell_exit > sell + SANITY_RULES['min_sell_exit_delta']):
                return False
        except Exception:
            return False
    return True
