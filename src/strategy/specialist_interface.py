"""
Specialist Strategy Interface - A31 Meta-Router Foundation
========================================================

Amac: Tum uzman stratejiler icin ortak interface tanimlar.
Plan: SSoT A31 bolumunde belirtilen 4 uzman (S1-S4) icin sozlesme.

Uzmanlar:
- S1: trend_pb_bo (mevcut PB/BO cekirdegi)
- S2: range_mr (yatay mean-reversion)
- S3: vol_breakout (Donchian kirilma)
- S4: xsect_mom (Cross-sectional momentum)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict

import pandas as pd


@dataclass
class SpecialistSignal:
    """Uzman strateji sinyal verisi"""
    signal: str  # "AL", "SAT", "BEKLE"
    confidence: float  # 0.0-1.0 arasi guven skoru
    metadata: Dict[str, Any]  # Ek veri (entry_reason, stop_level, etc.)

    def __post_init__(self):
        if self.signal not in ["AL", "SAT", "BEKLE"]:
            raise ValueError(f"Gecersiz sinyal: {self.signal}")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Guven skoru 0-1 araliginda olmali: {self.confidence}")


@dataclass
class GatingScores:
    """Kapi skorlari - hangi uzmanin aktif olacagini belirler"""
    trend_score: float      # ADX bazli trend gucu (0-1)
    squeeze_score: float    # BB bandwidth squeeze (0-1)
    chop_score: float       # RSI osillasyon (0-1)
    autocorr_1h: float      # 1h otokorelasyon (-1 to +1)
    volume_score: float     # Hacim yuzdesi (0-1+)

    def __post_init__(self):
        """Skorlari 0-1 araligina klamp et"""
        for field_name in ['trend_score', 'squeeze_score', 'chop_score', 'volume_score']:
            value = getattr(self, field_name)
            setattr(self, field_name, max(0.0, min(1.0, value)))

        # Autocorr -1 to +1 araliginda
        self.autocorr_1h = max(-1.0, min(1.0, self.autocorr_1h))


class SpecialistInterface(ABC):
    """
    Uzman Strateji Soyut Sinifi
    Tum uzmanlar bu interface'i implement etmeli.
    """

    @property
    @abstractmethod
    def specialist_id(self) -> str:
        """Uzman benzersiz kimligi (S1, S2, S3, S4)"""
        pass

    @property
    @abstractmethod
    def specialist_name(self) -> str:
        """Insan okunabilir isim"""
        pass

    @abstractmethod
    def is_gated(self, scores: GatingScores) -> bool:
        """
        Kapi kurallari - bu uzman su anki market rejiminde aktif mi?

        Args:
            scores: Hesaplanan market rejim skorlari

        Returns:
            True: Uzman aktif olabilir
            False: Market rejimi uygun degil, uzman pasif
        """
        pass

    @abstractmethod
    def generate_signal(self, symbol: str, data: pd.DataFrame,
                       indicators: Dict[str, Any]) -> SpecialistSignal:
        """
        Ana sinyal uretim metodu

        Args:
            symbol: Sembol (orn: "BTCUSDT")
            data: OHLCV verisi (DataFrame)
            indicators: Hesaplanmis indikatorler dict'i

        Returns:
            SpecialistSignal: Uzman karari + metadata
        """
        pass

    @abstractmethod
    def calculate_position_size(self, signal: SpecialistSignal,
                              risk_per_trade: float,
                              atr: float) -> float:
        """
        Uzman-spesifik pozisyon boyutu hesaplama

        Args:
            signal: Uretilen sinyal
            risk_per_trade: Risk miktari (USDT)
            atr: ATR degeri

        Returns:
            Position size (base currency)
        """
        pass

    @abstractmethod
    def get_performance_metrics(self) -> Dict[str, float]:
        """
        Uzman performans metrikleri (MWU icin)

        Returns:
            Dict: {"profit_factor": 1.2, "win_rate": 0.65, "sharpe": 0.8, ...}
        """
        pass

    def validate_data(self, data: pd.DataFrame) -> bool:
        """
        Veri dogrulama (opsiyonel override)

        Args:
            data: OHLCV DataFrame

        Returns:
            True: Veri gecerli
            False: Veri eksik/bozuk
        """
        if data is None or data.empty:
            return False

        required_cols = ['open', 'high', 'low', 'close', 'volume']
        return all(col in data.columns for col in required_cols)

    def __str__(self) -> str:
        return f"{self.specialist_id}: {self.specialist_name}"

    def __repr__(self) -> str:
        return f"<SpecialistInterface: {self.specialist_id}>"


def calculate_gating_scores(data: pd.DataFrame, indicators: Dict[str, Any]) -> GatingScores:
    """
    Market rejim skorlari hesaplama utility fonksiyonu

    Args:
        data: OHLCV DataFrame (son 180+ bar icermeli)
        indicators: Hesaplanmis indikatorler

    Returns:
        GatingScores: Hesaplanmis rejim skorlari
    """
    try:
        # Trend Score: ADX bazli
        adx = indicators.get('adx', 20.0)  # Default 20
        trend_score = max(0.0, min(1.0, (adx - 10) / (40 - 10)))

        # Squeeze Score: BB bandwidth percentile
        bb_upper = indicators.get('bb_upper', data['close'].iloc[-1] * 1.02)
        bb_lower = indicators.get('bb_lower', data['close'].iloc[-1] * 0.98)
        bb_bandwidth = (bb_upper - bb_lower) / data['close'].iloc[-1]

        # Son 180 bar BB bandwidth hesapla (approximation)
        lookback = min(180, len(data))
        historical_bw = []
        for i in range(max(1, len(data) - lookback), len(data)):
            if i >= 20:  # BB icin minimum veri
                period_data = data.iloc[i-20:i]
                sma = period_data['close'].mean()
                std = period_data['close'].std()
                h_upper = sma + 2 * std
                h_lower = sma - 2 * std
                h_bw = (h_upper - h_lower) / period_data['close'].iloc[-1]
                historical_bw.append(h_bw)

        if historical_bw:
            current_percentile = sum(1 for bw in historical_bw if bb_bandwidth >= bw) / len(historical_bw)
            squeeze_score = 1.0 - current_percentile  # Dusuk BW = yuksek squeeze
        else:
            squeeze_score = 0.5  # Default

        # Chop Score: RSI 35-65 arasi = chop
        rsi = indicators.get('rsi', 50.0)
        chop_score = 1.0 - abs(rsi - 50) / 50.0  # RSI 50'ye yakin = yuksek chop

        # Autocorr 1h (basit hesaplama)
        if len(data) >= 2:
            returns = data['close'].pct_change().dropna()
            if len(returns) >= 2:
                autocorr_1h = returns.iloc[-1] * returns.iloc[-2]  # Simplified
                autocorr_1h = max(-1.0, min(1.0, autocorr_1h * 10))  # Scale
            else:
                autocorr_1h = 0.0
        else:
            autocorr_1h = 0.0

        # Volume Score: Son hacim / medyan hacim
        if len(data) >= 20:
            recent_volume = data['volume'].iloc[-1]
            median_volume = data['volume'].iloc[-20:].median()
            volume_score = recent_volume / median_volume if median_volume > 0 else 1.0
        else:
            volume_score = 1.0

        return GatingScores(
            trend_score=trend_score,
            squeeze_score=squeeze_score,
            chop_score=chop_score,
            autocorr_1h=autocorr_1h,
            volume_score=volume_score
        )

    except Exception:
        # Fallback: orta degerler
        return GatingScores(
            trend_score=0.5,
            squeeze_score=0.5,
            chop_score=0.5,
            autocorr_1h=0.0,
            volume_score=1.0
        )
