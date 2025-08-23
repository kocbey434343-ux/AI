from __future__ import annotations

from enum import Enum


class OrderState(str, Enum):
    OPENING = "OPENING"
    OPEN = "OPEN"
    SCALING = "SCALING"
    CLOSING = "CLOSING"
    CLOSED = "CLOSED"


ALLOWED_TRANSITIONS: dict[OrderState, set[OrderState]] = {
    OrderState.OPENING: {OrderState.OPEN, OrderState.CLOSING},
    OrderState.OPEN: {OrderState.SCALING, OrderState.CLOSING},
    OrderState.SCALING: {OrderState.SCALING, OrderState.CLOSING},
    OrderState.CLOSING: {OrderState.CLOSED},
    OrderState.CLOSED: set(),
}


def transition(current: OrderState, target: OrderState) -> OrderState:
    """Validate and return target (falls back to current if illegal)."""
    try:
        if target in ALLOWED_TRANSITIONS.get(current, set()):
            return target
        return current
    except Exception:
        return current
