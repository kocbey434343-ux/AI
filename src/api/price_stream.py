import json
import random
import threading
import time
from typing import Callable, Optional

from src.utils.logger import get_logger


class PriceStreamManager:
    """Lightweight Binance websocket price stream manager.

    Uses public miniTicker stream to receive last prices. Callback signature:
        on_price(symbol: str, price: float) -> None
    """
    def __init__(self, symbols: list[str], on_price: Callable[[str, float], None], on_status: Optional[Callable[[str, Optional[str]], None]] = None,
                 base_backoff: float = 2.0, max_backoff: float = 60.0, timeout_sec: float = 25.0, max_retries: Optional[int] = None):
        self.logger = get_logger("PriceStream")
        self.symbols = [s.lower() for s in symbols]
        self.on_price = on_price
        self.on_status = on_status  # optional status callback: (status, info)
        self.thread: threading.Thread | None = None
        self.ws = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        # Backoff config
        self.base_backoff = base_backoff
        self.max_backoff = max_backoff
        self.max_retries = max_retries  # None = unlimited
        self._attempt = 0
        # Health tracking
        self._last_msg_ts = 0.0
        self.timeout_sec = timeout_sec

    def _build_url(self):
        # wss://stream.binance.com:9443/stream?streams=btcusdt@miniTicker/ethusdt@miniTicker
        streams = "/".join(f"{s}@miniTicker" for s in self.symbols)
        return f"wss://stream.binance.com:9443/stream?streams={streams}"

    def _on_message(self, _ws, message):
        try:
            data = json.loads(message)
            payload = data.get('data') or {}
            s = payload.get('s') or payload.get('symbol')
            c = payload.get('c')  # close price
            if s and c:
                try:
                    price = float(c)
                    self._last_msg_ts = time.time()
                    self.on_price(s.upper(), price)
                except Exception:
                    pass
        except Exception:
            pass

    def _on_error(self, _ws, error):
        self.logger.error(f"Websocket hata: {error}")
        try:
            if self.on_status:
                self.on_status("error", str(error))
        except Exception:
            pass

    def _on_close(self, *_):
        self.logger.info("Websocket kapandi")
        try:
            if self.on_status:
                self.on_status("closed", None)
        except Exception:
            pass

    def _on_open(self, *_):
            self.logger.info("Websocket acildi")
            try:
                if self.on_status:
                    self.on_status("open", None)
            except Exception:
                pass
            # Reset backoff & last message timestamp
            self._attempt = 0
            self._last_msg_ts = time.time()

    def _run(self):
        import websocket as _ws
        while not self._stop.is_set():
            url = self._build_url()
            self.logger.info(f"WS baglaniyor: {url}")
            try:
                if self.on_status:
                    self.on_status("connecting", None)
            except Exception:
                pass
            try:
                self.ws = _ws.WebSocketApp(url,
                                           on_message=self._on_message,
                                           on_open=self._on_open,
                                           on_error=self._on_error,
                                           on_close=self._on_close)
                self.ws.run_forever(ping_interval=30, ping_timeout=10)
            except Exception as e:
                self.logger.error(f"WS run_forever hata: {e}")
                try:
                    if self.on_status:
                        self.on_status("error", str(e))
                except Exception:
                    pass
            # Baglanti koptu veya cikildi
            if self._stop.is_set():
                break
            self._attempt += 1
            if self.max_retries is not None and self._attempt > self.max_retries:
                self.logger.error("Maksimum WS yeniden baglanma denemesi asildi; durduruluyor")
                try:
                    if self.on_status:
                        self.on_status("stopped", "max_retries")
                except Exception:
                    pass
                break
            backoff = min(self.max_backoff, self.base_backoff * (2 ** (self._attempt - 1)))
            # jitter
            backoff = backoff * (0.8 + 0.4 * random.random())
            try:
                if self.on_status:
                    self.on_status("reconnecting", f"{backoff:.1f}s")
            except Exception:
                pass
            slept = 0.0
            while slept < backoff and not self._stop.is_set():
                time.sleep(0.5)
                slept += 0.5

    def start(self):
        if self.thread and self.thread.is_alive():
            return
        self._stop.clear()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def stop(self):
        self._stop.set()
        try:
            if self.ws:
                self.ws.close()
        except Exception:
            pass
        if self.thread:
            self.thread.join(timeout=5)
            if self.thread.is_alive():
                self.logger.warning("WS thread join timeout; thread hala yasiyor - zorla durdurma gerekebilir")
                # Force termination sonrasi yeniden baslatmayi main thread'e birak
                # Thread icindeki ws.close() timeout'tan sonra calismasi bekleniyor
        self.thread = None
        try:
            if self.on_status:
                self.on_status("stopped", None)
        except Exception:
            pass

    # ---- Health Helpers ----
    def seconds_since_last_message(self) -> float:
        if self._last_msg_ts == 0:
            return float('inf')
        return time.time() - self._last_msg_ts

    def is_timed_out(self) -> bool:
        return self.seconds_since_last_message() > self.timeout_sec

    def restart(self, new_symbols: Optional[list[str]] = None):
        """Disaridan kontrollu restart (health check icin)."""
        with self._lock:
            if new_symbols is not None:
                self.symbols = [s.lower() for s in new_symbols]
            self.stop()
            # reset attempt so first connect uses small backoff
            self._attempt = 0
            self._stop.clear()
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()
