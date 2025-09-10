# flake8: noqa: RUF002
"""
Cost-of-Edge Calculator for A32 Edge Hardening
4x Cost Rule Implementation

Bu modül trading edge'lerinin maliyetini hesaplar ve 4x kuralini uygular:
EGE (Expected Gross Edge) >= 4 x Total Cost

Total Cost = Komisyon + Beklenen Slippage + Market Impact
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class CostModel(Enum):
    """Maliyet modelleri"""
    FLAT = "flat"
    TIERED = "tiered"
    DYNAMIC = "dynamic"


class SlippageModel(Enum):
    """Slippage modelleri"""
    STATIC = "static"
    DYNAMIC = "dynamic"
    SPREAD_BASED = "spread_based"


@dataclass
class CostComponents:
    """Maliyet bileşenleri"""
    fee_bps: float = 0.0
    slippage_bps: float = 0.0
    impact_bps: float = 0.0
    total_bps: float = 0.0

    def __post_init__(self):
        """Total maliyeti hesapla"""
        self.total_bps = self.fee_bps + self.slippage_bps + self.impact_bps


@dataclass
class EdgeExpectation:
    """Edge beklentisi bileşenleri"""
    confluence_score: float = 0.0  # [0,1] confluence skorlama
    regime_score: float = 0.0      # [0,1] rejim uygunluğu
    signal_strength: float = 0.0   # [0,1] sinyal gücü
    volume_score: float = 0.0      # [0,1] hacim adequacy
    total_ege: float = 0.0         # Expected Gross Edge

    def __post_init__(self):
        """EGE toplam hesapla"""
        self.total_ege = (
            self.confluence_score * 0.4 +
            self.regime_score * 0.3 +
            self.signal_strength * 0.2 +
            self.volume_score * 0.1
        )


@dataclass
class CostOfEdgeConfig:
    """Cost-of-Edge yapılandırması"""
    enabled: bool = False
    k_multiple: float = 4.0        # 4x kurali katsayisi
    fee_model: str = "tiered"      # flat, tiered, dynamic
    slippage_model: str = "dynamic"  # static, dynamic, spread_based

    # Flat fee modeli
    flat_fee_bps: float = 10.0     # 0.10% maker/taker ortalama

    # Tiered fee modeli (Binance benzeri)
    tier_levels: Optional[Dict[float, float]] = None  # volume_usdt -> fee_bps

    # Slippage kestirimi
    static_slippage_bps: float = 5.0
    spread_multiplier: float = 0.5   # spread'in yarisini slippage say

    # Market impact
    impact_threshold_usdt: float = 10000.0  # $10K üstü impact hesapla
    impact_rate_bps_per_1k: float = 0.1     # Her $1K için 0.01 BPS

    def __post_init__(self):
        """Varsayılan tier seviyeleri"""
        if self.tier_levels is None:
            self.tier_levels = {
                0.0: 10.0,        # <$1M: 0.10%
                1_000_000: 9.0,   # $1M+: 0.09%
                10_000_000: 8.0,  # $10M+: 0.08%
                50_000_000: 7.0,  # $50M+: 0.07%
            }


class CostOfEdgeCalculator:
    """4× Cost-of-Edge hesaplayıcısı"""

    def __init__(self, config: Optional[CostOfEdgeConfig] = None):
        """Hesaplayıcı başlatma"""
        self.config = config or CostOfEdgeConfig()
        self.user_volume_30d_usdt = 0.0  # 30 günlük hacim

        logger.info(
            f"CostOfEdgeCalculator initialized: enabled={self.config.enabled}, "
            f"k_multiple={self.config.k_multiple}, fee_model={self.config.fee_model}"
        )

    def update_user_volume(self, volume_usdt: float) -> None:
        """Kullanıcı 30 günlük hacmini güncelle"""
        self.user_volume_30d_usdt = max(0.0, volume_usdt)

    def calculate_fee_bps(self, order_value_usdt: float, is_maker: bool = True) -> float:
        """Komisyon hesaplama"""
        if self.config.fee_model == "flat":
            return self.config.flat_fee_bps

        if self.config.fee_model == "tiered":
            return self._calculate_tiered_fee(is_maker)

        if self.config.fee_model == "dynamic":
            # Gelişmiş model - şimdilik tiered fallback
            return self._calculate_tiered_fee(is_maker)

        return self.config.flat_fee_bps

    def _calculate_tiered_fee(self, is_maker: bool) -> float:
        """Seviyeli komisyon hesaplama"""
        # Kullanicinin tier seviyesini bul
        base_fee_bps = self.config.flat_fee_bps
        if self.config.tier_levels:
            for threshold, fee_bps in sorted(self.config.tier_levels.items()):
                if self.user_volume_30d_usdt >= threshold:
                    base_fee_bps = fee_bps

        # Maker/Taker ayrimi (maker %20 indirim)
        if is_maker:
            return base_fee_bps * 0.8
        return base_fee_bps

    def calculate_slippage_bps(
        self,
        order_value_usdt: float,
        current_spread_bps: Optional[float] = None,
        market_depth_usdt: Optional[float] = None
    ) -> float:
        """Slippage hesaplama"""
        if self.config.slippage_model == "static":
            return self.config.static_slippage_bps

        if self.config.slippage_model == "spread_based" and current_spread_bps is not None:
            return current_spread_bps * self.config.spread_multiplier

        if self.config.slippage_model == "dynamic":
            # Dinamik slippage: spread + depth analizi
            base_slip = self.config.static_slippage_bps

            if current_spread_bps is not None:
                spread_component = current_spread_bps * self.config.spread_multiplier
                base_slip = max(base_slip, spread_component)

            # Market depth penalty
            if market_depth_usdt is not None and market_depth_usdt > 0:
                depth_ratio = order_value_usdt / market_depth_usdt
                if depth_ratio > 0.05:  # Derinliğin %5'i üstü
                    depth_penalty = min(depth_ratio * 50, 20.0)  # Max 20 BPS penalty
                    base_slip += depth_penalty

            return base_slip

        return self.config.static_slippage_bps

    def calculate_market_impact_bps(
        self,
        order_value_usdt: float,
        market_depth_usdt: Optional[float] = None
    ) -> float:
        """Market impact hesaplama"""
        if order_value_usdt <= self.config.impact_threshold_usdt:
            return 0.0

        excess_value = order_value_usdt - self.config.impact_threshold_usdt
        impact_bps = (excess_value / 1000.0) * self.config.impact_rate_bps_per_1k

        # Market depth varsa daha doğru hesaplama
        if market_depth_usdt is not None and market_depth_usdt > 0:
            depth_ratio = order_value_usdt / market_depth_usdt
            if depth_ratio > 0.1:  # Derinliğin %10'u üstü
                impact_bps *= (1 + depth_ratio)

        return min(impact_bps, 50.0)  # Max 50 BPS cap

    def calculate_total_cost(
        self,
        order_value_usdt: float,
        is_maker: bool = True,
        current_spread_bps: Optional[float] = None,
        market_depth_usdt: Optional[float] = None
    ) -> CostComponents:
        """Toplam maliyet hesaplama"""
        fee_bps = self.calculate_fee_bps(order_value_usdt, is_maker)
        slippage_bps = self.calculate_slippage_bps(
            order_value_usdt, current_spread_bps, market_depth_usdt
        )
        impact_bps = self.calculate_market_impact_bps(order_value_usdt, market_depth_usdt)

        return CostComponents(
            fee_bps=fee_bps,
            slippage_bps=slippage_bps,
            impact_bps=impact_bps
        )

    def calculate_edge_expectation(
        self,
        confluence_score: float,
        regime_score: float,
        signal_strength: float,
        volume_score: float
    ) -> EdgeExpectation:
        """Expected Gross Edge hesaplama"""
        return EdgeExpectation(
            confluence_score=max(0.0, min(1.0, confluence_score)),
            regime_score=max(0.0, min(1.0, regime_score)),
            signal_strength=max(0.0, min(1.0, signal_strength)),
            volume_score=max(0.0, min(1.0, volume_score))
        )

    def should_proceed_with_trade(
        self,
        ege: EdgeExpectation,
        cost: CostComponents
    ) -> Tuple[bool, float, str]:
        """4× kuralı değerlendirmesi

        Returns:
            (should_proceed, ratio, reason)
        """
        if not self.config.enabled:
            return True, float('inf'), "cost_guard_disabled"

        if cost.total_bps <= 0.001:  # Very small cost threshold
            return True, float('inf'), "zero_cost"

        ratio = ege.total_ege / (cost.total_bps / 10000.0)  # BPS'i ondaliga cevir
        threshold = self.config.k_multiple

        if ratio >= threshold:
            return True, ratio, f"passed_4x_rule_{ratio:.2f}x"

        return False, ratio, f"failed_4x_rule_{ratio:.2f}x_<_{threshold}x"

    def evaluate_trade_feasibility(
        self,
        order_value_usdt: float,
        confluence_score: float,
        regime_score: float = 0.5,
        signal_strength: float = 0.5,
        volume_score: float = 0.5,
        is_maker: bool = True,
        current_spread_bps: Optional[float] = None,
        market_depth_usdt: Optional[float] = None
    ) -> Dict[str, Any]:
        """Kapsamlı trade fizibilitesi değerlendirmesi"""

        # Maliyet hesaplama
        cost = self.calculate_total_cost(
            order_value_usdt, is_maker, current_spread_bps, market_depth_usdt
        )

        # Edge beklentisi hesaplama
        ege = self.calculate_edge_expectation(
            confluence_score, regime_score, signal_strength, volume_score
        )

        # 4× kuralı değerlendirmesi
        should_proceed, ratio, reason = self.should_proceed_with_trade(ege, cost)

        return {
            "should_proceed": should_proceed,
            "cost_edge_ratio": ratio,
            "reason": reason,
            "cost_components": cost,
            "edge_expectation": ege,
            "order_value_usdt": order_value_usdt,
            "config": self.config
        }


# Global instance for convenience
_global_calculator: Optional[CostOfEdgeCalculator] = None


def get_cost_calculator() -> CostOfEdgeCalculator:
    """Global cost calculator instance"""
    global _global_calculator
    if _global_calculator is None:
        _global_calculator = CostOfEdgeCalculator()
    return _global_calculator


def evaluate_trade_cost(
    order_value_usdt: float,
    confluence_score: float,
    regime_score: float = 0.5,
    signal_strength: float = 0.5,
    volume_score: float = 0.5,
    **kwargs
) -> Dict[str, Any]:
    """Convenience function for trade cost evaluation"""
    calculator = get_cost_calculator()
    return calculator.evaluate_trade_feasibility(
        order_value_usdt=order_value_usdt,
        confluence_score=confluence_score,
        regime_score=regime_score,
        signal_strength=signal_strength,
        volume_score=volume_score,
        **kwargs
    )


def should_allow_trade_by_cost(
    order_value_usdt: float,
    confluence_score: float,
    **kwargs
) -> bool:
    """Convenience function - sadece proceed/block kararı"""
    result = evaluate_trade_cost(order_value_usdt, confluence_score, **kwargs)
    return result["should_proceed"]
