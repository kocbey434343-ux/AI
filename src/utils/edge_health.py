# flake8: noqa: RUF002, RUF003
"""
Edge Health Monitor (A32) - Trading Edge Saglik Izleme Sistemi

Bu modul trading edge'lerinin sagligini Wilson guven araligi ile izler
ve HOT/WARM/COLD siniflandirmasi yapar.
"""

import logging
import math
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class EdgeStatus(Enum):
    """Edge sağlık durumları"""
    HOT = "HOT"      # LB > 0.1R (güçlü edge)
    WARM = "WARM"    # 0 < LB ≤ 0.1R (zayıf ama pozitif)
    COLD = "COLD"    # LB ≤ 0 (edge yok/negatif)


@dataclass
class TradeResult:
    """Trade sonucu için veri sınıfı"""
    symbol: str
    r_multiple: float  # R-multiple sonucu
    timestamp: datetime
    win: bool
    strategy_id: Optional[str] = None


@dataclass
class EdgeHealthMetrics:
    """Edge sağlık metrikleri"""
    total_trades: int
    win_rate: float
    avg_win_r: float
    avg_loss_r: float
    expectancy_r: float
    wilson_lower_bound: float
    status: EdgeStatus
    confidence_interval: float = 0.95
    last_updated: Optional[datetime] = None


