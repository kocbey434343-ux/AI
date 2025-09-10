"""
Correlation Matrix Calculator for Multi-Asset Portfolio Analysis

Bu modul, portfolio icindeki varliklar arasindaki korelasyonlari hesaplar,
rolling pencere kullanarak dinamik korelasyon analizi yapar.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class CorrelationResult:
    """Korelasyon hesaplama sonucu"""
    correlation_matrix: pd.DataFrame
    eigenvalues: np.ndarray
    eigenvectors: np.ndarray
    max_eigenvalue: float
    condition_number: float
    calculation_timestamp: datetime


class CorrelationMatrix:
    """
    Multi-asset portfolio korelasyon analizi

    Ozellikler:
    - Rolling correlation calculation
    - Eigenvalue decomposition
    - Risk concentration detection
    - Dynamic correlation monitoring
    """

    def __init__(self, window_days: int = 30, min_periods: int = 20):
        """
        Args:
            window_days: Rolling korelasyon pencere suresi (gun)
            min_periods: Minimum gerekli veri noktasi sayisi
        """
        self.window_days = window_days
        self.min_periods = min_periods
        self.price_data: Dict[str, pd.Series] = {}
        self.return_data: Dict[str, pd.Series] = {}
        self.correlation_history: List[CorrelationResult] = []

    def add_price_data(self, symbol: str, prices: pd.Series):
        """
        Varlik fiyat serisi ekle

        Args:
            symbol: Varlik sembolu (BTCUSDT, ETHUSDT, vb.)
            prices: Timestamp indeksli fiyat serisi
        """
        self.price_data[symbol] = prices.copy()

        # Returns hesapla (log returns) - pandas Series kullan
        if isinstance(prices, pd.Series):
            log_returns = np.log(prices / prices.shift(1))
        else:
            price_series = pd.Series(prices)
            log_returns = np.log(price_series / price_series.shift(1))
        self.return_data[symbol] = log_returns.dropna()

        logger.info(f"Price data added for {symbol}: {len(prices)} points")

    def calculate_correlation(self, method: str = 'pearson') -> Optional[CorrelationResult]:
        """
        Portfolio korelasyon matrisi hesapla

        Args:
            method: Korelasyon yontemi ('pearson', 'spearman', 'kendall')

        Returns:
            CorrelationResult veya None (yetersiz veri)
        """
        if len(self.return_data) < 2:
            logger.warning("En az 2 varlik gerekli")
            return None

        # Return serilerini DataFrame'e donustur
        returns_df = pd.DataFrame(self.return_data)

        # Rolling window uygula
        end_date = returns_df.index.max()
        start_date = end_date - timedelta(days=self.window_days)

        window_data = returns_df[returns_df.index >= start_date]

        if len(window_data) < self.min_periods:
            logger.warning(f"Yetersiz veri: {len(window_data)} < {self.min_periods}")
            return None

        # Korelasyon matrisi hesapla
        corr_matrix = window_data.corr(method=method)

        # Eigenvalue decomposition
        eigenvalues, eigenvectors = np.linalg.eigh(corr_matrix.values)
        eigenvalues = np.sort(eigenvalues)[::-1]  # Buyukten kucuge sirala

        result = CorrelationResult(
            correlation_matrix=corr_matrix,
            eigenvalues=eigenvalues,
            eigenvectors=eigenvectors,
            max_eigenvalue=eigenvalues[0],
            condition_number=eigenvalues[0] / eigenvalues[-1],
            calculation_timestamp=datetime.now()
        )

        self.correlation_history.append(result)

        # History'yi sinirla (son 100 hesaplama)
        if len(self.correlation_history) > 100:
            self.correlation_history = self.correlation_history[-100:]

        logger.info(f"Correlation calculated: max eigenvalue {result.max_eigenvalue:.3f}")

        return result

    def get_risk_concentration(self, result: CorrelationResult) -> Dict[str, float]:
        """
        Risk konsantrasyonu analizi

        Returns:
            Dict: symbol -> risk contribution mapping
        """
        # Ilk principal component kullan
        pc1_weights = np.abs(result.eigenvectors[:, 0])
        symbols = result.correlation_matrix.columns

        risk_contribution = dict(zip(symbols, pc1_weights))

        return risk_contribution

    def detect_regime_change(self, threshold: float = 0.7) -> bool:
        """
        Korelasyon rejim degisikligi tespiti

        Args:
            threshold: Degisiklik esigi

        Returns:
            True: Rejim degisikligi var
        """
        if len(self.correlation_history) < 2:
            return False

        current = self.correlation_history[-1]
        previous = self.correlation_history[-2]

        # Ortalama korelasyon degisimi
        current_mean = current.correlation_matrix.values[np.triu_indices_from(
            current.correlation_matrix.values, k=1)].mean()
        previous_mean = previous.correlation_matrix.values[np.triu_indices_from(
            previous.correlation_matrix.values, k=1)].mean()

        change = abs(current_mean - previous_mean)

        return change > threshold

    def get_diversification_ratio(self, weights: Optional[Dict[str, float]] = None) -> float:
        """
        Diversification ratio hesapla

        Args:
            weights: Portfolio agirliklari (None = equal weight)

        Returns:
            Diversification ratio (>1 means diversification benefit)
        """
        if not self.correlation_history:
            return 1.0

        latest_corr = self.correlation_history[-1].correlation_matrix

        if weights is None:
            # Equal weight
            n_assets = len(latest_corr.columns)
            weights = dict.fromkeys(latest_corr.columns, 1.0 / n_assets)

        symbols = list(weights.keys())
        weight_array = np.array([weights[s] for s in symbols])

        # Portfolio volatility vs weighted average volatility
        cov_matrix = latest_corr.values  # Simplified (correlation as covariance)
        portfolio_vol = np.sqrt(weight_array.T @ cov_matrix @ weight_array)
        weighted_avg_vol = weight_array.sum()  # Simplified

        diversification_ratio = weighted_avg_vol / portfolio_vol if portfolio_vol > 0 else 1.0

        return diversification_ratio

    def get_statistics(self) -> Dict[str, float]:
        """Portfolio korelasyon istatistikleri"""
        if not self.correlation_history:
            return {}

        latest = self.correlation_history[-1]

        # Off-diagonal korelasyonlar
        corr_values = latest.correlation_matrix.values
        off_diagonal = corr_values[np.triu_indices_from(corr_values, k=1)]

        return {
            'mean_correlation': off_diagonal.mean(),
            'max_correlation': off_diagonal.max(),
            'min_correlation': off_diagonal.min(),
            'correlation_std': off_diagonal.std(),
            'max_eigenvalue': latest.max_eigenvalue,
            'condition_number': latest.condition_number,
            'n_assets': len(latest.correlation_matrix.columns),
            'diversification_ratio': self.get_diversification_ratio()
        }


# Global singleton instance
_correlation_matrix = None


def get_correlation_matrix() -> CorrelationMatrix:
    """Global CorrelationMatrix instance al"""
    global _correlation_matrix
    if _correlation_matrix is None:
        _correlation_matrix = CorrelationMatrix()
    return _correlation_matrix


def calculate_portfolio_correlation(price_data: Dict[str, pd.Series]) -> Optional[CorrelationResult]:
    """
    Convenience function - portfolio korelasyon hesapla

    Args:
        price_data: symbol -> price series mapping

    Returns:
        CorrelationResult veya None
    """
    cm = get_correlation_matrix()

    # Veri ekle
    for symbol, prices in price_data.items():
        cm.add_price_data(symbol, prices)

    return cm.calculate_correlation()
