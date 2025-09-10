"""Emir hazirlama, pozisyon acma-kaydetme ve kapama islemleri."""
from __future__ import annotations

import contextlib
import time
from dataclasses import dataclass
from typing import Any, Dict, NamedTuple, Optional

import pandas as pd
from config.settings import Settings

from src.execution.smart_execution import execute_sliced_market  # optional smart exec
from src.utils.order_state import OrderState  # FSM (CR-0063)
from src.utils.slippage_guard import get_slippage_guard  # CR-0065
from src.utils.structured_log import slog

from .metrics import maybe_trim_metrics


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
        if isinstance(atr_raw, pd.Series) and len(atr_raw) > 0:
            return float(atr_raw.iloc[-1])
    return None


def initial_levels(trader_instance, price: float, risk_side: str | None, atr: float | None):
    if risk_side in ('long', 'short'):
        sl = trader_instance.risk_manager.calculate_stop_loss(price, risk_side, atr)
        tp = trader_instance.risk_manager.calculate_take_profit(price, sl, risk_side)
    else:
        sl = trader_instance.risk_manager.calculate_stop_loss(price, 'long', atr)
        tp = trader_instance.risk_manager.calculate_take_profit(price, sl, 'long')
    return sl, tp


class SizeInputs(NamedTuple):
    symbol: str
    balance: float
    price: float
    stop_loss: float
    signal: Dict[str, Any]


def position_size(trader_instance, inputs: SizeInputs):
    size = trader_instance.risk_manager.calculate_position_size(inputs.balance, inputs.price, inputs.stop_loss)
    if size <= 0:
        return 0.0
    # Adaptive ATR scaling
    if Settings.ADAPTIVE_RISK_ENABLED:
        with contextlib.suppress(Exception):
            atr_raw = inputs.signal.get('indicators', {}).get('ATR')
            atr_val = float(atr_raw.iloc[-1]) if hasattr(atr_raw, 'iloc') else float(atr_raw)
            if inputs.price > 0 and atr_val > 0:
                atr_pct = (atr_val / inputs.price) * 100.0
                ref = Settings.ADAPTIVE_RISK_ATR_REF_PCT
                ratio = atr_pct / ref if ref > 0 else 1.0
                inv = 1.0 / max(0.1, ratio)
                size_mult = min(Settings.ADAPTIVE_RISK_MAX_MULT, max(Settings.ADAPTIVE_RISK_MIN_MULT, inv))
                size *= size_mult
    # Score based nudge
    with contextlib.suppress(Exception):
        total_score = float(inputs.signal.get('total_score', 50))
        strength = max(0.0, min(1.0, (total_score - 50)/50))
        size *= (0.9 + strength*0.4)
    # Quantize
    with contextlib.suppress(Exception):
        q_qty, _ = trader_instance.api.quantize(inputs.symbol, size, inputs.price)
        size = q_qty
    return size


def prepare_order_context(trader_instance, signal: Dict[str, Any], ctx: Dict[str, Any]):
    symbol = ctx['symbol']
    side = ctx['side']
    risk_side = ctx['risk_side']
    price = ctx['price']
    atr = compute_atr(signal)
    sl, tp = initial_levels(trader_instance, price, risk_side, atr)
    balance = trader_instance.get_account_balance()
    size = position_size(trader_instance, SizeInputs(symbol, balance, price, sl, signal))
    if not size or size <= 0:
        trader_instance.logger.info(f"{symbol} pozisyon acilmadi: size=0")
        with contextlib.suppress(Exception):
            slog('prepare_ctx_block', symbol=symbol, reason='size_zero')
        return None
    if not trader_instance.correlation_ok(symbol, price):
        with contextlib.suppress(Exception):
            slog('prepare_ctx_block', symbol=symbol, reason='correlation_block')
        return None

    # A30 PoR: Spread guard check
    if not trader_instance._check_spread_guard(symbol):
        with contextlib.suppress(Exception):
            slog('prepare_ctx_block', symbol=symbol, reason='spread_guard')
        return None

    # Removed max_loss_threshold check - not implemented in RiskManager
    protected = trader_instance.risk_manager.apply_slippage_protection(sl, risk_side or 'long')
    return OrderContext(symbol, side, risk_side, price, sl, tp, protected, size, atr)


