import contextlib
from datetime import datetime, timezone
import logging
import os

from config.settings import Settings
from src.trader import Trader
from src.utils.trade_store import TradeStore


def fresh_trader(tmp_path):
    db_file = tmp_path / 'trades.db'
    os.environ['TRADES_DB_PATH'] = str(db_file)
    tr = Trader()
    # isolate store
    tr.trade_store = TradeStore(str(db_file))
    return tr


def test_daily_risk_reset_triggers(tmp_path):
    tr = fresh_trader(tmp_path)
    # point halt flag path to temp
    flag_path = tmp_path / 'daily_halt.flag'
    Settings.DAILY_HALT_FLAG_PATH = str(flag_path)
    flag_path.write_text('halt')
    # force old date
    tr._risk_reset_date = '2000-01-01'
    # add guard counters
    tr.guard_counters['daily_loss'] = 3
    # call
    # Logger bellegi icin gecici handler
    records: list[str] = []
    class _ListHandler(logging.Handler):
        def emit(self, record):
            with contextlib.suppress(Exception):
                records.append(record.getMessage())
    logger = logging.getLogger("Trader")
    lh = _ListHandler()
    logger.addHandler(lh)
    try:
        res = tr._maybe_daily_risk_reset()
    finally:
        logger.removeHandler(lh)
    assert res is True
    assert not flag_path.exists(), 'halt flag silinmeli'
    assert len(tr.guard_counters) == 0, 'sayaclar sifirlanmali'
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    assert tr._risk_reset_date == today
    assert any('RISK_RESET:' in m for m in records), 'log mesaji yok'


def test_daily_risk_reset_noop_same_day(tmp_path):
    tr = fresh_trader(tmp_path)
    # ensure path isolated
    flag_path = tmp_path / 'daily_halt.flag'
    Settings.DAILY_HALT_FLAG_PATH = str(flag_path)
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    tr._risk_reset_date = today
    tr.guard_counters['dummy'] = 1
    res = tr._maybe_daily_risk_reset()
    assert res is False
    assert tr.guard_counters.get('dummy') == 1, 'sayac korunmali'
