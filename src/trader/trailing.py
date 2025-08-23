"""Trailing ve kismi cikis mantigi."""
from __future__ import annotations
import time
import contextlib
from typing import Dict, Any
from config.settings import Settings


def init_trailing(self):
    self.tp_levels = [
        (Settings.PARTIAL_TP1_R_MULT, Settings.PARTIAL_TP1_PCT / 100.0),
        (Settings.PARTIAL_TP2_R_MULT, Settings.PARTIAL_TP2_PCT / 100.0)
    ]
    self.partial_enabled = Settings.ENABLE_PARTIAL_EXITS
    self.trailing_activate_r = Settings.TRAILING_ACTIVATE_R_MULT
    self.trailing_step_pct = Settings.TRAILING_STEP_PCT
    self.last_trailing_update = {}  # type: Dict[str, float]


def compute_r_multiple(pos: Dict[str, Any], last_price: float):
    entry = pos['entry_price']
    stop = pos['stop_loss']
    risk = abs(entry - stop)
    if risk <= 0:
        return None
    if pos['side'] == 'BUY':
        return (last_price - entry) / risk
    return (entry - last_price) / risk


def maybe_partial_exits(self, symbol: str, pos: Dict[str, Any], last_price: float, r_gain: float):
    if not self.partial_enabled or pos.get('remaining_size', pos['position_size']) <= 0:
        return
    remaining = pos.get('remaining_size', pos['position_size'])
    for level, pct in self.tp_levels:
        if any(level == x[0] for x in pos.get('scaled_out', [])):
            continue
        if r_gain < level:
            continue
        qty = remaining * pct
        if qty <= 0:
            continue
        # record
        with contextlib.suppress(Exception):
            if pos.get('trade_id') is not None:
                self.trade_store.record_execution(
                    trade_id=pos['trade_id'], symbol=symbol, exec_type='scale_out', qty=qty,
                    price=last_price, side=pos['side'], r_mult=level
                )
        remaining -= qty
        pos['remaining_size'] = remaining
        pos.setdefault('scaled_out', []).append((level, qty))
        self.logger.info(f"Partial exit {symbol} r={level} qty={qty:.6f} rem={remaining:.6f}")
        # BE to entry
        if (pos['side'] == 'BUY' and last_price > pos['entry_price']) or (pos['side'] == 'SELL' and last_price < pos['entry_price']):
            pos['stop_loss'] = pos['entry_price']


def maybe_trailing(self, symbol: str, pos: Dict[str, Any], last_price: float, r_gain: float):
    if r_gain < self.trailing_activate_r:
        return
    # classic step trailing
    entry = pos['entry_price']
    stop = pos['stop_loss']
    side = pos['side']
    risk = abs(entry - stop)
    if risk <= 0:
        return
    gain = (last_price - entry) if side == 'BUY' else (entry - last_price)
    step = gain * (self.trailing_step_pct / 100.0)
    target = entry + (step if side == 'BUY' else -step)
    improved = (side == 'BUY' and target > stop) or (side == 'SELL' and target < stop)
    if improved:
        pos['stop_loss'] = target
        self.logger.debug(f"Trailing {symbol} stop->{target:.4f}")
    # ATR trailing (cooldown)
    atr = pos.get('atr')
    if not atr or atr <= 0:
        return
    now = time.time()
    lt = self.last_trailing_update.get(symbol, 0)
    if now - lt < Settings.ATR_TRAILING_COOLDOWN_SEC:
        return
    dist = atr * Settings.ATR_TRAILING_MULT
    new_sl = max(stop, last_price - dist) if side == 'BUY' else min(stop, last_price + dist)
    if new_sl != pos['stop_loss']:
        pos['stop_loss'] = new_sl
        self.last_trailing_update[symbol] = now
        self.logger.debug(f"ATR trailing {symbol} stop->{new_sl:.4f}")
