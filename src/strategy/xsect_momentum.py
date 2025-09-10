"""
S4: Cross-Sectional Momentum Specialist - A31 Implementation
==========================================================

Amaç: Top150 evreninde momentum ranking ile relative strength signals.
Plan: SSoT A31'de tanimlanan S4 uzmani - cross-sectional momentum mantigi.

Gating Rules:
- Gunluk rebalance saatinde (00:00 UTC)
- Top150 momentum hesaplama ile aktif
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Tuple

import pandas as pd

from .specialist_interface import GatingScores, SpecialistInterface, SpecialistSignal

logger = logging.getLogger(__name__)

# S4 Constants
LOOKBACK_HOURS = [3, 6, 12]
REBALANCE_HOUR = 0  # UTC
MAX_POSITION_PCT = 0.10
MOMENTUM_TOP_PERCENTILE = 80  # Top 20%
MOMENTUM_BOTTOM_PERCENTILE = 20  # Bottom 20%


class XSectMomSpecialist(SpecialistInterface):
    """
    S4: Cross-Sectional Momentum Uzmani
    Top150 momentum ranking ve risk parite allocation
    """

    def __init__(self):
        self._specialist_id = "S4"
        self._specialist_name = "XSect Mom"

        # Performance tracking
        self.total_signals = 0
        self.trade_count = 0
        self.win_count = 0
        self.cumulative_return = 0.0

        # Momentum state
        self.last_momentum_update = None
        self.momentum_rankings = {}
        self.universe_symbols = []

    @property
    def specialist_id(self) -> str:
        return "S4"

    @property
    def specialist_name(self) -> str:
        return "XSect Mom"

    def is_gated(self, scores: GatingScores) -> bool:
        """
        S4 Gating Rules:
        - Gunluk rebalance saatinde aktif (00:00 UTC)
        """
        current_hour = datetime.utcnow().hour
        is_rebalance_time = current_hour == REBALANCE_HOUR

        if is_rebalance_time:
            logger.debug(f"S4 aktif: rebalance saati ({current_hour}:00 UTC)")

        return is_rebalance_time

    def generate_signal(self, symbol: str, data: pd.DataFrame,
                       indicators: Dict[str, Any]) -> SpecialistSignal:
        """
        S4 sinyal uretimi - momentum ranking mantigi
        """
        self.total_signals += 1

        try:
            # Momentum hesapla
            momentum_score = self._calculate_momentum_score(symbol, data)

            # Signal belirle
            signal, confidence = self._determine_momentum_signal(
                symbol, momentum_score, data, indicators
            )

            # Metadata olustur
            metadata = {
                "specialist": "S4_xsect_mom",
                "symbol": symbol,
                "momentum_score": momentum_score,
                "momentum_percentile": self._get_momentum_percentile(symbol),
                "volatility": self._calculate_volatility(data),
                "entry_reason": f"momentum_rank_{confidence:.2f}"
            }

            return SpecialistSignal(
                signal=signal,
                confidence=confidence,
                metadata=metadata
            )

        except Exception as e:
            logger.error(f"S4 sinyal hatasi {symbol}: {e}")
            return SpecialistSignal(
                signal="BEKLE",
                confidence=0.0,
                metadata={"error": str(e), "specialist": "S4_xsect_mom"}
            )

    def _calculate_momentum_score(self, symbol: str, data: pd.DataFrame) -> float:
        """
        Composite momentum score (3h, 6h, 12h)
        """
        try:
            scores = []

            for hours in LOOKBACK_HOURS:
                periods = hours  # Assuming 1h timeframe
                if len(data) >= periods + 1:
                    current_price = data['close'].iloc[-1]
                    past_price = data['close'].iloc[-(periods + 1)]
                    return_pct = (current_price - past_price) / past_price
                    scores.append(return_pct)
                else:
                    scores.append(0.0)  # Insufficient data

            # Weighted composite: 3h=0.5, 6h=0.3, 12h=0.2
            if len(scores) == 3:
                composite = scores[0] * 0.5 + scores[1] * 0.3 + scores[2] * 0.2
            else:
                composite = 0.0

            return composite

        except Exception as e:
            logger.warning(f"Momentum hesaplama hatasi {symbol}: {e}")
            return 0.0

    def _get_momentum_percentile(self, symbol: str) -> float:
        """Symbol's momentum percentile in universe"""
        if symbol in self.momentum_rankings:
            return self.momentum_rankings[symbol]
        return 50.0  # Neutral if not ranked

    def _determine_momentum_signal(self, symbol: str, momentum_score: float,
                                 data: pd.DataFrame,
                                 indicators: Dict[str, Any]) -> Tuple[str, float]:
        """Momentum signal belirleme"""
        percentile = self._get_momentum_percentile(symbol)

        # Long signals: top momentum (>80th percentile)
        if percentile >= MOMENTUM_TOP_PERCENTILE:
            signal = "AL"
            confidence = min(1.0, (percentile - 80) / 20)  # Scale 80-100 to 0-1

        # Short signals: bottom momentum (<20th percentile)
        elif percentile <= MOMENTUM_BOTTOM_PERCENTILE:
            signal = "SAT"
            confidence = min(1.0, (20 - percentile) / 20)  # Scale 0-20 to 1-0

        else:
            signal = "BEKLE"
            confidence = 0.0

        return signal, confidence

    def _calculate_volatility(self, data: pd.DataFrame) -> float:
        """Symbol volatility (for risk parity)"""
        try:
            returns = data['close'].pct_change().dropna()
            if len(returns) >= 20:
                return returns.rolling(20).std().iloc[-1]
            return 0.02  # Default 2% volatility
        except (IndexError, KeyError, ValueError, AttributeError):
            return 0.02

    def update_momentum_rankings(self, universe_data: Dict[str, pd.DataFrame]):
        """
        Gunluk momentum ranking guncelleme
        External cagri - DataFetcher'dan gelen universe verileri
        """
        try:
            symbol_scores = {}

            for symbol, data in universe_data.items():
                momentum = self._calculate_momentum_score(symbol, data)
                symbol_scores[symbol] = momentum

            # Percentile rankings hesapla
            sorted_symbols = sorted(symbol_scores.items(), key=lambda x: x[1])
            total_symbols = len(sorted_symbols)

            self.momentum_rankings = {}
            for i, (symbol, score) in enumerate(sorted_symbols):
                percentile = (i / total_symbols) * 100
                self.momentum_rankings[symbol] = percentile

            self.universe_symbols = list(symbol_scores.keys())
            self.last_momentum_update = datetime.utcnow()

            logger.info(f"S4 momentum rankings guncellendi: {total_symbols} sembol")

        except Exception as e:
            logger.error(f"S4 momentum ranking hatasi: {e}")

    def get_top_momentum_symbols(self, count: int = 10) -> List[str]:
        """En yuksek momentum sembollerini getir"""
        sorted_rankings = sorted(
            self.momentum_rankings.items(),
            key=lambda x: x[1],
            reverse=True
        )
        return [symbol for symbol, _ in sorted_rankings[:count]]

    def calculate_position_size(self, signal: SpecialistSignal,
                              risk_per_trade: float,
                              atr: float) -> float:
        """
        S4 position sizing - risk parity approach
        """
        if signal.signal == "BEKLE":
            return 0.0

        # Base risk allocation
        base_risk = risk_per_trade

        # Risk parity adjustment (inverse volatility weighting)
        volatility = signal.metadata.get('volatility', 0.02)
        volatility_adj = 0.02 / max(0.005, volatility)  # Normalize to 2% vol

        # Position size with max constraint
        risk_adj_size = base_risk * volatility_adj
        max_size = risk_per_trade / MAX_POSITION_PCT  # Max 10% of total risk

        position_size = min(risk_adj_size, max_size)

        # Confidence scaling
        confidence_multiplier = signal.confidence

        return position_size * confidence_multiplier

    def get_performance_metrics(self) -> Dict[str, float]:
        """S4 performance metrikleri"""
        win_rate = self.win_count / self.trade_count if self.trade_count > 0 else 0.0
        avg_return = self.cumulative_return / self.trade_count if self.trade_count > 0 else 0.0

        return {
            "total_signals": float(self.total_signals),
            "trade_count": float(self.trade_count),
            "win_rate": win_rate,
            "cumulative_return": self.cumulative_return,
            "avg_return": avg_return,
            "profit_factor": 1.0 + max(0, avg_return),
            "specialist_id": 4.0,  # S4 identifier
            "universe_size": float(len(self.universe_symbols)),
            "last_update_hours": self._hours_since_update()
        }

    def _hours_since_update(self) -> float:
        """Son momentum update'ten bu yana gecen saat"""
        if self.last_momentum_update:
            delta = datetime.utcnow() - self.last_momentum_update
            return delta.total_seconds() / 3600
        return 999.0  # Never updated

    def update_trade_result(self, r_multiple: float):
        """Trade sonucu guncelleme (external cagri icin)"""
        self.trade_count += 1
        self.cumulative_return += r_multiple
        if r_multiple > 0:
            self.win_count += 1

    def __str__(self) -> str:
        return f"S4: XSect Mom (signals: {self.total_signals}, universe: {len(self.universe_symbols)})"
