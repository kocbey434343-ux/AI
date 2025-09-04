"""Basit feature flag altyapisi.

Kullanim:
from src.utils.feature_flags import flag_enabled
if flag_enabled('NEW_UI_PANEL'): ...

Kaynak:
- Ortam degiskeni FEATURE_FLAGS="FLAG1,FLAG2" seklinde.
- SSoT'ta yeni flag tanimi CR ile eklenmeli.
"""
from __future__ import annotations

import os
from functools import lru_cache

_ENV_VAR = 'FEATURE_FLAGS'

@lru_cache(maxsize=1)
def _load_flags() -> set[str]:
    raw = os.getenv(_ENV_VAR, '')
    return {f.strip().upper() for f in raw.split(',') if f.strip()}

def flag_enabled(name: str) -> bool:
    return name.upper() in _load_flags()
