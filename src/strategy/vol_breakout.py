"""
S3: Volume Breakout Specialist - A31 Implementation
=================================================

Amaç: Donchian breakout + volume/ATR confirmation ile momentum capture.
Plan: SSoT A31'de tanimlanan S3 uzmani - vol breakout mantigi.

Gating Rules:
- SqueezeScore≥0.6 ve hacim≥median×1.2
- Volatilite expansion ortamlarinda aktif
"""

import logging
from typing import Any, Dict

import pandas as pd

from .specialist_interface import GatingScores, SpecialistInterface, SpecialistSignal

logger = logging.getLogger(__name__)

# S3 Constants
SQUEEZE_MIN_THRESHOLD = 0.6
DONCHIAN_PERIODS = 20
ATR_MIN_MULT = 1.1
TARGET_R = 2.0
SL_ATR_MULT = 1.2
VOLUME_MIN_MULT = 1.2


class VolBreakoutSpecialist(SpecialistInterface):
    """
    S3: Volume Breakout Uzmani
    Donchian + ATR/volume breakout sinyalleri
    """

    def __init__(self):
        self._specialist_id = "S3"
        self._specialist_name = "Vol Breakout"

        # Performance tracking
        self.total_signals = 0
        self.trade_count = 0
        self.win_count = 0
        self.cumulative_return = 0.0

    @property
    def specialist_id(self) -> str:
        return "S3"

    @property
    def specialist_name(self) -> str:
        return "Vol Breakout"

    def is_gated(self, scores: GatingScores) -> bool:
        """
        S3 Gating Rules:
        - SqueezeScore≥0.6 ve hacim≥median×1.2
        """
        squeeze_ok = scores.squeeze_score >= SQUEEZE_MIN_THRESHOLD
        volume_ok = scores.volume_score >= VOLUME_MIN_MULT

        is_active = squeeze_ok and volume_ok

        if is_active:
            logger.debug(f"S3 aktif: squeeze={scores.squeeze_score:.3f}, "
                        f"volume={scores.volume_score:.3f}")

        return is_active

    def generate_signal(self, symbol: str, data: pd.DataFrame,
                       indicators: Dict[str, Any]) -> SpecialistSignal:
        """
        S3 sinyal uretimi - volume breakout mantigi
        """
        self.total_signals += 1

        try:
            signal, confidence = self._calculate_breakout_signal(data, indicators)

            # Metadata olustur
            metadata = {
                "specialist": "S3_vol_breakout",
                "symbol": symbol,
                "donchian_position": self._get_donchian_position(data, indicators),
                "atr": indicators.get('atr', 0.01),
                "volume_ratio": self._get_volume_ratio(data),
                "entry_reason": f"volume_breakout_{confidence:.2f}"
            }

            return SpecialistSignal(
                signal=signal,
                confidence=confidence,
                metadata=metadata
            )

        except Exception as e:
            logger.error(f"S3 sinyal hatasi {symbol}: {e}")
            return SpecialistSignal(
                signal="BEKLE",
                confidence=0.0,
                metadata={"error": str(e), "specialist": "S3_vol_breakout"}
            )

    def _calculate_breakout_signal(self, data: pd.DataFrame,
                                 indicators: Dict[str, Any]) -> tuple[str, float]:
        """
        Volume breakout sinyal hesaplama
        """
        signal = self._determine_breakout_signal(data, indicators)
        confidence = self._calculate_breakout_confidence(data, indicators, signal)

        return signal, confidence

    def _determine_breakout_signal(self, data: pd.DataFrame,
                                 indicators: Dict[str, Any]) -> str:
        """Donchian breakout sinyal belirleme"""
        current_price = data['close'].iloc[-1]
        atr = indicators.get('atr', 0.01)

        # Calculate Donchian channels
        donchian_upper = self._calculate_donchian_upper(data)
        donchian_lower = self._calculate_donchian_lower(data)

        # ATR median over 20 periods for volatility filter
        atr_median = data['close'].rolling(20).std().median() * 0.02  # Approximation
        atr_threshold = atr_median * ATR_MIN_MULT

        # Volume confirmation
        volume_ratio = self._get_volume_ratio(data)
        volume_confirmed = volume_ratio >= VOLUME_MIN_MULT

        # Volatility confirmation
        vol_confirmed = atr >= atr_threshold

        # Breakout conditions
        long_breakout = current_price > donchian_upper
        short_breakout = current_price < donchian_lower

        # Combined conditions
        if long_breakout and vol_confirmed and volume_confirmed:
            return "AL"
        if short_breakout and vol_confirmed and volume_confirmed:
            return "SAT"
        return "BEKLE"

    def _calculate_donchian_upper(self, data: pd.DataFrame) -> float:
        """Donchian channel upper band"""
        return data['high'].rolling(DONCHIAN_PERIODS).max().iloc[-1]

    def _calculate_donchian_lower(self, data: pd.DataFrame) -> float:
        """Donchian channel lower band"""
        return data['low'].rolling(DONCHIAN_PERIODS).min().iloc[-1]

    def _get_volume_ratio(self, data: pd.DataFrame) -> float:
        """Current volume vs 20-bar median"""
        if 'volume' not in data.columns:
            return 1.0  # Fallback if no volume data

        current_volume = data['volume'].iloc[-1]
        volume_median = data['volume'].rolling(20).median().iloc[-1]

        if volume_median > 0:
            return current_volume / volume_median
        return 1.0

    def _calculate_breakout_confidence(self, data: pd.DataFrame,
                                     indicators: Dict[str, Any],
                                     signal: str) -> float:
        """Volume breakout confidence hesaplama"""
        if signal == "BEKLE":
            return 0.0

        current_price = data['close'].iloc[-1]
        donchian_upper = self._calculate_donchian_upper(data)
        donchian_lower = self._calculate_donchian_lower(data)
        volume_ratio = self._get_volume_ratio(data)
        atr = indicators.get('atr', 0.01)

        # Breakout strength (distance beyond channel)
        if signal == "AL":
            breakout_strength = (current_price - donchian_upper) / (atr * 0.5)
        else:  # SAT
            breakout_strength = (donchian_lower - current_price) / (atr * 0.5)

        # Volume strength (excess above median)
        volume_strength = min(1.0, (volume_ratio - 1.0) / 1.0)  # Normalize to 0-1

        # ATR strength approximation
        recent_atr = data['close'].rolling(5).std().iloc[-1] * 0.02
        long_atr = data['close'].rolling(20).std().iloc[-1] * 0.02
        atr_strength = min(1.0, recent_atr / long_atr) if long_atr > 0 else 0.5

        # Weighted confidence
        confidence = min(1.0, (
            breakout_strength * 0.4 +
            volume_strength * 0.4 +
            atr_strength * 0.2
        ))

        return max(0.1, confidence)

    def _get_donchian_position(self, data: pd.DataFrame, indicators: Dict[str, Any]) -> str:
        """Donchian channel position"""
        current_price = data['close'].iloc[-1]
        donchian_upper = self._calculate_donchian_upper(data)
        donchian_lower = self._calculate_donchian_lower(data)
        donchian_middle = (donchian_upper + donchian_lower) / 2

        if current_price > donchian_upper:
            return "above_upper"
        if current_price < donchian_lower:
            return "below_lower"
        if current_price > donchian_middle:
            return "upper_half"
        return "lower_half"

    def calculate_position_size(self, signal: SpecialistSignal,
                              risk_per_trade: float,
                              atr: float) -> float:
        """
        S3 position sizing - breakout specific
        """
        if signal.signal == "BEKLE":
            return 0.0

        # Base size from risk/ATR (wider stops for breakouts)
        base_size = risk_per_trade / (atr * SL_ATR_MULT)

        # Confidence scaling
        confidence_multiplier = signal.confidence

        # Breakout specific: larger size due to momentum
        breakout_multiplier = 1.1  # Slightly aggressive for momentum

        return base_size * confidence_multiplier * breakout_multiplier

    def get_performance_metrics(self) -> Dict[str, float]:
        """S3 performance metrikleri"""
        win_rate = self.win_count / self.trade_count if self.trade_count > 0 else 0.0
        avg_return = self.cumulative_return / self.trade_count if self.trade_count > 0 else 0.0

        return {
            "total_signals": float(self.total_signals),
            "trade_count": float(self.trade_count),
            "win_rate": win_rate,
            "cumulative_return": self.cumulative_return,
            "avg_return": avg_return,
            "profit_factor": 1.0 + max(0, avg_return),
            "specialist_id": 3.0  # S3 identifier
        }

    def update_trade_result(self, r_multiple: float):
        """Trade sonucu guncelleme (external cagri icin)"""
        self.trade_count += 1
        self.cumulative_return += r_multiple
        if r_multiple > 0:
            self.win_count += 1

    def __str__(self) -> str:
        return f"S3: Vol Breakout (signals: {self.total_signals}, trades: {self.trade_count})"
