"""
Dynamic Volatility Regime Detection Framework

This module provides real-time market regime classification and volatility analysis
for adaptive trading strategy optimization.
"""

import logging
import time
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

import numpy as np

try:
    import importlib.util
    HAS_SCIPY = importlib.util.find_spec("scipy") is not None
except ImportError:
    HAS_SCIPY = False

try:
    import importlib.util
    HAS_TALIB = importlib.util.find_spec("talib") is not None
except ImportError:
    HAS_TALIB = False


class MarketRegime(Enum):
    """Market regime classifications"""
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    VOLATILE = "volatile"
    SQUEEZE = "squeeze"
    BREAKOUT = "breakout"
    UNKNOWN = "unknown"


class VolatilityState(Enum):
    """Volatility state classifications"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    EXTREME = "extreme"


@dataclass
class RegimeMetrics:
    """Metrics for market regime analysis"""
    trend_strength: float  # 0-1, strength of trend
    volatility_percentile: float  # 0-100, historical volatility percentile
    range_efficiency: float  # 0-1, how much price moves vs range
    autocorrelation: float  # -1 to 1, price momentum persistence
    volume_trend: float  # -1 to 1, volume trend vs price trend alignment
    regime_stability: float  # 0-1, how stable current regime is

    def __post_init__(self):
        """Validate metrics are within expected ranges"""
        assert 0 <= self.trend_strength <= 1, f"Invalid trend_strength: {self.trend_strength}"
        assert 0 <= self.volatility_percentile <= 100, f"Invalid volatility_percentile: {self.volatility_percentile}"
        assert 0 <= self.range_efficiency <= 1, f"Invalid range_efficiency: {self.range_efficiency}"
        assert -1 <= self.autocorrelation <= 1, f"Invalid autocorrelation: {self.autocorrelation}"
        assert -1 <= self.volume_trend <= 1, f"Invalid volume_trend: {self.volume_trend}"
        assert 0 <= self.regime_stability <= 1, f"Invalid regime_stability: {self.regime_stability}"


@dataclass
class RegimeDetection:
    """Result of regime detection analysis"""
    regime: MarketRegime
    volatility_state: VolatilityState
    confidence: float  # 0-1, confidence in regime classification
    metrics: RegimeMetrics
    timestamp: float
    lookback_periods: int

    @property
    def is_trending(self) -> bool:
        """Check if market is in trending regime"""
        return self.regime in [MarketRegime.TRENDING_UP, MarketRegime.TRENDING_DOWN]

    @property
    def is_directional(self) -> bool:
        """Check if market has clear direction"""
        return self.regime in [MarketRegime.TRENDING_UP, MarketRegime.TRENDING_DOWN, MarketRegime.BREAKOUT]

    @property
    def is_stable(self) -> bool:
        """Check if regime is stable (high confidence and stability)"""
        return self.confidence > 0.7 and self.metrics.regime_stability > 0.6


class VolatilityRegimeDetector:
    """
    Advanced volatility regime detection system using multiple indicators
    and machine learning techniques for real-time market state analysis.
    """

    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize volatility regime detector

        Args:
            config: Configuration dictionary with detection parameters
        """
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        # Numerical safety epsilon to avoid divide-by-zero and log(0) warnings
        self._EPS = 1e-12

        # Detection parameters
        self.lookback_short = self.config.get('lookback_short', 20)
        self.lookback_medium = self.config.get('lookback_medium', 50)
        self.lookback_long = self.config.get('lookback_long', 200)
        self.vol_window = self.config.get('volatility_window', 20)
        self.regime_smoothing = self.config.get('regime_smoothing', 5)

        # Thresholds
        self.trend_threshold = self.config.get('trend_threshold', 0.6)
        self.volatility_thresholds = self.config.get('volatility_thresholds', {
            'low': 25,
            'normal': 50,
            'high': 75,
            'extreme': 90
        })
        self.range_efficiency_threshold = self.config.get('range_efficiency_threshold', 0.3)

        # State tracking
        self.price_history = deque(maxlen=self.lookback_long * 2)
        self.volume_history = deque(maxlen=self.lookback_long * 2)
        self.regime_history = deque(maxlen=100)
        self.volatility_history = deque(maxlen=500)  # For percentile calculation

        self.logger.info(f"VolatilityRegimeDetector initialized: "
                        f"lookback=({self.lookback_short},{self.lookback_medium},{self.lookback_long}), "
                        f"vol_window={self.vol_window}, smoothing={self.regime_smoothing}")

    def update_data(self, price: float, volume: float = 0.0, timestamp: Optional[float] = None) -> None:
        """
        Update detector with new price and volume data

        Args:
            price: Current price
            volume: Current volume (optional)
            timestamp: Data timestamp (defaults to current time)
        """
        if timestamp is None:
            timestamp = time.time()

        self.price_history.append((price, timestamp))
        self.volume_history.append((volume, timestamp))

        # Update volatility history for percentile calculation
        if len(self.price_history) >= self.vol_window:
            recent_prices = [p[0] for p in list(self.price_history)[-self.vol_window:]]
            volatility = self._calculate_volatility(np.array(recent_prices))
            self.volatility_history.append(volatility)

    def detect_regime(self) -> Optional[RegimeDetection]:
        """
        Detect current market regime based on available data

        Returns:
            RegimeDetection object or None if insufficient data
        """
        if len(self.price_history) < self.lookback_medium:
            self.logger.debug(f"Insufficient data for regime detection: "
                            f"{len(self.price_history)} < {self.lookback_medium}")
            return None

        try:
            # Extract price series
            prices = np.array([p[0] for p in self.price_history])
            volumes = np.array([v[0] for v in self.volume_history])

            # Calculate regime metrics
            metrics = self._calculate_regime_metrics(prices, volumes)

            # Classify regime
            regime = self._classify_regime(metrics)

            # Determine volatility state
            volatility_state = self._classify_volatility_state(metrics.volatility_percentile)

            # Calculate confidence
            confidence = self._calculate_confidence(metrics, regime)

            detection = RegimeDetection(
                regime=regime,
                volatility_state=volatility_state,
                confidence=confidence,
                metrics=metrics,
                timestamp=time.time(),
                lookback_periods=len(self.price_history)
            )

            # Update regime history
            self.regime_history.append(detection)

            self.logger.debug(f"Regime detected: {regime.value}, "
                            f"volatility: {volatility_state.value}, "
                            f"confidence: {confidence:.3f}")

            return detection

        except Exception as e:
            self.logger.error(f"Error in regime detection: {e}")
            return None

    def _calculate_regime_metrics(self, prices: np.ndarray, volumes: np.ndarray) -> RegimeMetrics:
        """Calculate comprehensive regime analysis metrics"""

        # Trend strength calculation
        trend_strength = self._calculate_trend_strength(prices)

        # Volatility percentile
        current_volatility = self._calculate_volatility(prices[-self.vol_window:])
        volatility_percentile = self._calculate_volatility_percentile(current_volatility)

        # Range efficiency (how much price moves vs total range)
        range_efficiency = self._calculate_range_efficiency(prices)

        # Price autocorrelation (momentum persistence)
        autocorrelation = self._calculate_autocorrelation(prices)

        # Volume-price trend alignment
        volume_trend = self._calculate_volume_trend_alignment(prices, volumes)

        # Regime stability (consistency over recent periods)
        regime_stability = self._calculate_regime_stability()

        return RegimeMetrics(
            trend_strength=trend_strength,
            volatility_percentile=volatility_percentile,
            range_efficiency=range_efficiency,
            autocorrelation=autocorrelation,
            volume_trend=volume_trend,
            regime_stability=regime_stability
        )

    def _calculate_trend_strength(self, prices: np.ndarray) -> float:
        """
        Calculate trend strength using multiple timeframe analysis

        Returns:
            Float between 0-1 indicating trend strength
        """
        if len(prices) < self.lookback_medium:
            return 0.0

        # Multiple timeframe trend analysis
        short_trend = self._linear_regression_slope(prices[-self.lookback_short:])
        medium_trend = self._linear_regression_slope(prices[-self.lookback_medium:])

        # ADX-style directional movement
        adx_strength = self._calculate_adx_strength(prices)

        # Moving average convergence/divergence
        ma_alignment = self._calculate_ma_alignment(prices)

        # Combine metrics
        trend_strength = np.mean([
            abs(short_trend),
            abs(medium_trend),
            adx_strength,
            ma_alignment
        ])

        return float(np.clip(trend_strength, 0.0, 1.0))

    def _calculate_volatility(self, prices: np.ndarray) -> float:
        """Calculate realized volatility (annualized)"""
        if len(prices) < 2:
            return 0.0
        # Guard against non-positive prices and suppress log warnings
        with np.errstate(divide='ignore', invalid='ignore'):
            safe_prices = np.maximum(prices, self._EPS)
            returns = np.diff(np.log(safe_prices))
        # Use standard deviation (no change in semantics)
        volatility = np.std(returns) * np.sqrt(252)  # Annualized
        return volatility

    def _calculate_volatility_percentile(self, current_volatility: float) -> float:
        """Calculate current volatility percentile vs historical"""
        if len(self.volatility_history) < 10:
            return 50.0  # Default to median

        historical_vols = list(self.volatility_history)
        if HAS_SCIPY:
            from scipy import stats as scipy_stats
            percentile = scipy_stats.percentileofscore(historical_vols, current_volatility)
        else:
            # Fallback percentile calculation
            percentile = self._calculate_percentile_fallback(historical_vols, current_volatility)
        return float(np.clip(percentile, 0.0, 100.0))

    def _calculate_percentile_fallback(self, values: List[float], target: float) -> float:
        """Fallback percentile calculation without scipy"""
        if not values:
            return 50.0

        # Sort values and compute counts relative to target
        sorted_values = sorted(values)
        count_below = sum(1 for v in sorted_values if v < target)
        count_equal = sum(1 for v in sorted_values if v == target)

        # Percentile calculation (similar to scipy percentileofscore)
        percentile = (count_below + 0.5 * count_equal) / len(values) * 100.0
        return float(np.clip(percentile, 0.0, 100.0))

    def _calculate_range_efficiency(self, prices: np.ndarray) -> float:
        """Calculate how efficiently price moves in trending direction"""
        if len(prices) < self.lookback_short:
            return 0.0

        # Net price movement vs total range
        net_move = abs(prices[-1] - prices[-self.lookback_short])
        total_range = np.max(prices[-self.lookback_short:]) - np.min(prices[-self.lookback_short:])
        # Avoid division by zero, extremely tiny, or non-finite ranges
        if not np.isfinite(net_move) or not np.isfinite(total_range) or total_range <= self._EPS:
            return 0.0

        with np.errstate(divide='ignore', invalid='ignore'):
            efficiency = net_move / total_range
        if not np.isfinite(efficiency):
            return 0.0
        return float(np.clip(efficiency, 0.0, 1.0))

    def _calculate_autocorrelation(self, prices: np.ndarray) -> float:
        """Calculate price autocorrelation (momentum persistence)"""
        if len(prices) < self.lookback_short + 1:
            return 0.0
        # Use safe prices for log and suppress warnings
        with np.errstate(divide='ignore', invalid='ignore'):
            window_prices = prices[-self.lookback_short:]
            safe_prices = np.maximum(window_prices, self._EPS)
            returns = np.diff(np.log(safe_prices))
        if len(returns) < 2:
            return 0.0

        # Lag-1 autocorrelation
        # Avoid degenerate variance that causes warnings/NaNs
        if np.std(returns[:-1]) <= self._EPS or np.std(returns[1:]) <= self._EPS:
            return 0.0
        correlation = np.corrcoef(returns[:-1], returns[1:])[0, 1]

        if np.isnan(correlation):
            return 0.0

        return np.clip(correlation, -1.0, 1.0)

    def _calculate_volume_trend_alignment(self, prices: np.ndarray, volumes: np.ndarray) -> float:
        """Calculate alignment between volume and price trends"""
        if len(prices) < self.lookback_short or len(volumes) < self.lookback_short:
            return 0.0

        # Recent price and volume trends
        price_trend = self._linear_regression_slope(prices[-self.lookback_short:])
        volume_trend = self._linear_regression_slope(volumes[-self.lookback_short:])

        # Alignment: positive when both trending same direction
        if abs(price_trend) < 1e-6 or abs(volume_trend) < 1e-6:
            return 0.0

        alignment = np.sign(price_trend) * np.sign(volume_trend)
        return alignment

    def _calculate_regime_stability(self) -> float:
        """Calculate stability of recent regime classifications"""
        if len(self.regime_history) < self.regime_smoothing:
            return 0.0

        recent_regimes = list(self.regime_history)[-self.regime_smoothing:]
        regime_values = [r.regime for r in recent_regimes]

        # Calculate stability as consistency
        unique_regimes = len(set(regime_values))
        max_stability = 1.0 - (unique_regimes - 1) / (len(regime_values) - 1) if len(regime_values) > 1 else 1.0

        return max(0.0, max_stability)

    def _classify_regime(self, metrics: RegimeMetrics) -> MarketRegime:
        """Classify market regime based on calculated metrics"""

        # Check for special regimes first
        special_regime = self._check_special_regimes(metrics)
        if special_regime != MarketRegime.UNKNOWN:
            return special_regime

        # Check trending regimes
        trending_regime = self._check_trending_regimes(metrics)
        if trending_regime != MarketRegime.UNKNOWN:
            return trending_regime

        # Default to ranging
        return MarketRegime.RANGING

    def _check_special_regimes(self, metrics: RegimeMetrics) -> MarketRegime:
        """Check for special market regimes (volatile, squeeze, breakout)"""

        # High volatility check
        if metrics.volatility_percentile > self.volatility_thresholds['extreme']:
            return MarketRegime.VOLATILE

        # Squeeze regime (low volatility, high stability)
        if (metrics.volatility_percentile < self.volatility_thresholds['low'] and
            metrics.regime_stability > 0.7):
            return MarketRegime.SQUEEZE

        # Breakout regime (increasing volatility after squeeze)
        if (len(self.regime_history) > 0 and
            self.regime_history[-1].regime == MarketRegime.SQUEEZE and
            metrics.volatility_percentile > self.volatility_thresholds['normal']):
            return MarketRegime.BREAKOUT

        return MarketRegime.UNKNOWN

    def _check_trending_regimes(self, metrics: RegimeMetrics) -> MarketRegime:
        """Check for trending market regimes"""

        # Trending regime check
        if metrics.trend_strength > self.trend_threshold:
            if metrics.range_efficiency > self.range_efficiency_threshold:
                # Determine trend direction via recent price action
                if hasattr(self, '_recent_price_direction'):
                    direction = self._recent_price_direction()
                    return MarketRegime.TRENDING_UP if direction > 0 else MarketRegime.TRENDING_DOWN
                return MarketRegime.TRENDING_UP  # Default assumption

        return MarketRegime.UNKNOWN

    def _classify_volatility_state(self, volatility_percentile: float) -> VolatilityState:
        """Classify volatility state based on historical percentile"""
        thresholds = self.volatility_thresholds

        if volatility_percentile >= thresholds['extreme']:
            return VolatilityState.EXTREME
        if volatility_percentile >= thresholds['high']:
            return VolatilityState.HIGH
        if volatility_percentile >= thresholds['normal']:
            return VolatilityState.NORMAL
        return VolatilityState.LOW

    def _calculate_confidence(self, metrics: RegimeMetrics, regime: MarketRegime) -> float:
        """Calculate confidence in regime classification"""

        # Base confidence from metric consistency
        base_confidence = 0.5

        # Boost confidence for clear trends
        if regime in [MarketRegime.TRENDING_UP, MarketRegime.TRENDING_DOWN]:
            base_confidence += 0.3 * metrics.trend_strength

        # Boost confidence for stable regimes
        base_confidence += 0.2 * metrics.regime_stability

        # Boost confidence for strong range efficiency
        if metrics.range_efficiency > 0.5:
            base_confidence += 0.1

        # Reduce confidence for high volatility uncertainty
        if metrics.volatility_percentile > 80:
            base_confidence -= 0.2

        return np.clip(base_confidence, 0.0, 1.0)

    def _linear_regression_slope(self, values: np.ndarray) -> float:
        """Calculate linear regression slope (normalized)"""
        if len(values) < 2:
            return 0.0

        x = np.arange(len(values))
        try:
            slope, _ = np.polyfit(x, values, 1)
            # Normalize by value range
            value_range = np.max(values) - np.min(values)
            if value_range > 0:
                normalized_slope = slope / value_range * len(values)
            else:
                normalized_slope = 0.0

            return np.clip(normalized_slope, -1.0, 1.0)
        except np.linalg.LinAlgError:
            return 0.0

    def _calculate_adx_strength(self, prices: np.ndarray) -> float:
        """Calculate ADX-style directional strength"""
        if len(prices) < 14:
            return 0.0

        try:
            if HAS_TALIB:
                import talib
                high = prices  # Simplified: using close as high
                low = prices   # Simplified: using close as low
                close = prices
                adx = talib.ADX(high, low, close, timeperiod=14)
                current_adx = adx[-1] if not np.isnan(adx[-1]) else 0.0
            else:
                current_adx = 0.0

            # Normalize ADX (typically 0-100) to 0-1
            return np.clip(current_adx / 100.0, 0.0, 1.0)

        except Exception:
            # Fallback calculation if TA-Lib fails
            return self._simple_directional_strength(prices)

    def _simple_directional_strength(self, prices: np.ndarray) -> float:
        """Simple directional strength calculation"""
        if len(prices) < 14:
            return 0.0

        # Calculate up and down movements
        diff = np.diff(prices[-14:])
        up_moves = np.sum(diff[diff > 0])
        down_moves = abs(np.sum(diff[diff < 0]))

        total_moves = up_moves + down_moves
        if total_moves == 0:
            return 0.0

        # Directional strength as imbalance
        directional_strength = abs(up_moves - down_moves) / total_moves
        return np.clip(directional_strength, 0.0, 1.0)

    def _calculate_ma_alignment(self, prices: np.ndarray) -> float:
        """Calculate moving average alignment strength"""
        if len(prices) < self.lookback_medium:
            return 0.0

        # Calculate multiple timeframe MAs
        ma_short = np.mean(prices[-self.lookback_short:])
        ma_medium = np.mean(prices[-self.lookback_medium:])
        current_price = prices[-1]

        # Check alignment: all MAs in same direction relative to price
        if current_price > ma_short > ma_medium:
            alignment = 1.0  # Strong uptrend alignment
        elif current_price < ma_short < ma_medium:
            alignment = 1.0  # Strong downtrend alignment
        else:
            # Partial alignment
            price_vs_short = 1 if current_price > ma_short else -1
            short_vs_medium = 1 if ma_short > ma_medium else -1
            alignment = 0.5 if price_vs_short == short_vs_medium else 0.0

        return alignment

    def _recent_price_direction(self) -> float:
        """Determine recent price direction"""
        if len(self.price_history) < 2:
            return 0.0

        recent_prices = [p[0] for p in list(self.price_history)[-5:]]
        if len(recent_prices) < 2:
            return 0.0

        return 1.0 if recent_prices[-1] > recent_prices[0] else -1.0

    def get_regime_statistics(self) -> Dict:
        """Get comprehensive regime detection statistics"""
        if not self.regime_history:
            return {}

        recent_regimes = list(self.regime_history)[-50:]  # Last 50 detections

        regime_counts = {}
        for detection in recent_regimes:
            regime = detection.regime.value
            regime_counts[regime] = regime_counts.get(regime, 0) + 1

        avg_confidence = np.mean([d.confidence for d in recent_regimes])
        avg_volatility_percentile = np.mean([d.metrics.volatility_percentile for d in recent_regimes])

        return {
            'total_detections': len(self.regime_history),
            'recent_regime_distribution': regime_counts,
            'average_confidence': avg_confidence,
            'average_volatility_percentile': avg_volatility_percentile,
            'data_points': len(self.price_history),
            'volatility_history_length': len(self.volatility_history)
        }