class EdgeHealthMonitor:
    """
    Trading edge'lerinin sağlığını Wilson güven aralığı ile izleyen sistem.

    Özellikler:
    - 200 trade kayan pencere (minimum 50 trade)
    - Wilson alt sınır hesaplama
    - HOT/WARM/COLD sınıflandırma
    - Strateji bazlı veya global izleme
    """

    def __init__(self,
                 window_trades: int = 200,
                 min_trades: int = 50,
                 confidence_interval: float = 0.95,
                 hot_threshold: float = 0.10,
                 warm_threshold: float = 0.0):
        """
        Args:
            window_trades: Kayan pencere boyutu
            min_trades: Minimum trade sayısı
            confidence_interval: Güven aralığı (0.95 = %95)
            hot_threshold: HOT edge eşiği (R-multiple)
            warm_threshold: WARM edge eşiği (R-multiple)
        """
        self.window_trades = window_trades
        self.min_trades = min_trades
        self.confidence_interval = confidence_interval
        self.hot_threshold = hot_threshold
        self.warm_threshold = warm_threshold

        # Trade sonuçları saklanır (FIFO)
        self.trade_results: List[TradeResult] = []

        # Strateji bazlı sonuçlar
        self.strategy_results: Dict[str, List[TradeResult]] = {}

        # Son hesaplanan metrikler
        self.current_metrics: Optional[EdgeHealthMetrics] = None
        self.strategy_metrics: Dict[str, EdgeHealthMetrics] = {}

        logger.info(f"EdgeHealthMonitor initialized: window={window_trades}, "
                   f"min={min_trades}, confidence={confidence_interval}")

    def add_trade_result(self, result: TradeResult) -> None:
        """Yeni trade sonucu ekle"""
        # Global listeye ekle
        self.trade_results.append(result)

        # FIFO - pencere boyutunu aş
        if len(self.trade_results) > self.window_trades:
            self.trade_results.pop(0)

        # Strateji bazlı ekleme
        if result.strategy_id:
            if result.strategy_id not in self.strategy_results:
                self.strategy_results[result.strategy_id] = []

            self.strategy_results[result.strategy_id].append(result)

            # Strateji pencere kontrolü
            if len(self.strategy_results[result.strategy_id]) > self.window_trades:
                self.strategy_results[result.strategy_id].pop(0)

    def calculate_wilson_lower_bound(self,
                                   wins: int,
                                   total: int,
                                   confidence: float = 0.95) -> float:
        """
        Wilson güven aralığı alt sınırını hesapla.

        Args:
            wins: Kazanan trade sayısı
            total: Toplam trade sayısı
            confidence: Güven seviyesi

        Returns:
            Wilson alt sınır değeri
        """
        if total == 0:
            return 0.0

        # Z-score for confidence level
        z_scores = {0.90: 1.645, 0.95: 1.96, 0.99: 2.576}
        z = z_scores.get(confidence, 1.96)

        p = wins / total
        n = total

        # Wilson formula
        center = (p + z*z/(2*n)) / (1 + z*z/n)
        margin = z * math.sqrt((p*(1-p) + z*z/(4*n)) / n) / (1 + z*z/n)

        lower_bound = center - margin
        return max(0.0, lower_bound)

    def calculate_expectancy_r(self, results: List[TradeResult]) -> Tuple[float, float, float, float]:
        """
        R-multiple expectancy hesapla.

        Returns:
            (win_rate, avg_win_r, avg_loss_r, expectancy_r)
        """
        if not results:
            return 0.0, 0.0, 0.0, 0.0

        wins = [r.r_multiple for r in results if r.win]
        losses = [r.r_multiple for r in results if not r.win]

        win_rate = len(wins) / len(results)
        avg_win_r = float(np.mean(wins)) if wins else 0.0
        avg_loss_r = float(abs(np.mean(losses))) if losses else 0.0  # Pozitif yapiyoruz

        # Expectancy = WinRate x AvgWin - LossRate x AvgLoss
        expectancy_r = win_rate * avg_win_r - (1 - win_rate) * avg_loss_r

        return win_rate, avg_win_r, avg_loss_r, expectancy_r

    def classify_edge_status(self, wilson_lb: float) -> EdgeStatus:
        """Wilson alt sınırına göre edge durumu sınıflandır"""
        if wilson_lb > self.hot_threshold:
            return EdgeStatus.HOT
        if wilson_lb >= self.warm_threshold:
            return EdgeStatus.WARM
        return EdgeStatus.COLD

    def update_global_metrics(self) -> Optional[EdgeHealthMetrics]:
        """Global edge metriklerini güncelle"""
        if len(self.trade_results) < self.min_trades:
            logger.debug(f"Insufficient trades for global metrics: "
                        f"{len(self.trade_results)} < {self.min_trades}")
            return None

        # Expectancy hesapla
        win_rate, avg_win_r, avg_loss_r, expectancy_r = self.calculate_expectancy_r(
            self.trade_results
        )

        # Wilson alt sınır
        wins = sum(1 for r in self.trade_results if r.win)
        wilson_lb = self.calculate_wilson_lower_bound(
            wins, len(self.trade_results), self.confidence_interval
        )

        # Edge durumu
        status = self.classify_edge_status(expectancy_r)  # Expectancy kullanıyoruz

        self.current_metrics = EdgeHealthMetrics(
            total_trades=len(self.trade_results),
            win_rate=win_rate,
            avg_win_r=avg_win_r,
            avg_loss_r=avg_loss_r,
            expectancy_r=expectancy_r,
            wilson_lower_bound=wilson_lb,
            status=status,
            confidence_interval=self.confidence_interval,
            last_updated=datetime.now()
        )

        logger.debug(f"Global edge metrics updated: {self.current_metrics}")
        return self.current_metrics

    def update_strategy_metrics(self, strategy_id: str) -> Optional[EdgeHealthMetrics]:
        """Belirli strateji için edge metriklerini güncelle"""
        if strategy_id not in self.strategy_results:
            return None

        results = self.strategy_results[strategy_id]
        if len(results) < self.min_trades:
            logger.debug(f"Insufficient trades for strategy {strategy_id}: "
                        f"{len(results)} < {self.min_trades}")
            return None

        # Expectancy hesapla
        win_rate, avg_win_r, avg_loss_r, expectancy_r = self.calculate_expectancy_r(results)

        # Wilson alt sınır
        wins = sum(1 for r in results if r.win)
        wilson_lb = self.calculate_wilson_lower_bound(
            wins, len(results), self.confidence_interval
        )

        # Edge durumu
        status = self.classify_edge_status(expectancy_r)

        metrics = EdgeHealthMetrics(
            total_trades=len(results),
            win_rate=win_rate,
            avg_win_r=avg_win_r,
            avg_loss_r=avg_loss_r,
            expectancy_r=expectancy_r,
            wilson_lower_bound=wilson_lb,
            status=status,
            confidence_interval=self.confidence_interval,
            last_updated=datetime.now()
        )

        self.strategy_metrics[strategy_id] = metrics
        logger.debug(f"Strategy {strategy_id} metrics updated: {metrics}")
        return metrics

    def get_global_status(self) -> EdgeStatus:
        """Global edge durumunu döndür"""
        self.update_global_metrics()
        if self.current_metrics:
            return self.current_metrics.status
        return EdgeStatus.COLD  # Veri yoksa COLD

    def get_strategy_status(self, strategy_id: str) -> EdgeStatus:
        """Strateji edge durumunu döndür"""
        self.update_strategy_metrics(strategy_id)
        if strategy_id in self.strategy_metrics:
            return self.strategy_metrics[strategy_id].status
        return EdgeStatus.COLD  # Veri yoksa COLD

    def should_allow_trade(self, strategy_id: Optional[str] = None) -> bool:
        """
        Trade'e izin verilip verilmeyeceğini kontrol et.

        Args:
            strategy_id: Strateji ID (None ise global kontrol)

        Returns:
            True if trade allowed (HOT/WARM), False if COLD
        """
        status = self.get_strategy_status(strategy_id) if strategy_id else self.get_global_status()
        return status != EdgeStatus.COLD

    def get_risk_multiplier(self, strategy_id: Optional[str] = None) -> float:
        """
        Edge durumuna göre risk çarpanını döndür.

        Returns:
            1.0 for HOT, 0.5 for WARM, 0.0 for COLD
        """
        status = self.get_strategy_status(strategy_id) if strategy_id else self.get_global_status()

        if status == EdgeStatus.HOT:
            return 1.0
        if status == EdgeStatus.WARM:
            return 0.5
        return 0.0  # COLD

    def get_global_edge_health(self) -> Dict[str, Any]:
        """Global edge health bilgilerini dict olarak döndür"""
        self.update_global_metrics()

        return {
            'sufficient_data': len(self.trade_results) >= self.min_trades,
            'total_trades': len(self.trade_results),
            'status': self.current_metrics.status if self.current_metrics else EdgeStatus.COLD,
            'win_rate': self.current_metrics.win_rate if self.current_metrics else 0.0,
            'expectancy_r': self.current_metrics.expectancy_r if self.current_metrics else 0.0,
            'wilson_lower_bound': self.current_metrics.wilson_lower_bound if self.current_metrics else 0.0,
            'risk_multiplier': self.get_risk_multiplier()
        }

    def get_statistics(self) -> Dict[str, Any]:
        """Detaylı istatistikler döndür"""
        return {
            "global": self.current_metrics.__dict__ if self.current_metrics else None,
            "strategies": {k: v.__dict__ for k, v in self.strategy_metrics.items()},
            "trade_counts": {
                "global": len(self.trade_results),
                "by_strategy": {k: len(v) for k, v in self.strategy_results.items()}
            },
            "config": {
                "window_trades": self.window_trades,
                "min_trades": self.min_trades,
                "hot_threshold": self.hot_threshold,
                "warm_threshold": self.warm_threshold,
                "confidence_interval": self.confidence_interval
            }
        }