def place_main_and_protection(trader_instance, oc: OrderContext):
    """
    Ana emir yerlestirir ve slippage kontrolu yapar (CR-0065)

    Returns:
        Order response veya None (slippage guard tarafindan iptal edilirse)
    """
    # Smart Execution (TWAP/VWAP) optional path
    if getattr(Settings, 'SMART_EXECUTION_ENABLED', False):
        last_order, executed_qty = execute_sliced_market(
            trader_instance.api, oc.symbol, oc.side, oc.position_size, oc.price, sleep_fn=time.sleep
        )
        # Eğer hiç fill yoksa None dön (retry/backoff devreye girer)
        if not last_order and executed_qty <= 0:
            return None
    # Synthetic aggregate order object (let fill/price extraction work)
        order = last_order or {
            'price': oc.price,
            'avgPrice': oc.price,
            'fills': [{'price': oc.price, 'qty': executed_qty}]
        }
    else:
    # Single-shot MARKET order
        order = trader_instance.api.place_order(
            symbol=oc.symbol,
            side=oc.side,
            order_type='MARKET',
            quantity=oc.position_size,
            price=None
        )

    if not order:
        return None

    # Fill price'i al (API response'undan)
    fill_price = _extract_fill_price(trader_instance, order, oc.symbol)
    if fill_price is None:
        trader_instance.logger.warning(f"{oc.symbol}: Fill price alinamadi, slippage kontrolu atlanacak")
        return order

    # CR-0065: Slippage guard kontrolu - RE-ENABLED FOR PRODUCTION
    slippage_guard = get_slippage_guard()
    is_safe, corrective_action = slippage_guard.validate_order_execution({
        'symbol': oc.symbol,
        'side': oc.side,
        'expected_price': oc.price,
        'fill_price': fill_price,
        'quantity': oc.position_size,
        'order_id': order.get('orderId') if order else None
    })

    if not is_safe and corrective_action:
        action = corrective_action.get('action', 'ABORT')

        if action == 'ABORT':
            # Order iptal et (eger mumkunse)
            trader_instance.logger.error(f"{oc.symbol}: Slippage guard ABORT - "
                            f"slippage: {corrective_action.get('slippage_bps', 0):.1f}bps")
            slog('order_aborted', symbol=oc.symbol, reason='slippage_guard',
                 action=corrective_action)

            # Market order hemen doldugu icin iptal etmek zor
            # Bu durumda pozisyonu hemen kapatmak gerekebilir
            trader_instance._handle_slippage_abort(oc, order, corrective_action)
            return None

        if action == 'REDUCE':
            # Position size'i azalt (gelecek emirler icin)
            new_qty = corrective_action.get('new_qty')
            if new_qty and new_qty < oc.position_size:
                trader_instance.logger.warning(f"{oc.symbol}: Slippage guard REDUCE - "
                                  f"next order qty: {new_qty:.6f}")
                # Not: Bu order zaten execute oldu, bir sonraki trade icin kota azaltilabilir

    return order

def _extract_fill_price(trader_instance, order: Dict[str, Any], symbol: str) -> Optional[float]:
    """Order response'undan fill price'i extract et"""
    try:
        # Binance API response formats
        if order.get('fills'):
            # Market order fills array'i
            fill = order['fills'][0]  # İlk fill'i al
            return float(fill['price'])
        p = order.get('price')
        if p is not None:
            return float(p)
        ap = order.get('avgPrice')
        if ap is not None:
            return float(ap)
        trader_instance.logger.warning(f"{symbol}: Order response'da price bulunamadi: {order.keys()}")
        return None
    except (KeyError, ValueError, IndexError) as e:
        trader_instance.logger.error(f"{symbol}: Fill price extraction error: {e}")
        return None

def _handle_slippage_abort(trader_instance, oc: OrderContext, order: Dict[str, Any],
                         corrective_action: Dict[str, Any]):
    """Slippage abort durumunu handle et"""
    # Market order zaten execute oldu, pozisyonu immediate close et
    symbol = oc.symbol

    # Pozisyonu track etme (slippage problemi olan pozisyon)
    slippage_bps = corrective_action.get('slippage_bps', 0)
    trader_instance.logger.error(f"{symbol}: Slippage guard forced close - "
                     f"slippage {slippage_bps:.1f}bps exceeded threshold")

    slog('slippage_forced_close', symbol=symbol, slippage_bps=slippage_bps,
         order_id=order.get('orderId'), corrective_action=corrective_action)

    # Immediate close order place et (emergency)
    try:
        opposite_side = 'SELL' if oc.side == 'BUY' else 'BUY'
        close_order = trader_instance.api.place_order(
            symbol=symbol,
            side=opposite_side,
            order_type='MARKET',
            quantity=oc.position_size,
            price=None
        )

        if close_order:
            trader_instance.logger.info(f"{symbol}: Emergency close order placed due to slippage guard")
        else:
            trader_instance.logger.error(f"{symbol}: Emergency close order FAILED")

    except Exception as e:
        trader_instance.logger.error(f"{symbol}: Emergency close order exception: {e}")
        # Manual intervention may be needed


