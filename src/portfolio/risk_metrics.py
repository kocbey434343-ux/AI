"""
Risk Metrics Calculator for Portfolio Analysis

VaR, Expected Shortfall, ve diger risk metriklerini hesaplar.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class VarResult:
    """Value at Risk hesaplama sonucu"""
    var_95: float
    var_99: float
    expected_shortfall_95: float
    expected_shortfall_99: float
    confidence_level: float
    method: str
    calculation_timestamp: datetime


@dataclass
class RiskMetrics:
    """Portfolio risk metrikleri"""
    daily_var: VarResult
    annual_volatility: float
    sharpe_ratio: float
    max_drawdown: float
    calmar_ratio: float
    sortino_ratio: float
    beta: Optional[float] = None
    alpha: Optional[float] = None


class VarCalculator:
    """
    Value at Risk ve Expected Shortfall hesaplayici

    Yontemler:
    - Historical simulation
    - Parametric (Normal distribution)
    - Monte Carlo simulation
    """

    def __init__(self, confidence_levels: Optional[List[float]] = None):
        """
        Args:
            confidence_levels: Guven seviyeleri (default: [0.95, 0.99])
        """
        self.confidence_levels = confidence_levels or [0.95, 0.99]
        self.return_history: List[float] = []

    def add_return(self, return_value: float):
        """Portfolio getirisi ekle"""
        self.return_history.append(return_value)

        # History'yi sinirla (son 250 gun)
        if len(self.return_history) > 250:
            self.return_history = self.return_history[-250:]

    def calculate_historical_var(self) -> Optional[VarResult]:
        """Historical simulation ile VaR hesapla"""
        if len(self.return_history) < 30:
            logger.warning(f"Yetersiz veri: {len(self.return_history)} < 30")
            return None

        returns = np.array(self.return_history)

        # Percentile hesapla
        var_95 = np.percentile(returns, 5)  # 5% worst case
        var_99 = np.percentile(returns, 1)  # 1% worst case

        # Expected Shortfall (CVaR)
        es_95 = returns[returns <= var_95].mean()
        es_99 = returns[returns <= var_99].mean()

        return VarResult(
            var_95=float(var_95),
            var_99=float(var_99),
            expected_shortfall_95=float(es_95),
            expected_shortfall_99=float(es_99),
            confidence_level=0.95,
            method='historical',
            calculation_timestamp=datetime.now()
        )

    def calculate_parametric_var(self) -> Optional[VarResult]:
        """Normal dagilim varsayimi ile parametrik VaR"""
        if len(self.return_history) < 30:
            return None

        returns = np.array(self.return_history)

        # Normal dagilim parametreleri
        mean_return = returns.mean()
        std_return = returns.std()

        # Z-score'lar (manuel olarak tanimlandi)
        z_95 = -1.645  # %5 percentile
        z_99 = -2.326  # %1 percentile

        # VaR hesapla
        var_95 = mean_return + z_95 * std_return
        var_99 = mean_return + z_99 * std_return

        # Expected Shortfall (basitlestirilmis normal yaklasim)
        es_95 = mean_return - std_return * 0.3989 / 0.05  # Simplified normal PDF
        es_99 = mean_return - std_return * 0.0484 / 0.01

        return VarResult(
            var_95=var_95,
            var_99=var_99,
            expected_shortfall_95=es_95,
            expected_shortfall_99=es_99,
            confidence_level=0.95,
            method='parametric',
            calculation_timestamp=datetime.now()
        )

    def calculate_monte_carlo_var(self, n_simulations: int = 10000) -> Optional[VarResult]:
        """Monte Carlo simulasyonu ile VaR"""
        if len(self.return_history) < 30:
            return None

        returns = np.array(self.return_history)

        # Dagilim parametreleri
        mean_return = returns.mean()
        std_return = returns.std()

        # Monte Carlo simulasyon - modern numpy kullan
        rng = np.random.default_rng()
        simulated_returns = rng.normal(mean_return, std_return, n_simulations)

        # VaR hesapla
        var_95 = np.percentile(simulated_returns, 5)
        var_99 = np.percentile(simulated_returns, 1)

        # Expected Shortfall
        es_95 = simulated_returns[simulated_returns <= var_95].mean()
        es_99 = simulated_returns[simulated_returns <= var_99].mean()

        return VarResult(
            var_95=float(var_95),
            var_99=float(var_99),
            expected_shortfall_95=float(es_95),
            expected_shortfall_99=float(es_99),
            confidence_level=0.95,
            method='monte_carlo',
            calculation_timestamp=datetime.now()
        )


class PortfolioRiskAnalyzer:
    """
    Kapsamli portfolio risk analizi
    """

    def __init__(self):
        self.var_calculator = VarCalculator()
        self.price_history: Dict[str, List[float]] = {}
        self.weight_history: Dict[str, List[float]] = {}
        self.benchmark_returns: List[float] = []

    def add_portfolio_snapshot(self, prices: Dict[str, float], weights: Dict[str, float]):
        """Portfolio snapshot ekle"""
        for symbol in prices:
            if symbol not in self.price_history:
                self.price_history[symbol] = []
                self.weight_history[symbol] = []

            self.price_history[symbol].append(prices[symbol])
            self.weight_history[symbol].append(weights.get(symbol, 0.0))

    def calculate_portfolio_returns(self) -> List[float]:
        """Portfolio getirilerini hesapla"""
        if not self.price_history:
            return []

        # En kisa seriyi bul
        min_length = min(len(series) for series in self.price_history.values())

        if min_length < 2:
            return []

        portfolio_returns = []

        for i in range(1, min_length):
            period_return = 0.0

            for symbol in self.price_history:
                if len(self.price_history[symbol]) > i and len(self.weight_history[symbol]) > i:
                    price_return = (self.price_history[symbol][i] /
                                  self.price_history[symbol][i-1] - 1)
                    weight = self.weight_history[symbol][i-1]  # Previous period weight
                    period_return += price_return * weight

            portfolio_returns.append(period_return)

        return portfolio_returns

    def calculate_comprehensive_risk(self, benchmark_returns: Optional[List[float]] = None) -> Optional[RiskMetrics]:
        """Kapsamli risk analizi"""
        portfolio_returns = self.calculate_portfolio_returns()

        if len(portfolio_returns) < 30:
            logger.warning("Yetersiz portfolio getiri verisi")
            return None

        returns = np.array(portfolio_returns)

        # VaR hesapla
        for ret in portfolio_returns:
            self.var_calculator.add_return(ret)

        daily_var = self.var_calculator.calculate_historical_var()

        if not daily_var:
            return None

        # Temel metrikler
        annual_vol = returns.std() * np.sqrt(252)  # Gunluk -> yillik
        mean_return = returns.mean()
        annual_return = mean_return * 252

        # Sharpe ratio (risk-free rate = 0 varsayimi)
        sharpe = annual_return / annual_vol if annual_vol > 0 else 0

        # Maximum drawdown
        cumulative_returns = np.cumprod(1 + returns)
        running_max = np.maximum.accumulate(cumulative_returns)
        drawdown = (cumulative_returns - running_max) / running_max
        max_drawdown = drawdown.min()

        # Calmar ratio
        calmar = annual_return / abs(max_drawdown) if max_drawdown != 0 else 0

        # Sortino ratio (downside deviation)
        downside_returns = returns[returns < 0]
        downside_std = downside_returns.std() * np.sqrt(252) if len(downside_returns) > 0 else annual_vol
        sortino = annual_return / downside_std if downside_std > 0 else 0

        # Beta ve Alpha (benchmark varsa)
        beta = None
        alpha = None

        if benchmark_returns and len(benchmark_returns) == len(portfolio_returns):
            benchmark_array = np.array(benchmark_returns)
            covariance = np.cov(returns, benchmark_array)[0][1]
            benchmark_variance = benchmark_array.var()

            if benchmark_variance > 0:
                beta = covariance / benchmark_variance
                alpha = annual_return - beta * benchmark_array.mean() * 252

        return RiskMetrics(
            daily_var=daily_var,
            annual_volatility=annual_vol,
            sharpe_ratio=sharpe,
            max_drawdown=max_drawdown,
            calmar_ratio=calmar,
            sortino_ratio=sortino,
            beta=beta,
            alpha=alpha
        )

    def stress_test(self, shock_scenarios: Dict[str, float]) -> Dict[str, float]:
        """
        Stress test - sok senaryolari uygula

        Args:
            shock_scenarios: {'symbol': shock_percentage}

        Returns:
            Senaryo sonuclari
        """
        if not self.price_history or not self.weight_history:
            return {}

        results = {}

        # Mevcut fiyatlar (son snapshot)
        current_prices = {symbol: prices[-1] for symbol, prices in self.price_history.items()}
        current_weights = {symbol: weights[-1] for symbol, weights in self.weight_history.items()}

        for scenario_name, shock_pct in shock_scenarios.items():
            scenario_impact = 0.0

            for symbol in current_prices:
                if symbol in current_weights:
                    # Sok uygula
                    shocked_price = current_prices[symbol] * (1 + shock_pct)
                    price_impact = (shocked_price / current_prices[symbol] - 1)
                    weighted_impact = price_impact * current_weights[symbol]
                    scenario_impact += weighted_impact

            results[scenario_name] = scenario_impact

        return results


# Global singleton
_portfolio_risk_analyzer = None


def get_portfolio_risk_analyzer() -> PortfolioRiskAnalyzer:
    """Global PortfolioRiskAnalyzer instance"""
    global _portfolio_risk_analyzer
    if _portfolio_risk_analyzer is None:
        _portfolio_risk_analyzer = PortfolioRiskAnalyzer()
    return _portfolio_risk_analyzer
