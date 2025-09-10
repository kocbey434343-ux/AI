"""
CR-0065: Slippage Guard & Abort Protection

Bu modul acilis slippage'ini kontrol eder ve threshold asiminda order'lari
iptal eder veya pozisyon boyutunu azaltir.

Slippage: Beklenen fiyat ile gercek fill fiyati arasindaki fark (basis points).
Yuksek slippage ticarette kayip demektir, guard ile korunacak.

Policy Options:
- ABORT: Order iptal, trade acilmaz
- REDUCE: Pozisyon boyutu %50 azalt, retry
"""
from __future__ import annotations

import contextlib
import os
from typing import Any, Dict, Literal, Optional, Tuple, cast

from config.settings import Settings

from src.utils.logger import get_logger
from src.utils.structured_log import slog

SlippagePolicy = Literal["ABORT", "REDUCE"]

class SlippageGuard:
    """Slippage kontrolu ve koruma sinifi"""

    def __init__(self):
        self.logger = get_logger("SlippageGuard")
        self.violation_count = 0
        self.violations_by_symbol = {}
        self.total_slippage_bps = 0.0  # Metric tracking

    def calculate_slippage_bps(self, expected_price: float, fill_price: float,
                              side: str) -> float:
        """
        Slippage'i basis points olarak hesapla

        Args:
            expected_price: Sinyal/order'daki beklenen fiyat
            fill_price: Borsadan gelen gercek fill fiyati
            side: "BUY" veya "SELL"

        Returns:
            float: Slippage basis points (positive = unfavorable)
        """
        if expected_price <= 0 or fill_price <= 0:
            return 0.0

        # Slippage calculation depends on side
        if side == "BUY":
            # BUY icin: gercek fiyat > beklenen = negative slippage (unfavorable)
            slippage_ratio = (fill_price - expected_price) / expected_price
        else:  # SELL
            # SELL icin: gercek fiyat < beklenen = negative slippage (unfavorable)
            slippage_ratio = (expected_price - fill_price) / expected_price

        return slippage_ratio * 10000  # Convert to basis points

    def check_slippage_threshold(self, expected_price: float, fill_price: float,
                               side: str, symbol: str) -> Tuple[bool, float, str]:
        """
        Slippage threshold kontrolu

        Args:
            expected_price: Beklenen fiyat
            fill_price: Gercek fill fiyati
            side: Trade direction
            symbol: Trading pair

        Returns:
            tuple: (is_violation, slippage_bps, reason)
        """
        slippage_bps = self.calculate_slippage_bps(expected_price, fill_price, side)

        # Threshold from config
        max_slippage_bps = getattr(Settings, 'MAX_SLIPPAGE_BPS', 50.0)  # Default 0.5%

        # Only check unfavorable slippage (positive values)
        if slippage_bps > max_slippage_bps:
            # Violation detected - unfavorable slippage exceeds threshold
            self.violation_count += 1
            self.violations_by_symbol[symbol] = self.violations_by_symbol.get(symbol, 0) + 1
            self.total_slippage_bps += slippage_bps

            reason = f"slippage_{slippage_bps:.1f}bps_exceeds_{max_slippage_bps}bps"

            self.logger.warning(f"{symbol}: Slippage violation - {slippage_bps:.1f}bps "
                              f"exceeds threshold {max_slippage_bps}bps ({side})")

            slog('slippage_violation', symbol=symbol, side=side,
                 slippage_bps=slippage_bps, expected_price=expected_price,
                 fill_price=fill_price, threshold_bps=max_slippage_bps)

            return True, slippage_bps, reason

        return False, slippage_bps, ""

    def get_slippage_policy(self) -> SlippagePolicy:
        """Slippage policy konfigurasyonunu al"""
        policy_str = getattr(Settings, 'SLIPPAGE_GUARD_POLICY', 'ABORT')
        with contextlib.suppress(Exception):
            self.logger.info(f"Slippage policy check: {policy_str}")

        if policy_str.upper() == 'REDUCE':
            return 'REDUCE'
        return 'ABORT'  # Default safe option

    def handle_slippage_violation(self, symbol: str, slippage_bps: float,
                                current_qty: float) -> Tuple[str, Optional[float]]:
        """
        Slippage violation handling

        Args:
            symbol: Trading pair
            slippage_bps: Detected slippage
            current_qty: Current order quantity

        Returns:
            tuple: (action, new_qty) where action is "ABORT" or "REDUCE"
        """
        policy = self.get_slippage_policy()

        if policy == "ABORT":
            self.logger.warning(f"{symbol}: Slippage guard ABORT - order cancelled")
            slog('slippage_guard_action', symbol=symbol, action='ABORT',
                 slippage_bps=slippage_bps, original_qty=current_qty)
            return "ABORT", None

        if policy == "REDUCE":
            # Reduce quantity by 50%
            reduction_factor = getattr(Settings, 'SLIPPAGE_REDUCTION_FACTOR', 0.5)
            new_qty = current_qty * reduction_factor

            self.logger.warning(f"{symbol}: Slippage guard REDUCE - qty {current_qty:.6f} "
                              f"-> {new_qty:.6f} (factor: {reduction_factor})")

            slog('slippage_guard_action', symbol=symbol, action='REDUCE',
                 slippage_bps=slippage_bps, original_qty=current_qty,
                 new_qty=new_qty, reduction_factor=reduction_factor)

            return "REDUCE", new_qty

        return "ABORT", None  # Fallback

    def validate_order_execution(self, order_context: Dict[str, Any]) -> Tuple[bool, Optional[Dict]]:
        """
        Order execution'dan sonra slippage kontrolu

        Args:
            order_context: {
                'symbol': str,
                'side': str,
                'expected_price': float,
                'fill_price': float,
                'quantity': float,
                'order_id': str (optional)
            }

        Returns:
            tuple: (is_safe, corrective_action)
        """
        try:
            symbol = order_context.get('symbol')
            side = order_context.get('side')
            expected_price = order_context.get('expected_price')
            fill_price = order_context.get('fill_price')
            quantity = order_context.get('quantity')

            if not all([symbol, side, expected_price, fill_price, quantity]):
                self.logger.error("Slippage validation: Missing required order context")
                return False, {"action": "ABORT", "reason": "incomplete_context"}

            is_violation, slippage_bps, reason = self.check_slippage_threshold(
                cast(float, expected_price), cast(float, fill_price), cast(str, side), cast(str, symbol)
            )

            if not is_violation:
                # Normal slippage, no action needed
                return True, None

            # Violation detected, determine corrective action
            action, new_qty = self.handle_slippage_violation(cast(str, symbol), slippage_bps, cast(float, quantity))

            corrective_action = {
                "action": action,
                "reason": reason,
                "slippage_bps": slippage_bps,
                "original_qty": quantity,
                "new_qty": new_qty
            }

            return False, corrective_action

        except Exception as e:
            self.logger.error(f"Slippage validation error: {e}")
            slog('slippage_guard_error', error=str(e), context=order_context)
            return False, {"action": "ABORT", "reason": "validation_error"}

    def get_metrics(self) -> Dict[str, Any]:
        """Slippage guard metrics"""
        return {
            'violation_count': self.violation_count,
            'violations_by_symbol': dict(self.violations_by_symbol),
            'total_slippage_bps': self.total_slippage_bps,
            'avg_violation_slippage': (self.total_slippage_bps / self.violation_count
                                     if self.violation_count > 0 else 0.0),
            'guard_name': 'slippage'
        }

    def reset_daily_counters(self):
        """Daily reset for metrics"""
        self.logger.info(f"Slippage guard daily reset - violations: {self.violation_count}")
        self.violation_count = 0
        self.violations_by_symbol.clear()
        self.total_slippage_bps = 0.0