# Convenience functions
def create_regime_detector(config: Optional[Dict] = None) -> VolatilityRegimeDetector:
    """Create regime detector with default or custom configuration"""
    return VolatilityRegimeDetector(config)


def analyze_market_regime(prices: List[float], volumes: Optional[List[float]] = None,
                         config: Optional[Dict] = None) -> Optional[RegimeDetection]:
    """
    Analyze market regime for given price series

    Args:
        prices: List of price values
        volumes: Optional list of volume values
        config: Optional detector configuration

    Returns:
        RegimeDetection object or None if insufficient data
    """
    detector = create_regime_detector(config)

    if volumes is None:
        volumes = [0.0] * len(prices)

    # Feed data to detector
    for price, volume in zip(prices, volumes):
        detector.update_data(price, volume)

    # Return final regime detection
    return detector.detect_regime()


if __name__ == "__main__":
    # Example usage
    logging.basicConfig(level=logging.INFO)

    # Generate sample price data
    rng = np.random.default_rng(42)
    n_points = 100
    trend = np.linspace(100, 110, n_points)
    noise = rng.normal(0, 1, n_points)
    prices = trend + noise

    # Analyze regime
    detection = analyze_market_regime(prices.tolist())

    if detection:
        print(f"Detected regime: {detection.regime.value}")
        print(f"Volatility state: {detection.volatility_state.value}")
        print(f"Confidence: {detection.confidence:.3f}")
        print(f"Trend strength: {detection.metrics.trend_strength:.3f}")
        print(f"Volatility percentile: {detection.metrics.volatility_percentile:.1f}")
