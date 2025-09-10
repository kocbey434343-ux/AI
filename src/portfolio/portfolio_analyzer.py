"""
Portfolio Analyzer - Ana portfolio analiz motoru

Multi-asset portfolio analizi, risk metrikleri ve optimizasyon.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from .correlation_matrix import CorrelationMatrix, CorrelationResult
from .risk_metrics import PortfolioRiskAnalyzer, RiskMetrics

logger = logging.getLogger(__name__)


@dataclass
class PortfolioPosition:
    """Portfolio pozisyon bilgisi"""
    symbol: str
    quantity: float
    price: float
    weight: float
    value: float
    sector: Optional[str] = None


@dataclass
class PortfolioSnapshot:
    """Portfolio anlik durum"""
    timestamp: datetime
    positions: List[PortfolioPosition]
    total_value: float
    cash: float
    leverage: float
    correlation_result: Optional[CorrelationResult] = None
    risk_metrics: Optional[RiskMetrics] = None


class PortfolioAnalyzer:
    """
    Kapsamli portfolio analizi ve optimizasyon

    Ozellikler:
    - Multi-asset portfolio tracking
    - Risk analytics (VaR, correlations)
    - Performance attribution
    - Optimization suggestions
    """

    def __init__(self, base_currency: str = 'USDT'):
        """
        Args:
            base_currency: Temel para birimi
        """
        self.base_currency = base_currency
        self.correlation_matrix = CorrelationMatrix()
        self.risk_analyzer = PortfolioRiskAnalyzer()

        self.snapshots: List[PortfolioSnapshot] = []
        self.sector_mapping: Dict[str, str] = {}

        # Performance tracking
        self.performance_history: List[float] = []
        self.benchmark_history: List[float] = []

        # Analytics cache
        self._analytics_cache: Dict[str, Any] = {}
        self._cache_timestamp: Optional[datetime] = None

    def add_sector_mapping(self, symbol_sector_map: Dict[str, str]):
        """Sembol -> sektor eslemesi ekle"""
        self.sector_mapping.update(symbol_sector_map)
        logger.info(f"Sector mapping updated: {len(symbol_sector_map)} symbols")

    def take_snapshot(self, positions: Dict[str, Tuple[float, float]],
                     cash: float = 0.0, leverage: float = 1.0) -> PortfolioSnapshot:
        """
        Portfolio snapshot al

        Args:
            positions: {symbol: (quantity, current_price)}
            cash: Nakit miktar
            leverage: Kaldirac orani

        Returns:
            PortfolioSnapshot
        """
        timestamp = datetime.now()

        # Position objects olustur
        portfolio_positions = []
        total_value = cash

        for symbol, (quantity, price) in positions.items():
            value = quantity * price
            total_value += value

            position = PortfolioPosition(
                symbol=symbol,
                quantity=quantity,
                price=price,
                weight=0.0,  # Sonra hesaplanacak
                value=value,
                sector=self.sector_mapping.get(symbol)
            )
            portfolio_positions.append(position)

        # Weight'leri hesapla
        if total_value > 0:
            for position in portfolio_positions:
                position.weight = position.value / total_value

        # Price data ekle (correlation icin)
        price_data = {symbol: price for symbol, (_, price) in positions.items()}
        for symbol, price in price_data.items():
            # Basit price series olustur (gercek implementasyonda tarihsel veri kullanilir)
            price_series = pd.Series([price], index=[timestamp])
            self.correlation_matrix.add_price_data(symbol, price_series)

        # Correlation hesapla
        correlation_result = self.correlation_matrix.calculate_correlation()

        # Risk analyzer icin snapshot ekle
        weights = {pos.symbol: pos.weight for pos in portfolio_positions}
        prices = {pos.symbol: pos.price for pos in portfolio_positions}
        self.risk_analyzer.add_portfolio_snapshot(prices, weights)

        # Risk metrics hesapla
        risk_metrics = self.risk_analyzer.calculate_comprehensive_risk()

        snapshot = PortfolioSnapshot(
            timestamp=timestamp,
            positions=portfolio_positions,
            total_value=total_value,
            cash=cash,
            leverage=leverage,
            correlation_result=correlation_result,
            risk_metrics=risk_metrics
        )

        self.snapshots.append(snapshot)

        # History sinirla (son 1000 snapshot)
        if len(self.snapshots) > 1000:
            self.snapshots = self.snapshots[-1000:]

        # Analytics cache'i temizle
        self._cache_timestamp = None

        logger.info(f"Portfolio snapshot taken: {len(portfolio_positions)} positions, "
                   f"total value: {total_value:.2f} {self.base_currency}")

        return snapshot

    def get_latest_snapshot(self) -> Optional[PortfolioSnapshot]:
        """Son portfolio snapshot'i al"""
        return self.snapshots[-1] if self.snapshots else None

    def calculate_sector_allocation(self) -> Dict[str, float]:
        """Sektor dagilimi hesapla"""
        latest = self.get_latest_snapshot()
        if not latest:
            return {}

        sector_values = {}

        for position in latest.positions:
            sector = position.sector or 'Unknown'
            sector_values[sector] = sector_values.get(sector, 0) + position.value

        # Yuzdelere cevir
        total_value = sum(sector_values.values())
        if total_value > 0:
            return {sector: value/total_value for sector, value in sector_values.items()}
        return {}

    def calculate_concentration_risk(self) -> Dict[str, float]:
        """Konsantrasyon riski analizi"""
        latest = self.get_latest_snapshot()
        if not latest:
            return {}

        # Position concentration
        position_weights = [pos.weight for pos in latest.positions]

        # Herfindahl-Hirschman Index
        hhi = sum(w**2 for w in position_weights)

        # Top N concentration
        sorted_weights = sorted(position_weights, reverse=True)
        top_3 = sum(sorted_weights[:3]) if len(sorted_weights) >= 3 else sum(sorted_weights)
        top_5 = sum(sorted_weights[:5]) if len(sorted_weights) >= 5 else sum(sorted_weights)

        # Sector concentration
        sector_allocation = self.calculate_sector_allocation()
        sector_hhi = sum(w**2 for w in sector_allocation.values())

        return {
            'position_hhi': hhi,
            'sector_hhi': sector_hhi,
            'top_3_concentration': top_3,
            'top_5_concentration': top_5,
            'effective_positions': 1.0 / hhi if hhi > 0 else 0
        }

    def calculate_performance_attribution(self, period_days: int = 30) -> Dict[str, Any]:
        """Performance attribution analizi"""
        if len(self.snapshots) < 2:
            return {}

        # Period belirleme
        end_snapshot = self.snapshots[-1]
        start_date = end_snapshot.timestamp - timedelta(days=period_days)

        start_snapshot = None
        for snapshot in reversed(self.snapshots):
            if snapshot.timestamp <= start_date:
                start_snapshot = snapshot
                break

        if not start_snapshot:
            start_snapshot = self.snapshots[0]

        # Total return
        total_return = (end_snapshot.total_value / start_snapshot.total_value - 1) if start_snapshot.total_value > 0 else 0

        # Position contributions
        contributions = {}

        # Start pozisyonlarini dict'e cevir
        start_positions = {pos.symbol: pos for pos in start_snapshot.positions}

        for end_pos in end_snapshot.positions:
            start_pos = start_positions.get(end_pos.symbol)

            if start_pos:
                # Price return
                price_return = (end_pos.price / start_pos.price - 1) if start_pos.price > 0 else 0

                # Weight contribution (ortalama weight ile)
                avg_weight = (start_pos.weight + end_pos.weight) / 2
                contribution = price_return * avg_weight

                contributions[end_pos.symbol] = contribution

        return {
            'total_return': total_return,
            'contributions': contributions,
            'period_days': period_days
        }

    def get_optimization_suggestions(self) -> List[str]:
        """Portfolio optimizasyon onerileri"""
        suggestions = []

        latest = self.get_latest_snapshot()
        if not latest:
            return ["Yeterli veri yok"]

        # Concentration risk kontrolu
        concentration = self.calculate_concentration_risk()

        if concentration.get('position_hhi', 0) > 0.25:
            suggestions.append("Yuksek pozisyon konsantrasyonu - daha fazla diversifikasyon onerilir")

        if concentration.get('top_3_concentration', 0) > 0.6:
            suggestions.append("Ilk 3 pozisyon portfolio'nun %60'indan fazlasi - risk azaltma onerilir")

        # Correlation analizi
        if latest.correlation_result:
            stats = self.correlation_matrix.get_statistics()
            avg_corr = stats.get('mean_correlation', 0)

            if avg_corr > 0.7:
                suggestions.append("Yuksek ortalama korelasyon - dusuk korelasyonlu varliklar ekleyin")
            elif avg_corr < 0.1:
                suggestions.append("Cok dusuk korelasyon - bazi pozisyonlar gereksiz olabilir")

        # Risk metrics kontrolu
        if latest.risk_metrics:
            if latest.risk_metrics.sharpe_ratio < 0.5:
                suggestions.append("Dusuk Sharpe ratio - risk/getiri dengesini gozden gecirin")

            if latest.risk_metrics.max_drawdown < -0.15:
                suggestions.append("Yuksek maximum drawdown - stop-loss stratejilerini degerlendirin")

        # Sector diversity
        sector_allocation = self.calculate_sector_allocation()
        if len(sector_allocation) == 1:
            suggestions.append("Tek sektor konsantrasyonu - cross-sector diversifikasyon onerilir")

        if not suggestions:
            suggestions.append("Portfolio dengeli gorunuyor")

        return suggestions

    def get_analytics_summary(self) -> Dict[str, Any]:
        """Kapsamli analytics ozeti"""
        # Cache kontrolu
        if (self._cache_timestamp and
            datetime.now() - self._cache_timestamp < timedelta(minutes=5)):
            return self._analytics_cache

        latest = self.get_latest_snapshot()
        if not latest:
            return {}

        summary = {
            'timestamp': latest.timestamp.isoformat(),
            'total_value': latest.total_value,
            'position_count': len(latest.positions),
            'leverage': latest.leverage,
            'concentration_risk': self.calculate_concentration_risk(),
            'sector_allocation': self.calculate_sector_allocation(),
            'performance_attribution': self.calculate_performance_attribution(),
            'optimization_suggestions': self.get_optimization_suggestions()
        }

        # Correlation stats
        if latest.correlation_result:
            summary['correlation_stats'] = self.correlation_matrix.get_statistics()

        # Risk metrics
        if latest.risk_metrics:
            summary['risk_metrics'] = {
                'annual_volatility': latest.risk_metrics.annual_volatility,
                'sharpe_ratio': latest.risk_metrics.sharpe_ratio,
                'max_drawdown': latest.risk_metrics.max_drawdown,
                'calmar_ratio': latest.risk_metrics.calmar_ratio,
                'sortino_ratio': latest.risk_metrics.sortino_ratio
            }

            if latest.risk_metrics.daily_var:
                summary['var_metrics'] = {
                    'var_95': latest.risk_metrics.daily_var.var_95,
                    'var_99': latest.risk_metrics.daily_var.var_99,
                    'expected_shortfall_95': latest.risk_metrics.daily_var.expected_shortfall_95
                }

        # Cache'le
        self._analytics_cache = summary
        self._cache_timestamp = datetime.now()

        return summary

    def export_to_dict(self) -> Dict[str, Any]:
        """Portfolio verilerini dict olarak export et"""
        latest = self.get_latest_snapshot()
        if not latest:
            return {}

        return {
            'snapshot': {
                'timestamp': latest.timestamp.isoformat(),
                'total_value': latest.total_value,
                'cash': latest.cash,
                'leverage': latest.leverage,
                'positions': [
                    {
                        'symbol': pos.symbol,
                        'quantity': pos.quantity,
                        'price': pos.price,
                        'weight': pos.weight,
                        'value': pos.value,
                        'sector': pos.sector
                    }
                    for pos in latest.positions
                ]
            },
            'analytics': self.get_analytics_summary()
        }


# Global singleton
_portfolio_analyzer = None


def get_portfolio_analyzer() -> PortfolioAnalyzer:
    """Global PortfolioAnalyzer instance"""
    global _portfolio_analyzer
    if _portfolio_analyzer is None:
        _portfolio_analyzer = PortfolioAnalyzer()
    return _portfolio_analyzer
