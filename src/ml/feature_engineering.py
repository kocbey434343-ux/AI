"""
Machine Learning Pipeline - Feature Engineering ve Model Training Framework

Bu modül şu özellikleri sağlar:
- Technical indicator feature engineering
- Market regime detection and classification
- Model training pipeline (supervised & unsupervised)
- Feature selection and dimensionality reduction
- Real-time prediction interface
- Performance monitoring and model drift detection

Modular Design:
- FeatureEngineer: Technical/fundamental feature computation
- RegimeDetector: Market state classification (trend/range/squeeze)
- ModelTrainer: ML model training and validation framework
- Predictor: Real-time inference engine
- ModelMonitor: Performance tracking and drift detection
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List

import numpy as np
import pandas as pd

# ML dependencies with fallback
try:
    from sklearn.cluster import KMeans
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.preprocessing import RobustScaler, StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    print("scikit-learn not available - ML features disabled")
    RandomForestClassifier = None
    StandardScaler = None
    RobustScaler = None
    KMeans = None
    SKLEARN_AVAILABLE = False

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
    LOW_VOLATILITY = "low_vol"
    SQUEEZE = "squeeze"
    BREAKOUT = "breakout"
    UNKNOWN = "unknown"

@dataclass
class FeatureConfig:
    """Configuration for feature engineering"""
    lookback_periods: List[int] = None
    technical_indicators: List[str] = None
    price_features: bool = True
    volume_features: bool = True
    volatility_features: bool = True
    momentum_features: bool = True
    trend_features: bool = True
    microstructure_features: bool = False

    def __post_init__(self):
        if self.lookback_periods is None:
            self.lookback_periods = [5, 10, 20, 50, 100, 200]
        if self.technical_indicators is None:
            self.technical_indicators = ['rsi', 'macd', 'bb_width', 'adx', 'atr']

@dataclass
class ModelConfig:
    """Configuration for ML models"""
    model_type: str = "random_forest"
    n_estimators: int = 100
    max_depth: int = 10
    random_state: int = 42
    test_size: float = 0.2
    cv_folds: int = 5
    feature_selection: bool = True
    max_features: int = 50

class FeatureEngineer:
    """
    Feature engineering pipeline for ML models
    Generates technical, fundamental, and microstructure features
    """

    def __init__(self, config=None):
        self.config = config or FeatureConfig()
        self.logger = logging.getLogger(__name__)
        self.scaler = StandardScaler() if SKLEARN_AVAILABLE else None
        self.features_computed = False

    def compute_price_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute price-based features"""
        features = df.copy()

        # Price returns at multiple timeframes
        for period in self.config.lookback_periods:
            if period < len(df):
                features[f'return_{period}'] = df['close'].pct_change(period)
                features[f'log_return_{period}'] = np.log(df['close'] / df['close'].shift(period))

        # Price position relative to highs/lows
        for period in [20, 50, 100]:
            if period < len(df):
                features[f'high_pct_{period}'] = (df['close'] - df['high'].rolling(period).min()) / (
                    df['high'].rolling(period).max() - df['high'].rolling(period).min())
                features[f'low_pct_{period}'] = (df['close'] - df['low'].rolling(period).min()) / (
                    df['high'].rolling(period).max() - df['low'].rolling(period).min())

        return features

    def compute_volume_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute volume-based features"""
        features = df.copy()

        # Volume statistics
        for period in [10, 20, 50]:
            if period < len(df):
                features[f'volume_ma_{period}'] = df['volume'].rolling(period).mean()
                features[f'volume_std_{period}'] = df['volume'].rolling(period).std()
                features[f'volume_ratio_{period}'] = df['volume'] / features[f'volume_ma_{period}']

        # Volume price analysis
        features['vwap_20'] = (df['volume'] * df['close']).rolling(20).sum() / df['volume'].rolling(20).sum()
        features['price_volume_trend'] = ((df['close'] - df['close'].shift(1)) / df['close'].shift(1)) * df['volume']

        return features

    def compute_volatility_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute volatility-based features"""
        features = df.copy()

        # Realized volatility at multiple timeframes
        for period in [10, 20, 50]:
            if period < len(df):
                returns = df['close'].pct_change()
                features[f'realized_vol_{period}'] = returns.rolling(period).std() * np.sqrt(252)

                # Parkinson volatility (high-low estimator)
                features[f'parkinson_vol_{period}'] = np.sqrt(
                    (np.log(df['high'] / df['low']) ** 2).rolling(period).mean() / (4 * np.log(2))
                ) * np.sqrt(252)

        # Volatility regime
        vol_20 = features['realized_vol_20']
        vol_percentile = vol_20.rolling(200).rank(pct=True)
        features['vol_regime'] = np.where(vol_percentile > 0.8, 2,  # High vol
                                 np.where(vol_percentile < 0.2, 0, 1))  # Low/Med vol

        return features

    def compute_momentum_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute momentum-based features"""
        features = df.copy()

        # Multiple timeframe momentum
        for period in [5, 10, 20, 50]:
            if period < len(df):
                features[f'momentum_{period}'] = df['close'] / df['close'].shift(period) - 1

        # Momentum acceleration
        features['momentum_acceleration'] = features['momentum_10'] - features['momentum_20']

        # Relative strength vs market (if market data available)
        # This would need market index data

        return features

    def compute_trend_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute trend-based features"""
        features = df.copy()

        # Moving average ratios
        for fast, slow in [(10, 20), (20, 50), (50, 100)]:
            if slow < len(df):
                ma_fast = df['close'].rolling(fast).mean()
                ma_slow = df['close'].rolling(slow).mean()
                features[f'ma_ratio_{fast}_{slow}'] = ma_fast / ma_slow - 1

        # Trend strength
        for period in [20, 50]:
            if period < len(df):
                ma = df['close'].rolling(period).mean()
                features[f'trend_strength_{period}'] = (df['close'] - ma) / ma

        return features

    def compute_technical_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute technical indicator features"""
        features = df.copy()

        if not IndicatorCalculator:
            return features

        try:
            calc = IndicatorCalculator()

            # RSI at multiple timeframes
            for period in [14, 21, 50]:
                if period < len(df):
                    # RSI hesaplama - sadece close price gerekiyor
                    close_values = df['close'].values
                    if len(close_values) >= period:
                        features[f'rsi_{period}'] = calc.calculate_rsi(pd.DataFrame({'close': close_values}), period)

            # MACD features - DataFrame gerekiyor
            macd_df = pd.DataFrame({'close': df['close']})
            macd_result = calc.calculate_macd(macd_df)
            if isinstance(macd_result, tuple) and len(macd_result) >= 3:
                features['macd_line'] = macd_result[0]
                features['macd_signal'] = macd_result[1]
                features['macd_histogram'] = macd_result[2]
                macd_line = macd_result[0]
                macd_signal = macd_result[1]
                if hasattr(macd_line, '__iter__') and hasattr(macd_signal, '__iter__'):
                    features['macd_crossover'] = np.where(
                        pd.Series(macd_line) > pd.Series(macd_signal), 1, 0)

            # Bollinger Bands - DataFrame gerekiyor
            bb_df = pd.DataFrame({'close': df['close']})
            bb_result = calc.calculate_bollinger_bands(bb_df)
            if isinstance(bb_result, tuple) and len(bb_result) >= 3:
                bb_upper, bb_middle, bb_lower = bb_result[0], bb_result[1], bb_result[2]
                if all(hasattr(x, '__iter__') for x in [bb_upper, bb_middle, bb_lower]):
                    bb_upper_s = pd.Series(bb_upper)
                    bb_middle_s = pd.Series(bb_middle)
                    bb_lower_s = pd.Series(bb_lower)
                    features['bb_width'] = (bb_upper_s - bb_lower_s) / bb_middle_s
                    features['bb_position'] = (df['close'] - bb_lower_s) / (bb_upper_s - bb_lower_s)

            # ADX - high, low, close gerekiyor
            adx_result = calc.calculate_adx(df['high'], df['low'], df['close'])
            if hasattr(adx_result, '__iter__'):
                features['adx'] = adx_result

        except Exception as e:
            self.logger.warning(f"Error computing technical features: {e}")

        return features

    def engineer_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Main feature engineering pipeline

        Args:
            df: OHLCV DataFrame

        Returns:
            DataFrame with engineered features
        """
        if df.empty or len(df) < max(self.config.lookback_periods):
            return pd.DataFrame()

        features = df.copy()

        # Add each feature group
        if self.config.price_features:
            features = self.compute_price_features(features)

        if self.config.volume_features:
            features = self.compute_volume_features(features)

        if self.config.volatility_features:
            features = self.compute_volatility_features(features)

        if self.config.momentum_features:
            features = self.compute_momentum_features(features)

        if self.config.trend_features:
            features = self.compute_trend_features(features)

        # Technical indicators
        features = self.compute_technical_features(features)

        # Clean features
        features = self._clean_features(features)

        self.features_computed = True
        return features

    def _clean_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean and prepare features for ML"""
        # Forward fill missing values
        df = df.fillna(method='ffill')

        # Replace remaining NaN with 0
        df = df.fillna(0)

        # Remove infinite values
        df = df.replace([np.inf, -np.inf], 0)

        return df

    def get_feature_importance(self, model, feature_names: List[str]) -> Dict[str, float]:
        """Get feature importance from trained model"""
        if not hasattr(model, 'feature_importances_'):
            return {}

        importance_dict = dict(zip(feature_names, model.feature_importances_))
        return dict(sorted(importance_dict.items(), key=lambda x: x[1], reverse=True))

class RegimeDetector:
    """
    Market regime detection using unsupervised and supervised methods
    """

    def __init__(self, n_regimes: int = 4):
        self.n_regimes = n_regimes
        self.kmeans = KMeans(n_clusters=n_regimes, random_state=42) if SKLEARN_AVAILABLE else None
        self.scaler = RobustScaler() if SKLEARN_AVAILABLE else None
        self.is_fitted = False
        self.logger = logging.getLogger(__name__)

    def detect_regime_unsupervised(self, features: pd.DataFrame) -> np.ndarray:
        """Detect market regimes using K-means clustering"""
        if not SKLEARN_AVAILABLE or features.empty:
            return np.zeros(len(features))

        # Select regime-relevant features
        regime_features = self._select_regime_features(features)

        if regime_features.empty:
            return np.zeros(len(features))

        # Scale features
        scaled_features = self.scaler.fit_transform(regime_features)

        # Fit K-means
        regimes = self.kmeans.fit_predict(scaled_features)
        self.is_fitted = True

        return regimes

    def detect_regime_rule_based(self, features: pd.DataFrame) -> np.ndarray:
        """Rule-based regime detection"""
        regimes = np.full(len(features), MarketRegime.UNKNOWN.value)

        if 'adx' not in features.columns or 'bb_width' not in features.columns:
            return regimes

        adx = features['adx']
        bb_width = features['bb_width']

        # Define regime conditions
        trending_up = (adx > 25) & (features.get('ma_ratio_20_50', 0) > 0.02)
        trending_down = (adx > 25) & (features.get('ma_ratio_20_50', 0) < -0.02)
        ranging = (adx < 20) & (bb_width < bb_width.rolling(50).quantile(0.3))
        high_vol = features.get('vol_regime', 0) == 2
        squeeze = bb_width < bb_width.rolling(100).quantile(0.2)

        # Assign regimes
        regimes = np.where(trending_up, MarketRegime.TRENDING_UP.value,
                  np.where(trending_down, MarketRegime.TRENDING_DOWN.value,
                  np.where(ranging, MarketRegime.RANGING.value,
                  np.where(high_vol, MarketRegime.HIGH_VOLATILITY.value,
                  np.where(squeeze, MarketRegime.SQUEEZE.value,
                           MarketRegime.UNKNOWN.value)))))

        return regimes

    def _select_regime_features(self, features: pd.DataFrame) -> pd.DataFrame:
        """Select features relevant for regime detection"""
        regime_cols = []

        # Volatility features
        vol_cols = [col for col in features.columns if 'vol' in col or 'atr' in col]
        regime_cols.extend(vol_cols)

        # Trend features
        trend_cols = [col for col in features.columns if 'ma_ratio' in col or 'trend' in col]
        regime_cols.extend(trend_cols)

        # Technical indicators
        tech_cols = ['adx', 'bb_width', 'rsi_14']
        regime_cols.extend([col for col in tech_cols if col in features.columns])

        # Momentum features
        mom_cols = [col for col in features.columns if 'momentum' in col][:3]  # Limit
        regime_cols.extend(mom_cols)

        return features[regime_cols].dropna()

# Global convenience functions
_feature_engineer = None
_regime_detector = None

def get_feature_engineer() -> FeatureEngineer:
    """Get singleton FeatureEngineer instance"""
    global _feature_engineer
    if _feature_engineer is None:
        _feature_engineer = FeatureEngineer()
    return _feature_engineer

def get_regime_detector() -> RegimeDetector:
    """Get singleton RegimeDetector instance"""
    global _regime_detector
    if _regime_detector is None:
        _regime_detector = RegimeDetector()
    return _regime_detector

def engineer_features_for_symbol(symbol: str, df: pd.DataFrame) -> pd.DataFrame:
    """Convenience function to engineer features for a symbol"""
    engineer = get_feature_engineer()
    return engineer.engineer_features(df)

def detect_market_regime(features: pd.DataFrame, method: str = "rule_based") -> np.ndarray:
    """Convenience function to detect market regime"""
    detector = get_regime_detector()

    if method == "rule_based":
        return detector.detect_regime_rule_based(features)
    if method == "unsupervised":
        return detector.detect_regime_unsupervised(features)
    raise ValueError(f"Unknown method: {method}")

# Statistics and monitoring
def get_ml_statistics() -> Dict[str, Any]:
    """Get ML pipeline statistics"""
    stats = {
        'sklearn_available': SKLEARN_AVAILABLE,
        'feature_engineer_ready': _feature_engineer is not None and _feature_engineer.features_computed,
        'regime_detector_fitted': _regime_detector is not None and _regime_detector.is_fitted,
        'supported_regimes': [regime.value for regime in MarketRegime],
        'feature_groups': ['price', 'volume', 'volatility', 'momentum', 'trend', 'technical']
    }

    return stats

if __name__ == "__main__":
    # Simple demonstration
    print("ML Pipeline initialized")
    print(f"scikit-learn available: {SKLEARN_AVAILABLE}")
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
    engineer = FeatureEngineer()
    features = engineer.engineer_features(sample_data)
    print(f"Generated {len(features.columns)} features from sample data")

    # Test regime detection
    regimes = detect_market_regime(features, method="rule_based")
    unique_regimes = np.unique(regimes)
    print(f"Detected regimes: {unique_regimes}")
