"""
Test for ML Pipeline Feature Engineering

Simple integration test for the ML pipeline components
"""

import unittest
import numpy as np
import pandas as pd
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

try:
    from src.ml.simple_ml_pipeline import (
        SimpleFeatureEngineer, RuleBasedRegimeDetector, FeatureConfig,
        MarketRegime, engineer_features_for_symbol, detect_market_regime,
        get_ml_statistics
    )
    ML_AVAILABLE = True
except ImportError as e:
    print(f"ML pipeline import failed: {e}")
    ML_AVAILABLE = False

class TestMLPipeline(unittest.TestCase):
    """Test ML pipeline components"""

    def setUp(self):
        """Set up test data"""
        if not ML_AVAILABLE:
            self.skipTest("ML pipeline not available")

        # Create synthetic OHLCV data
        np.random.seed(42)
        n_periods = 100

        dates = pd.date_range('2024-01-01', periods=n_periods, freq='1H')
        base_price = 100

        # Generate realistic price data with trends
        price_changes = np.random.normal(0, 0.02, n_periods)
        trend = np.sin(np.arange(n_periods) * 0.1) * 0.01
        price_changes += trend

        prices = base_price * np.cumprod(1 + price_changes)

        self.test_data = pd.DataFrame({
            'timestamp': dates,
            'open': prices,
            'high': prices * (1 + np.abs(np.random.normal(0, 0.005, n_periods))),
            'low': prices * (1 - np.abs(np.random.normal(0, 0.005, n_periods))),
            'close': prices * (1 + np.random.normal(0, 0.001, n_periods)),
            'volume': np.random.randint(1000, 10000, n_periods)
        })

    def test_feature_engineer_initialization(self):
        """Test FeatureEngineer initialization"""
        config = FeatureConfig()
        engineer = SimpleFeatureEngineer(config)

        self.assertIsNotNone(engineer.config)
        self.assertEqual(len(engineer.config.lookback_periods), 4)
        self.assertTrue(engineer.config.include_price_features)

    def test_feature_engineering_basic(self):
        """Test basic feature engineering"""
        engineer = SimpleFeatureEngineer()
        features = engineer.engineer_features(self.test_data)

        self.assertIsInstance(features, pd.DataFrame)
        self.assertGreater(len(features.columns), len(self.test_data.columns))
        self.assertEqual(len(features), len(self.test_data))

        # Check for specific features
        feature_names = engineer.get_feature_names()
        self.assertIn('return_5', feature_names)
        self.assertIn('sma_20', feature_names)
        self.assertIn('volatility_10', feature_names)

    def test_feature_engineering_empty_data(self):
        """Test feature engineering with empty data"""
        engineer = SimpleFeatureEngineer()
        empty_df = pd.DataFrame()

        result = engineer.engineer_features(empty_df)
        self.assertTrue(result.empty)

    def test_feature_engineering_minimal_data(self):
        """Test with minimal data"""
        engineer = SimpleFeatureEngineer()
        minimal_data = self.test_data.head(3)  # Only 3 rows

        result = engineer.engineer_features(minimal_data)
        self.assertFalse(result.empty)
        self.assertEqual(len(result), 3)

    def test_regime_detector_initialization(self):
        """Test RegimeDetector initialization"""
        detector = RuleBasedRegimeDetector()
        self.assertIsNotNone(detector.logger)

    def test_regime_detection_basic(self):
        """Test basic regime detection"""
        engineer = SimpleFeatureEngineer()
        features = engineer.engineer_features(self.test_data)

        detector = RuleBasedRegimeDetector()
        regimes = detector.detect_regime(features)

        self.assertEqual(len(regimes), len(features))
        self.assertIsInstance(regimes, np.ndarray)

        # Check that we have valid regime values
        unique_regimes = np.unique(regimes)
        valid_regimes = [r.value for r in MarketRegime]
        for regime in unique_regimes:
            self.assertIn(regime, valid_regimes)

    def test_regime_probabilities(self):
        """Test regime probability calculation"""
        engineer = SimpleFeatureEngineer()
        features = engineer.engineer_features(self.test_data)

        detector = RuleBasedRegimeDetector()
        probs = detector.get_regime_probabilities(features)

        self.assertIsInstance(probs, dict)

        # Probabilities should sum to 1
        total_prob = sum(probs.values())
        self.assertAlmostEqual(total_prob, 1.0, places=5)

        # All probabilities should be >= 0
        for prob in probs.values():
            self.assertGreaterEqual(prob, 0.0)

    def test_convenience_functions(self):
        """Test convenience functions"""
        # Test engineer_features_for_symbol
        features = engineer_features_for_symbol("BTCUSDT", self.test_data)
        self.assertIsInstance(features, pd.DataFrame)
        self.assertGreater(len(features.columns), len(self.test_data.columns))

        # Test detect_market_regime
        regimes = detect_market_regime(features)
        self.assertEqual(len(regimes), len(features))

        # Test get_ml_statistics
        stats = get_ml_statistics()
        self.assertIsInstance(stats, dict)
        self.assertIn('feature_engineer_available', stats)
        self.assertIn('supported_regimes', stats)

    def test_feature_cleaning(self):
        """Test feature cleaning handles edge cases"""
        # Create data with problematic values
        problematic_data = self.test_data.copy()
        problematic_data.loc[10, 'close'] = np.inf
        problematic_data.loc[20, 'volume'] = np.nan

        engineer = SimpleFeatureEngineer()
        features = engineer.engineer_features(problematic_data)

        # Should not have any inf or nan values
        self.assertFalse(np.isinf(features.select_dtypes(include=[np.number]).values).any())
        self.assertFalse(features.select_dtypes(include=[np.number]).isnull().any().any())

    def test_different_configurations(self):
        """Test different feature configurations"""
        # Test with only price features
        config = FeatureConfig()
        config.include_volume_features = False
        config.include_volatility_features = False
        config.include_technical_features = False

        engineer = SimpleFeatureEngineer(config)
        features = engineer.engineer_features(self.test_data)

        # Should have fewer features
        feature_names = engineer.get_feature_names()
        self.assertTrue(any('return_' in name for name in feature_names))
        self.assertFalse(any('volume_' in name for name in feature_names))

    def test_regime_detection_edge_cases(self):
        """Test regime detection with edge cases"""
        detector = RuleBasedRegimeDetector()

        # Empty features
        empty_features = pd.DataFrame()
        regimes = detector.detect_regime(empty_features)
        self.assertEqual(len(regimes), 0)

        # Features without required columns
        minimal_features = pd.DataFrame({'close': [100, 101, 102]})
        regimes = detector.detect_regime(minimal_features)
        self.assertEqual(len(regimes), 3)

    def test_integration_workflow(self):
        """Test complete ML pipeline workflow"""
        # Step 1: Engineer features
        engineer = SimpleFeatureEngineer()
        features = engineer.engineer_features(self.test_data)

        # Step 2: Detect regimes
        detector = RuleBasedRegimeDetector()
        regimes = detector.detect_regime(features)

        # Step 3: Get statistics
        stats = get_ml_statistics()

        # Verify integration
        self.assertEqual(len(features), len(self.test_data))
        self.assertEqual(len(regimes), len(features))
        self.assertTrue(stats['feature_engineer_available'])
        self.assertTrue(stats['regime_detector_available'])

        # Test that we can add regimes to features
        features_with_regimes = features.copy()
        features_with_regimes['regime'] = regimes

        self.assertIn('regime', features_with_regimes.columns)
        self.assertEqual(len(features_with_regimes), len(self.test_data))

if __name__ == '__main__':
    unittest.main()
