import json
from datetime import datetime
from pathlib import Path
from config.settings import Settings
from src.utils.logger import get_logger

LOGGER = get_logger("RuntimeCosts")
COSTS_FILE = Path("config/runtime_costs.json")

def load_runtime_costs():
    if not COSTS_FILE.exists():
        return False
    try:
        data = json.loads(COSTS_FILE.read_text(encoding='utf-8'))
        commission = data.get('commission_pct_per_side')
        slippage = data.get('slippage_pct_per_side')
        next_bar = data.get('use_next_bar_fill')
        if commission is not None:
            Settings.COMMISSION_PCT_PER_SIDE = float(commission)
        if slippage is not None:
            Settings.SLIPPAGE_PCT_PER_SIDE = float(slippage)
        if next_bar is not None:
            Settings.USE_NEXT_BAR_FILL = bool(next_bar)
        LOGGER.info(f"Loaded runtime costs: commission={Settings.COMMISSION_PCT_PER_SIDE} slippage={Settings.SLIPPAGE_PCT_PER_SIDE} next_bar_fill={Settings.USE_NEXT_BAR_FILL}")
        return True
    except Exception as e:
        LOGGER.error(f"Runtime costs load failed: {e}")
        return False

def persist_runtime_costs(source: str = "manual"):
    payload = {
        "ts": datetime.utcnow().isoformat() + "Z",
        "commission_pct_per_side": Settings.COMMISSION_PCT_PER_SIDE,
        "slippage_pct_per_side": Settings.SLIPPAGE_PCT_PER_SIDE,
        "use_next_bar_fill": Settings.USE_NEXT_BAR_FILL,
        "source": source
    }
    try:
        COSTS_FILE.write_text(json.dumps(payload, indent=2), encoding='utf-8')
        LOGGER.info(f"Persisted runtime costs: {payload}")
        return True
    except Exception as e:
        LOGGER.error(f"Persist runtime costs failed: {e}")
        return False
