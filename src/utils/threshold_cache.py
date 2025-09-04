"""
CR-0070: Threshold overrides caching system
Performance-optimized threshold access with override management
"""

import json
import os
import threading
import time
from collections import namedtuple
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.settings import Settings
from src.utils.logger import get_logger

logger = get_logger("ThresholdCache")

# Cache entry structure
CacheEntry = namedtuple('CacheEntry', ['value', 'source', 'timestamp', 'ttl'])

@dataclass
class ThresholdHistory:
    """Threshold değişiklik geçmişi"""
    threshold_name: str
    old_value: float
    new_value: float
    source: str
    timestamp: float
    reason: str = ""

class ThresholdCache:
    """
    High-performance threshold caching system with override support

    Features:
    - O(1) threshold lookups
    - Runtime override management
    - Persistent override storage
    - Change history tracking
    - Thread-safe operations
    - Auto-refresh with TTL
    """

    def __init__(self,
                 override_file: str = "data/param_overrides.json",
                 default_ttl: float = 300.0,  # 5 dakika
                 max_history: int = 1000):
        self._cache: Dict[str, CacheEntry] = {}
        self._overrides: Dict[str, float] = {}
        self._history: List[ThresholdHistory] = []
        self._override_file = override_file
        self._default_ttl = default_ttl
        self._max_history = max_history
        self._lock = threading.RLock()

        # Performance metrics
        self._cache_hits = 0
        self._cache_misses = 0
        self._override_sets = 0

        self._init_cache()
        self._load_overrides()

    def _init_cache(self):
        """Initialize cache with default Settings values"""
        threshold_names = [
            'BUY_SIGNAL_THRESHOLD', 'SELL_SIGNAL_THRESHOLD',
            'BUY_EXIT_THRESHOLD', 'SELL_EXIT_THRESHOLD'
        ]

        current_time = time.time()
        with self._lock:
            for name in threshold_names:
                if hasattr(Settings, name):
                    value = getattr(Settings, name)
                    self._cache[name] = CacheEntry(
                        value=value,
                        source='settings',
                        timestamp=current_time,
                        ttl=self._default_ttl
                    )
                    logger.info(f"ThresholdCache init: {name}={value}")

    def _load_overrides(self):
        """Load persistent overrides from JSON file"""
        try:
            if os.path.exists(self._override_file):
                with open(self._override_file, 'r') as f:
                    overrides = json.load(f)

                with self._lock:
                    self._overrides.update(overrides)

                    # Apply overrides to cache
                    current_time = time.time()
                    for name, value in overrides.items():
                        self._cache[name] = CacheEntry(
                            value=value,
                            source='override',
                            timestamp=current_time,
                            ttl=self._default_ttl
                        )

                logger.info(f"ThresholdCache loaded {len(overrides)} overrides from {self._override_file}")
        except Exception as e:
            logger.error(f"ThresholdCache override load error: {e}")

    def _save_overrides(self):
        """Persist current overrides to JSON file"""
        try:
            # Ensure directory exists
            Path(self._override_file).parent.mkdir(parents=True, exist_ok=True)

            with self._lock, open(self._override_file, 'w') as f:
                json.dump(self._overrides, f, indent=2)

            logger.info(f"ThresholdCache saved {len(self._overrides)} overrides to {self._override_file}")
        except Exception as e:
            logger.error(f"ThresholdCache override save error: {e}")

    def get_threshold(self, name: str) -> float:
        """
        Get threshold value with caching

        Args:
            name: Threshold name (e.g., 'BUY_SIGNAL_THRESHOLD')

        Returns:
            Threshold value

        Performance: O(1) memory lookup
        """
        current_time = time.time()

        with self._lock:
            # Check cache hit
            if name in self._cache:
                entry = self._cache[name]

                # Check TTL
                if current_time - entry.timestamp < entry.ttl:
                    self._cache_hits += 1
                    return entry.value

                # Expired - refresh from source
                self._refresh_entry(name, current_time)
                if name in self._cache:
                    self._cache_hits += 1
                    return self._cache[name].value

            # Cache miss
            self._cache_misses += 1

            # Fallback to Settings
            if hasattr(Settings, name):
                value = getattr(Settings, name)
                self._cache[name] = CacheEntry(
                    value=value,
                    source='settings_fallback',
                    timestamp=current_time,
                    ttl=self._default_ttl
                )
                logger.warning(f"ThresholdCache fallback for {name}={value}")
                return value

            raise ValueError(f"Unknown threshold: {name}")

    def _refresh_entry(self, name: str, current_time: float):
        """Refresh cache entry from authoritative source"""
        try:
            # Check override first
            if name in self._overrides:
                value = self._overrides[name]
                source = 'override'
            elif hasattr(Settings, name):
                value = getattr(Settings, name)
                source = 'settings'
            else:
                logger.error(f"ThresholdCache refresh failed - unknown threshold: {name}")
                return

            self._cache[name] = CacheEntry(
                value=value,
                source=source,
                timestamp=current_time,
                ttl=self._default_ttl
            )
        except Exception as e:
            logger.error(f"ThresholdCache refresh error for {name}: {e}")

    def set_override(self, name: str, value: float, reason: str = "manual", persist: bool = True):
        """
        Set runtime threshold override

        Args:
            name: Threshold name
            value: New threshold value
            reason: Change reason for history
            persist: Save override to disk
        """
        current_time = time.time()

        with self._lock:
            # Get old value for history
            old_value = None
            if name in self._cache:
                old_value = self._cache[name].value

            # Update override
            self._overrides[name] = value
            self._override_sets += 1

            # Update cache
            self._cache[name] = CacheEntry(
                value=value,
                source='override',
                timestamp=current_time,
                ttl=self._default_ttl
            )

            # Record history
            if old_value is not None:
                history_entry = ThresholdHistory(
                    threshold_name=name,
                    old_value=old_value,
                    new_value=value,
                    source='override',
                    timestamp=current_time,
                    reason=reason
                )
                self._history.append(history_entry)

                # Trim history if needed
                if len(self._history) > self._max_history:
                    self._history = self._history[-self._max_history:]

            # Persist if requested
            if persist:
                self._save_overrides()

            logger.info(f"ThresholdCache override set: {name}={value} (reason: {reason})")

    def remove_override(self, name: str, persist: bool = True):
        """Remove threshold override, revert to Settings value"""
        current_time = time.time()

        with self._lock:
            if name in self._overrides:
                old_value = self._overrides[name]
                del self._overrides[name]

                # Refresh from Settings
                if hasattr(Settings, name):
                    new_value = getattr(Settings, name)
                    self._cache[name] = CacheEntry(
                        value=new_value,
                        source='settings',
                        timestamp=current_time,
                        ttl=self._default_ttl
                    )

                    # Record history
                    history_entry = ThresholdHistory(
                        threshold_name=name,
                        old_value=old_value,
                        new_value=new_value,
                        source='revert',
                        timestamp=current_time,
                        reason="override_removed"
                    )
                    self._history.append(history_entry)

                if persist:
                    self._save_overrides()

                logger.info(f"ThresholdCache override removed: {name}")

    def invalidate_cache(self, name: Optional[str] = None):
        """
        Invalidate cache entries (force refresh)

        Args:
            name: Specific threshold name, or None for all
        """
        with self._lock:
            if name:
                if name in self._cache:
                    del self._cache[name]
                    logger.info(f"ThresholdCache invalidated: {name}")
            else:
                self._cache.clear()
                logger.info("ThresholdCache fully invalidated")
                self._init_cache()

    def get_statistics(self) -> Dict[str, Any]:
        """Get cache performance statistics"""
        with self._lock:
            total_requests = self._cache_hits + self._cache_misses
            hit_rate = (self._cache_hits / total_requests * 100) if total_requests > 0 else 0

            return {
                'cache_hits': self._cache_hits,
                'cache_misses': self._cache_misses,
                'hit_rate_percent': round(hit_rate, 2),
                'total_requests': total_requests,
                'override_sets': self._override_sets,
                'cached_entries': len(self._cache),
                'active_overrides': len(self._overrides),
                'history_entries': len(self._history)
            }

    def get_cache_status(self) -> Dict[str, Dict]:
        """Get detailed cache status for all entries"""
        with self._lock:
            current_time = time.time()
            status = {}

            for name, entry in self._cache.items():
                age = current_time - entry.timestamp
                expired = age >= entry.ttl

                status[name] = {
                    'value': entry.value,
                    'source': entry.source,
                    'age_seconds': round(age, 1),
                    'ttl_seconds': entry.ttl,
                    'expired': expired,
                    'has_override': name in self._overrides
                }

            return status

    def get_history(self, name: Optional[str] = None, limit: int = 50) -> List[Dict]:
        """
        Get threshold change history

        Args:
            name: Specific threshold name, or None for all
            limit: Maximum number of entries

        Returns:
            List of history entries
        """
        with self._lock:
            history = self._history

            if name:
                history = [h for h in history if h.threshold_name == name]

            # Sort by timestamp (newest first) and limit
            history = sorted(history, key=lambda x: x.timestamp, reverse=True)[:limit]

            return [
                {
                    'threshold_name': h.threshold_name,
                    'old_value': h.old_value,
                    'new_value': h.new_value,
                    'source': h.source,
                    'timestamp': h.timestamp,
                    'formatted_time': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(h.timestamp)),
                    'reason': h.reason
                }
                for h in history
            ]

# Module-level cache instance
_threshold_cache: Optional[ThresholdCache] = None
_cache_lock = threading.Lock()

def get_threshold_cache() -> ThresholdCache:
    """Get global threshold cache instance (singleton)"""
    global _threshold_cache

    if _threshold_cache is None:
        with _cache_lock:
            if _threshold_cache is None:
                _threshold_cache = ThresholdCache()

    return _threshold_cache  # type: ignore

# Convenience functions for backward compatibility
def get_cached_threshold(name: str) -> float:
    """Get threshold value using cache"""
    return get_threshold_cache().get_threshold(name)

def set_threshold_override(name: str, value: float, reason: str = "api"):
    """Set threshold override using cache"""
    return get_threshold_cache().set_override(name, value, reason)

def remove_threshold_override(name: str):
    """Remove threshold override using cache"""
    return get_threshold_cache().remove_override(name)

def get_threshold_statistics() -> Dict[str, Any]:
    """Get cache statistics"""
    return get_threshold_cache().get_statistics()
