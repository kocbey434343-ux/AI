"""Trailing ve kismi cikis mantigi."""
from __future__ import annotations
import contextlib
from typing import Dict, Any
from config.settings import Settings
from src.utils.structured_log import slog


def init_trailing(self):
    raw_levels = [
        (Settings.PARTIAL_TP1_R_MULT, Settings.PARTIAL_TP1_PCT / 100.0),
        (Settings.PARTIAL_TP2_R_MULT, Settings.PARTIAL_TP2_PCT / 100.0)
    ]
    # Duplicate R seviyelerini (örn her ikisi de 1.0 ise) tekille
    seen = set()
    dedup = []
    for lvl, pct in raw_levels:
        if lvl in seen:
            continue
        seen.add(lvl)
        dedup.append((lvl, pct))
    self.tp_levels = dedup
    self.partial_enabled = Settings.ENABLE_PARTIAL_EXITS
    self.trailing_activate_r = Settings.TRAILING_ACTIVATE_R_MULT
    self.trailing_step_pct = Settings.TRAILING_STEP_PCT
    self.last_trailing_update = {}  # runtime assign; explicit tip iptal (lint uyumu)


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
    done_levels = pos.setdefault('partial_done_levels', set())
    remaining = pos.get('remaining_size', pos['position_size'])
    for level, pct in self.tp_levels:
        if level in done_levels:
            continue
        if any(level == x[0] for x in pos.get('scaled_out', [])):
            done_levels.add(level)
            continue
        if r_gain < level:
            continue
        # DB idempotency guard (teorik cift invocation durumuna karsi)
        if pos.get('trade_id') is not None:
            try:
                cur = self.trade_store._conn.cursor()
                row = cur.execute("SELECT 1 FROM executions WHERE trade_id=? AND exec_type='scale_out' AND ABS(r_mult-?)<0.0001 LIMIT 1", (pos['trade_id'], level)).fetchone()
                if row:
                    done_levels.add(level)
                    continue
            except Exception:
                pass
        qty = remaining * pct
        if qty <= 0:
            continue
        if pos.get('trade_id') is not None:
            result = self.trade_store.record_scale_out(pos['trade_id'], symbol, qty, last_price, level)
            self.logger.debug(f"Partial exit DB write result: {result}")
            if not result:
                import json
                import sqlite3
                TOL = 1e-9
                try:
                    cur = self.trade_store._conn.cursor()
                    row = cur.execute("SELECT scaled_out_json FROM trades WHERE id=?", (pos['trade_id'],)).fetchone()
                    existing = []
                    if row and row[0]:
                        with contextlib.suppress(Exception):
                            existing = json.loads(row[0]) or []
                    if not any(abs(e.get('r_mult', -999) - level) < TOL for e in existing):
                        existing.append({'r_mult': level, 'qty': qty})
                        cur.execute("UPDATE trades SET scaled_out_json=? WHERE id=?", (json.dumps(existing, ensure_ascii=False), pos['trade_id']))
                        self.trade_store._conn.commit()
                except sqlite3.Error:
                    pass
        remaining -= qty
        pos['remaining_size'] = remaining
        pos.setdefault('scaled_out', []).append((level, qty))
        done_levels.add(level)
        self.logger.info(f"Partial exit {symbol} r={level} qty={qty:.6f} rem={remaining:.6f}")
        slog('partial_exit', symbol=symbol, r_mult=level, qty=qty, remaining=remaining, trade_id=pos.get('trade_id'))
        if (pos['side'] == 'BUY' and last_price > pos['entry_price']) or (pos['side'] == 'SELL' and last_price < pos['entry_price']):
            if pos['side'] == 'BUY':
                pos['stop_loss'] = max(pos['stop_loss'], pos['entry_price'])
            else:
                pos['stop_loss'] = min(pos['stop_loss'], pos['entry_price'])


def maybe_trailing(self, symbol: str, pos: Dict[str, Any], last_price: float, r_gain: float):
    """Classic + ATR trailing uygula.

    Kompleksiteyi azaltmak icin iki blok fonksiyona ayrildi.
    """
    if r_gain < self.trailing_activate_r:
        return
    _maybe_classic_trailing(self, symbol, pos, last_price, r_gain)
    _maybe_atr_trailing(self, symbol, pos, last_price, r_gain)


def _maybe_classic_trailing(self, symbol: str, pos: Dict[str, Any], last_price: float, _r_gain: float):
    if pos.get('classic_trailing_done'):
        return
    entry = pos['entry_price']
    side = pos['side']
    stop_before = pos['stop_loss']
    gain = (last_price - entry) if side == 'BUY' else (entry - last_price)
    step = gain * (self.trailing_step_pct / 100.0)
    target = entry + step if side == 'BUY' else entry - step
    improved = (side == 'BUY' and target > stop_before) or (side == 'SELL' and target < stop_before)
    if not improved:
        return
    pos['stop_loss'] = target
    pos['classic_trailing_done'] = True
    if pos.get('trade_id') is not None:
        with contextlib.suppress(Exception):
            self.trade_store.update_stop_loss(pos['trade_id'], target)
            self.trade_store.record_execution(pos['trade_id'], symbol, 'trailing_update', price=last_price, qty=None, side=None, r_mult=None)
    slog('trailing_classic_update', symbol=symbol, new_sl=target, price=last_price, trade_id=pos.get('trade_id'))
    slog('trailing_update', symbol=symbol, new_stop=target, price=last_price, trade_id=pos.get('trade_id'), mode='classic')


def _maybe_atr_trailing(self, symbol: str, pos: Dict[str, Any], last_price: float, r_gain: float):
    if not Settings.ATR_TRAILING_ENABLED:
        return
    atr = pos.get('atr')
    if not atr or atr <= 0 or r_gain < Settings.ATR_TRAILING_START_R:
        return
    side = pos['side']
    dist = atr * Settings.ATR_TRAILING_MULT
    atr_target = (last_price - dist) if side == 'BUY' else (last_price + dist)
    improved_atr = (side == 'BUY' and atr_target > pos['stop_loss']) or (side == 'SELL' and atr_target < pos['stop_loss'])
    if not improved_atr:
        return
    pos['stop_loss'] = atr_target
    if pos.get('trade_id') is not None:
        with contextlib.suppress(Exception):
            self.trade_store.update_stop_loss(pos['trade_id'], atr_target)
            self.trade_store.record_execution(pos['trade_id'], symbol, 'trailing_update', price=last_price, qty=None, side=None, r_mult=None)
    slog('trailing_atr_update', symbol=symbol, new_sl=atr_target, price=last_price, trade_id=pos.get('trade_id'))
    slog('trailing_update', symbol=symbol, new_stop=atr_target, price=last_price, trade_id=pos.get('trade_id'), mode='atr')
