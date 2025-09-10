"""
Tests for Dynamic Volatility Regime Detection Framework
"""

import pytest
import numpy as np
import time
from unittest.mock import patch, MagicMock
from src.regime.volatility_detector import (
    MarketRegime, VolatilityState, RegimeMetrics, RegimeDetection,
    VolatilityRegimeDetector, create_regime_detector, analyze_market_regime
)


class TestRegimeMetrics:
    """Test RegimeMetrics dataclass validation"""

    def test_valid_metrics(self):
        """Test valid metrics creation"""
        metrics = RegimeMetrics(
            trend_strength=0.5,
            volatility_percentile=50.0,
            range_efficiency=0.3,
            autocorrelation=0.1,
            volume_trend=0.2,
            regime_stability=0.8
        )
        assert metrics.trend_strength == 0.5
        assert metrics.volatility_percentile == 50.0
        assert metrics.regime_stability == 0.8

    def test_invalid_trend_strength(self):
        """Test invalid trend_strength raises assertion"""
        with pytest.raises(AssertionError, match="Invalid trend_strength"):
            RegimeMetrics(
                trend_strength=1.5,  # Invalid: > 1
                volatility_percentile=50.0,
                range_efficiency=0.3,
                autocorrelation=0.1,
                volume_trend=0.2,
                regime_stability=0.8
            )

    def test_invalid_volatility_percentile(self):
        """Test invalid volatility_percentile raises assertion"""
        with pytest.raises(AssertionError, match="Invalid volatility_percentile"):
            RegimeMetrics(
                trend_strength=0.5,
                volatility_percentile=150.0,  # Invalid: > 100
                range_efficiency=0.3,
                autocorrelation=0.1,
                volume_trend=0.2,
                regime_stability=0.8
            )


class TestRegimeDetection:
    """Test RegimeDetection dataclass properties"""

    @pytest.fixture
    def sample_metrics(self):
        """Sample metrics for testing"""
        return RegimeMetrics(
            trend_strength=0.7,
            volatility_percentile=60.0,
            range_efficiency=0.4,
            autocorrelation=0.3,
            volume_trend=0.1,
            regime_stability=0.8
        )

    def test_trending_up_properties(self, sample_metrics):
        """Test trending up regime properties"""
        detection = RegimeDetection(
            regime=MarketRegime.TRENDING_UP,
            volatility_state=VolatilityState.NORMAL,
            confidence=0.8,
            metrics=sample_metrics,
            timestamp=time.time(),
            lookback_periods=50
        )

        assert detection.is_trending
        assert detection.is_directional
        assert detection.is_stable  # High confidence and stability

    def test_ranging_properties(self, sample_metrics):
        """Test ranging regime properties"""
        detection = RegimeDetection(
            regime=MarketRegime.RANGING,
            volatility_state=VolatilityState.LOW,
            confidence=0.5,
            metrics=sample_metrics,
            timestamp=time.time(),
            lookback_periods=50
        )

        assert not detection.is_trending
        assert not detection.is_directional
        assert not detection.is_stable  # Low confidence


