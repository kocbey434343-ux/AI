"""
A31 Meta-Router & Ensemble System (A31 Implementation)
==================================================

Amac: 4 uzman stratejiyi koordine etmek ve MWU learning ile adaptif agirlik.
Plan: SSoT A31 bolumunde detaylandirilan ensemble system.

Sistem Bilesenleri:
- SpecialistRegistry: Uzman kayit ve yonetim
- MWULearner: Multiplicative Weight Update algoritmasi
- MetaRouter: Ana orchestrator sinifi
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from .specialist_interface import (
    GatingScores,
    SpecialistInterface,
    SpecialistSignal,
    calculate_gating_scores,
)

logger = logging.getLogger(__name__)

# Constants
MIN_TRADES_FOR_OOS = 5  # Minimum trade sayisi for OOS guard


@dataclass
class SpecialistWeight:
    """Uzman agirlik ve performans izleme"""
    specialist_id: str
    weight: float = 0.25  # Baslangic esit agirlik (4 uzman icin)
    last_return: float = 0.0  # Son trade return'u (R-multiple)
    cumulative_return: float = 0.0  # Kumulatif return
    trade_count: int = 0
    win_count: int = 0

    # OOS (Out-of-Sample) guard icin
    recent_profit_factor: float = 1.0
    last_updated: datetime = field(default_factory=datetime.now)

    @property
    def win_rate(self) -> float:
        """Win rate hesaplama"""
        return self.win_count / self.trade_count if self.trade_count > 0 else 0.0

    def update_performance(self, trade_return: float):
        """Performans guncelleme"""
        self.last_return = trade_return
        self.cumulative_return += trade_return
        self.trade_count += 1
        if trade_return > 0:
            self.win_count += 1
        self.last_updated = datetime.now()


@dataclass
class MWUConfig:
    """MWU algoritmasi konfigurasyonu"""
    eta: float = 0.10  # Learning rate
    min_weight: float = 0.10  # Minimum agirlik
    max_weight: float = 0.60  # Maximum agirlik
    window_bars: int = 24  # Guncelleme penceresi
    oos_window_days: int = 14  # OOS guard penceresi
    min_profit_factor: float = 1.10  # OOS minimum PF


class MWULearner:
    """
    Multiplicative Weight Update Algoritmasi
    Her uzman icin adaptif agirlik ogrenme
    """

    def __init__(self, config: MWUConfig):
        self.config = config
        self.weights: Dict[str, SpecialistWeight] = {}
        self.update_counter = 0

    def register_specialist(self, specialist_id: str):
        """Yeni uzman kaydet"""
        if specialist_id not in self.weights:
            self.weights[specialist_id] = SpecialistWeight(specialist_id=specialist_id)
            self._normalize_weights()

    def update_weights(self, returns: Dict[str, float]):
        """
        MWU agirlik guncelleme

        Args:
            returns: {specialist_id: r_multiple} dict'i
        """
        self.update_counter += 1

        # Her uzman icin MWU guncelleme
        for specialist_id, trade_return in returns.items():
            if specialist_id in self.weights:
                weight_obj = self.weights[specialist_id]

                # Performance guncelleme
                weight_obj.update_performance(trade_return)

                # MWU: w_{t+1} = w_t * exp(eta * r_t)
                new_weight = weight_obj.weight * np.exp(self.config.eta * trade_return)
                weight_obj.weight = new_weight

        # Normalizasyon ve clamp
        self._normalize_weights()
        self._apply_bounds()

        # OOS guard kontrolu
        self._apply_oos_guard()

        logger.info(f"MWU guncelleme #{self.update_counter}: {self.get_weight_summary()}")

    def _normalize_weights(self):
        """Agirlik normalize et (toplam = 1.0)"""
        total_weight = sum(w.weight for w in self.weights.values())
        if total_weight > 0:
            for weight_obj in self.weights.values():
                weight_obj.weight /= total_weight

    def _apply_bounds(self):
        """Min/max agirlik sinirlarini uygula"""
        for weight_obj in self.weights.values():
            weight_obj.weight = max(self.config.min_weight,
                                  min(self.config.max_weight, weight_obj.weight))

        # Tekrar normalize (bounds sonrasi)
        self._normalize_weights()

    def _apply_oos_guard(self):
        """Out-of-Sample guard: dusuk performans uzmanlari minimize et"""
        current_time = datetime.now()

        for weight_obj in self.weights.values():
            # Son 14 gun icinde yeterli trade var mi?
            days_since_update = (current_time - weight_obj.last_updated).days

            if (days_since_update <= self.config.oos_window_days and
                weight_obj.trade_count >= MIN_TRADES_FOR_OOS and  # Minimum trade sayisi
                weight_obj.recent_profit_factor < self.config.min_profit_factor):

                # Dusuk performans: min_weight'e sabitle
                weight_obj.weight = self.config.min_weight
                logger.warning(f"OOS guard: {weight_obj.specialist_id} agirligi minimize edildi "
                             f"(PF: {weight_obj.recent_profit_factor:.2f})")

        # Final normalizasyon
        self._normalize_weights()

    def get_current_weights(self) -> Dict[str, float]:
        """Guncel agirlik dict'i dondur"""
        return {sid: w.weight for sid, w in self.weights.items()}

    def get_weights(self) -> Dict[str, float]:
        """Alias for get_current_weights"""
        return self.get_current_weights()

    def get_weight_summary(self) -> str:
        """Agirlik ozeti string"""
        summary: List[str] = []
        for sid, weight_obj in self.weights.items():
            summary.append(f"{sid}:{weight_obj.weight:.3f}")
        return ", ".join(summary)


