"""Core Trader.

Modul fonksiyonlari burada orkestre edilir.
Ozellikler:
 - Guard kontrolleri (halt, gunluk risk, outlier, hacim, korelasyon)
 - Pozisyon acma (ATR tabanli SL/TP, adaptif boyutlama, slippage korumasi)
 - Kismi cikislar & klasik + ATR trailing
 - Metrik toplama & anomaly uyari
 - Basit kapama & toplu kapama
"""
from __future__ import annotations
from typing import Dict, Any, Optional
from dataclasses import dataclass
import threading
from collections import defaultdict
import contextlib
from datetime import datetime, timezone
from pathlib import Path

from config.settings import Settings, RuntimeConfig
from src.api.binance_api import BinanceAPI
from src.risk_manager import RiskManager
from src.utils.logger import get_logger
from src.utils.trade_store import TradeStore
from src.utils.correlation_cache import CorrelationCache

# Alt modul fonksiyonlari
from .guards import pre_trade_pipeline, correlation_ok
from .execution import open_position as _open_position, close_position as _close_position
from .execution import place_protection_orders  # noqa: F401 future reconciliation usage
from .execution import position_size  # noqa: F401 (dis salgindan test icin kullanilabilir)
from .trailing import init_trailing, compute_r_multiple, maybe_partial_exits, maybe_trailing
from .metrics import init_metrics, maybe_flush_metrics, maybe_check_anomalies, recent_latency_slippage_stats

 # (Settings zaten import edildi)

# --- Data containers ---
@dataclass(slots=True)
class OrderRequest:
    symbol: str
    side: str  # BUY / SELL
    price: float
    quantity: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None


