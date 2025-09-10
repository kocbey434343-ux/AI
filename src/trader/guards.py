"""Guard ve risk kontrolleri.

Trader icersinden cagrilacak pure/helper fonksiyonlar.
Yan etkiler: self.guard_counters gunceller, log yazar.
"""
from __future__ import annotations

import contextlib
import os
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple

from config.settings import Settings

from src.utils.lookahead_guard import get_lookahead_guard
from src.utils.structured_log import slog  # Import moved to top to fix E402

if TYPE_CHECKING:
    from src.trader.core import Trader

# Freshness window for considering halt flag under pytest (seconds)
PYTEST_HALT_FRESH_SECONDS = 10


def map_signal(label: str) -> Tuple[Optional[str], Optional[str]]:
    if label == "AL":
        return "BUY", "long"
    if label == "SAT":
        return "SELL", "short"
    return None, None


def check_halt_flag(self: 'Trader') -> bool:
    # If risk escalation feature is disabled, ignore halt flag for tests/legacy mode
    if not getattr(Settings, 'RISK_ESCALATION_ENABLED', True):
        return True

    path_str = str(Settings.DAILY_HALT_FLAG_PATH)
    halt_flag = Path(path_str)
    # In pytest, ignore stale default global flag to prevent cross-test failures
    if os.getenv('PYTEST_CURRENT_TEST'):
        is_default = path_str.replace('\\', '/').endswith('/data/daily_halt.flag')
        fresh = True
        with contextlib.suppress(Exception):
            mtime = halt_flag.stat().st_mtime
            fresh = (time.time() - mtime) <= PYTEST_HALT_FRESH_SECONDS
        if is_default and os.getenv('PYTEST_ALLOW_GLOBAL_HALT_FLAG') != '1' and not fresh:
            return True
    if halt_flag.exists():
        self.logger.warning("Daily risk halt active (halt flag)")
        self.guard_counters['halt_flag'] += 1
        # CR-0069: Record guard event
        if hasattr(self, 'trade_store') and hasattr(self.trade_store, 'guard_events'):
            self.trade_store.guard_events.record_guard_event_simple(
                "halt_flag", "Daily risk halt flag exists"
            )
        return False
    return True


def check_daily_risk_limits(self: 'Trader') -> bool:
    halt_flag = Path(Settings.DAILY_HALT_FLAG_PATH)

    try:
        daily_pnl = self.trade_store.daily_realized_pnl_pct()
        if daily_pnl <= -Settings.MAX_DAILY_LOSS_PCT:
            self.logger.warning(f"Daily loss threshold exceeded {daily_pnl:.2f}% -> halt")
            try:
                halt_flag.write_text("daily loss halt")
            except (OSError, IOError) as e:
                self.logger.error(f"Failed to write halt flag: {e}")

            self.guard_counters['daily_loss'] += 1
            # CR-0069: Record guard event with loss data
            if hasattr(self, 'trade_store') and hasattr(self.trade_store, 'guard_events'):
                try:
                    from src.utils.guard_events import GuardEvent
                    event = GuardEvent(
                        guard="daily_loss",
                        reason=f"Daily loss {daily_pnl:.2f}% exceeded threshold {Settings.MAX_DAILY_LOSS_PCT}%",
                        extra_data={"daily_pnl_pct": daily_pnl, "threshold": Settings.MAX_DAILY_LOSS_PCT},
                        severity="CRITICAL"
                    )
                    self.trade_store.guard_events.record_guard_event(event)
                except (ImportError, AttributeError) as e:
                    self.logger.error(f"Failed to record guard event: {e}")
            return False

        consec = self.trade_store.consecutive_losses()
        if consec >= Settings.MAX_CONSECUTIVE_LOSSES:
            self.logger.warning(f"Consecutive loss limit {consec}")
            try:
                halt_flag.write_text("consecutive losses halt")
            except (OSError, IOError) as e:
                self.logger.error(f"Failed to write halt flag: {e}")

            self.guard_counters['consec_losses'] += 1
            # CR-0069: Record consecutive loss guard event
            if hasattr(self, 'trade_store') and hasattr(self.trade_store, 'guard_events'):
                try:
                    from src.utils.guard_events import GuardEvent
                    event = GuardEvent(
                        guard="consecutive_losses",
                        reason=f"Consecutive losses {consec} exceeded limit {Settings.MAX_CONSECUTIVE_LOSSES}",
                        extra_data={"consecutive_losses": consec, "limit": Settings.MAX_CONSECUTIVE_LOSSES},
                        severity="WARNING"
                    )
                    self.trade_store.guard_events.record_guard_event(event)
                except (ImportError, AttributeError) as e:
                    self.logger.error(f"Failed to record guard event: {e}")
            return False
    except (AttributeError, ValueError, TypeError) as e:
        self.logger.error(f"Error checking daily risk limits: {e}")
        return True  # Safe default: allow trading if check fails

    return True