class SpecialistRegistry:
    """Uzman strateji kayit ve yonetim"""

    def __init__(self):
        self.specialists: Dict[str, SpecialistInterface] = {}

    def register(self, specialist: SpecialistInterface):
        """Uzman kaydet"""
        specialist_id = specialist.specialist_id
        self.specialists[specialist_id] = specialist
        logger.info(f"Uzman kaydedildi: {specialist}")

    def register_specialist(self, specialist_id: str, specialist: SpecialistInterface):
        """Uzman kaydet (ID ile)"""
        self.specialists[specialist_id] = specialist
        logger.info(f"Uzman kaydedildi: {specialist_id} -> {specialist}")

    def get_specialist(self, specialist_id: str) -> Optional[SpecialistInterface]:
        """Uzman getir"""
        return self.specialists.get(specialist_id)

    def get_active_specialists(self, gating_scores: GatingScores) -> List[SpecialistInterface]:
        """Aktif uzman listesi (gating kurallarina gore)"""
        active: List[SpecialistInterface] = []
        for specialist in self.specialists.values():
            if specialist.is_gated(gating_scores):
                active.append(specialist)
        return active

    def list_all(self) -> List[str]:
        """Tum uzman ID'leri"""
        return list(self.specialists.keys())


@dataclass
class EnsembleSignal:
    """Ensemble sinyal sonucu"""
    final_signal: str  # "AL", "SAT", "BEKLE"
    confidence: float  # Agirlikli guven skoru
    active_specialists: List[str]  # Aktif uzman ID'leri
    specialist_signals: Dict[str, SpecialistSignal]  # Bireysel sinyaller
    weights_used: Dict[str, float]  # Kullanilan agirliklar
    gating_scores: GatingScores  # Market rejim skorlari

    def get_signal_breakdown(self) -> str:
        """Sinyal detay ozeti"""
        breakdown: List[str] = []
        for sid, signal in self.specialist_signals.items():
            weight = self.weights_used.get(sid, 0.0)
            breakdown.append(f"{sid}:{signal.signal}({weight:.2f})")
        return " | ".join(breakdown)


