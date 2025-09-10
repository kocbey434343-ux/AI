import time
from collections import deque
from typing import Deque, Dict, List, Tuple

import pandas as pd


class CorrelationCache:
    """Maintains a rolling window of close prices per symbol and computes pairwise correlations.
    Only stores minimal data; full matrix computed on demand.
    """
    def __init__(self, window: int = 50, ttl_seconds: int = 900):
        self.window = window
        self.ttl = ttl_seconds
        self.data: Dict[str, Deque[Tuple[float, float]]] = {}
        # deque entries: (timestamp, price)

    def update(self, symbol: str, price: float, ts: float | None = None):
        ts = ts or time.time()
        dq = self.data.setdefault(symbol, deque())
        dq.append((ts, price))
        while len(dq) > self.window:
            dq.popleft()
        # TTL purge
        cutoff = ts - self.ttl
        while dq and dq[0][0] < cutoff:
            dq.popleft()

    def _series(self, symbol: str) -> pd.Series:
        dq = self.data.get(symbol)
        if not dq or len(dq) < 2:
            return pd.Series([], dtype=float)
        return pd.Series([p for _, p in dq])

    def correlation(self, a: str, b: str) -> float | None:
        sa = self._series(a)
        sb = self._series(b)
        if len(sa) < 5 or len(sb) < 5:
            return None
        try:
            return float(sa.pct_change().dropna().corr(sb.pct_change().dropna()))
        except Exception:
            return None

    def correlated_symbols(self, target: str, threshold: float) -> List[str]:
        out = []
        for s in self.data.keys():
            if s == target:
                continue
            c = self.correlation(target, s)
            if c is not None and c >= threshold:
                out.append(s)
        return out

__all__ = ["CorrelationCache"]
