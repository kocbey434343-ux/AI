"""
Basit idempotent submit deduplication yardimcisi.
Ana fikir: Kisa bir TTL icinde ayni dedup_key ile gelen emirleri engelle.
"""
from __future__ import annotations

import threading
import time
from typing import Dict

from config.settings import Settings


class _OrderDedup:
    def __init__(self):
        self._lock = threading.RLock()
        self._seen: Dict[str, float] = {}

    def _cleanup(self) -> None:
        now = time.time()
        # Lazy cleanup (O(n)) — veri az, basit tutuyoruz
        dead = [k for k, exp in self._seen.items() if exp < now]
        for k in dead:
            self._seen.pop(k, None)

    def should_submit(self, key: str) -> bool:
        with self._lock:
            self._cleanup()
            exp = self._seen.get(key)
            return exp is None or exp < time.time()

    def mark_submitted(self, key: str) -> None:
        with self._lock:
            ttl = max(1.0, float(Settings.ORDER_DEDUP_TTL_SEC))
            self._seen[key] = time.time() + ttl


_GLOBAL_SINGLETON: _OrderDedup | None = None


def get_order_dedup() -> _OrderDedup:
    # Basit, tembel singleton (global atama yan etkisi olmadan)
    instance = globals().get("_GLOBAL_SINGLETON")
    if instance is None:
        instance = _OrderDedup()
        globals()["_GLOBAL_SINGLETON"] = instance
    return instance


__all__ = ["get_order_dedup"]


def _reset_for_tests() -> None:
    """Yalnizca testlerde kullanilir: global singleton temizle."""
    globals()["_GLOBAL_SINGLETON"] = None

