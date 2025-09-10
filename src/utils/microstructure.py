"""
A32 Microstructure Filters Implementation
Real-time OBI (Order Book Imbalance) and AFR (Aggressive Fill Ratio) filtering
"""

import time
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

# Constants
TRADE_CACHE_MAX_AGE_SECONDS = 3600  # 1 hour


class ConflictAction(Enum):
    """Actions to take when OBI and AFR signals conflict"""
    WAIT = "wait"
    ABORT = "abort"


@dataclass
class MicrostructureConfig:
    """Configuration for microstructure filters"""
    enabled: bool = False
    obi_levels: int = 5
    obi_long_min: float = 0.20
    obi_short_max: float = -0.20
    afr_window_trades: int = 80
    afr_long_min: float = 0.55
    afr_short_max: float = 0.45
    conflict_action: ConflictAction = ConflictAction.WAIT
    cache_ttl_seconds: float = 2.0
    min_trades_for_afr: int = 20


@dataclass
class OrderBookSnapshot:
    """Order book snapshot data"""
    timestamp: float
    bids: List[Tuple[float, float]]
    asks: List[Tuple[float, float]]

    def __post_init__(self):
        """Sort bids/asks after initialization"""
        self.bids = sorted(self.bids, key=lambda x: x[0], reverse=True)
        self.asks = sorted(self.asks, key=lambda x: x[0])


@dataclass
class TradeData:
    """Individual trade data"""
    timestamp: float
    price: float
    quantity: float
    is_buyer_maker: bool

    @property
    def is_aggressive_buy(self) -> bool:
        """True if this is an aggressive buy (taker buy)"""
        return not self.is_buyer_maker

    @property
    def is_aggressive_sell(self) -> bool:
        """True if this is an aggressive sell (taker sell)"""
        return self.is_buyer_maker


@dataclass
class MicrostructureSignal:
    """Generated microstructure signal"""
    timestamp: float
    obi_value: float
    afr_value: Optional[float]
    long_allowed: bool
    short_allowed: bool
    conflict_detected: bool
    action: str  # "LONG", "SHORT", "WAIT", "ABORT"