class MetaRouter:
    """
    Meta-Router Ana Orchestrator
    4 uzman stratejiyi koordine eder ve ensemble karar verir
    """

    def __init__(self, mwu_config: Optional[MWUConfig] = None):
        self.registry = SpecialistRegistry()
        self.mwu = MWULearner(mwu_config or MWUConfig())
        self.enabled = False  # Feature flag

        # Istatistikler
        self.total_signals = 0
        self.ensemble_decisions = {"AL": 0, "SAT": 0, "BEKLE": 0}

    def enable(self):
        """Meta-Router'i etkinlestir"""
        self.enabled = True
        logger.info("Meta-Router aktif edildi")

    def disable(self):
        """Meta-Router'i devre disi birak"""
        self.enabled = False
        logger.info("Meta-Router devre disi birakildi")

    def register_specialist(self, specialist: SpecialistInterface):
        """Uzman kaydet ve MWU'ya ekle"""
        self.registry.register(specialist)
        self.mwu.register_specialist(specialist.specialist_id)

    def generate_ensemble_signal(self, symbol: str, data: pd.DataFrame,
                                indicators: Dict[str, Any]) -> EnsembleSignal:
        """
        Ana ensemble sinyal uretim metodu

        Args:
            symbol: Sembol adi
            data: OHLCV DataFrame
            indicators: Hesaplanmis indikatorler

        Returns:
            EnsembleSignal: Ensemble karar + metadata
        """
        self.total_signals += 1

        if not self.enabled:
            # Meta-Router kapali: fallback to BEKLE
            return EnsembleSignal(
                final_signal="BEKLE",
                confidence=0.0,
                active_specialists=[],
                specialist_signals={},
                weights_used={},
                gating_scores=GatingScores(0.5, 0.5, 0.5, 0.0, 1.0)
            )

        # 1. Market rejim skorlari hesapla
        gating_scores = calculate_gating_scores(data, indicators)

        # 2. Aktif uzmanlari belirle
        active_specialists = self.registry.get_active_specialists(gating_scores)

        if not active_specialists:
            # Hic aktif uzman yok
            return EnsembleSignal(
                final_signal="BEKLE",
                confidence=0.0,
                active_specialists=[],
                specialist_signals={},
                weights_used={},
                gating_scores=gating_scores
            )

        # 3. Aktif uzmanlardan sinyal topla
        specialist_signals: Dict[str, SpecialistSignal] = {}
        for specialist in active_specialists:
            try:
                signal = specialist.generate_signal(symbol, data, indicators)
                specialist_signals[specialist.specialist_id] = signal
            except Exception as e:
                logger.error(f"Uzman {specialist.specialist_id} sinyal hatasi: {e}")
                # Hatali uzman atla
                continue

        # 4. Ensemble karar verme
        ensemble_result = self._make_ensemble_decision(specialist_signals, gating_scores)

        # 5. Istatistik guncelle
        self.ensemble_decisions[ensemble_result.final_signal] += 1

        return ensemble_result

    def _make_ensemble_decision(self, specialist_signals: Dict[str, SpecialistSignal],
                               gating_scores: GatingScores) -> EnsembleSignal:
        """
        Ensemble karar algoritmasi
        Agirlikli voting + confidence averaging
        """
        if not specialist_signals:
            return EnsembleSignal(
                final_signal="BEKLE",
                confidence=0.0,
                active_specialists=[],
                specialist_signals={},
                weights_used={},
                gating_scores=gating_scores
            )

        # Mevcut agirliklari al
        current_weights = self.mwu.get_current_weights()

        # Agirlikli oylama
        signal_scores = {"AL": 0.0, "SAT": 0.0, "BEKLE": 0.0}
        confidence_sum = 0.0
        total_weight = 0.0
        weights_used: Dict[str, float] = {}

        for specialist_id, signal in specialist_signals.items():
            weight = current_weights.get(specialist_id, 0.0)
            if weight > 0:
                signal_scores[signal.signal] += weight * signal.confidence
                confidence_sum += weight * signal.confidence
                total_weight += weight
                weights_used[specialist_id] = weight

        # En yuksek skorlu sinyal sec
        if total_weight > 0:
            final_signal = max(signal_scores, key=lambda k: signal_scores[k])
            final_confidence = confidence_sum / total_weight
        else:
            final_signal = "BEKLE"
            final_confidence = 0.0

        return EnsembleSignal(
            final_signal=final_signal,
            confidence=final_confidence,
            active_specialists=list(specialist_signals.keys()),
            specialist_signals=specialist_signals,
            weights_used=weights_used,
            gating_scores=gating_scores
        )

    def update_performance(self, specialist_returns: Dict[str, float]):
        """
        Uzman performanslarini guncelle (trade kapandiginda cagrilir)

        Args:
            specialist_returns: {specialist_id: r_multiple} dict'i
        """
        self.mwu.update_weights(specialist_returns)

    def get_current_weights(self) -> Dict[str, float]:
        """Guncel uzman agirliklarini dondur"""
        return self.mwu.get_current_weights()

    def get_status(self) -> Dict[str, Any]:
        """Meta-Router durum ozeti"""
        return {
            "enabled": self.enabled,
            "total_signals": self.total_signals,
            "decisions": self.ensemble_decisions.copy(),
            "registered_specialists": self.registry.list_all(),
            "current_weights": self.mwu.get_current_weights(),
            "mwu_updates": self.mwu.update_counter
        }

    def get_performance_summary(self) -> Dict[str, Dict[str, float]]:
        """Uzman performans ozeti"""
        summary: Dict[str, Dict[str, float]] = {}
        for specialist_id, weight_obj in self.mwu.weights.items():
            summary[specialist_id] = {
                "weight": weight_obj.weight,
                "cumulative_return": weight_obj.cumulative_return,
                "win_rate": weight_obj.win_rate,
                "trade_count": float(weight_obj.trade_count),
                "recent_pf": weight_obj.recent_profit_factor
            }
        return summary
