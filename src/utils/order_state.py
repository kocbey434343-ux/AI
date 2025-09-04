from __future__ import annotations

from enum import Enum
from dataclasses import dataclass
from typing import Iterable


class OrderState(str, Enum):
    INIT = "INIT"
    SUBMITTING = "SUBMITTING"
    OPEN_PENDING = "OPEN_PENDING"
    PARTIAL = "PARTIAL"
    OPEN = "OPEN"
    ACTIVE = "ACTIVE"  # koruma emirleri yerlesmis
    SCALING_OUT = "SCALING_OUT"
    TRAILING_ADJUST = "TRAILING_ADJUST"
    CLOSING = "CLOSING"
    CLOSED = "CLOSED"
    CANCEL_PENDING = "CANCEL_PENDING"
    CANCELLED = "CANCELLED"
    ERROR = "ERROR"


ALLOWED_TRANSITIONS: dict[OrderState, set[OrderState]] = {
    OrderState.INIT: {OrderState.SUBMITTING, OrderState.CANCEL_PENDING, OrderState.ERROR},
    OrderState.SUBMITTING: {OrderState.OPEN_PENDING, OrderState.OPEN, OrderState.CANCEL_PENDING, OrderState.ERROR},
    OrderState.OPEN_PENDING: {OrderState.PARTIAL, OrderState.OPEN, OrderState.CANCEL_PENDING, OrderState.ERROR},
    OrderState.PARTIAL: {OrderState.PARTIAL, OrderState.OPEN, OrderState.SCALING_OUT, OrderState.CLOSING, OrderState.ERROR},
    OrderState.OPEN: {OrderState.ACTIVE, OrderState.SCALING_OUT, OrderState.CLOSING, OrderState.TRAILING_ADJUST, OrderState.ERROR},
    OrderState.ACTIVE: {OrderState.SCALING_OUT, OrderState.TRAILING_ADJUST, OrderState.CLOSING, OrderState.ERROR},
    OrderState.SCALING_OUT: {OrderState.ACTIVE, OrderState.SCALING_OUT, OrderState.CLOSING, OrderState.ERROR},
    OrderState.TRAILING_ADJUST: {OrderState.ACTIVE, OrderState.CLOSING, OrderState.ERROR},
    OrderState.CLOSING: {OrderState.CLOSED, OrderState.ERROR},
    OrderState.CANCEL_PENDING: {OrderState.CANCELLED, OrderState.ERROR},
    OrderState.CANCELLED: set(),
    OrderState.CLOSED: set(),
    OrderState.ERROR: {OrderState.CLOSING, OrderState.CANCEL_PENDING},
}


@dataclass(slots=True)
class StateTransition:
    trade_id: int | None
    symbol: str
    from_state: OrderState
    to_state: OrderState
    reason: str | None = None


def is_valid_transition(current: OrderState, target: OrderState) -> bool:
    return target in ALLOWED_TRANSITIONS.get(current, set())


def assert_transition(current: OrderState, target: OrderState) -> None:
    if not is_valid_transition(current, target):
        raise ValueError(f"Illegal transition {current} -> {target}")


def transition(current: OrderState, target: OrderState) -> OrderState:
    """Return target if valid else raise ValueError (strict mode)."""
    assert_transition(current, target)
    return target


def possible_targets(current: OrderState) -> Iterable[OrderState]:  # helper for tests
    return ALLOWED_TRANSITIONS.get(current, set())
