"""Emir hazirlama, pozisyon acma-kaydetme ve kapama islemleri."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Dict, Any
import time
import contextlib
import pandas as pd

from config.settings import Settings


@dataclass(slots=True)
class OrderContext:
    symbol: str
    side: str
    risk_side: Optional[str]
    price: float
    stop_loss: float
    take_profit: float
    protected_stop: float
    position_size: float
    atr: Optional[float]


def compute_atr(signal: Dict[str, Any]):
    atr_raw = signal.get('indicators', {}).get('ATR')
    with contextlib.suppress(Exception):
        if isinstance(atr_raw, (int, float)):
            return float(atr_raw)
        import pandas as pd  # lazy
        if isinstance(atr_raw, pd.Series) and len(atr_raw) > 0:
            return float(atr_raw.iloc[-1])
    return None


def initial_levels(self, price: float, risk_side: str | None, atr: float | None):
    if risk_side in ('long', 'short'):
        sl = self.risk_manager.calculate_stop_loss(price, risk_side, atr)
        tp = self.risk_manager.calculate_take_profit(price, sl, risk_side)
    else:
        sl = self.risk_manager.calculate_stop_loss(price, 'long', atr)
        tp = self.risk_manager.calculate_take_profit(price, sl, 'long')
    return sl, tp


def position_size(self, symbol: str, balance: float, price: float, stop_loss: float, signal: Dict[str, Any]):
    size = self.risk_manager.calculate_position_size(balance, price, stop_loss)
    if size <= 0:
        return 0.0
    # Adaptive ATR scaling
    if Settings.ADAPTIVE_RISK_ENABLED:
        with contextlib.suppress(Exception):
            atr_raw = signal.get('indicators', {}).get('ATR')
            atr_val = float(atr_raw.iloc[-1]) if hasattr(atr_raw, 'iloc') else float(atr_raw)
            if price > 0 and atr_val > 0:
                atr_pct = (atr_val / price) * 100.0
                ref = Settings.ADAPTIVE_RISK_ATR_REF_PCT
                ratio = atr_pct / ref if ref > 0 else 1.0
                inv = 1.0 / max(0.1, ratio)
                size_mult = min(Settings.ADAPTIVE_RISK_MAX_MULT, max(Settings.ADAPTIVE_RISK_MIN_MULT, inv))
                size *= size_mult
    # Score based nudge
    with contextlib.suppress(Exception):
        total_score = float(signal.get('total_score', 50))
        strength = max(0.0, min(1.0, (total_score - 50)/50))
        size *= (0.9 + strength*0.4)
    # Quantize
    with contextlib.suppress(Exception):
        q_qty, _ = self.api.quantize(symbol, size, price)
        size = q_qty
    return size


def prepare_order_context(self, signal: Dict[str, Any], ctx: Dict[str, Any]):
    symbol = ctx['symbol']
    side = ctx['side']
    risk_side = ctx['risk_side']
    price = ctx['price']
    atr = compute_atr(signal)
    sl, tp = initial_levels(self, price, risk_side, atr)
    balance = self.get_account_balance()
    size = position_size(self, symbol, balance, price, sl, signal)
    if not size or size <= 0:
        self.logger.info(f"{symbol} pozisyon acilmadi: size=0")
        return None
    if not self.correlation_ok(symbol, price):
        return None
    max_loss = self.risk_manager.calculate_max_loss(price, sl, size)
    if max_loss > balance * 0.04:
        self.logger.info(f"{symbol} max_loss limit disi {max_loss:.2f}")
        return None
    protected = self.risk_manager.apply_slippage_protection(sl, risk_side or 'long')
    return OrderContext(symbol, side, risk_side, price, sl, tp, protected, size, atr)


def place_main_and_protection(self, oc: OrderContext):
    # spot: market -> optional OCO
    order = self.api.place_order(symbol=oc.symbol, side=oc.side, order_type='MARKET', quantity=oc.position_size, price=None)
    if not order:
        return None
    # (Protection emirleri - gelecekte OCO / stop / tp eklenebilir)
    return order


def place_protection_orders(self, oc: OrderContext, _fill_price: float):
    """Gercek stop / take profit emirleri yerlestirir.
    Spot: OCO (SELL) - sadece long islemler varsayilir.
    Futures: Ayrik STOP_MARKET & TAKE_PROFIT_MARKET.
    Kayit: pozisyon dict icine order id referanslari.
    """
    if Settings.OFFLINE_MODE:
        return
    side = oc.side.upper()
    exit_side = 'SELL' if side == 'BUY' else 'BUY'
    pos = self.positions.get(oc.symbol)
    if not pos:
        return
    try:
        if self.market_mode == 'spot':
            if side == 'BUY':
                resp = self.api.place_oco_order(
                    symbol=oc.symbol,
                    side=side,  # API icinde exit side hesaplanacak
                    quantity=pos['remaining_size'],
                    take_profit=oc.take_profit,
                    stop_loss=oc.protected_stop
                )
                pos['oco_resp'] = {'ids': _extract_order_ids(resp)} if resp else None
        else:  # futures
            # STOP
            sl_order = self.api.place_order(
                symbol=oc.symbol,
                side=exit_side,
                order_type='STOP_MARKET',
                quantity=pos['remaining_size'],
                price=None,
                stopPrice=oc.protected_stop,
                closePosition=False
            )
            tp_order = self.api.place_order(
                symbol=oc.symbol,
                side=exit_side,
                order_type='TAKE_PROFIT_MARKET',
                quantity=pos['remaining_size'],
                price=None,
                stopPrice=oc.take_profit,
                closePosition=False
            )
            pos['futures_protection'] = {
                'sl_id': _extract_single_id(sl_order),
                'tp_id': _extract_single_id(tp_order)
            }
    except Exception as e:  # pragma: no cover
        self.logger.warning(f"Koruma emirleri hata {oc.symbol}: {e}")


def _extract_order_ids(resp):  # helper best effort
    try:
        if isinstance(resp, dict):
            # OCO response structure may contain 'orderReports'
            if 'orderReports' in resp:
                return [r.get('orderId') for r in resp['orderReports']]
            return [resp.get('orderId')]
    except Exception:
        return []
    return []


def _extract_single_id(resp):
    try:
        if isinstance(resp, dict):
            return resp.get('orderId')
    except Exception:
        return None
    return None


def extract_fills(order: Dict[str, Any], ref_price: float, side: str, qty: float):
    fill = ref_price
    slip = None
    with contextlib.suppress(Exception):
        raw = order.get('price') or order.get('avgPrice')
        if raw not in (None, '', 0):
            fill = float(raw)
        elif order.get('fills'):
            total_qty = 0.0
            total_cost = 0.0
            for f in order['fills']:
                fp = float(f.get('price', 0))
                fq = float(f.get('qty', 0))
                total_qty += fq
                total_cost += fp * fq
            if total_qty > 0:
                fill = total_cost / total_qty
    if fill and ref_price:
        if side == 'BUY':
            slip = (fill - ref_price) / ref_price * 10000.0
        else:
            slip = (ref_price - fill) / ref_price * 10000.0
    return fill, slip, qty


def record_open(self, oc: OrderContext, fill: float, slip_bps: float | None, qty: float):
    trade_id = None
    with contextlib.suppress(Exception):
        trade_id = self.trade_store.insert_open(
            symbol=oc.symbol,
            side=oc.side,
            entry_price=fill,
            size=qty,
            opened_at=pd.Timestamp.utcnow().isoformat(),
            strategy_tag='core',
            stop_loss=oc.protected_stop,
            take_profit=oc.take_profit,
            param_set_id=Settings.PARAM_SET_ID,
            entry_slippage_bps=slip_bps,
            raw={}
        )
    self.positions[oc.symbol] = {
        'side': oc.side,
        'entry_price': fill,
        'position_size': qty,
        'remaining_size': qty,
        'stop_loss': oc.protected_stop,
        'take_profit': oc.take_profit,
        'atr': oc.atr,
        'trade_id': trade_id,
        'scaled_out': []
    }
    return trade_id


def open_position(self, signal: Dict[str, Any], ctx: Dict[str, Any]):
    oc = prepare_order_context(self, signal, ctx)
    if not oc:
        return False
    t0 = time.time()
    order = place_main_and_protection(self, oc)
    if not order:
        return False
    fill, slip_bps, exec_qty = extract_fills(order, oc.price, oc.side, oc.position_size)
    record_open(self, oc, fill, slip_bps, exec_qty)
    # Koruma emirleri (gercek)
    place_protection_orders(self, oc, fill)
    latency_ms = (time.time() - t0) * 1000
    self.recent_open_latencies.append(latency_ms)
    if slip_bps is not None:
        self.recent_entry_slippage_bps.append(float(slip_bps))
    self.logger.info(f"ACILDI {oc.symbol} {oc.side} size={exec_qty:.6f} entry={fill:.4f} sl={oc.protected_stop:.4f} tp={oc.take_profit:.4f} slip={slip_bps}")
    return True


def close_position(self, symbol: str):
    pos = self.positions.get(symbol)
    if not pos:
        return False
    t0 = time.time()
    # basit market kapatma (ters emir)
    opposite = 'SELL' if pos['side'] == 'BUY' else 'BUY'
    order = self.api.place_order(symbol=symbol, side=opposite, order_type='MARKET', quantity=pos['remaining_size'], price=None)
    if not order:
        return False
    fill, slip_bps, _ = extract_fills(order, pos['entry_price'], opposite, pos['remaining_size'])
    with contextlib.suppress(Exception):
        if pos.get('trade_id') is not None:
            self.trade_store.close_trade(pos['trade_id'], fill, pandas_ts(), exit_slippage_bps=slip_bps, exit_qty=pos['remaining_size'])
    self.positions.pop(symbol, None)
    latency = (time.time() - t0) * 1000
    self.recent_close_latencies.append(latency)
    if slip_bps is not None:
        self.recent_exit_slippage_bps.append(float(slip_bps))
    self.logger.info(f"KAPANDI {symbol} lat={latency:.1f}ms slip={slip_bps}")
    return True


def pandas_ts():  # separated for testability
    return pd.Timestamp.utcnow().isoformat()
