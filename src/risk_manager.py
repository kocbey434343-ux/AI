from __future__ import annotations
from typing import Optional, Literal
import math
from src.utils.logger import get_logger
from config.settings import Settings, RuntimeConfig

Side = Literal["long", "short"]

class RiskManager:
    """Pozisyon boyutu, stop ve hedef hesapları için risk yönetimi.

    Varsayılan yaklaşım:
      - Risk: hesap bakiyesinin risk_percent%'i.
      - Stop mesafesi: ATR tabanlı (atr_multiplier * ATR) veya fallback sabit %.
      - Pozisyon değeri = risk_amount / (stop_distance_pct)
      - Kaldıraç yalnızca futures modunda efektif pozisyon değerini büyütür; marjin = pozisyon_değeri / leverage.
    """

    def __init__(self) -> None:
        self.logger = get_logger("RiskManager")
        self.risk_percent: float = Settings.DEFAULT_RISK_PERCENT
        self.leverage: int = Settings.DEFAULT_LEVERAGE
        self.max_positions: int = Settings.DEFAULT_MAX_POSITIONS
        self.min_volume: float = Settings.DEFAULT_MIN_VOLUME
        self.atr_multiplier: float = 2.0
        self.fallback_stop_pct: float = 0.6  # %0.6 default (eski %0.3 çok sıkıydı)
        self.take_profit_rr: float = 2.2  # risk:reward

    # ---------------- Configuration -----------------
    def update_settings(self, risk_percent: Optional[float] = None, leverage: Optional[int] = None,
                        max_positions: Optional[int] = None, min_volume: Optional[float] = None,
                        atr_multiplier: Optional[float] = None, fallback_stop_pct: Optional[float] = None,
                        take_profit_rr: Optional[float] = None) -> None:
        if risk_percent is not None:
            self.risk_percent = risk_percent
        if leverage is not None:
            self.leverage = leverage
        if max_positions is not None:
            self.max_positions = max_positions
        if min_volume is not None:
            self.min_volume = min_volume
        if atr_multiplier is not None and atr_multiplier > 0:
            self.atr_multiplier = atr_multiplier
        if fallback_stop_pct is not None and fallback_stop_pct > 0:
            self.fallback_stop_pct = fallback_stop_pct
        if take_profit_rr is not None and take_profit_rr > 0:
            self.take_profit_rr = take_profit_rr
        self.logger.info(
            f"Risk ayarları -> risk%={self.risk_percent} lev={self.leverage}x max_pos={self.max_positions} min_vol={self.min_volume}"
            f" atr_mult={self.atr_multiplier} fb_stop%={self.fallback_stop_pct} rr={self.take_profit_rr}"
        )

    # ---------------- Core Calculations -----------------
    def _resolve_stop_distance(self, entry_price: float, side: Side, atr_value: Optional[float]) -> float:
        if atr_value and atr_value > 0:
            return atr_value * self.atr_multiplier
        return entry_price * (self.fallback_stop_pct / 100.0)

    def calculate_stop_loss(self, entry_price: float, side: Side, atr_value: Optional[float] = None) -> float:
        dist = self._resolve_stop_distance(entry_price, side, atr_value)
        return entry_price - dist if side == "long" else entry_price + dist

    def calculate_position_size(self, account_balance: float, entry_price: float, stop_loss_price: float) -> float:
        """Risk tabanlı pozisyon boyu.

        position_value = risk_amount / stop_distance_pct
        Futures: margin_required = position_value / leverage; spot'ta leverage=1 kabul edilir.
        position_size = position_value / entry_price
        """
        if entry_price <= 0 or stop_loss_price <= 0:
            return 0.0
        stop_distance_pct = abs(entry_price - stop_loss_price) / entry_price
        if stop_distance_pct <= 0:
            return 0.0
        risk_amount = account_balance * (self.risk_percent / 100.0)
        position_value = risk_amount / stop_distance_pct
        if RuntimeConfig.get_market_mode() == "futures" and self.leverage > 1:
            # Pozisyon değeri (notional), marjin = position_value / leverage -> risk'e uygun
            margin_required = position_value / self.leverage
            if margin_required > account_balance * 0.9:  # aşırı kullanım guard
                scale = (account_balance * 0.9) / margin_required
                position_value *= scale
        position_size = position_value / entry_price
        return max(0.0, position_size)

    def calculate_take_profit(self, entry_price: float, stop_loss_price: float, side: Side) -> float:
        risk_distance = abs(entry_price - stop_loss_price)
        profit_distance = risk_distance * self.take_profit_rr
        return entry_price + profit_distance if side == "long" else entry_price - profit_distance

    # ---------------- Checks -----------------
    def check_volume(self, volume_24h: float) -> bool:
        return volume_24h >= self.min_volume

    def check_max_positions(self, open_positions_count: int) -> bool:
        return open_positions_count < self.max_positions

    def calculate_max_loss(self, entry_price: float, stop_loss_price: float, position_size: float) -> float:
        return abs(entry_price - stop_loss_price) * position_size

    def apply_slippage_protection(self, stop_loss_price: float, side: Side) -> float:
        # Basit tampon: stop'u %0.1 daha uzaklaştır
        slippage_percent = 0.1
        return stop_loss_price * (1 - slippage_percent / 100) if side == "long" else stop_loss_price * (1 + slippage_percent / 100)

    # ---------------- Utility -----------------
    def describe(self) -> dict:
        return {
            "risk_percent": self.risk_percent,
            "leverage": self.leverage,
            "atr_multiplier": self.atr_multiplier,
            "fallback_stop_pct": self.fallback_stop_pct,
            "rr": self.take_profit_rr
        }
