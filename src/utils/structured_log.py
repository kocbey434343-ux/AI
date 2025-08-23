from __future__ import annotations

import contextlib
import json
import time
from collections import deque
from typing import Any, Dict, List, Optional

from config.settings import Settings
from src.utils.logger import get_logger


_slog = get_logger("Structured")

# In-memory halka buffer (testler icin). Varsayilan 500 olay saklar.
_BUF_MAX = 500
_EVENT_BUFFER: deque[dict] = deque(maxlen=_BUF_MAX)


def slog(event: str, **fields: Any) -> None:
    """Lightweight structured log (JSON). Test icin ring buffer'a da yazar."""
    payload: Dict[str, Any] = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()), "event": event}
    payload.update(fields)
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
