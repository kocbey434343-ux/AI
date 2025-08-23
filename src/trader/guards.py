"""Guard ve risk kontrolleri.

Trader icersinden cagrilacak pure/helper fonksiyonlar.
Yan etkiler: self.guard_counters gunceller, log yazar.
"""
from __future__ import annotations
import contextlib
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from config.settings import Settings


def map_signal(label: str) -> Tuple[Optional[str], Optional[str]]:
    if label == "AL":
        return "BUY", "long"
    if label == "SAT":
        return "SELL", "short"
    return None, None


def check_halt_flag(self) -> bool:
    halt_flag = Path(Settings.DAILY_HALT_FLAG_PATH)
    if halt_flag.exists():
        self.logger.warning("Gunluk risk kilidi aktif (halt flag)")
        self.guard_counters['halt_flag'] += 1
        return False
    return True


def check_daily_risk_limits(self) -> bool:
    halt_flag = Path(Settings.DAILY_HALT_FLAG_PATH)
    with contextlib.suppress(Exception):
        daily_pnl = self.trade_store.daily_realized_pnl_pct()
        if daily_pnl <= -Settings.MAX_DAILY_LOSS_PCT:
            self.logger.warning(f"Gunluk zarar esigi asildi {daily_pnl:.2f}% -> halt")
            with contextlib.suppress(Exception):
                halt_flag.write_text("daily loss halt")
            self.guard_counters['daily_loss'] += 1
            return False
        consec = self.trade_store.consecutive_losses()
        if consec >= Settings.MAX_CONSECUTIVE_LOSSES:
            self.logger.warning(f"Ardisik kayip limiti {consec}")
            with contextlib.suppress(Exception):
                halt_flag.write_text("consecutive losses halt")
            self.guard_counters['consec_losses'] += 1
            return False
    return True


def check_outlier_bar(self, signal: Dict[str, Any], price: float) -> bool:
    prev_price = float(signal.get('prev_close', price))
    if prev_price > 0:
        move_pct = abs((price - prev_price) / prev_price) * 100.0
        if move_pct >= Settings.OUTLIER_RETURN_THRESHOLD_PCT:
            self.logger.info(f"Outlier bar filtrelendi {signal['symbol']} move={move_pct:.2f}%")
            self.guard_counters['outlier_bar'] += 1
            return False
    return True


def check_volume_capacity(self, signal: Dict[str, Any]) -> bool:
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


def correlation_ok(self, symbol: str, price: float) -> bool:
    # cache update (suppress if errors)
    with contextlib.suppress(Exception):
        self.corr_cache.update(symbol, price)
    details = []
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
            return False
    except Exception:  # pragma: no cover
        pass
    return True


def pre_trade_pipeline(self, signal: Dict[str, Any]):
    symbol = signal['symbol']
    sig_label = signal.get('signal') or ""
    side, risk_side = map_signal(str(sig_label))
    if not side:
        return False, {}
    price = float(signal['close_price'])
    # sequential guards
    if not check_halt_flag(self):
        return False, {}
    if not check_daily_risk_limits(self):
        return False, {}
    if not check_outlier_bar(self, signal, price):
        return False, {}
    if not check_volume_capacity(self, signal):
        return False, {}
    return True, {
        'symbol': symbol,
        'side': side,
        'risk_side': risk_side,
        'price': price
    }
