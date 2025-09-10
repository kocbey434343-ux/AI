"""
Advanced Market Impact Models for Liquidity-Aware Execution
Sophisticated impact estimation and cost analysis
"""

import logging
import math
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .liquidity_analyzer import OrderBookSnapshot, OrderSide

# Constants for calibration
MIN_CALIBRATION_POINTS = 3
MIN_CORRELATION_THRESHOLD = 0.3


class ImpactModel(Enum):
    """Market impact model types"""
    LINEAR = "linear"                    # Linear impact model
    SQUARE_ROOT = "square_root"         # Square-root impact (Almgren-Chriss)
    KYLE_LAMBDA = "kyle_lambda"         # Kyle's lambda model
    POWER_LAW = "power_law"             # Power law with exponent
    CONCAVE = "concave"                 # Concave impact function


@dataclass(frozen=True)
class ImpactParameters:
    """Parameters for market impact calculation"""
    model: ImpactModel = ImpactModel.SQUARE_ROOT
    temporary_impact_coef: float = 0.1   # Temporary impact coefficient
    permanent_impact_coef: float = 0.05  # Permanent impact coefficient
    volatility: float = 0.01             # Daily volatility (default expected by tests)
    volume_rate: float = 5000.0          # Default expected by tests
    power_exponent: float = 0.5          # For power law model
    liquidity_lambda: float = 1e-6       # Kyle's lambda parameter
    resilience_half_life: float = 600    # Time for impact to halve (seconds)


@dataclass
class MarketImpactEstimate:
    """Comprehensive market impact estimation"""
    # Fields required by tests (with defaults for flexible construction)
    symbol: str = ""
    total_cost_bps: float = 0.0
    temporary_impact_bps: float = 0.0
    permanent_impact_bps: float = 0.0
    confidence_interval: Tuple[float, float] = (0.0, 0.0)
    optimal_participation_rate: float = 0.0

    # Additional diagnostic fields used by the framework
    order_size: float = 0.0
    market_volume: float = 0.0
    total_impact_bps: float = 0.0
    implementation_shortfall_bps: float = 0.0
    expected_completion_time: float = 0.0
    risk_penalty_bps: float = 0.0