class MicrostructureFilter:
    """Real-time microstructure filter for OBI/AFR analysis"""

    def __init__(self, config: MicrostructureConfig):
        self.config = config
        self._trade_cache: Dict[str, deque] = {}
        self._obi_cache: Dict[str, Tuple[float, float]] = {}  # (value, timestamp)

    def calculate_obi(self, orderbook: OrderBookSnapshot, levels: Optional[int] = None) -> float:
        """Calculate Order Book Imbalance"""
        if not self.config.enabled:
            return 0.0

        if not orderbook.bids or not orderbook.asks:
            return 0.0

        max_levels = levels or self.config.obi_levels

        bid_volume = sum(volume for _, volume in orderbook.bids[:max_levels])
        ask_volume = sum(volume for _, volume in orderbook.asks[:max_levels])

        total_volume = bid_volume + ask_volume
        if total_volume == 0:
            return 0.0

        return (bid_volume - ask_volume) / total_volume

    def update_obi_cache(self, symbol: str, orderbook: OrderBookSnapshot) -> float:
        """Update OBI cache for symbol"""
        obi = self.calculate_obi(orderbook)
        self._obi_cache[symbol] = (obi, time.time())
        return obi

    def get_cached_obi(self, symbol: str) -> Optional[float]:
        """Get cached OBI if still valid"""
        if symbol not in self._obi_cache:
            return None

        obi_value, timestamp = self._obi_cache[symbol]
        if time.time() - timestamp > self.config.cache_ttl_seconds:
            del self._obi_cache[symbol]
            return None

        return obi_value

    def update_trades(self, symbol: str, trades: List[TradeData]):
        """Update trade cache for symbol"""
        if not self.config.enabled:
            return

        if symbol not in self._trade_cache:
            self._trade_cache[symbol] = deque()

        cache = self._trade_cache[symbol]

        # Add new trades
        for trade in trades:
            cache.append(trade)

        # Remove old trades
        current_time = time.time()
        while cache and current_time - cache[0].timestamp > TRADE_CACHE_MAX_AGE_SECONDS:
            cache.popleft()

        # Limit cache size
        while len(cache) > self.config.afr_window_trades:
            cache.popleft()

    def calculate_afr(self, symbol: str) -> Optional[float]:
        """Calculate Aggressive Fill Ratio"""
        if not self.config.enabled:
            return None

        if symbol not in self._trade_cache:
            return None

        trades = list(self._trade_cache[symbol])
        if len(trades) < self.config.min_trades_for_afr:
            return None

        # Calculate volume-weighted AFR
        aggressive_buy_volume = sum(trade.quantity for trade in trades if trade.is_aggressive_buy)
        total_volume = sum(trade.quantity for trade in trades)

        if total_volume == 0:
            return None

        return aggressive_buy_volume / total_volume

    def _get_direction_allowances(self, obi: float, afr: Optional[float]) -> Tuple[bool, bool, bool, bool]:
        """Helper: Get direction allowances based on thresholds"""
        # OBI preferences
        obi_favors_long = obi >= self.config.obi_long_min
        obi_favors_short = obi <= self.config.obi_short_max

        # AFR preferences (if available)
        afr_favors_long = afr >= self.config.afr_long_min if afr is not None else True
        afr_favors_short = afr <= self.config.afr_short_max if afr is not None else True

        # Final allowances (both must agree)
        long_allowed = obi_favors_long and afr_favors_long
        short_allowed = obi_favors_short and afr_favors_short

        return long_allowed, short_allowed, obi_favors_long, obi_favors_short

    def _detect_conflicts(self, obi_favors_long: bool, obi_favors_short: bool, afr: Optional[float]) -> bool:
        """Helper: Detect if there's a conflict between OBI and AFR signals"""
        if afr is None:
            return False  # No conflict if AFR not available

        afr_favors_long = afr >= self.config.afr_long_min
        afr_favors_short = afr <= self.config.afr_short_max

        # Conflict occurs when OBI and AFR favor opposite directions
        return (obi_favors_long and afr_favors_short and not afr_favors_long) or \
               (obi_favors_short and afr_favors_long and not afr_favors_short)

    def _determine_action(self, long_allowed: bool, short_allowed: bool, conflict_detected: bool) -> str:
        """Helper: Determine final action based on allowances and conflicts"""
        if conflict_detected:
            return self.config.conflict_action.value.upper()

        if long_allowed:
            return "LONG"
        if short_allowed:
            return "SHORT"
        return "WAIT"

    def generate_signal(self, symbol: str, orderbook: Optional[OrderBookSnapshot] = None) -> MicrostructureSignal:
        """Generate microstructure signal for symbol"""
        current_time = time.time()

        if not self.config.enabled:
            return MicrostructureSignal(
                timestamp=current_time,
                obi_value=0.0,
                afr_value=0.5,
                long_allowed=True,
                short_allowed=True,
                conflict_detected=False,
                action="WAIT"
            )

        # Calculate OBI
        if orderbook:
            obi = self.update_obi_cache(symbol, orderbook)
        else:
            obi = self.get_cached_obi(symbol) or 0.0

        # Calculate AFR
        afr = self.calculate_afr(symbol)

        # Determine direction allowances
        long_allowed, short_allowed, obi_favors_long, obi_favors_short = self._get_direction_allowances(obi, afr)

        # Detect conflicts
        conflict_detected = self._detect_conflicts(obi_favors_long, obi_favors_short, afr)

        # Determine final action
        action = self._determine_action(long_allowed, short_allowed, conflict_detected)

        return MicrostructureSignal(
            timestamp=current_time,
            obi_value=obi,
            afr_value=afr,
            long_allowed=long_allowed,
            short_allowed=short_allowed,
            conflict_detected=conflict_detected,
            action=action
        )

    def should_allow_trade(self, symbol: str, direction: str, orderbook: Optional[OrderBookSnapshot] = None) -> bool:
        """Check if trade should be allowed based on microstructure"""
        if not self.config.enabled:
            return True

        signal = self.generate_signal(symbol, orderbook)

        if signal.action == "ABORT":
            return False

        if direction.upper() == "LONG":
            return signal.long_allowed
        if direction.upper() == "SHORT":
            return signal.short_allowed

        return False


# Global singleton instance
_microstructure_filter: Optional[MicrostructureFilter] = None


def get_microstructure_filter() -> MicrostructureFilter:
    """Get global microstructure filter instance"""
    # Use module-level singleton pattern to avoid global statement
    global _microstructure_filter
    if _microstructure_filter is None:
        config = MicrostructureConfig()
        _microstructure_filter = MicrostructureFilter(config)
    return _microstructure_filter


def calculate_order_book_imbalance(bids: List[Tuple[float, float]],
                                 asks: List[Tuple[float, float]],
                                 levels: int = 5) -> float:
    """Calculate OBI from bid/ask lists"""
    if not bids or not asks:
        return 0.0

    bid_volume = sum(volume for _, volume in bids[:levels])
    ask_volume = sum(volume for _, volume in asks[:levels])

    total_volume = bid_volume + ask_volume
    if total_volume == 0:
        return 0.0

    return (bid_volume - ask_volume) / total_volume


def should_allow_trade_by_microstructure(symbol: str,
                                       direction: str,
                                       orderbook_data: Optional[Dict[str, Any]] = None) -> bool:
    """Global convenience function for trade allowance"""
    filter_instance = get_microstructure_filter()

    orderbook = None
    if orderbook_data:
        orderbook = OrderBookSnapshot(
            timestamp=time.time(),
            bids=orderbook_data.get('bids', []),
            asks=orderbook_data.get('asks', [])
        )

    return filter_instance.should_allow_trade(symbol, direction, orderbook)