class Trader:
    """Tum trade yasam dongusunu yöneten ana sinif."""
    def __init__(self) -> None:
        # Bilesenler
        self.logger = get_logger("Trader")
        self.api = BinanceAPI()
        self.risk_manager = RiskManager()
        self.trade_store = TradeStore()
        self.corr_cache = CorrelationCache(window=Settings.CORRELATION_WINDOW, ttl_seconds=Settings.CORRELATION_TTL_SECONDS)

        # Durum
        self.positions: Dict[str, Dict[str, Any]] = {}
        self.open_positions = self.positions  # backward compat (tests)
        self.guard_counters: Dict[str, int] = defaultdict(int)
        self._lock = threading.RLock()
        self._started = False
        self.market_mode = RuntimeConfig.get_market_mode()
        self.start_balance = 10_000.0  # offline varsayilan

        # Trailing & metrics init
        # Metrics attribute stublar (tip analiz icin)
        self.metrics_lock = threading.RLock()
        self.MAX_RECENT_SAMPLES = 500
        self.recent_open_latencies = []  # type: ignore[attr-defined]
        self.recent_close_latencies = []  # type: ignore[attr-defined]
        self.recent_entry_slippage_bps = []  # type: ignore[attr-defined]
        self.recent_exit_slippage_bps = []  # type: ignore[attr-defined]
        init_trailing(self)
        init_metrics(self)
        # Gunluk risk reset tarihi (timezone aware UTC)
        self._risk_reset_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')

        # Startup weighted pnl recompute (sessiz)
        with contextlib.suppress(Exception):
            n = self.trade_store.recompute_all_weighted_pnl()
            if n:
                self.logger.info(f"Weighted PnL backfill: {n} kayit")

        # Restart reload
        with contextlib.suppress(Exception):
            self._reload_open_positions()  # type: ignore[attr-defined]

    # --- Public API (stable surface for tests) ---
    def execute_trade(self, signal: Dict[str, Any]) -> bool:
        """Tek sinyal isleyip pozisyon acmaya calisir."""
        # Gunluk risk reset kontrolu
        self._maybe_daily_risk_reset()
        ok, ctx = pre_trade_pipeline(self, signal)
        if not ok:
            return False
        with self._lock:
            res = _open_position(self, signal, ctx)
        maybe_flush_metrics(self)
        maybe_check_anomalies(self)
        return res

    def process_price_update(self, symbol: str, last_price: float) -> None:
        pos = self.positions.get(symbol)
        if not pos:
            return
        r_mult = compute_r_multiple(pos, last_price)
        if r_mult is None:
            return
        maybe_partial_exits(self, symbol, pos, last_price, r_mult)
        maybe_trailing(self, symbol, pos, last_price, r_mult)
        maybe_flush_metrics(self)
        maybe_check_anomalies(self)

    def close_position(self, symbol: str) -> bool:
        with self._lock:
            res = _close_position(self, symbol)
        maybe_flush_metrics(self)
        maybe_check_anomalies(self)
        return res

    def close_all_positions(self) -> int:
        syms = list(self.positions.keys())
        c = 0
        for s in syms:
            if self.close_position(s):
                c += 1
        return c

    def get_open_positions(self) -> Dict[str, Dict[str, Any]]:
        return dict(self.positions)

    def recompute_weighted_pnl(self) -> int:
        with contextlib.suppress(Exception):
            return self.trade_store.recompute_all_weighted_pnl() or 0
        return 0

    def start(self):
        self._started = True
        # Oturum basinda reset kontrol
        self._maybe_daily_risk_reset()
        # Baslangicta emir durum senkronu (placeholder)
        with contextlib.suppress(Exception):
            self._reconcile_open_orders()
        return True

    def stop(self):
        self._started = False
        maybe_flush_metrics(self, force=True)
        return True

    # --- Exposed helpers for tests / monitoring ---
    def recent_latency_slippage_stats(self, window: int = 30):
        return recent_latency_slippage_stats(self, window)

    # alias for guard check in execution module
    def correlation_ok(self, symbol: str, price: float) -> bool:  # pragma: no cover
        return correlation_ok(self, symbol, price)

    # Backward compat: eski testler _check_correlation_guard bekliyor
    def _check_correlation_guard(self, symbol: str):  # pragma: no cover
        # Testler (legacy) ikinci alan olarak detay bekliyor (bloklayan semboller ve korelasyon degerleri)
        details = []
        try:
            # cache update'a price gerekli degil burada; 0.0 ile guncelleme atlar
            threshold = Settings.CORRELATION_THRESHOLD
            for sym in self.positions:
                if sym == symbol:
                    continue
                c = self.corr_cache.correlation(symbol, sym)
                if c is not None and c >= threshold:
                    details.append((sym, round(c, 3)))
            # limit kontrolu
            if len(details) >= Settings.MAX_CORRELATED_POSITIONS:
                return False, details
            return True, details
        except Exception:
            return True, details

    # Basit bakiye dondurucu
    def get_account_balance(self) -> float:
        if Settings.OFFLINE_MODE:
            return self.start_balance
        # Spot USDT serbest bakiye dene
        try:  # pragma: no cover - can vary live
            info = self.api.client.get_account()  # type: ignore[attr-defined]
            balances = info['balances'] if isinstance(info, dict) and 'balances' in info else []
            for b in balances:
                asset = b.get('asset') if isinstance(b, dict) else None
                if asset == 'USDT':
                    free_raw = b.get('free', 0) if isinstance(b, dict) else 0
                    free = float(free_raw or 0)
                    if free > 0:
                        return free
        except Exception:
            pass
        return self.start_balance

    # ---------- Internal helpers (state management) ----------
    def _reload_open_positions(self):
        rows = self.trade_store.open_trades()
        for r in rows:
            trade_id = r['id']
            scaled = self.trade_store.scale_executions(trade_id)
            total_scaled = sum(x['qty'] for x in scaled)
            entry_size = r['size'] or 0.0
            remaining = max(0.0, entry_size - total_scaled)
            self.positions[r['symbol']] = {
                'side': 'BUY' if r['side'].upper() == 'BUY' else 'SELL',
                'entry_price': r['entry_price'],
                'position_size': entry_size,
                'remaining_size': remaining,
                'stop_loss': r['stop_loss'],
                'take_profit': r['take_profit'],
                'atr': None,
                'trade_id': trade_id,
                'scaled_out': [(x['r_mult'], x['qty']) for x in scaled if x.get('r_mult') is not None]
            }
        if rows:
            self.logger.info(f"Reloaded {len(rows)} open trades from DB")

    def _reconcile_open_orders(self):  # placeholder for future: query exchange open orders
        # Reconciliation: local state ↔ exchange (open positions & protection orders)
        summary = {
            'missing_stop_tp': [],
            'orphan_local_position': [],
            'orphan_exchange_position': []
        }
    # Acik emirler su an sadece koruma varligi kontrolunde dolayli; ileride detayli diff icin kullanilacak.
        with contextlib.suppress(Exception):
            _ = self.api.get_open_orders()
        try:
            exch_positions = self.api.get_positions() or []
        except Exception:
            exch_positions = []

        exch_pos_map = {p.get('symbol'): p for p in exch_positions if isinstance(p, dict)}
        exch_pos_syms = set(exch_pos_map.keys())
        local_syms = set(self.positions.keys())

        # Orphan exchange positions (on exchange but not locally tracked)
        for sym in sorted([s for s in (exch_pos_syms - local_syms) if s]):
            summary['orphan_exchange_position'].append(sym)
            self.logger.info(f"RECON:orphan_exchange_position:{sym}:{ { 'side': exch_pos_map[sym].get('side'), 'size': exch_pos_map[sym].get('size') } }")

        # Local positions checks
        for sym, pos in self.positions.items():
            # Missing on exchange
            if sym not in exch_pos_syms:
                summary['orphan_local_position'].append(sym)
                self.logger.info(f"RECON:orphan_local_position:{sym}:{ { 'side': pos.get('side'), 'remaining': pos.get('remaining_size') } }")
            # Protection orders missing
            has_protection = any(k in pos for k in ('oco_resp', 'futures_protection'))
            if not has_protection:
                summary['missing_stop_tp'].append(sym)
                self.logger.info(f"RECON:missing_stop_tp:{sym}:{ { 'side': pos.get('side'), 'remaining': pos.get('remaining_size') } }")

        return summary

    def _maybe_daily_risk_reset(self, now_ts: float | None = None):
        try:
            now = datetime.fromtimestamp(now_ts, tz=timezone.utc) if now_ts else datetime.now(timezone.utc)
            today = now.strftime('%Y-%m-%d')
            if today == getattr(self, '_risk_reset_date', None):
                return False
            # tarih degismis -> reset
            old = getattr(self, '_risk_reset_date', None)
            self._risk_reset_date = today
            # halt flag sil
            try:
                flag = Path(Settings.DAILY_HALT_FLAG_PATH)
                if flag.exists():
                    flag.unlink()
            except Exception:
                pass
            # sayaclari sifirla
            self.guard_counters.clear()
            self.logger.info(f"RISK_RESET:{old}->{today}")
            return True
        except Exception:
            return False