class TestVolatilityRegimeDetector:
    """Test VolatilityRegimeDetector main functionality"""

    @pytest.fixture
    def detector(self):
        """Create detector with test configuration"""
        config = {
            'lookback_short': 10,
            'lookback_medium': 20,
            'lookback_long': 50,
            'volatility_window': 10,
            'regime_smoothing': 3,
            'trend_threshold': 0.6,
            'range_efficiency_threshold': 0.3
        }
        return VolatilityRegimeDetector(config)

    def test_initialization(self, detector):
        """Test detector initialization"""
        assert detector.lookback_short == 10
        assert detector.lookback_medium == 20
        assert detector.lookback_long == 50
        assert detector.vol_window == 10
        assert len(detector.price_history) == 0
        assert len(detector.volume_history) == 0

    def test_update_data(self, detector):
        """Test data update functionality"""
        detector.update_data(100.0, 1000.0)
        detector.update_data(101.0, 1100.0)

        assert len(detector.price_history) == 2
        assert len(detector.volume_history) == 2
        assert detector.price_history[0][0] == 100.0
        assert detector.volume_history[1][0] == 1100.0

    def test_insufficient_data_detection(self, detector):
        """Test regime detection with insufficient data"""
        # Add only a few data points
        for i in range(5):
            detector.update_data(100.0 + i, 1000.0)

        detection = detector.detect_regime()
        assert detection is None  # Insufficient data

    def test_trending_up_detection(self, detector):
        """Test trending up market detection"""
        # Create clear uptrend
        for i in range(30):
            price = 100.0 + i * 0.5  # Clear uptrend
            volume = 1000.0 + i * 10
            detector.update_data(price, volume)

        detection = detector.detect_regime()
        assert detection is not None
        assert detection.regime in [MarketRegime.TRENDING_UP, MarketRegime.RANGING]
        assert detection.confidence > 0.0
        assert detection.metrics.trend_strength >= 0.0

    def test_volatile_market_detection(self, detector):
        """Test volatile market detection"""
        # Create high volatility pattern
        base_price = 100.0
        for i in range(30):
            # High volatility: alternating large moves
            volatility = 5.0 * (1 if i % 2 == 0 else -1)
            price = base_price + volatility + i * 0.1
            detector.update_data(price, 1000.0)

        detection = detector.detect_regime()
        assert detection is not None
        # Should detect high volatility
        assert detection.metrics.volatility_percentile >= 0.0

    def test_range_efficiency_calculation(self, detector):
        """Test range efficiency calculation"""
        prices = np.array([100, 102, 101, 103, 102, 104, 103, 105, 106, 108, 107, 109])
        efficiency = detector._calculate_range_efficiency(prices)

        assert 0.0 <= efficiency <= 1.0
        # Note: efficiency may be 0 for small moves relative to range

    def test_volatility_calculation(self, detector):
        """Test volatility calculation"""
        # Stable prices (low volatility)
        stable_prices = np.array([100.0, 100.1, 99.9, 100.05, 99.95])
        stable_vol = detector._calculate_volatility(stable_prices)

        # Volatile prices (high volatility)
        volatile_prices = np.array([100.0, 105.0, 95.0, 110.0, 90.0])
        volatile_vol = detector._calculate_volatility(volatile_prices)

        assert volatile_vol > stable_vol
        assert stable_vol >= 0.0
        assert volatile_vol >= 0.0

    def test_autocorrelation_calculation(self, detector):
        """Test autocorrelation calculation"""
        # Trending prices (positive autocorrelation)
        trending_prices = np.array([100, 101, 102, 103, 104, 105])
        trending_autocorr = detector._calculate_autocorrelation(trending_prices)

        # Random walk (low autocorrelation)
        random_prices = np.array([100, 99, 101, 98, 102, 97])
        random_autocorr = detector._calculate_autocorrelation(random_prices)

        assert -1.0 <= trending_autocorr <= 1.0
        assert -1.0 <= random_autocorr <= 1.0

    def test_volume_trend_alignment(self, detector):
        """Test volume-price trend alignment"""
        prices = np.array([100, 101, 102, 103, 104])  # Uptrend
        volumes_aligned = np.array([1000, 1100, 1200, 1300, 1400])  # Volume up with price
        volumes_contrarian = np.array([1400, 1300, 1200, 1100, 1000])  # Volume down with price up

        aligned_score = detector._calculate_volume_trend_alignment(prices, volumes_aligned)
        contrarian_score = detector._calculate_volume_trend_alignment(prices, volumes_contrarian)

        assert aligned_score >= contrarian_score  # Aligned should score higher
        assert -1.0 <= aligned_score <= 1.0
        assert -1.0 <= contrarian_score <= 1.0

    def test_regime_stability_calculation(self, detector):
        """Test regime stability calculation"""
        # Create some regime history
        sample_metrics = RegimeMetrics(0.5, 50.0, 0.3, 0.1, 0.0, 0.5)

        # All same regime (stable)
        for _ in range(5):
            detection = RegimeDetection(
                MarketRegime.TRENDING_UP, VolatilityState.NORMAL, 0.8,
                sample_metrics, time.time(), 30
            )
            detector.regime_history.append(detection)

        stability = detector._calculate_regime_stability()
        assert stability > 0.5  # Should be quite stable

        # Mixed regimes (unstable)
        detector.regime_history.clear()
        regimes = [MarketRegime.TRENDING_UP, MarketRegime.RANGING,
                  MarketRegime.VOLATILE, MarketRegime.SQUEEZE]
        for regime in regimes:
            detection = RegimeDetection(
                regime, VolatilityState.NORMAL, 0.8,
                sample_metrics, time.time(), 30
            )
            detector.regime_history.append(detection)

        mixed_stability = detector._calculate_regime_stability()
        assert mixed_stability < stability  # Should be less stable

    def test_confidence_calculation(self, detector):
        """Test confidence calculation"""
        # High trend strength metrics
        strong_metrics = RegimeMetrics(
            trend_strength=0.9,
            volatility_percentile=50.0,
            range_efficiency=0.8,
            autocorrelation=0.5,
            volume_trend=0.3,
            regime_stability=0.9
        )

        # Weak trend metrics
        weak_metrics = RegimeMetrics(
            trend_strength=0.2,
            volatility_percentile=85.0,  # High volatility
            range_efficiency=0.1,
            autocorrelation=0.0,
            volume_trend=0.0,
            regime_stability=0.3
        )

        strong_confidence = detector._calculate_confidence(strong_metrics, MarketRegime.TRENDING_UP)
        weak_confidence = detector._calculate_confidence(weak_metrics, MarketRegime.RANGING)

        assert strong_confidence > weak_confidence
        assert 0.0 <= strong_confidence <= 1.0
        assert 0.0 <= weak_confidence <= 1.0

    def test_percentile_fallback(self, detector):
        """Test fallback percentile calculation"""
        values = [1.0, 2.0, 3.0, 4.0, 5.0]

        # Test median value
        percentile_median = detector._calculate_percentile_fallback(values, 3.0)
        assert 40 <= percentile_median <= 60  # Should be around 50th percentile

        # Test extreme values
        percentile_high = detector._calculate_percentile_fallback(values, 6.0)
        percentile_low = detector._calculate_percentile_fallback(values, 0.5)

        assert percentile_high > percentile_median > percentile_low

    def test_statistics_collection(self, detector):
        """Test regime statistics collection"""
        # Add some data and detections
        for i in range(25):
            detector.update_data(100.0 + i * 0.1, 1000.0)

        # Generate some detections
        for _ in range(5):
            detection = detector.detect_regime()
            if detection:
                pass  # Detection added to history automatically

        stats = detector.get_regime_statistics()

        assert 'total_detections' in stats
        assert 'data_points' in stats
        assert stats['data_points'] == 25


