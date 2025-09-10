"""
Liquidity-Aware Execution Framework - Order Book Analysis

Advanced order book analysis for optimal trade execution
"""

import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

import numpy as np


class LiquidityTier(Enum):
    """Liquidity classification levels"""
    EXCELLENT = "excellent"  # Very deep order book, minimal impact
    GOOD = "good"           # Adequate liquidity, low impact
    MODERATE = "moderate"   # Limited liquidity, moderate impact
    POOR = "poor"          # Thin liquidity, high impact
    CRITICAL = "critical"   # Very thin, execution risky


@dataclass
class OrderBookLevel:
    """Single order book level"""
    price: float
    quantity: float
    cumulative_quantity: float = 0.0


@dataclass
class OrderBookSnapshot:
    """Complete order book snapshot"""
    symbol: str
    timestamp: float
    bids: List[OrderBookLevel]
    asks: List[OrderBookLevel]

    def __post_init__(self):
        """Calculate cumulative quantities"""
        # Calculate cumulative for bids (descending price)
        cumsum = 0.0
        for level in self.bids:
            cumsum += level.quantity
            level.cumulative_quantity = cumsum

        # Calculate cumulative for asks (ascending price)
        cumsum = 0.0
        for level in self.asks:
            cumsum += level.quantity
            level.cumulative_quantity = cumsum


@dataclass
class LiquidityMetrics:
    """Comprehensive liquidity assessment"""
    symbol: str
    timestamp: float

    # Spread metrics
    spread_abs: float
    spread_bps: float
    mid_price: float

    # Depth metrics
    bid_depth_1: float  # Depth at best bid
    ask_depth_1: float  # Depth at best ask
    bid_depth_5: float  # Cumulative depth top 5 levels
    ask_depth_5: float  # Cumulative depth top 5 levels

    # Imbalance metrics
    order_book_imbalance: float  # (bid_vol - ask_vol) / (bid_vol + ask_vol)
    depth_ratio: float          # bid_depth / ask_depth

    # Impact estimates
    impact_100_usd: float       # Expected impact for $100 order
    impact_1000_usd: float      # Expected impact for $1000 order
    impact_5000_usd: float      # Expected impact for $5000 order

    # Liquidity tier
    liquidity_tier: LiquidityTier

    # Market microstructure
    effective_spread: float     # Effective spread estimate
    realized_spread: float      # Realized spread (if available)