def place_protection_orders(trader_instance, oc: OrderContext, _fill_price: float):
    """Gercek stop / take profit emirleri yerlestirir.
    Spot: OCO (SELL) - sadece long islemler varsayilir.
    Futures: Ayrik STOP_MARKET & TAKE_PROFIT_MARKET.
    Kayit: pozisyon dict icine order id referanslari.
    Exception narrowing (CR-EXC-P2): Sadece beklenen runtime hatalari yakalanir.
    """
    if Settings.OFFLINE_MODE:
        return
    side = oc.side.upper()
    exit_side = 'SELL' if side == 'BUY' else 'BUY'
    pos = trader_instance.positions.get(oc.symbol)
    if not pos:
        return
    try:
        if trader_instance.market_mode == 'spot':
            if side == 'BUY':
                resp = trader_instance.api.place_oco_order(
                    symbol=oc.symbol,
                    side=side,  # API icinde exit side hesaplanacak
                    quantity=pos['remaining_size'],
                    take_profit=oc.take_profit,
                    stop_loss=oc.protected_stop
                )
                pos['oco_resp'] = {'ids': _extract_order_ids(resp)} if resp else None
        else:  # futures
            sl_order = trader_instance.api.place_order(
                symbol=oc.symbol,
                side=exit_side,
                order_type='STOP_MARKET',
                quantity=pos['remaining_size'],
                price=None,
                stopPrice=oc.protected_stop,
                closePosition=False
            )
            tp_order = trader_instance.api.place_order(
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
    except (KeyError, ValueError, TypeError, AttributeError) as e:  # narrowed
        trader_instance.logger.warning(f"Koruma emirleri hata (runtime) {oc.symbol}: {e}")
    except Exception as e:  # pragma: no cover - beklenmeyen (logla ve devam)
        trader_instance.logger.error(f"Koruma emirleri beklenmeyen hata {oc.symbol}: {e}")


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


def record_open(trader_instance, oc: OrderContext, fill: float, slip_bps: float | None, qty: float):
    trade_id = None
    try:
        trade_id = trader_instance.trade_store.insert_open(
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
        print(f"✅ Trade opened successfully: ID={trade_id}, {oc.symbol} {oc.side}")
    except Exception as e:
        print(f"❌ ERROR recording trade open: {e}")
        print(f"   Symbol: {oc.symbol}, Side: {oc.side}, Fill: {fill}")

    trader_instance.positions[oc.symbol] = {
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


def apply_partial_fill(trader_instance, oc: OrderContext, fill_price: float, fill_qty: float, slip_bps: float | None = None):
    """CR-0012: Partial fill uygulama / biriktirme.
    Ilk partial fill'de pozisyon kaydi olusturulur (position_size = hedef toplam oc.position_size),
    sonraki partial fill'lerde remaining_size azaltilir ve ortalama entry yeniden hesaplanir.
    """
    if fill_qty <= 0:
        return None
    pos = trader_instance.positions.get(oc.symbol)
    if not pos:
        # ilk partial -> trade_store'a total size ile kayit
        trade_id = None
        with contextlib.suppress(Exception):
            trade_id = trader_instance.trade_store.insert_open(
                symbol=oc.symbol,
                side=oc.side,
                entry_price=fill_price,
                size=oc.position_size,  # toplam hedef
                opened_at=pd.Timestamp.utcnow().isoformat(),
                strategy_tag='core',
                stop_loss=oc.protected_stop,
                take_profit=oc.take_profit,
                param_set_id=Settings.PARAM_SET_ID,
                entry_slippage_bps=slip_bps,
                raw={'partial': True}
            )
        remaining = max(0.0, oc.position_size - fill_qty)
        trader_instance.positions[oc.symbol] = {
            'side': oc.side,
            'entry_price': fill_price,
            'position_size': oc.position_size,
            'filled_size': fill_qty,
            'remaining_size': remaining,
            'stop_loss': oc.protected_stop,
            'take_profit': oc.take_profit,
            'atr': oc.atr,
            'trade_id': trade_id,
            'scaled_out': [],
            'protection_qty': remaining  # ilk protection remaining bazli
        }
        return trader_instance.positions[oc.symbol]
    # sonraki partial
    total_size = pos.get('position_size', oc.position_size)
    prev_filled = pos.get('filled_size', total_size - pos.get('remaining_size', 0.0))
    new_filled = prev_filled + fill_qty
    new_filled = min(new_filled, total_size)
    # VWAP entry update
    try:
        old_entry = float(pos.get('entry_price', fill_price))
        if prev_filled + fill_qty > 0 and new_filled > 0:
            pos['entry_price'] = ((old_entry * prev_filled) + (fill_price * fill_qty)) / new_filled
    except (ValueError, TypeError, ZeroDivisionError) as e:  # narrowed
        trader_instance.logger.debug(f"apply_partial_fill entry vwap skip:{oc.symbol}:{e}")
    pos['filled_size'] = new_filled
    pos['remaining_size'] = max(0.0, total_size - new_filled)
    return pos


def maybe_revise_protection_orders(trader_instance, symbol: str):
    """CR-0012: Partial fill sonrasi koruma emir miktar revizyonu.
    Offline modda sadece state alanlarini gunceller; gercek modda iptal & yeniden
    yerlestirme gelecekte eklenecek.
    """
    pos = trader_instance.positions.get(symbol)
    if not pos:
        return False

    # Currently we only adjust in offline mode or record state changes. Detailed
    # protection order revision (cancel+replace) is not implemented here.
    try:
        if Settings.OFFLINE_MODE:
            # Check current state
            remaining = pos.get('remaining_size', pos.get('position_size', 0.0))
            current_protection_qty = pos.get('protection_qty', 0.0)
            already_cleared = pos.get('protection_cleared', False)

            # If already cleared and remaining is still zero, no change needed (idempotent)
            if already_cleared and abs(remaining) < 1e-12:
                return False

            # Update protection_qty to match remaining_size
            pos['protection_qty'] = remaining

            # Set protection_cleared flag when remaining size reaches zero
            if abs(remaining) < 1e-12:  # Zero tolerance
                pos['protection_cleared'] = True
                return True  # Changed - cleared protection

            # Return True if protection_qty changed
            return abs(current_protection_qty - remaining) > 1e-12
    except Exception:
        # swallow unexpected errors - this function is best-effort
        return True

    # Real-time revision not implemented yet; return True to indicate handled.
    return True


def open_position(trader_instance, signal: Dict[str, Any], ctx: Dict[str, Any]):
    """Prepare and submit an order based on a signal/context.

    Returns True if order submitted and processed (position opened), False otherwise.
    """
    oc = prepare_order_context(trader_instance, signal, ctx)
    if not oc:
        return False

    # Idempotent submit guard (CR-0083)
    try:
        from src.utils.order_dedup import get_order_dedup  # local import to avoid cycles
        dedup = get_order_dedup()
        dedup_key = f"{oc.symbol}|{oc.side}|{trader_instance.market_mode}|{round(oc.price, 8)}|{round(oc.position_size, 8)}"
        if not dedup.should_submit(dedup_key):
            with contextlib.suppress(Exception):
                slog('order_submit_dedup', action='skip', key=dedup_key, symbol=oc.symbol, side=oc.side)
            trader_instance.logger.info(f"{oc.symbol} idempotent skip (dedup)")
            return False
        dedup.mark_submitted(dedup_key)
        with contextlib.suppress(Exception):
            slog('order_submit_dedup', action='mark', key=dedup_key, symbol=oc.symbol, side=oc.side)
    except Exception:
        # Dedup sistemi basarisiz olsa bile trade devam edebilir
        pass

    # FSM: INIT -> SUBMITTING
    state_manager = getattr(trader_instance, 'state_manager', None)
    if state_manager:
        state_manager.transition_to(oc.symbol, OrderState.SUBMITTING)

    t0 = time.time()
    # Retry/backoff (CR-0083): place_main_and_protection icin jitterli exponential backoff
    order = _place_with_retry(trader_instance, oc)
    if not order:
        if state_manager:
            state_manager.transition_to(oc.symbol, OrderState.ERROR, reason="Order placement failed")
        return False

    fill, slip_bps, exec_qty = extract_fills(order, oc.price, oc.side, oc.position_size)

    # FSM: SUBMITTING -> OPEN
    if state_manager:
        state_manager.transition_to(oc.symbol, OrderState.OPEN)

    trade_id = record_open(trader_instance, oc, fill, slip_bps, exec_qty)

    # Koruma emirleri (gercek)
    place_protection_orders(trader_instance, oc, fill)

    # FSM: OPEN -> ACTIVE
    if state_manager:
        state_manager.transition_to(oc.symbol, OrderState.ACTIVE)

    latency_ms = (time.time() - t0) * 1000
    trader_instance.recent_open_latencies.append(latency_ms)
    if slip_bps is not None:
        trader_instance.recent_entry_slippage_bps.append(float(slip_bps))
    maybe_trim_metrics(trader_instance)
    trader_instance.logger.info(f"ACILDI {oc.symbol} {oc.side} size={exec_qty:.6f} entry={fill:.4f} sl={oc.protected_stop:.4f} tp={oc.take_profit:.4f} slip={slip_bps}")
    # Structured log
    slog(
        'trade_open',
        symbol=oc.symbol,
        side=oc.side,
        size=exec_qty,
        entry=fill,
        stop=oc.protected_stop,
        take_profit=oc.take_profit,
        latency_ms=round(latency_ms, 2),
        slip_bps=slip_bps,
        trade_id=trade_id
    )
    return True


def _place_with_retry(trader_instance, oc: OrderContext):
    """Ana emri retry/backoff ile dener, basarili olursa order dondurur, yoksa None.
    Jitterli exponential backoff kullanir ve metrik/log kaydi yapar.
    """
    order = None
    attempt = 0
    max_attempts = max(1, int(getattr(Settings, 'RETRY_MAX_ATTEMPTS', 3)))
    base = float(getattr(Settings, 'RETRY_BACKOFF_BASE_SEC', 0.5))
    mult = float(getattr(Settings, 'RETRY_BACKOFF_MULT', 2.0))
    while attempt < max_attempts:
        order = place_main_and_protection(trader_instance, oc)
        if order:
            return order
        attempt += 1
        if attempt >= max_attempts:
            break
        # Jitterli exponential backoff
        try:
            import random
            sleep_sec = base * (mult ** (attempt - 1))
            jitter = random.uniform(0.8, 1.2)
            sleep_sec = max(0.05, min(10.0, sleep_sec * jitter))
        except Exception:
            sleep_sec = 0.2
        # Metrics + slog
        with contextlib.suppress(Exception):
            if hasattr(trader_instance, 'metrics') and trader_instance.metrics:
                trader_instance.metrics.observe_backoff_seconds(sleep_sec)
                trader_instance.metrics.record_order_submit_retry('order_place_fail')
            slog('order_submit_retry', symbol=oc.symbol, attempt=attempt, max_attempts=max_attempts, sleep_sec=round(sleep_sec, 3))
        time.sleep(sleep_sec)
    return None


def close_position(trader_instance, symbol: str):
    pos = trader_instance.positions.get(symbol)
    if not pos:
        return False
    state_manager = getattr(trader_instance, 'state_manager', None)
    if state_manager:
        state_manager.transition_to(symbol, OrderState.CLOSING)

    t0 = time.time()
    opposite = 'SELL' if pos['side'] == 'BUY' else 'BUY'
    order = trader_instance.api.place_order(symbol=symbol, side=opposite, order_type='MARKET', quantity=pos['remaining_size'], price=None)
    if not order:
        if state_manager:
            state_manager.transition_to(symbol, OrderState.ERROR, reason="Close order placement failed")
        return False

    fill, slip_bps, _ = extract_fills(order, pos['entry_price'], opposite, pos['remaining_size'])

    # Database kayit islemi - hata yakalama kaldirildi debug icin
    try:
        if pos.get('trade_id') is not None:
            success = trader_instance.trade_store.close_trade(pos['trade_id'], fill, pandas_ts(), exit_slippage_bps=slip_bps, exit_qty=pos['remaining_size'])
            if success:
                print(f"✅ Trade closed successfully: ID={pos['trade_id']}, {symbol} @ {fill}")
            else:
                print(f"❌ ERROR: close_trade returned False for ID={pos['trade_id']}, {symbol}")
        else:
            print(f"❌ ERROR: No trade_id for position {symbol}, cannot close in database")
    except Exception as e:
        print(f"❌ ERROR closing trade in database: {e}")
        print(f"   Trade ID: {pos.get('trade_id')}, Symbol: {symbol}, Fill: {fill}")

    trader_instance.positions.pop(symbol, None)
    latency = (time.time() - t0) * 1000
    trader_instance.recent_close_latencies.append(latency)
    if slip_bps is not None:
        trader_instance.recent_exit_slippage_bps.append(float(slip_bps))
    maybe_trim_metrics(trader_instance)
    trader_instance.logger.info(f"KAPANDI {symbol} lat={latency:.1f}ms slip={slip_bps}")
    slog(
        'trade_close',
        symbol=symbol,
        latency_ms=round(latency, 2),
        slip_bps=slip_bps,
        fill=fill,
        trade_id=pos.get('trade_id')
    )

    if state_manager:
        state_manager.transition_to(symbol, OrderState.CLOSED)
        state_manager.clear_state(symbol)

    return True


def pandas_ts():  # separated for testability
    return pd.Timestamp.utcnow().isoformat()



