"""
S1: Trend Pullback/Breakout Specialist - A31 Implementation
=========================================================

Amac: Mevcut PB/BO stratejisini Meta-Router uyumlu hale getirmek.
Plan: SSoT A31'de tanimlanan S1 uzmani - trend + squeeze-breakout mantigi.

Gating Rules:
- TrendScore≥0.35 ve (SqueezeScore≥0.5 veya ADX≥18)
- Trend ortamlarinda aktif
"""

import logging
from typing import Any, Dict

import pandas as pd

from .specialist_interface import GatingScores, SpecialistInterface, SpecialistSignal

logger = logging.getLogger(__name__)


class TrendPBBOSpecialist(SpecialistInterface):
    """
    S1: Trend Pullback/Breakout Uzmani
    Mevcut confluence tabanli stratejiyi implement eder
    """

    def __init__(self):
        self._specialist_id = "S1"
        self._specialist_name = "Trend PB/BO"

        # Performance tracking
        self.total_signals = 0
        self.trade_count = 0
        self.win_count = 0
        self.cumulative_return = 0.0

    @property
    def specialist_id(self) -> str:
        return "S1"

    @property
    def specialist_name(self) -> str:
        return "Trend PB/BO"

    def is_gated(self, scores: GatingScores) -> bool:
        """
        S1 Gating Rules:
        - TrendScore≥0.35 ve (SqueezeScore≥0.5 veya ADX≥18)
        """
        trend_ok = scores.trend_score >= 0.35
        squeeze_or_strong_trend = (scores.squeeze_score >= 0.5 or
                                  scores.trend_score >= 0.45)  # ADX≥18 approximation

        is_active = trend_ok and squeeze_or_strong_trend

        if is_active:
            logger.debug(f"S1 aktif: trend={scores.trend_score:.3f}, "
                        f"squeeze={scores.squeeze_score:.3f}")

        return is_active

    def generate_signal(self, symbol: str, data: pd.DataFrame,
                       indicators: Dict[str, Any]) -> SpecialistSignal:
        """
        S1 sinyal uretimi - mevcut confluence mantigi
        """
        self.total_signals += 1

        try:
            # Mevcut confluence scoring sistemini kullan
            signal, confidence = self._calculate_confluence_signal(data, indicators)

            # Metadata olustur
            metadata = {
                "specialist": "S1_trend_pb_bo",
                "symbol": symbol,
                "rsi": indicators.get('rsi', 50.0),
                "macd": indicators.get('macd', 0.0),
                "bb_position": self._get_bb_position(data, indicators),
                "adx": indicators.get('adx', 20.0),
                "entry_reason": f"confluence_score_{confidence:.2f}"
            }

            return SpecialistSignal(
                signal=signal,
                confidence=confidence,
                metadata=metadata
            )

        except Exception as e:
            logger.error(f"S1 sinyal hatasi {symbol}: {e}")
            # Safe fallback
            return SpecialistSignal(
                signal="BEKLE",
                confidence=0.0,
                metadata={"error": str(e), "specialist": "S1_trend_pb_bo"}
            )

    def _calculate_confluence_signal(self, data: pd.DataFrame,
                                   indicators: Dict[str, Any]) -> tuple[str, float]:
        """
        Confluence tabanli sinyal hesaplama
        Mevcut indicators.py score_indicators mantigini taklit eder
        """
        rsi = indicators.get('rsi', 50.0)
        macd = indicators.get('macd', 0.0)
        macd_signal = indicators.get('macd_signal', 0.0)
        bb_upper = indicators.get('bb_upper', data['close'].iloc[-1] * 1.02)
        bb_lower = indicators.get('bb_lower', data['close'].iloc[-1] * 0.98)
        adx = indicators.get('adx', 20.0)

        current_price = data['close'].iloc[-1]

        # RSI component (oversold/overbought bias)
        if rsi <= 30:
            rsi_score = 1.0  # Strong buy
        elif rsi <= 40:
            rsi_score = 0.5
        elif rsi >= 70:
            rsi_score = -1.0  # Strong sell
        elif rsi >= 60:
            rsi_score = -0.5
        else:
            rsi_score = 0.0  # Neutral

        # MACD component
        macd_diff = macd - macd_signal
        if macd_diff > 0 and macd > 0:
            macd_score = 1.0
        elif macd_diff > 0:
            macd_score = 0.5
        elif macd_diff < 0 and macd < 0:
            macd_score = -1.0
        elif macd_diff < 0:
            macd_score = -0.5
        else:
            macd_score = 0.0

        # Bollinger Bands component
        bb_range = bb_upper - bb_lower
        bb_middle = (bb_upper + bb_lower) / 2

        if current_price <= bb_lower + 0.1 * bb_range:
            bb_score = 1.0  # Near lower band
        elif current_price <= bb_middle:
            bb_score = 0.5
        elif current_price >= bb_upper - 0.1 * bb_range:
            bb_score = -1.0  # Near upper band
        elif current_price >= bb_middle:
            bb_score = -0.5
        else:
            bb_score = 0.0

        # ADX strength filter
        adx_multiplier = min(1.0, adx / 25.0)  # Normalize to 25

        # Weighted confluence score
        confluence = (rsi_score * 0.4 + macd_score * 0.4 + bb_score * 0.2) * adx_multiplier

        # Signal decision with selectivity threshold
        selectivity_threshold = 0.75  # SSoT'de 75+ selectivity hedefi

        if confluence >= selectivity_threshold:
            signal = "AL"
            confidence = min(1.0, confluence)
        elif confluence <= -selectivity_threshold:
            signal = "SAT"
            confidence = min(1.0, abs(confluence))
        else:
            signal = "BEKLE"
            confidence = 0.5 - abs(confluence) / 2  # Lower confidence for HOLD

        return signal, confidence

    def _get_bb_position(self, data: pd.DataFrame, indicators: Dict[str, Any]) -> str:
        """Bollinger Bands pozisyon belirleme"""
        bb_upper = indicators.get('bb_upper', data['close'].iloc[-1] * 1.02)
        bb_lower = indicators.get('bb_lower', data['close'].iloc[-1] * 0.98)
        current_price = data['close'].iloc[-1]

        bb_range = bb_upper - bb_lower
        if current_price <= bb_lower + 0.2 * bb_range:
            return "lower"
        if current_price >= bb_upper - 0.2 * bb_range:
            return "upper"
        return "middle"

    def calculate_position_size(self, signal: SpecialistSignal,
                              risk_per_trade: float,
                              atr: float) -> float:
        """
        S1 position sizing - standard ATR based
        """
        if signal.signal == "BEKLE":
            return 0.0

        # Base size from risk/ATR
        base_size = risk_per_trade / (atr * 2.0)  # 2 ATR stop

        # Confidence scaling
        confidence_multiplier = signal.confidence

        return base_size * confidence_multiplier

    def get_performance_metrics(self) -> Dict[str, float]:
        """S1 performance metrikleri"""
        win_rate = self.win_count / self.trade_count if self.trade_count > 0 else 0.0
        avg_return = self.cumulative_return / self.trade_count if self.trade_count > 0 else 0.0

        return {
            "total_signals": float(self.total_signals),
            "trade_count": float(self.trade_count),
            "win_rate": win_rate,
            "cumulative_return": self.cumulative_return,
            "avg_return": avg_return,
            "profit_factor": 1.0 + max(0, avg_return),  # Simplified PF
            "specialist_id": 1.0  # S1 identifier
        }

    def update_trade_result(self, r_multiple: float):
        """Trade sonucu guncelleme (external cagri icin)"""
        self.trade_count += 1
        self.cumulative_return += r_multiple
        if r_multiple > 0:
            self.win_count += 1

    def __str__(self) -> str:
        return f"S1: Trend PB/BO (signals: {self.total_signals}, trades: {self.trade_count})"