class AdvancedMarketImpactCalculator:
    """
    Advanced market impact calculation with multiple models
    Implements Almgren-Chriss, Kyle's lambda, and other sophisticated models
    """

    def __init__(self,
                 impact_params: Optional[ImpactParameters] = None,
                 calibration_data: Optional[Dict[str, Any]] = None):
        """
        Initialize market impact calculator

        Args:
            impact_params: Impact model parameters
            calibration_data: Historical calibration data
        """
        self.impact_params = impact_params or ImpactParameters()
        self.calibration_data = calibration_data or {}
        self.logger = logging.getLogger(__name__)

        # Model-specific parameters
        self.model_cache = {}
        self.last_calibration = 0

        self.logger.info(f"AdvancedMarketImpactCalculator initialized: "
                        f"model={self.impact_params.model.value}, "
                        f"temp_coef={self.impact_params.temporary_impact_coef}, "
                        f"perm_coef={self.impact_params.permanent_impact_coef}")

    def calculate_impact(self,
                        symbol: str,
                        side: OrderSide,
                        order_size: float,
                        order_book: OrderBookSnapshot,
                        execution_horizon: float = 300.0) -> MarketImpactEstimate:
        """
        Calculate comprehensive market impact estimate

        Args:
            symbol: Trading symbol
            side: Order side (BUY/SELL)
            order_size: Order size in base currency
            order_book: Current order book snapshot
            execution_horizon: Expected execution time in seconds

        Returns:
            Comprehensive market impact estimate
        """
        try:
            # Zero-size orders: no impact/cost
            if order_size <= 0:
                return MarketImpactEstimate(
                    symbol=symbol,
                    order_size=0.0,
                    market_volume=0.0,
                    temporary_impact_bps=0.0,
                    permanent_impact_bps=0.0,
                    total_impact_bps=0.0,
                    implementation_shortfall_bps=0.0,
                    optimal_participation_rate=0.0,
                    expected_completion_time=0.0,
                    confidence_interval=(0.0, 0.0),
                    risk_penalty_bps=0.0,
                    total_cost_bps=0.0,
                )
            # Calculate market volume and participation rate
            market_volume = self._estimate_market_volume(symbol, order_book)
            participation_rate = order_size / market_volume if market_volume > 0 else 1.0

            # Calculate temporary impact
            temp_impact = self._calculate_temporary_impact(
                order_size, participation_rate
            )

            # Calculate permanent impact
            perm_impact = self._calculate_permanent_impact(
                participation_rate
            )

            # Calculate optimal execution parameters
            optimal_rate, completion_time = self._optimize_execution_schedule(
                order_size, market_volume, execution_horizon
            )

            # Implementation shortfall calculation
            impl_shortfall = self._calculate_implementation_shortfall(
                temp_impact, perm_impact, participation_rate, execution_horizon
            )

            # Risk penalty
            risk_penalty = self._calculate_risk_penalty(
                order_size, market_volume, execution_horizon
            )

            # Confidence interval
            confidence_interval = self._calculate_confidence_interval(
                temp_impact + perm_impact, order_size, market_volume
            )

            total_impact = temp_impact + perm_impact
            total_cost = total_impact + risk_penalty

            return MarketImpactEstimate(
                symbol=symbol,
                order_size=order_size,
                market_volume=market_volume,
                temporary_impact_bps=temp_impact,
                permanent_impact_bps=perm_impact,
                total_impact_bps=total_impact,
                implementation_shortfall_bps=impl_shortfall,
                optimal_participation_rate=optimal_rate,
                expected_completion_time=completion_time,
                confidence_interval=confidence_interval,
                risk_penalty_bps=risk_penalty,
                total_cost_bps=total_cost,
            )

        except Exception as e:
            self.logger.error(f"Error calculating market impact for {symbol}: {e}")
            # Return conservative fallback estimate
            return self._fallback_impact_estimate(symbol, order_size, order_book)

    def _calculate_temporary_impact(self,
                                   order_size: float,
                                   participation_rate: float) -> float:
        """Calculate temporary market impact in basis points"""

        model = self.impact_params.model

        if model == ImpactModel.LINEAR:
            # Linear impact: I = eta * (X / V)
            return (self.impact_params.temporary_impact_coef *
                   participation_rate * 10000)  # Convert to BPS

        if model == ImpactModel.SQUARE_ROOT:
            # Square-root impact: I = eta * sigma * sqrt(X / V)
            volatility = self.impact_params.volatility
            return (self.impact_params.temporary_impact_coef *
                   volatility * math.sqrt(participation_rate) * 10000)

        if model == ImpactModel.KYLE_LAMBDA:
            # Kyle's lambda: I = lambda * X
            return (self.impact_params.liquidity_lambda *
                   order_size * 10000)

        if model == ImpactModel.POWER_LAW:
            # Power law: I = eta * (X / V)^alpha
            exponent = self.impact_params.power_exponent
            return (self.impact_params.temporary_impact_coef *
                   (participation_rate ** exponent) * 10000)

        if model == ImpactModel.CONCAVE:
            # Concave function: I = eta * log(1 + X / V)
            return (self.impact_params.temporary_impact_coef *
                   math.log(1 + participation_rate) * 10000)

        # Default to square-root
        volatility = self.impact_params.volatility
        return (self.impact_params.temporary_impact_coef *
               volatility * math.sqrt(participation_rate) * 10000)

    def _calculate_permanent_impact(self,
                                   participation_rate: float) -> float:
        """Calculate permanent market impact in basis points"""

        # Permanent impact is typically smaller and linear
        return (self.impact_params.permanent_impact_coef *
               participation_rate * 10000)

    def _optimize_execution_schedule(self,
                                   order_size: float,
                                   market_volume: float,
                                   horizon: float) -> Tuple[float, float]:
        """
        Optimize execution schedule using Almgren-Chriss framework

        Returns:
            (optimal_participation_rate, completion_time)
        """
        try:
            # Simplified Almgren-Chriss optimization
            eta = self.impact_params.temporary_impact_coef
            gamma = self.impact_params.permanent_impact_coef
            sigma = self.impact_params.volatility

            # Risk aversion parameter (can be made configurable)
            risk_aversion = 1e-6

            # Optimal participation rate
            if risk_aversion > 0 and sigma > 0:
                optimal_rate = math.sqrt(
                    (gamma * market_volume) /
                    (eta * risk_aversion * sigma ** 2 * horizon)
                )
                optimal_rate = min(optimal_rate, 0.3)  # Cap at 30%
            else:
                optimal_rate = 0.1  # Default 10%

            # Completion time based on optimal rate
            completion_time = order_size / (optimal_rate * market_volume) if optimal_rate > 0 else horizon
            completion_time = min(completion_time, horizon)

            return optimal_rate, completion_time

        except Exception as e:
            self.logger.warning(f"Error in execution optimization: {e}")
            return 0.1, horizon  # Conservative fallback

    def _calculate_implementation_shortfall(self,
                                          temp_impact: float,
                                          perm_impact: float,
                                          participation_rate: float,
                                          horizon: float) -> float:
        """Calculate implementation shortfall in basis points"""

        # Implementation shortfall includes market risk and timing risk
        timing_risk = self.impact_params.volatility * math.sqrt(horizon / 86400) * 10000
        market_risk = temp_impact * participation_rate

        return perm_impact + market_risk + timing_risk * 0.5

    def _calculate_risk_penalty(self,
                               order_size: float,
                               market_volume: float,
                               horizon: float) -> float:
        """Calculate risk penalty for delayed execution"""

        volatility = self.impact_params.volatility
        participation_rate = order_size / market_volume if market_volume > 0 else 1.0

        # Risk penalty increases with size and time
        size_penalty = participation_rate * 10  # BPS per 1% participation
        time_penalty = (horizon / 3600) * volatility * 10000 * 0.1  # Time risk

        return min(size_penalty + time_penalty, 50)  # Cap at 50 BPS

    def _calculate_confidence_interval(self,
                                     impact_estimate: float,
                                     order_size: float,
                                     market_volume: float) -> Tuple[float, float]:
        """Calculate confidence interval for impact estimate"""

        # Standard error based on order size and market conditions
        participation_rate = order_size / market_volume if market_volume > 0 else 1.0
        std_error = impact_estimate * (0.1 + 0.2 * participation_rate)

        # 95% confidence interval
        lower_bound = max(0, impact_estimate - 1.96 * std_error)
        upper_bound = impact_estimate + 1.96 * std_error

        return (lower_bound, upper_bound)

    def _estimate_market_volume(self,
                               symbol: str,
                               order_book: OrderBookSnapshot) -> float:
        """Estimate daily market volume from order book"""

        # Use order book depth as proxy for volume
        total_depth = sum(level.quantity for level in order_book.bids[:10])
        total_depth += sum(level.quantity for level in order_book.asks[:10])

        # Estimate daily volume as 100x order book depth (rough heuristic)
        estimated_volume = total_depth * 100

        # Apply symbol-specific adjustments if available
        if symbol in self.calibration_data:
            volume_multiplier = self.calibration_data[symbol].get('volume_multiplier', 1.0)
            estimated_volume *= volume_multiplier

        return max(estimated_volume, 1.0)  # Minimum volume

    def _fallback_impact_estimate(self,
                                 symbol: str,
                                 order_size: float,
                                 order_book: OrderBookSnapshot) -> MarketImpactEstimate:
        """Conservative fallback impact estimate"""

        market_volume = self._estimate_market_volume("UNKNOWN", order_book)
        participation_rate = order_size / market_volume

        # Conservative estimates
        temp_impact = min(participation_rate * 50, 100)  # Max 100 BPS
        perm_impact = min(participation_rate * 20, 50)   # Max 50 BPS

        total_impact = temp_impact + perm_impact
        total_cost = total_impact + 10.0

        return MarketImpactEstimate(
            symbol=symbol,
            order_size=order_size,
            market_volume=market_volume,
            temporary_impact_bps=temp_impact,
            permanent_impact_bps=perm_impact,
            total_impact_bps=total_impact,
            implementation_shortfall_bps=total_impact + 10,
            optimal_participation_rate=0.1,
            expected_completion_time=300.0,
            confidence_interval=(total_impact - 20, total_impact + 50),
            risk_penalty_bps=10.0,
            total_cost_bps=total_cost,
        )

    def calibrate_model(self, arg1, arg2: Optional[Dict[str, Any]] = None):
        """Calibrate impact model.

        Supports two calling conventions:
          - New (tests expect): calibrate_model(execution_data: List[dict], historical_data: Optional[dict]) -> dict
          - Legacy: calibrate_model(symbol: str, historical_data: List[dict]) -> bool
        """
        try:
            # New style: first argument is a list of execution records -> return dict
            if isinstance(arg1, list):
                execution_data: List[Dict[str, Any]] = arg1
                if len(execution_data) < MIN_CALIBRATION_POINTS:
                    return {"calibration_result": "insufficient_data", "adjusted_parameters": {}}

                # Extract features with flexible keys
                order_sizes = [float(d.get("order_size", 0.0)) for d in execution_data]
                # realized impact may be provided as 'realized_impact' (fraction) or 'impact_bps'
                realized_impacts = [
                    (float(d.get("impact_bps")) if d.get("impact_bps") is not None else float(d.get("realized_impact", 0.0)) * 10000)
                    for d in execution_data
                ]
                # Determine market volumes: prefer explicit, else derive from participation_rate
                market_volumes: List[float] = []
                for d, sz in zip(execution_data, order_sizes):
                    if d.get("market_volume"):
                        market_volumes.append(float(d["market_volume"]))
                    else:
                        pr = float(d.get("participation_rate", 0.0))
                        market_volumes.append((sz / pr) if pr > 0 else 1.0)

                participation_rates = [sz / vol if vol > 0 else 0.0 for sz, vol in zip(order_sizes, market_volumes)]
                if len([r for r in participation_rates if r > 0]) < MIN_CALIBRATION_POINTS:
                    return {"calibration_result": "insufficient_data", "adjusted_parameters": {}}

                correlation = np.corrcoef(participation_rates, realized_impacts)[0, 1]
                if np.isnan(correlation) or correlation <= MIN_CORRELATION_THRESHOLD:
                    return {"calibration_result": "insufficient_data", "adjusted_parameters": {}}

                avg_impact_per_participation = float(np.mean(realized_impacts) / max(np.mean(participation_rates), 1e-12))
                new_coef = avg_impact_per_participation / 10000.0

                # Update parameters (replace frozen dataclass)
                self.impact_params = ImpactParameters(
                    model=self.impact_params.model,
                    temporary_impact_coef=new_coef,
                    permanent_impact_coef=self.impact_params.permanent_impact_coef,
                    volatility=self.impact_params.volatility,
                    volume_rate=self.impact_params.volume_rate,
                    power_exponent=self.impact_params.power_exponent,
                    liquidity_lambda=self.impact_params.liquidity_lambda,
                    resilience_half_life=self.impact_params.resilience_half_life,
                )

                return {
                    "calibration_result": "success",
                    "adjusted_parameters": {
                        "temporary_impact_coef": new_coef,
                        "permanent_impact_coef": self.impact_params.permanent_impact_coef,
                    },
                }

            # Legacy style: first argument is symbol -> return bool
            symbol: str = str(arg1)
            historical_data: List[Dict[str, Any]] = list(arg2 or [])
            if not historical_data:
                return False

            order_sizes = [d.get('order_size', 0) for d in historical_data]
            realized_impacts = [d.get('impact_bps', 0) for d in historical_data]
            market_volumes = [d.get('market_volume', 1) for d in historical_data]
            if not order_sizes or not realized_impacts:
                return False

            participation_rates = [size / vol if vol > 0 else 0 for size, vol in zip(order_sizes, market_volumes)]
            if len(participation_rates) >= MIN_CALIBRATION_POINTS:
                correlation = np.corrcoef(participation_rates, realized_impacts)[0, 1]
                if not np.isnan(correlation) and correlation > MIN_CORRELATION_THRESHOLD:
                    avg_impact_per_participation = float(np.mean(realized_impacts) / max(np.mean(participation_rates), 1e-12))
                    new_coef = float(avg_impact_per_participation / 10000)
                    self.impact_params = ImpactParameters(
                        model=self.impact_params.model,
                        temporary_impact_coef=new_coef,
                        permanent_impact_coef=self.impact_params.permanent_impact_coef,
                        volatility=self.impact_params.volatility,
                        volume_rate=self.impact_params.volume_rate,
                        power_exponent=self.impact_params.power_exponent,
                        liquidity_lambda=self.impact_params.liquidity_lambda,
                        resilience_half_life=self.impact_params.resilience_half_life
                    )
                    self.calibration_data[symbol] = {
                        'volume_multiplier': float(np.mean(market_volumes) / 1000.0),
                        'impact_coefficient': avg_impact_per_participation,
                        'last_calibration': time.time(),
                        'data_points': len(historical_data)
                    }
                    self.logger.info(
                        f"Model calibrated for {symbol}: coefficient={avg_impact_per_participation:.6f}, correlation={correlation:.3f}"
                    )
                    return True
            return False
        except Exception as e:
            # For new style, return dict; for legacy, return False
            if isinstance(arg1, list):
                self.logger.error(f"Error calibrating model: {e}")
                return {"calibration_result": "error", "adjusted_parameters": {}}
            self.logger.error(f"Error calibrating model for {arg1}: {e}")
            return False

    def get_model_statistics(self) -> Dict[str, Any]:
        """Get model statistics and performance metrics"""

        return {
            'model_type': self.impact_params.model.value,
            'calibrated_symbols': len(self.calibration_data),
            'parameters': {
                'temporary_impact_coef': self.impact_params.temporary_impact_coef,
                'permanent_impact_coef': self.impact_params.permanent_impact_coef,
                'volatility': self.impact_params.volatility,
                'liquidity_lambda': self.impact_params.liquidity_lambda
            },
            'calibration_data': {
                symbol: {
                    'impact_coefficient': data.get('impact_coefficient', 0),
                    'data_points': data.get('data_points', 0),
                    'last_calibration': data.get('last_calibration', 0)
                }
                for symbol, data in self.calibration_data.items()
            }
        }


# Global instance for convenience
_impact_calculator = None

def get_market_impact_calculator() -> AdvancedMarketImpactCalculator:
    """Get singleton market impact calculator"""
    global _impact_calculator
    if _impact_calculator is None:
        _impact_calculator = AdvancedMarketImpactCalculator()
    return _impact_calculator

def calculate_market_impact(symbol: str,
                           side: OrderSide,
                           order_size: float,
                           order_book: OrderBookSnapshot,
                           execution_horizon: float = 300.0) -> MarketImpactEstimate:
    """Convenience function for market impact calculation"""
    calculator = get_market_impact_calculator()
    return calculator.calculate_impact(symbol, side, order_size, order_book, execution_horizon)

def calibrate_impact_model(symbol: str,
                          historical_data: List[Dict[str, Any]]) -> bool:
    """Convenience function for model calibration"""
    calculator = get_market_impact_calculator()
    return calculator.calibrate_model(symbol, historical_data)