# Global instance
_slippage_guard = None
_last_pytest_test = None  # Test izolasyonu icin mevcut test adi

def get_slippage_guard() -> SlippageGuard:
    """Global slippage guard instance'ini al"""
    global _slippage_guard, _last_pytest_test

    # Pytest altinda her test icin taze ornek olustur (state leakage engelleme)
    current_test_raw = os.environ.get('PYTEST_CURRENT_TEST')
    # Normalize to avoid phase changes (setup/call/teardown) causing mid-test resets
    current_test = current_test_raw.split(' ', 1)[0] if current_test_raw else None
    if current_test and _last_pytest_test != current_test:
        _slippage_guard = SlippageGuard()
        _last_pytest_test = current_test

    if _slippage_guard is None:
        _slippage_guard = SlippageGuard()
    return _slippage_guard


def reset_slippage_guard() -> None:
    """Singleton'i manuel olarak sifirla (testler/diagnostic icin)."""
    global _slippage_guard, _last_pytest_test
    _slippage_guard = None
    _last_pytest_test = None


def validate_order_slippage(expected_price: float, fill_price: float,
                          side: str, symbol: str, quantity: float) -> Tuple[bool, Optional[Dict]]:
    """
    Public API: Order slippage doğrulamasi

    Returns:
        tuple: (is_safe, corrective_action)
    """
    guard = get_slippage_guard()

    order_context = {
        'symbol': symbol,
        'side': side,
        'expected_price': expected_price,
        'fill_price': fill_price,
        'quantity': quantity
    }

    return guard.validate_order_execution(order_context)


def calculate_slippage_bps(expected_price: float, fill_price: float, side: str) -> float:
    """Public API: Slippage calculation utility"""
    guard = get_slippage_guard()
    return guard.calculate_slippage_bps(expected_price, fill_price, side)