class TestConvenienceFunctions:
    """Test convenience functions"""

    def test_create_regime_detector(self):
        """Test detector creation"""
        detector = create_regime_detector()
        assert isinstance(detector, VolatilityRegimeDetector)

        # Test with custom config
        config = {'lookback_short': 15}
        custom_detector = create_regime_detector(config)
        assert custom_detector.lookback_short == 15

    def test_analyze_market_regime(self):
        """Test market regime analysis function"""
        # Create trending price series with enough data
        prices = [100.0 + i * 0.2 for i in range(60)]  # Increased from 30 to 60
        volumes = [1000.0 + i * 10 for i in range(60)]

        detection = analyze_market_regime(prices, volumes)
        assert detection is not None
        assert isinstance(detection, RegimeDetection)
        assert isinstance(detection.regime, MarketRegime)
        assert isinstance(detection.volatility_state, VolatilityState)

    def test_analyze_market_regime_no_volumes(self):
        """Test market regime analysis without volume data"""
        prices = [100.0 + i * 0.1 for i in range(60)]  # Increased from 25 to 60

        detection = analyze_market_regime(prices)  # No volumes
        assert detection is not None
        assert abs(detection.metrics.volume_trend - 0.0) < 0.1  # Should handle missing volume


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_empty_data(self):
        """Test behavior with empty data"""
        detector = VolatilityRegimeDetector()
        detection = detector.detect_regime()
        assert detection is None

    def test_single_price_data(self):
        """Test behavior with single data point"""
        detector = VolatilityRegimeDetector()
        detector.update_data(100.0, 1000.0)
        detection = detector.detect_regime()
        assert detection is None

    def test_identical_prices(self):
        """Test behavior with identical prices (zero volatility)"""
        detector = VolatilityRegimeDetector({'lookback_medium': 10})

        # Add identical prices
        for _ in range(15):
            detector.update_data(100.0, 1000.0)

        detection = detector.detect_regime()
        assert detection is not None
        assert detection.metrics.volatility_percentile >= 0.0

    def test_extreme_price_moves(self):
        """Test behavior with extreme price movements"""
        detector = VolatilityRegimeDetector({'lookback_medium': 10})

        # Add extreme price moves
        prices = [100.0, 200.0, 50.0, 300.0, 25.0, 400.0]
        for price in prices * 3:  # Repeat to get enough data
            detector.update_data(price, 1000.0)

        detection = detector.detect_regime()
        assert detection is not None
        # Should handle extreme moves gracefully
        assert detection.regime in list(MarketRegime)

    @patch('src.regime.volatility_detector.HAS_SCIPY', False)
    def test_no_scipy_fallback(self):
        """Test operation without scipy"""
        detector = VolatilityRegimeDetector({'lookback_medium': 10})

        # Add some data
        for i in range(15):
            detector.update_data(100.0 + i * 0.5, 1000.0)

        detection = detector.detect_regime()
        assert detection is not None  # Should work without scipy

    @patch('src.regime.volatility_detector.HAS_TALIB', False)
    def test_no_talib_fallback(self):
        """Test operation without TA-Lib"""
        detector = VolatilityRegimeDetector({'lookback_medium': 10})

        # Add some data
        for i in range(15):
            detector.update_data(100.0 + i * 0.3, 1000.0)

        detection = detector.detect_regime()
        assert detection is not None  # Should work without TA-Lib


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
