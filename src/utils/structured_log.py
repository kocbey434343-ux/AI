from __future__ import annotations

import contextlib
import json
import time
from collections import deque
from typing import Any, Dict, List, Optional

from config.settings import Settings
from src.utils.logger import get_logger

# Try to import validator, graceful degradation if not available
try:
    from utils.structured_log_validator import validate_event
    VALIDATOR_AVAILABLE = True
except ImportError:
    validate_event = None  # type: ignore
    VALIDATOR_AVAILABLE = False


_slog = get_logger("Structured")

# In-memory halka buffer (testler icin). Varsayilan 500 olay saklar.
_BUF_MAX = 500
_EVENT_BUFFER: deque[dict] = deque(maxlen=_BUF_MAX)

# Validation statistics
_VALIDATION_STATS = {
    "total_events": 0,
    "validation_errors": 0,
    "validation_disabled": 0
}


def slog(event: str, **fields: Any) -> None:
    """
    Lightweight structured log (JSON) with optional schema validation.
    Test icin ring buffer'a da yazar.

    Args:
        event: Event name/type
        **fields: Additional event fields
    """
    _VALIDATION_STATS["total_events"] += 1

    # Build payload with timestamp
    payload: Dict[str, Any] = {"ts": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime()), "event": event}
    payload.update(fields)

    # Validate if validator is available and not disabled
    validation_enabled = getattr(Settings, "STRUCTURED_LOG_VALIDATION", True)
    if VALIDATOR_AVAILABLE and validation_enabled and validate_event is not None:
        with contextlib.suppress(Exception):
            is_valid, error_msg = validate_event(payload)
            if not is_valid:
                _VALIDATION_STATS["validation_errors"] += 1
                # Log validation error but don't block the event
                _slog.warning(f"Structured log validation failed for event '{event}': {error_msg}")
                # Add validation failure marker to payload
                payload["_validation_error"] = error_msg
    elif not VALIDATOR_AVAILABLE or not validation_enabled:
        _VALIDATION_STATS["validation_disabled"] += 1

    # Buffer'a ekle (her zaman) - testler buradan dogrulayabilir
    with contextlib.suppress(Exception):
        _EVENT_BUFFER.append(dict(payload))

    if not Settings.STRUCTURED_LOG_ENABLED:
        return

    with contextlib.suppress(Exception):
        _slog.info(json.dumps(payload, ensure_ascii=False))


def get_slog_events(event: Optional[str] = None) -> List[dict]:
    """Testler icin biriktirilmis olaylari dondurur. Filtre opsiyonel."""
    if event is None:
        return list(_EVENT_BUFFER)
    return [p for p in _EVENT_BUFFER if p.get('event') == event]


def clear_slog_events():
    """Buffer'i temizle (test izolasyonu)."""
    _EVENT_BUFFER.clear()


def get_validation_stats() -> Dict[str, int]:
    """Validation istatistiklerini dondurur - CR-0075."""
    return dict(_VALIDATION_STATS)


def reset_validation_stats():
    """Validation sayaclarini sifirla - test utility."""
    _VALIDATION_STATS["total_events"] = 0
    _VALIDATION_STATS["validation_errors"] = 0
    _VALIDATION_STATS["validation_disabled"] = 0