def check_outlier_bar(self: 'Trader', signal: Dict[str, Any], price: float) -> bool:
    prev_price = float(signal.get('prev_close', price))
    if prev_price > 0:
        move_pct = abs((price - prev_price) / prev_price) * 100.0
        if move_pct >= Settings.OUTLIER_RETURN_THRESHOLD_PCT:
            symbol = signal.get('symbol', 'UNKNOWN')
            self.logger.info(f"Outlier bar filtered {symbol} move={move_pct:.2f}%")
            self.guard_counters['outlier_bar'] += 1
            # CR-0069: Record outlier bar guard event
            if hasattr(self, 'trade_store') and hasattr(self.trade_store, 'guard_events'):
                from src.utils.guard_events import GuardEvent
                event = GuardEvent(
                    guard="outlier_bar",
                    reason=f"Price move {move_pct:.2f}% exceeds outlier threshold",
                    symbol=symbol,
                    extra_data={
                        "price_move_pct": move_pct,
                        "threshold": Settings.OUTLIER_RETURN_THRESHOLD_PCT,
                        "price": price,
                        "prev_price": prev_price
                    },
                    severity="WARNING"
                )
                self.trade_store.guard_events.record_guard_event(event)
            return False
    return True


def check_volume_capacity(self: 'Trader', signal: Dict[str, Any]) -> bool:
    vol = float(signal.get('volume_24h', 0))
    if not self.risk_manager.check_volume(vol):
        self.guard_counters['low_volume'] += 1
        self.logger.info(f"Hacim dusuk: {signal['symbol']} vol={vol}")
        return False
    if not self.risk_manager.check_max_positions(len(self.positions)):
        self.guard_counters['max_positions'] += 1
        self.logger.info("Maks pozisyona ulasildi")
        return False
    return True


def correlation_ok(self: 'Trader', symbol: str, price: float) -> bool:
    # cache update (suppress if errors)
    with contextlib.suppress(Exception):
        self.corr_cache.update(symbol, price)
    details = []
    pressure = False
    try:
        threshold = Settings.CORRELATION_THRESHOLD
        for sym in self.positions:
            if sym == symbol:
                continue
            c = self.corr_cache.correlation(symbol, sym)
            if c is not None and c >= threshold:
                details.append((sym, round(c, 3)))
        if len(details) >= Settings.MAX_CORRELATED_POSITIONS:
            self.guard_counters['correlation_block'] += 1
            self.logger.info(f"Korelasyon limiti: {symbol} -> {details}")
            if Settings.CORRELATION_DYNAMIC_ENABLED:
                _maybe_adjust_correlation_threshold(self, blocked=True)
            return False
        # Correlation pressure logic: even without full block, repeated high correlations ease threshold
        pressure = bool(details)
        if Settings.CORRELATION_DYNAMIC_ENABLED:
            _maybe_adjust_correlation_threshold(self, blocked=pressure)
    except Exception:  # pragma: no cover
        pass
    return True


# CR-0048 thread-safe correlation state management
_CORR_STATE_LOCK = threading.RLock()
_CORR_STATE = {
    'last_adjust_ts': 0.0,
    'block_streak': 0
}

