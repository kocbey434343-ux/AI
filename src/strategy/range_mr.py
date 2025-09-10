"""
S2: Range Mean-Reversion Specialist - A31 Implementation
======================================================

Amaç: Yatay market koşullarında BB bounce + RSI reversal sinyalleri.
Plan: SSoT A31'de tanimlanan S2 uzmani - range mean-reversion mantigi.

Gating Rules:
- TrendScore≤0.25 ve ChopScore≥0.6 (ADX<20; 4h slope≈0)
- Range/sideways ortamlarinda aktif
"""

import logging
from typing import Any, Dict

import pandas as pd

from .specialist_interface import GatingScores, SpecialistInterface, SpecialistSignal

logger = logging.getLogger(__name__)

# S2 Constants
TREND_MAX_THRESHOLD = 0.25
CHOP_MIN_THRESHOLD = 0.6
RSI_OVERSOLD = 35
RSI_OVERBOUGHT = 65
BB_TOUCH_ATR_MULT = 0.1
TARGET_R = 1.5
SL_ATR_MULT = 1.0


class RangeMRSpecialist(SpecialistInterface):
    """
    S2: Range Mean-Reversion Uzmani
    BB + RSI mean reversion sinyalleri
    """

    def __init__(self):
        self._specialist_id = "S2"
        self._specialist_name = "Range MR"

        # Performance tracking
        self.total_signals = 0
        self.trade_count = 0
        self.win_count = 0
        self.cumulative_return = 0.0

    @property
    def specialist_id(self) -> str:
        return "S2"

    @property
    def specialist_name(self) -> str:
        return "Range MR"

    def is_gated(self, scores: GatingScores) -> bool:
        """
        S2 Gating Rules:
        - TrendScore≤0.25 ve ChopScore≥0.6 (ADX<20; 4h slope≈0)
        """
        trend_weak = scores.trend_score <= TREND_MAX_THRESHOLD
        chop_high = scores.chop_score >= CHOP_MIN_THRESHOLD

        is_active = trend_weak and chop_high

        if is_active:
            logger.debug(f"S2 aktif: trend={scores.trend_score:.3f}, "
                        f"chop={scores.chop_score:.3f}")

        return is_active

    def generate_signal(self, symbol: str, data: pd.DataFrame,
                       indicators: Dict[str, Any]) -> SpecialistSignal:
        """
        S2 sinyal uretimi - mean reversion mantigi
        """
        self.total_signals += 1

        try:
            signal, confidence = self._calculate_mr_signal(data, indicators)

            # Metadata olustur
            metadata = {
                "specialist": "S2_range_mr",
                "symbol": symbol,
                "rsi": indicators.get('rsi', 50.0),
                "bb_position": self._get_bb_position_mr(data, indicators),
                "atr": indicators.get('atr', 0.01),
                "entry_reason": f"mean_reversion_{confidence:.2f}"
            }

            return SpecialistSignal(
                signal=signal,
                confidence=confidence,
                metadata=metadata
            )

        except Exception as e:
            logger.error(f"S2 sinyal hatasi {symbol}: {e}")
            return SpecialistSignal(
                signal="BEKLE",
                confidence=0.0,
                metadata={"error": str(e), "specialist": "S2_range_mr"}
            )

    def _calculate_mr_signal(self, data: pd.DataFrame,
                           indicators: Dict[str, Any]) -> tuple[str, float]:
        """
        Mean reversion sinyal hesaplama
        """
        signal = self._determine_mr_signal(data, indicators)
        confidence = self._calculate_mr_confidence(data, indicators, signal)

        return signal, confidence

    def _determine_mr_signal(self, data: pd.DataFrame,
                           indicators: Dict[str, Any]) -> str:
        """Mean reversion sinyal belirleme"""
        rsi = indicators.get('rsi', 50.0)
        bb_upper = indicators.get('bb_upper', data['close'].iloc[-1] * 1.02)
        bb_lower = indicators.get('bb_lower', data['close'].iloc[-1] * 0.98)
        atr = indicators.get('atr', 0.01)
        current_price = data['close'].iloc[-1]

        # BB touch thresholds with ATR adjustment
        bb_lower_touch = bb_lower + BB_TOUCH_ATR_MULT * atr
        bb_upper_touch = bb_upper - BB_TOUCH_ATR_MULT * atr

        # LONG conditions: close <= BB_lower + 0.1*ATR & RSI<=35
        long_bb_condition = current_price <= bb_lower_touch
        long_rsi_condition = rsi <= RSI_OVERSOLD

        # SHORT conditions: close >= BB_upper - 0.1*ATR & RSI>=65
        short_bb_condition = current_price >= bb_upper_touch
        short_rsi_condition = rsi >= RSI_OVERBOUGHT

        if long_bb_condition and long_rsi_condition:
            return "AL"
        if short_bb_condition and short_rsi_condition:
            return "SAT"
        return "BEKLE"

    def _calculate_mr_confidence(self, data: pd.DataFrame,
                               indicators: Dict[str, Any],
                               signal: str) -> float:
        """Mean reversion confidence hesaplama"""
        if signal == "BEKLE":
            return 0.0

        rsi = indicators.get('rsi', 50.0)
        bb_upper = indicators.get('bb_upper', data['close'].iloc[-1] * 1.02)
        bb_lower = indicators.get('bb_lower', data['close'].iloc[-1] * 0.98)
        current_price = data['close'].iloc[-1]

        # BB position strength (0-1)
        bb_range = bb_upper - bb_lower
        if signal == "AL":
            # Distance below lower band
            bb_strength = max(0, (bb_lower - current_price) / (bb_range * 0.2))
            rsi_strength = max(0, (40 - rsi) / 10)  # More oversold = higher strength
        else:  # SAT
            # Distance above upper band
            bb_strength = max(0, (current_price - bb_upper) / (bb_range * 0.2))
            rsi_strength = max(0, (rsi - 60) / 10)  # More overbought = higher strength

        # Weighted confidence
        confidence = min(1.0, (bb_strength * 0.6 + rsi_strength * 0.4))
        return max(0.1, confidence)  # Minimum confidence

    def _get_bb_position_mr(self, data: pd.DataFrame, indicators: Dict[str, Any]) -> str:
        """BB position for MR strategy"""
        bb_upper = indicators.get('bb_upper', data['close'].iloc[-1] * 1.02)
        bb_lower = indicators.get('bb_lower', data['close'].iloc[-1] * 0.98)
        current_price = data['close'].iloc[-1]

        bb_range = bb_upper - bb_lower
        if current_price <= bb_lower + 0.1 * bb_range:
            return "extreme_lower"
        if current_price >= bb_upper - 0.1 * bb_range:
            return "extreme_upper"
        if current_price <= bb_lower + 0.3 * bb_range:
            return "lower_zone"
        if current_price >= bb_upper - 0.3 * bb_range:
            return "upper_zone"
        return "middle_zone"

    def calculate_position_size(self, signal: SpecialistSignal,
                              risk_per_trade: float,
                              atr: float) -> float:
        """
        S2 position sizing - mean reversion specific
        """
        if signal.signal == "BEKLE":
            return 0.0

        # Base size from risk/ATR (tighter stops for MR)
        base_size = risk_per_trade / (atr * SL_ATR_MULT)

        # Confidence scaling
        confidence_multiplier = signal.confidence

        # MR specific: smaller size due to lower win rate
        mr_multiplier = 0.75  # Conservative sizing for MR

        return base_size * confidence_multiplier * mr_multiplier

    def get_performance_metrics(self) -> Dict[str, float]:
        """S2 performance metrikleri"""
        win_rate = self.win_count / self.trade_count if self.trade_count > 0 else 0.0
        avg_return = self.cumulative_return / self.trade_count if self.trade_count > 0 else 0.0

        return {
            "total_signals": float(self.total_signals),
            "trade_count": float(self.trade_count),
            "win_rate": win_rate,
            "cumulative_return": self.cumulative_return,
            "avg_return": avg_return,
            "profit_factor": 1.0 + max(0, avg_return),
            "specialist_id": 2.0  # S2 identifier
        }

    def update_trade_result(self, r_multiple: float):
        """Trade sonucu guncelleme (external cagri icin)"""
        self.trade_count += 1
        self.cumulative_return += r_multiple
        if r_multiple > 0:
            self.win_count += 1

    def __str__(self) -> str:
        return f"S2: Range MR (signals: {self.total_signals}, trades: {self.trade_count})"