# Global singleton instance
_edge_health_monitor: Optional[EdgeHealthMonitor] = None


def get_edge_health_monitor() -> EdgeHealthMonitor:
    """Global EdgeHealthMonitor instance döndür"""
    global _edge_health_monitor  # noqa: PLW0603
    if _edge_health_monitor is None:
        _edge_health_monitor = EdgeHealthMonitor()
    return _edge_health_monitor


def add_trade_result(symbol: str,
                    r_multiple: float,
                    win: bool,
                    strategy_id: Optional[str] = None,
                    timestamp: Optional[datetime] = None) -> None:
    """Convenience function: trade sonucu ekle"""
    if timestamp is None:
        timestamp = datetime.now()

    result = TradeResult(
        symbol=symbol,
        r_multiple=r_multiple,
        timestamp=timestamp,
        win=win,
        strategy_id=strategy_id
    )

    monitor = get_edge_health_monitor()
    monitor.add_trade_result(result)


def get_edge_status(strategy_id: Optional[str] = None) -> EdgeStatus:
    """Convenience function: edge durumu al"""
    monitor = get_edge_health_monitor()
    return monitor.get_strategy_status(strategy_id) if strategy_id else monitor.get_global_status()


def should_allow_trade(strategy_id: Optional[str] = None) -> bool:
    """Convenience function: trade izin kontrolü"""
    monitor = get_edge_health_monitor()
    return monitor.should_allow_trade(strategy_id)


def get_risk_multiplier(strategy_id: Optional[str] = None) -> float:
    """Convenience function: risk çarpanı al"""
    monitor = get_edge_health_monitor()
    return monitor.get_risk_multiplier(strategy_id)