class OrderBookAnalyzer:
    """
    Advanced order book analysis for liquidity assessment
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__)

        # Configuration parameters
        self.max_levels = self.config.get('max_levels', 20)
        self.impact_amounts = self.config.get('impact_amounts', [100, 1000, 5000])
        self.liquidity_thresholds = self.config.get('liquidity_thresholds', {
            'excellent_spread_bps': 2.0,
            'good_spread_bps': 5.0,
            'moderate_spread_bps': 10.0,
            'poor_spread_bps': 20.0,
            'excellent_depth_usd': 10000,
            'good_depth_usd': 5000,
            'moderate_depth_usd': 2000,
            'poor_depth_usd': 500
        })

        # Cache for recent analyses
        self.cache = {}
        self.cache_ttl = self.config.get('cache_ttl_seconds', 5)

    def analyze_order_book(self, snapshot: OrderBookSnapshot) -> LiquidityMetrics:
        """
        Comprehensive order book analysis

        Args:
            snapshot: Order book snapshot to analyze

        Returns:
            LiquidityMetrics with comprehensive assessment
        """
        try:
            # Check cache first
            cache_key = f"{snapshot.symbol}_{snapshot.timestamp}"
            if self._check_cache(cache_key):
                return self.cache[cache_key]['metrics']

            if not snapshot.bids or not snapshot.asks:
                return self._create_empty_metrics(snapshot)

            # Basic price metrics
            best_bid = snapshot.bids[0].price
            best_ask = snapshot.asks[0].price
            mid_price = (best_bid + best_ask) / 2.0
            spread_abs = best_ask - best_bid
            spread_bps = (spread_abs / mid_price) * 10000 if mid_price > 0 else float('inf')

            # Depth analysis
            bid_depth_1 = snapshot.bids[0].quantity * best_bid
            ask_depth_1 = snapshot.asks[0].quantity * best_ask

            bid_depth_5 = sum(level.quantity * level.price
                             for level in snapshot.bids[:5])
            ask_depth_5 = sum(level.quantity * level.price
                             for level in snapshot.asks[:5])

            # Imbalance metrics
            total_bid_vol = sum(level.quantity for level in snapshot.bids[:10])
            total_ask_vol = sum(level.quantity for level in snapshot.asks[:10])

            total_vol = total_bid_vol + total_ask_vol
            order_book_imbalance = ((total_bid_vol - total_ask_vol) / total_vol
                                   if total_vol > 0 else 0.0)

            depth_ratio = bid_depth_5 / ask_depth_5 if ask_depth_5 > 0 else float('inf')

            # Market impact estimation
            impact_estimates = {}
            for amount_usd in self.impact_amounts:
                impact_bps = self._estimate_market_impact(snapshot, amount_usd, mid_price)
                impact_estimates[f"impact_{amount_usd}_usd"] = impact_bps

            # Liquidity tier classification
            liquidity_tier = self._classify_liquidity_tier(
                spread_bps, bid_depth_5 + ask_depth_5
            )

            # Effective spread estimation
            effective_spread = self._estimate_effective_spread(snapshot, mid_price)

            # Create metrics object
            metrics = LiquidityMetrics(
                symbol=snapshot.symbol,
                timestamp=snapshot.timestamp,
                spread_abs=spread_abs,
                spread_bps=spread_bps,
                mid_price=mid_price,
                bid_depth_1=bid_depth_1,
                ask_depth_1=ask_depth_1,
                bid_depth_5=bid_depth_5,
                ask_depth_5=ask_depth_5,
                order_book_imbalance=order_book_imbalance,
                depth_ratio=depth_ratio,
                impact_100_usd=impact_estimates.get("impact_100_usd", 0.0),
                impact_1000_usd=impact_estimates.get("impact_1000_usd", 0.0),
                impact_5000_usd=impact_estimates.get("impact_5000_usd", 0.0),
                liquidity_tier=liquidity_tier,
                effective_spread=effective_spread,
                realized_spread=0.0  # Will be calculated from trade data
            )

            # Cache the result
            self._cache_metrics(cache_key, metrics)

            return metrics

        except Exception as e:
            self.logger.warning(f"Error analyzing order book for {snapshot.symbol}: {e}")
            return self._create_empty_metrics(snapshot)

    def _estimate_market_impact(self, snapshot: OrderBookSnapshot,
                               amount_usd: float, mid_price: float) -> float:
        """
        Estimate market impact for given order size

        Args:
            snapshot: Order book snapshot
            amount_usd: Order size in USD
            mid_price: Current mid price

        Returns:
            Estimated impact in basis points
        """
        try:
            # Determine side (assume worst case - we're taking liquidity)
            # For buy orders, walk through asks
            # For sell orders, walk through bids

            # Calculate for both sides and take average
            buy_impact = self._calculate_side_impact(
                snapshot.asks, amount_usd, mid_price, is_buy=True
            )
            sell_impact = self._calculate_side_impact(
                snapshot.bids, amount_usd, mid_price, is_buy=False
            )

            # Return average impact
            return (buy_impact + sell_impact) / 2.0

        except Exception as e:
            self.logger.warning(f"Error estimating market impact: {e}")
            return 0.0

    def _calculate_side_impact(self, levels: List[OrderBookLevel],
                              amount_usd: float, mid_price: float,
                              is_buy: bool) -> float:
        """Calculate impact for one side of the book"""
        remaining_usd = amount_usd
        total_quantity = 0.0
        volume_weighted_price = 0.0

        for level in levels:
            if remaining_usd <= 0:
                break

            level_value_usd = level.quantity * level.price

            if level_value_usd <= remaining_usd:
                # Consume entire level
                total_quantity += level.quantity
                volume_weighted_price += level.quantity * level.price
                remaining_usd -= level_value_usd
            else:
                # Partial level consumption
                partial_quantity = remaining_usd / level.price
                total_quantity += partial_quantity
                volume_weighted_price += partial_quantity * level.price
                remaining_usd = 0

        if total_quantity == 0:
            return float('inf')  # No liquidity available

        avg_execution_price = volume_weighted_price / total_quantity

        if is_buy:
            impact_abs = avg_execution_price - mid_price
        else:
            impact_abs = mid_price - avg_execution_price

        impact_bps = (impact_abs / mid_price) * 10000 if mid_price > 0 else 0.0

        return max(0.0, impact_bps)  # Impact should be non-negative

    def _classify_liquidity_tier(self, spread_bps: float, total_depth_usd: float) -> LiquidityTier:
        """Classify liquidity based on spread and depth"""
        thresholds = self.liquidity_thresholds

        # Excellent: tight spread AND deep book
        if (spread_bps <= thresholds['excellent_spread_bps'] and
            total_depth_usd >= thresholds['excellent_depth_usd']):
            return LiquidityTier.EXCELLENT

        # Good: reasonable spread AND adequate depth
        if (spread_bps <= thresholds['good_spread_bps'] and
              total_depth_usd >= thresholds['good_depth_usd']):
            return LiquidityTier.GOOD

        # Moderate: acceptable spread OR moderate depth
        if (spread_bps <= thresholds['moderate_spread_bps'] and
              total_depth_usd >= thresholds['moderate_depth_usd']):
            return LiquidityTier.MODERATE

        # Poor: wide spread OR thin depth
        if (spread_bps <= thresholds['poor_spread_bps'] and
              total_depth_usd >= thresholds['poor_depth_usd']):
            return LiquidityTier.POOR

        # Critical: very wide spread AND very thin depth
        return LiquidityTier.CRITICAL

    def _estimate_effective_spread(self, snapshot: OrderBookSnapshot,
                                  mid_price: float) -> float:
        """Estimate effective spread based on order book characteristics"""
        try:
            quoted_spread = snapshot.asks[0].price - snapshot.bids[0].price
            quoted_spread_bps = (quoted_spread / mid_price) * 10000

            # Effective spread is typically 40-60% of quoted spread for liquid markets
            # Adjust based on order book imbalance
            total_bid_vol = sum(level.quantity for level in snapshot.bids[:5])
            total_ask_vol = sum(level.quantity for level in snapshot.asks[:5])

            if total_bid_vol + total_ask_vol == 0:
                return quoted_spread_bps

            imbalance = abs(total_bid_vol - total_ask_vol) / (total_bid_vol + total_ask_vol)

            # Base effective spread ratio
            effective_ratio = 0.5  # 50% of quoted spread

            # Adjust for imbalance (higher imbalance = higher effective spread)
            effective_ratio += imbalance * 0.2

            return quoted_spread_bps * effective_ratio

        except Exception as e:
            self.logger.warning(f"Error estimating effective spread: {e}")
            return 0.0

    def _create_empty_metrics(self, snapshot: OrderBookSnapshot) -> LiquidityMetrics:
        """Create empty metrics for error cases"""
        return LiquidityMetrics(
            symbol=snapshot.symbol,
            timestamp=snapshot.timestamp,
            spread_abs=float('inf'),
            spread_bps=float('inf'),
            mid_price=0.0,
            bid_depth_1=0.0,
            ask_depth_1=0.0,
            bid_depth_5=0.0,
            ask_depth_5=0.0,
            order_book_imbalance=0.0,
            depth_ratio=0.0,
            impact_100_usd=float('inf'),
            impact_1000_usd=float('inf'),
            impact_5000_usd=float('inf'),
            liquidity_tier=LiquidityTier.CRITICAL,
            effective_spread=float('inf'),
            realized_spread=0.0
        )

    def _check_cache(self, cache_key: str) -> bool:
        """Check if cache entry is valid"""
        if cache_key not in self.cache:
            return False

        entry = self.cache[cache_key]
        return time.time() - entry['timestamp'] < self.cache_ttl

    def _cache_metrics(self, cache_key: str, metrics: LiquidityMetrics):
        """Cache metrics for reuse"""
        self.cache[cache_key] = {
            'timestamp': time.time(),
            'metrics': metrics
        }

        # Cleanup old cache entries
        current_time = time.time()
        keys_to_remove = [
            key for key, entry in self.cache.items()
            if current_time - entry['timestamp'] > self.cache_ttl * 2
        ]

        for key in keys_to_remove:
            del self.cache[key]

    def get_liquidity_summary(self, symbol: str) -> Optional[Dict]:
        """Get summary of recent liquidity metrics"""
        try:
            recent_entries = [
                entry for key, entry in self.cache.items()
                if symbol in key and time.time() - entry['timestamp'] < 60
            ]

            if not recent_entries:
                return None

            metrics_list = [entry['metrics'] for entry in recent_entries]

            return {
                'symbol': symbol,
                'sample_count': len(metrics_list),
                'avg_spread_bps': np.mean([m.spread_bps for m in metrics_list]),
                'avg_depth_usd': np.mean([m.bid_depth_5 + m.ask_depth_5 for m in metrics_list]),
                'avg_imbalance': np.mean([m.order_book_imbalance for m in metrics_list]),
                'dominant_tier': max(set(m.liquidity_tier for m in metrics_list),
                                   key=lambda x: sum(1 for m in metrics_list if m.liquidity_tier == x)),
                'last_update': max(m.timestamp for m in metrics_list)
            }

        except Exception as e:
            self.logger.warning(f"Error generating liquidity summary: {e}")
            return None


# Convenience functions for easy integration
_analyzer_instance = None

def get_order_book_analyzer(config: Optional[Dict] = None) -> OrderBookAnalyzer:
    """Get singleton order book analyzer instance"""
    global _analyzer_instance
    if _analyzer_instance is None:
        _analyzer_instance = OrderBookAnalyzer(config)
    return _analyzer_instance

def analyze_liquidity(snapshot: OrderBookSnapshot) -> LiquidityMetrics:
    """Convenience function for liquidity analysis"""
    analyzer = get_order_book_analyzer()
    return analyzer.analyze_order_book(snapshot)

def create_order_book_snapshot(symbol: str, bids_data: List[Tuple[float, float]],
                              asks_data: List[Tuple[float, float]],
                              timestamp: Optional[float] = None) -> OrderBookSnapshot:
    """
    Create order book snapshot from price/quantity tuples

    Args:
        symbol: Trading symbol
        bids_data: List of (price, quantity) tuples for bids
        asks_data: List of (price, quantity) tuples for asks
        timestamp: Optional timestamp (defaults to current time)

    Returns:
        OrderBookSnapshot object
    """
    if timestamp is None:
        timestamp = time.time()

    # Sort bids descending by price, asks ascending by price
    bids_sorted = sorted(bids_data, key=lambda x: x[0], reverse=True)
    asks_sorted = sorted(asks_data, key=lambda x: x[0])

    bids = [OrderBookLevel(price=price, quantity=qty) for price, qty in bids_sorted]
    asks = [OrderBookLevel(price=price, quantity=qty) for price, qty in asks_sorted]

    return OrderBookSnapshot(
        symbol=symbol,
        timestamp=timestamp,
        bids=bids,
        asks=asks
    )

def get_liquidity_statistics() -> Dict:
    """Get system statistics for liquidity analysis"""
    analyzer = get_order_book_analyzer()

    return {
        'analyzer_available': True,
        'cache_size': len(analyzer.cache),
        'cache_ttl': analyzer.cache_ttl,
        'max_levels': analyzer.max_levels,
        'supported_tiers': [tier.value for tier in LiquidityTier],
        'impact_amounts': analyzer.impact_amounts
    }
