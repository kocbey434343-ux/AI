from __future__ import annotations
from typing import Sequence

def should_restart_ws(last_check_ts: float,
                      now_ts: float,
                      debounce_sec: float,
                      current_symbols: Sequence[str] | None,
                      new_symbols: Sequence[str] | None) -> bool:
    """Decide if websocket stream should restart.

    Rules:
      - Inside debounce window -> normally NO restart unless we had no symbols before and now we do.
      - Outside debounce window -> restart if symbol sets differ OR previous empty and new non-empty.
    """
    if current_symbols is None:
        current_symbols = []
    if new_symbols is None:
        new_symbols = []

    # Debounce window
    if (now_ts - last_check_ts) < debounce_sec:
        if not current_symbols and new_symbols:
            return True
        return False

    # Outside debounce window
    if not current_symbols and new_symbols:
        return True
    if set(current_symbols) != set(new_symbols):
        return True
    return False

__all__ = ["should_restart_ws"]