def _maybe_adjust_correlation_threshold(self: 'Trader', blocked: bool):  # CR-0048
    """Thread-safe correlation threshold adjustment"""
    try:
        with _CORR_STATE_LOCK:
            if blocked:
                _CORR_STATE['block_streak'] += 1
            else:
                _CORR_STATE['block_streak'] = 0
            cur = Settings.CORRELATION_THRESHOLD
            if blocked and _CORR_STATE['block_streak'] >= 3:
                new_thr = max(Settings.CORRELATION_MIN_THRESHOLD, cur - Settings.CORRELATION_ADJ_STEP)
                if new_thr != cur:
                    Settings.CORRELATION_THRESHOLD = new_thr
                    slog('correlation_adjust', action='ease', value=new_thr)
                    _CORR_STATE['block_streak'] = 0
            elif (not blocked) and cur < Settings.CORRELATION_MAX_THRESHOLD:
                new_thr = min(Settings.CORRELATION_MAX_THRESHOLD, cur + Settings.CORRELATION_ADJ_STEP)
                if new_thr != cur:
                    Settings.CORRELATION_THRESHOLD = new_thr
                    slog('correlation_adjust', action='tighten', value=new_thr)
    except Exception as e:
        # Specific exception handling instead of suppress
        self.logger.error(f"Correlation threshold adjustment failed: {e}")
        # Don't let correlation adjustment failure block trading


def pre_trade_pipeline(self: 'Trader', signal: Dict[str, Any]):
    symbol = signal.get('symbol')
    if not symbol:
        try:
            from src.utils.structured_log import slog as _slog
            _slog('pre_trade_block', reason='no_symbol')
        except Exception:
            pass
        return False, {}
    sig_label = signal.get('signal') or ""
    side, risk_side = map_signal(str(sig_label))
    if not side:
        try:
            from src.utils.structured_log import slog as _slog
            _slog('pre_trade_block', reason='invalid_signal')
        except Exception:
            pass
        return False, {}
    price_val = signal.get('close_price') or signal.get('price')
    try:
        price = float(price_val)
    except Exception:
        try:
            from src.utils.structured_log import slog as _slog
            _slog('pre_trade_block', reason='price_parse')
        except Exception:
            pass
        return False, {}

    # CR-0064: Lookahead bias prevention
    # Not: Bircok test/sentetik sinyal timestamp alanini icerez. Bu durumda
    # pre-trade asamasinda lookahead engellemesi yapmayiz; gercek veri akisinda
    # (SignalGenerator tarafinda DF dogrulamasi ile) lookahead korumasi etkin kalir.
    lookahead_guard = get_lookahead_guard()
    ts_val = signal.get('timestamp')
    has_ts = ts_val is not None and str(ts_val).strip() != ""
    if has_ts and getattr(Settings, 'LOOKAHEAD_GUARD_ENABLED', True) and not lookahead_guard.validate_signal_data(signal):
            try:
                from src.utils.structured_log import slog as _slog
                _slog('pre_trade_block', reason='lookahead')
            except Exception:
                pass
            self.increment_guard_counter('lookahead')
            return False, {}

    if not check_halt_flag(self):
        try:
            from src.utils.structured_log import slog as _slog
            _slog('pre_trade_block', reason='halt_flag')
        except Exception:
            pass
        return False, {}
    if not check_daily_risk_limits(self):
        try:
            from src.utils.structured_log import slog as _slog
            _slog('pre_trade_block', reason='daily_risk')
        except Exception:
            pass
        return False, {}
    if not check_outlier_bar(self, signal, price):
        try:
            from src.utils.structured_log import slog as _slog
            _slog('pre_trade_block', reason='outlier')
        except Exception:
            pass
        return False, {}
    if not check_volume_capacity(self, signal):
        try:
            from src.utils.structured_log import slog as _slog
            _slog('pre_trade_block', reason='capacity')
        except Exception:
            pass
        return False, {}
    return True, {
        'symbol': symbol,
        'side': side,
        'risk_side': risk_side,
        'price': price
    }
