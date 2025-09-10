"""
Machine Learning Pipeline - Simplified Feature Engineering Framework

Bu modül şu özellikleri sağlar:
- Technical feature engineering (basit)
- Market regime detection (rule-based)
- Real-time feature computation
- Performance monitoring

Modular Design:
- SimpleFeatureEngineer: Temel feature engineering
- RuleBasedRegimeDetector: Kural tabanlı market regime tespiti
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List

import numpy as np
import pandas as pd

# Config and dependencies
try:
    from config.settings import Settings

    from src.data_fetcher import DataFetcher
    from src.indicators import IndicatorCalculator
    from src.utils.structured_log import slog
except ImportError as e:
    print(f"Import warning: {e}")
    # Fallback for testing
    Settings = None
    IndicatorCalculator = None
    DataFetcher = None
    slog = None

class MarketRegime(Enum):
    """Market regime classification"""
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    HIGH_VOLATILITY = "high_vol"
    SQUEEZE = "squeeze"
    UNKNOWN = "unknown"

@dataclass
class FeatureConfig:
    """Configuration for feature engineering"""
    lookback_periods: List[int] = None
    include_price_features: bool = True
    include_volume_features: bool = True
    include_volatility_features: bool = True
    include_technical_features: bool = True

    def __post_init__(self):
        if self.lookback_periods is None:
            self.lookback_periods = [5, 10, 20, 50]

class SimpleFeatureEngineer:
    """
    Simplified feature engineering pipeline for ML models
    Focus on basic, proven features
    """

    def __init__(self, config=None):
        self.config = config or FeatureConfig()
        self.logger = logging.getLogger(__name__)

    def compute_price_returns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute basic price return features"""
        features = df.copy()

        # Simple returns at multiple timeframes
        for period in self.config.lookback_periods:
            if period < len(df):
                features[f'return_{period}'] = df['close'].pct_change(period).fillna(0)
                features[f'log_return_{period}'] = np.log(df['close'] / df['close'].shift(period)).fillna(0)

        # Price percentiles
        for period in [20, 50]:
            if period < len(df):
                rolling_min = df['low'].rolling(period, min_periods=1).min()
                rolling_max = df['high'].rolling(period, min_periods=1).max()
                features[f'price_percentile_{period}'] = (
                    (df['close'] - rolling_min) / (rolling_max - rolling_min + 1e-8)
                ).fillna(0.5)

        return features

    def compute_volume_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute volume-based features"""
        features = df.copy()

        # Volume moving averages and ratios
        for period in [10, 20]:
            if period < len(df):
                vol_ma = df['volume'].rolling(period, min_periods=1).mean()
                features[f'volume_ma_{period}'] = vol_ma
                features[f'volume_ratio_{period}'] = (df['volume'] / (vol_ma + 1e-8)).fillna(1.0)

        # Volume trend
        if len(df) >= 5:
            features['volume_trend'] = df['volume'].rolling(5, min_periods=1).mean().pct_change().fillna(0)

        return features

    def compute_volatility_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute volatility features"""
        features = df.copy()

        # Simple volatility measures
        for period in [10, 20]:
            if period <= len(df):  # Changed from < to <=
                returns = df['close'].pct_change().fillna(0)
                features[f'volatility_{period}'] = returns.rolling(period, min_periods=1).std().fillna(0)

                # High-low volatility
                features[f'hl_volatility_{period}'] = (
                    (df['high'] - df['low']) / df['close']
                ).rolling(period, min_periods=1).mean().fillna(0)

        return features

    def compute_basic_technicals(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute basic technical indicators"""
        features = df.copy()

        # Simple moving averages
        for period in [10, 20, 50]:
            if period <= len(df):  # Changed from < to <=
                features[f'sma_{period}'] = df['close'].rolling(period, min_periods=1).mean()
                features[f'price_to_sma_{period}'] = (
                    df['close'] / features[f'sma_{period}'] - 1
                ).fillna(0)

        # Moving average crossovers
        if len(df) >= 20:
            sma_10 = df['close'].rolling(10, min_periods=1).mean()
            sma_20 = df['close'].rolling(20, min_periods=1).mean()
            features['ma_crossover_10_20'] = np.where(sma_10 > sma_20, 1, 0)

        # Basic RSI approximation
        if len(df) >= 14:
            delta = df['close'].diff()
            gain = delta.where(delta > 0, 0).rolling(14, min_periods=1).mean()
            loss = (-delta).where(delta < 0, 0).rolling(14, min_periods=1).mean()
            rs = gain / (loss + 1e-8)
            features['rsi_approx'] = (100 - (100 / (1 + rs))).fillna(50)

        return features

    def engineer_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Main feature engineering pipeline

        Args:
            df: OHLCV DataFrame

        Returns:
            DataFrame with engineered features
        """
        if df.empty:
            return pd.DataFrame()

        if len(df) < 3:  # Need at least 3 rows for basic features
            return df.copy()  # Return original data for very small datasets

        features = df.copy()

        try:
            # Add each feature group
            if self.config.include_price_features:
                features = self.compute_price_returns(features)

            if self.config.include_volume_features and 'volume' in df.columns:
                features = self.compute_volume_features(features)

            if self.config.include_volatility_features:
                features = self.compute_volatility_features(features)

            if self.config.include_technical_features:
                features = self.compute_basic_technicals(features)

            # Clean features
            features = self._clean_features(features)

        except Exception as e:
            self.logger.warning(f"Error in feature engineering: {e}")
            return df  # Return original data if feature engineering fails

        return features

    def _clean_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean and prepare features"""
        # Replace inf values
        df = df.replace([np.inf, -np.inf], 0)

        # Fill remaining NaN
        df = df.fillna(0)

        return df

    def get_feature_names(self) -> List[str]:
        """Get list of generated feature names"""
        feature_names = []

        if self.config.include_price_features:
            for period in self.config.lookback_periods:
                feature_names.extend([f'return_{period}', f'log_return_{period}'])
            for period in [20, 50]:
                feature_names.append(f'price_percentile_{period}')

        if self.config.include_volume_features:
            for period in [10, 20]:
                feature_names.extend([f'volume_ma_{period}', f'volume_ratio_{period}'])
            feature_names.append('volume_trend')

        if self.config.include_volatility_features:
            for period in [10, 20]:
                feature_names.extend([f'volatility_{period}', f'hl_volatility_{period}'])

        if self.config.include_technical_features:
            for period in [10, 20, 50]:
                feature_names.extend([f'sma_{period}', f'price_to_sma_{period}'])
            feature_names.extend(['ma_crossover_10_20', 'rsi_approx'])

        return feature_names

class RuleBasedRegimeDetector:
    """
    Rule-based market regime detection
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def detect_regime(self, features: pd.DataFrame) -> np.ndarray:
        """Detect market regime using rule-based approach"""
        if features.empty:
            return np.array([])

        regimes = np.full(len(features), MarketRegime.UNKNOWN.value)

        try:
            # Trend detection using moving averages
            has_sma_10 = 'sma_10' in features.columns
            has_sma_20 = 'sma_20' in features.columns
            has_volatility = 'volatility_20' in features.columns
            has_rsi = 'rsi_approx' in features.columns

            if has_sma_10 and has_sma_20:
                # Trend conditions
                uptrend = (features['sma_10'] > features['sma_20']) & (
                    features['close'] > features['sma_20']
                )
                downtrend = (features['sma_10'] < features['sma_20']) & (
                    features['close'] < features['sma_20']
                )

                # Volatility conditions
                if has_volatility:
                    vol_threshold = features['volatility_20'].rolling(50, min_periods=10).quantile(0.7)
                    high_vol = features['volatility_20'] > vol_threshold

                    # Squeeze detection (low volatility)
                    vol_low_threshold = features['volatility_20'].rolling(50, min_periods=10).quantile(0.3)
                    squeeze = features['volatility_20'] < vol_low_threshold

                    # Assign regimes
                    regimes = np.where(
                        squeeze, MarketRegime.SQUEEZE.value,
                        np.where(
                            high_vol, MarketRegime.HIGH_VOLATILITY.value,
                            np.where(
                                uptrend, MarketRegime.TRENDING_UP.value,
                                np.where(
                                    downtrend, MarketRegime.TRENDING_DOWN.value,
                                    MarketRegime.RANGING.value
                                )
                            )
                        )
                    )
                else:
                    # Simplified without volatility
                    regimes = np.where(
                        uptrend, MarketRegime.TRENDING_UP.value,
                        np.where(
                            downtrend, MarketRegime.TRENDING_DOWN.value,
                            MarketRegime.RANGING.value
                        )
                    )

        except Exception as e:
            self.logger.warning(f"Error in regime detection: {e}")

        return regimes

    def get_regime_probabilities(self, features: pd.DataFrame) -> Dict[str, float]:
        """Get probability distribution of regimes over the data"""
        regimes = self.detect_regime(features)

        if len(regimes) == 0:
            return {}

        unique, counts = np.unique(regimes, return_counts=True)
        total = len(regimes)

        return {regime: count / total for regime, count in zip(unique, counts)}

# Global instances
_feature_engineer = None
_regime_detector = None

def get_feature_engineer() -> SimpleFeatureEngineer:
    """Get singleton SimpleFeatureEngineer instance"""
    global _feature_engineer
    if _feature_engineer is None:
        _feature_engineer = SimpleFeatureEngineer()
    return _feature_engineer

def get_regime_detector() -> RuleBasedRegimeDetector:
    """Get singleton RuleBasedRegimeDetector instance"""
    global _regime_detector
    if _regime_detector is None:
        _regime_detector = RuleBasedRegimeDetector()
    return _regime_detector

def engineer_features_for_symbol(symbol: str, df: pd.DataFrame) -> pd.DataFrame:
    """Convenience function to engineer features for a symbol"""
    engineer = get_feature_engineer()
    return engineer.engineer_features(df)

def detect_market_regime(features: pd.DataFrame) -> np.ndarray:
    """Convenience function to detect market regime"""
    detector = get_regime_detector()
    return detector.detect_regime(features)

def get_ml_statistics() -> Dict[str, Any]:
    """Get ML pipeline statistics"""
    stats = {
        'feature_engineer_available': _feature_engineer is not None,
        'regime_detector_available': _regime_detector is not None,
        'supported_regimes': [regime.value for regime in MarketRegime],
        'feature_types': ['price_returns', 'volume', 'volatility', 'technical'],
        'implementation': 'simplified_rule_based'
    }

    if _feature_engineer:
        stats['feature_names'] = _feature_engineer.get_feature_names()

    return stats

if __name__ == "__main__":
    # Simple demonstration
    print("Simplified ML Pipeline initialized")
    print(f"Supported regimes: {[r.value for r in MarketRegime]}")

    # Create sample data for testing
    rng = np.random.default_rng(42)
    dates = pd.date_range('2024-01-01', periods=100, freq='1H')
    sample_data = pd.DataFrame({
        'timestamp': dates,
        'open': 100 + np.cumsum(rng.normal(0, 0.01, 100)),
        'high': 0,
        'low': 0,
        'close': 0,
        'volume': rng.integers(1000, 10000, 100)
    })
    sample_data['high'] = sample_data['open'] + rng.random(100) * 0.5
    sample_data['low'] = sample_data['open'] - rng.random(100) * 0.5
    sample_data['close'] = sample_data['open'] + rng.normal(0, 0.1, 100)

    # Test feature engineering
    engineer = SimpleFeatureEngineer()
    features = engineer.engineer_features(sample_data)
    print(f"Generated {len(features.columns)} features from sample data")

    # Test regime detection
    detector = RuleBasedRegimeDetector()
    regimes = detector.detect_regime(features)
    unique_regimes = np.unique(regimes)
    print(f"Detected regimes: {unique_regimes}")

    # Get regime probabilities
    regime_probs = detector.get_regime_probabilities(features)
    print(f"Regime distribution: {regime_probs}")

    # Get statistics
    stats = get_ml_statistics()
    print(f"ML Pipeline stats: {stats}")
