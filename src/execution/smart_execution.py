"""Smart, liquidity-aware execution (TWAP/VWAP).

FEATURES:
- TWAP (Time-Weighted Average Price): Equal-sized slices over time
- VWAP (Volume-Weighted Average Price): Volume-proportional slices
- Participation Rate Limiting: Max % of market volume per slice
- Quantization & Min-Notional Guards: Exchange compliance
- Dynamic Configuration: Runtime env variable overrides for tests

MODES:
- "twap": Equal slices (default, backwards compatible)
- "vwap": Volume-weighted slices with participation limiting
- "auto": VWAP if data available, fallback to TWAP

CONFIGURATION:
- SMART_EXECUTION_ENABLED: Enable/disable smart execution
- SMART_EXECUTION_MODE: twap|vwap|auto
- TWAP_SLICES: Number of slices (default: 4)
- TWAP_INTERVAL_SEC: Time between slices (default: 0.5s)
- MAX_PARTICIPATION_RATE: Max % of market volume (default: 20%)
- VWAP_WINDOW_BARS: Lookback for volume data (default: 20)
- MIN_SLICE_NOTIONAL_USDT: Min slice value (default: 10.0)
- MIN_SLICE_QTY: Min slice quantity (default: 0.0)

Minimal, test-friendly implementation guarded by Settings.SMART_EXECUTION_ENABLED.
Defaults are conservative and backwards compatible (no behavior change when disabled).
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from importlib import import_module
from typing import Any, Dict, List, Optional, Tuple


@dataclass(slots=True)
class SlicePlan:
    slices: int
    interval_sec: float
    min_slice_notional: float
    min_slice_qty: float
    mode: str = "twap"  # twap|vwap|auto
    max_participation_rate: float = 0.2  # participation limit for VWAP


@dataclass(slots=True)
class VWAPData:
    """Volume data for VWAP calculation."""
    volumes: List[float]  # recent volume data
    prices: List[float]   # corresponding prices
    total_volume: float   # cumulative volume for participation calc


def _compute_slice_quantity(total_qty: float, i: int, n: int, mode: str = "twap",
                           vwap_data: Optional[VWAPData] = None) -> float:
    """TWAP: Equal-weighted deterministic slicing. VWAP: Volume-weighted slicing."""
    if n <= 1:
        return total_qty

    # Auto mode: use VWAP if data available, else TWAP
    if mode == "auto":
        mode = "vwap" if vwap_data and len(vwap_data.volumes) >= n else "twap"

    if mode == "vwap" and vwap_data and len(vwap_data.volumes) >= n:
        # Volume-weighted: slice proportional to historical volume distribution
        total_vol = sum(vwap_data.volumes[:n])
        if total_vol > 0:
            vol_weight = vwap_data.volumes[i] / total_vol
            return total_qty * vol_weight

    # Default TWAP: equal slices
    base = total_qty / n
    if i == n - 1:
        return max(0.0, total_qty - base * (n - 1))
    return base


def _apply_participation_limit(slice_qty: float, market_volume: float,
                              max_participation: float) -> float:
    """Limit slice size to maximum participation rate."""
    if max_participation <= 0 or market_volume <= 0:
        return slice_qty
    max_qty = market_volume * max_participation
    return min(slice_qty, max_qty)


def _quantize(api, symbol: str, qty: float, price: Optional[float]) -> float:
    try:
        q_qty, _ = api.quantize(symbol, qty, price)
        return float(q_qty)
    except Exception:
        return max(0.0, qty)


def plan_slices() -> SlicePlan:
    # Dynamically resolve Settings to honor env changes and module reloads in tests
    settings = import_module('config.settings').Settings

    # Dynamic retrieval for test environment overrides
    import os
    n = max(1, int(os.getenv('TWAP_SLICES', getattr(settings, 'TWAP_SLICES', '4'))))
    interval = max(0.0, float(os.getenv('TWAP_INTERVAL_SEC', getattr(settings, 'TWAP_INTERVAL_SEC', '0.5'))))
    mode = os.getenv('SMART_EXECUTION_MODE', getattr(settings, 'SMART_EXECUTION_MODE', 'twap'))
    participation = os.getenv('MAX_PARTICIPATION_RATE', getattr(settings, 'MAX_PARTICIPATION_RATE', '0.2'))
    participation = max(0.0, min(1.0, float(participation)))

    return SlicePlan(
        slices=n,
        interval_sec=interval,
        min_slice_notional=max(0.0, float(settings.MIN_SLICE_NOTIONAL_USDT)),
        min_slice_qty=max(0.0, float(settings.MIN_SLICE_QTY)),
        mode=mode,
        max_participation_rate=participation,
    )


@dataclass(slots=True)
class ExecutionContext:
    """Execution parameters container to reduce function arguments."""
    api: Any
    symbol: str
    side: str
    total_qty: float
    ref_price: float
    sleep_fn: Any = time.sleep


def _create_vwap_data() -> Optional[VWAPData]:
    """Create VWAP data from recent market volumes. Placeholder implementation."""
    try:
        # Future: fetch recent klines/volume data from API
        # For now, return None to fall back to TWAP
        return None
    except Exception:
        return None


def _validate_and_prepare_slice(ctx: ExecutionContext, sp: SlicePlan, raw_slice: float,
                               vwap_data: Optional[VWAPData]) -> Tuple[bool, float]:
    """Validate slice constraints and return (should_skip, final_qty)."""
    # Apply participation limit if VWAP mode
    if sp.mode == "vwap" and vwap_data and vwap_data.total_volume > 0:
        raw_slice = _apply_participation_limit(raw_slice, vwap_data.total_volume, sp.max_participation_rate)

    # Min qty guard
    if sp.min_slice_qty > 0 and raw_slice < sp.min_slice_qty:
        return True, 0.0

    # Min notional guard
    if sp.min_slice_notional > 0 and ctx.ref_price > 0 and (raw_slice * ctx.ref_price) < sp.min_slice_notional:
        return True, 0.0

    # Quantize
    qty = _quantize(ctx.api, ctx.symbol, raw_slice, ctx.ref_price)
    if qty <= 0:
        return True, 0.0

    return False, qty


def _execute_single_slice(ctx: ExecutionContext, qty: float) -> Optional[Dict[str, Any]]:
    """Execute a single slice order."""
    return ctx.api.place_order(
        symbol=ctx.symbol,
        side=ctx.side,
        order_type='MARKET',
        quantity=qty,
        price=None
    )


def _sleep_between_slices(sp: SlicePlan, slice_index: int, total_slices: int, sleep_fn):
    """Handle inter-slice sleep with Settings override."""
    if slice_index >= total_slices - 1:
        return

    settings = import_module('config.settings').Settings
    delay = float(getattr(settings, 'SMART_EXECUTION_SLEEP_SEC', 0) or sp.interval_sec)
    if delay > 0:
        sleep_fn(max(0.0, delay))


def execute_sliced_market(api, symbol: str, side: str, total_qty: float, ref_price: float,
                          sleep_fn=time.sleep) -> Tuple[Optional[Dict[str, Any]], float]:
    """Place multiple market orders in slices. Returns (last_order, executed_qty).

    Notes:
    - Supports TWAP (equal slices) and VWAP (volume-weighted) modes.
    - Uses API.quantize for per-slice qty.
    - Skips zero/notional-too-small slices.
    - Sleep between slices is controlled by Settings and can be overridden in tests.
    """
    ctx = ExecutionContext(api, symbol, side, total_qty, ref_price, sleep_fn)
    sp = plan_slices()
    # Auto mode needs VWAP data to decide between VWAP and TWAP
    vwap_data = _create_vwap_data() if sp.mode in ("vwap", "auto") else None

    remaining = max(0.0, float(total_qty))
    executed = 0.0
    last_order: Optional[Dict[str, Any]] = None

    for i in range(sp.slices):
        if remaining <= 0:
            break

        raw_slice = _compute_slice_quantity(remaining, i, sp.slices - i, sp.mode, vwap_data)
        should_skip, qty = _validate_and_prepare_slice(ctx, sp, raw_slice, vwap_data)

        if should_skip:
            continue

        order = _execute_single_slice(ctx, qty)
        if order:
            executed += qty
            last_order = order
        remaining = max(0.0, remaining - qty)

        _sleep_between_slices(sp, i, sp.slices, sleep_fn)

    return last_order, executed
