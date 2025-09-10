import hashlib
import hmac
import math
import random
import time

import pandas as pd
import requests
from binance import Client
from binance.exceptions import BinanceAPIException
from config.settings import RuntimeConfig, Settings

from src.utils.logger import get_logger
from src.utils.prometheus_export import get_exporter_instance


class BinanceAPI:
    def __init__(self, mode: str | None = None):
        self.mode = (mode or RuntimeConfig.get_market_mode()).lower()
        self.logger = get_logger("BinanceAPI")
        # In-memory filters cache: { symbol: { 'filters': {type: obj}, 'ts': epoch_sec } }
        self._filters_cache = {}
        self._filters_cache_ttl_sec = 300  # 5 min
        # Initialize client
        # Offline / test fallback: if OFFLINE_MODE skip real client heavy init (still create realistic simulator for testing)
        if Settings.OFFLINE_MODE:
            class _RealisticSimulator:
                """Realistic simulator for offline testing with actual market-like behavior."""

                def __init__(self):
                    # Base prices for major crypto pairs (in USDT)
                    self.base_prices = {
                        'BTCUSDT': 43500.0,
                        'ETHUSDT': 2650.0,
                        'BNBUSDT': 315.0,
                        'ADAUSDT': 0.52,
                        'XRPUSDT': 0.61,
                        'SOLUSDT': 98.0,
                        'DOTUSDT': 7.2,
                        'MATICUSDT': 0.85,
                        'AVAXUSDT': 38.5,
                        'LINKUSDT': 15.8
                    }
                    self.price_volatility = {}  # Track price movements

                def __getattr__(self, item):
                    def _f(*a, **k):
                        return [] if 'ticker' in item.lower() else {}
                    return _f

                def get_server_time(self):
                    return {"serverTime": int(time.time()*1000)}

                def get_ticker(self, symbol=None):
                    """Realistic ticker with bid/ask spread simulation."""
                    if symbol and symbol in self.base_prices:
                        base_price = self.base_prices[symbol]
                        # Simulate realistic price movement (±0.5%)
                        current_price = base_price * (1 + random.uniform(-0.005, 0.005))
                        spread_bps = random.uniform(1.0, 5.0)  # 1-5 BPS spread
                        spread_abs = current_price * (spread_bps / 10000)

                        return {
                            'symbol': symbol,
                            'price': f"{current_price:.8f}",
                            'bidPrice': f"{current_price - spread_abs/2:.8f}",
                            'askPrice': f"{current_price + spread_abs/2:.8f}",
                            'volume': f"{random.uniform(10000, 100000):.2f}",
                            'count': random.randint(1000, 10000)
                        }
                    return {}

                def get_order_book(self, symbol, limit=10):
                    """Realistic order book simulation."""
                    if symbol in self.base_prices:
                        base_price = self.base_prices[symbol]
                        current_price = base_price * (1 + random.uniform(-0.005, 0.005))

                        bids = []
                        asks = []

                        # Generate realistic bid/ask levels
                        for i in range(limit):
                            bid_price = current_price * (1 - (i + 1) * 0.0001)
                            ask_price = current_price * (1 + (i + 1) * 0.0001)
                            bid_qty = random.uniform(0.1, 10.0)
                            ask_qty = random.uniform(0.1, 10.0)

                            bids.append([f"{bid_price:.8f}", f"{bid_qty:.8f}"])
                            asks.append([f"{ask_price:.8f}", f"{ask_qty:.8f}"])

                        return {'bids': bids, 'asks': asks}
                    return {'bids': [], 'asks': []}

                def get_klines(self, symbol, interval, limit=500):
                    """Generate realistic OHLCV data for backtesting."""
                    if symbol in self.base_prices:
                        base_price = self.base_prices[symbol]
                        klines = []
                        current_time = int(time.time() * 1000)

                        # Interval to milliseconds mapping
                        interval_ms = {'1m': 60000, '5m': 300000, '15m': 900000, '1h': 3600000, '4h': 14400000, '1d': 86400000}.get(interval, 60000)

                        for i in range(limit):
                            # Simulate realistic OHLCV with proper relationships
                            price_variance = random.uniform(-0.02, 0.02)
                            open_price = base_price * (1 + price_variance)

                            high_variance = random.uniform(0, 0.01)
                            low_variance = random.uniform(-0.01, 0)
                            close_variance = random.uniform(-0.01, 0.01)

                            high_price = open_price * (1 + high_variance)
                            low_price = open_price * (1 + low_variance)
                            close_price = open_price * (1 + close_variance)

                            volume = random.uniform(100, 1000)

                            kline_time = current_time - (i * interval_ms)  # Dynamic intervals
                            klines.append([
                                kline_time,
                                f"{open_price:.8f}",
                                f"{high_price:.8f}",
                                f"{low_price:.8f}",
                                f"{close_price:.8f}",
                                f"{volume:.8f}",
                                kline_time + interval_ms - 1,
                                f"{volume * close_price:.8f}",
                                random.randint(10, 100),
                                f"{volume * 0.6:.8f}",
                                f"{volume * close_price * 0.6:.8f}",
                                "0"
                            ])

                        return list(reversed(klines))  # Chronological order
                    return []

                def get_symbol_info(self, symbol):
                    """Realistic symbol info for filters."""
                    return {
                        'symbol': symbol,
                        'status': 'TRADING',
                        'filters': [
                            {'filterType': 'LOT_SIZE', 'minQty': '0.00001', 'stepSize': '0.00001'},
                            {'filterType': 'PRICE_FILTER', 'minPrice': '0.00001', 'tickSize': '0.01'},
                            {'filterType': 'MIN_NOTIONAL', 'minNotional': '10.0'}
                        ]
                    }

            self.client = _RealisticSimulator()
            self.logger.info("OFFLINE_MODE aktif: realistic simulator kullaniliyor")
        else:
            # Operasyonel guvenlik: Prod yalnizca ALLOW_PROD=true ise acilir
            if not Settings.USE_TESTNET and not Settings.ALLOW_PROD:
                raise RuntimeError("Prod endpoint kapali: ALLOW_PROD=true olmadan prod'a baglanilamaz")
            self.client = Client(
                api_key=Settings.BINANCE_API_KEY,
                api_secret=Settings.BINANCE_API_SECRET,
                testnet=Settings.USE_TESTNET
            )
            # Manual testnet URL fix for python-binance library
            if Settings.USE_TESTNET:
                self.client.API_URL = 'https://testnet.binance.vision/api'
                self.client.FUTURES_URL = 'https://testnet.binancefuture.com/fapi'
                self.logger.info(f"TESTNET URLs manually set: API={self.client.API_URL}, FUTURES={self.client.FUTURES_URL}")

        # Metrics exporter (safe if not available)
        try:
            self.metrics = get_exporter_instance()
        except Exception:
            self.metrics = None

        # Monkey patch python-binance client to use V2 endpoints
        self._patch_client_for_v2_endpoints()

    def _signed_request_v2(self, http_method: str, url_path: str, payload: dict = None):
        """Manual signed request for V2/V3 endpoints that python-binance doesn't support"""
        if Settings.OFFLINE_MODE:
            return {}
        if payload is None:
            payload = {}

        # Base URL for futures
        if Settings.USE_TESTNET:
            base_url = "https://testnet.binancefuture.com"
        else:
            base_url = "https://fapi.binance.com"

        # Create query string
        query_string = "&".join([f"{k}={v}" for k, v in payload.items()])
        timestamp = int(time.time() * 1000)
        query_string = f"{query_string}&timestamp={timestamp}" if query_string else f"timestamp={timestamp}"

        # Sign the request
        signature = hmac.new(
            Settings.BINANCE_API_SECRET.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        # Build URL and headers
        url = f"{base_url}{url_path}?{query_string}&signature={signature}"
        headers = {"X-MBX-APIKEY": Settings.BINANCE_API_KEY}

        try:
            response = requests.request(http_method, url, headers=headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error(f"V2 request error {url_path}: {e}")
            return {}

    def _patch_client_for_v2_endpoints(self):
        """Monkey patch python-binance client to use V2 endpoints for futures"""
        if not hasattr(self.client, '_original_futures_position_information'):
            # Store original method
            self.client._original_futures_position_information = self.client.futures_position_information

            # Replace with V2 wrapper
            def futures_position_information_v2(**kwargs):
                """V2 wrapper for futures position information"""
                try:
                    return self._signed_request_v2("GET", "/fapi/v2/positionRisk", kwargs)
                except Exception as e:
                    self.logger.warning(f"V2 endpoint failed, falling back to V1: {e}")
                    # Fallback to original method if V2 fails
                    return self.client._original_futures_position_information(**kwargs)

            # Apply the monkey patch
            self.client.futures_position_information = futures_position_information_v2
            self.logger.info("Applied V2 endpoint monkey patch for futures_position_information")

    # ---------- Helpers for filters ----------
    def _spot_symbol_info(self, symbol: str):
        return self.client.get_symbol_info(symbol)

    def _futures_symbol_info(self, symbol: str):
        info = self.client.futures_exchange_info()
        if isinstance(info, dict):
            for s in info.get('symbols', []):
                if s.get('symbol') == symbol:
                    return s
        return None

    def _get_filters(self, symbol: str):
        if self.mode == "futures":
            s = self._futures_symbol_info(symbol) or {}
        else:
            s = self._spot_symbol_info(symbol) or {}
        if isinstance(s, dict):
            return {f['filterType']: f for f in s.get('filters', [])}
        return {}

    def _get_filters_cached(self, symbol: str, force_refresh: bool = False):
        now = time.time()
        cached = self._filters_cache.get(symbol)
        if (not force_refresh) and cached and (now - cached.get('ts', 0)) < self._filters_cache_ttl_sec:
            return cached.get('filters', {})
        filters = self._get_filters(symbol)
        self._filters_cache[symbol] = {'filters': filters, 'ts': now}
        return filters

    def _round_step(self, value: float, step: float):
        if step in (0, None):
            return value
        return math.floor(value / step) * step

    def quantize(self, symbol: str, quantity: float, price: float | None = None):
        """Quantize amount and price according to exchange filters.
        Rules:
        - Quantity rounded down to LOT_SIZE.stepSize; if < minQty => return (0.0, px)
        - Price rounded down to PRICE_FILTER.tickSize and >= minPrice when provided
        - If price provided and NOTIONAL/MIN_NOTIONAL exists and qty*price < minNotional => return (0.0, px)
        """
        filters = self._get_filters_cached(symbol)
        # Quantity
        step = float(filters.get('LOT_SIZE', {}).get('stepSize', 0) or 0)
        min_qty = float(filters.get('LOT_SIZE', {}).get('minQty', 0) or 0)
    # Yeni mantik: minQty altinda kalan miktari minQty'ye zorlamak yerine 0 dondur (islem atlanir)
        if step:
            rounded = self._round_step(quantity, step)
            if quantity < min_qty:
                qty = 0.0
            else:
                qty = max(rounded, min_qty)
        else:
            qty = quantity

        # Price
        px = price
        if price is not None:
            tick = float(filters.get('PRICE_FILTER', {}).get('tickSize', 0) or 0)
            min_price = float(filters.get('PRICE_FILTER', {}).get('minPrice', 0) or 0)
            px = max(self._round_step(price, tick), min_price) if tick else price

        # Notional (spot: MIN_NOTIONAL, futures: NOTIONAL or MIN_NOTIONAL)
        if px is not None and qty and qty > 0:
            min_notional = None
            # futures sometimes exposes NOTIONAL, spot MIN_NOTIONAL
            if 'MIN_NOTIONAL' in filters:
                mn = filters.get('MIN_NOTIONAL', {})
                # Binance sometimes uses 'minNotional', sometimes 'notional'
                min_notional = float(mn.get('minNotional') or mn.get('notional') or mn.get('minNotionalValue') or 0)
            if (min_notional is None or min_notional == 0) and 'NOTIONAL' in filters:
                mn = filters.get('NOTIONAL', {})
                min_notional = float(mn.get('minNotional') or mn.get('notional') or mn.get('minNotionalValue') or 0)
            if min_notional and (qty * (px or 0)) < float(min_notional):
                # Do not auto-upsize risking more than requested; signal caller to skip
                qty = 0.0

        return qty, px

    # ---------- Market data ----------
    def get_server_time(self):
        return self.client.get_server_time()

    def get_ticker_24hr(self):
        try:
            if Settings.OFFLINE_MODE:
                # Minimal synthetic subset for tests/debug
                return [
                    {'symbol': 'BTCUSDT', 'quoteVolume': '100000000'},
                    {'symbol': 'ETHUSDT', 'quoteVolume': '50000000'},
                    {'symbol': 'XRPUSDT', 'quoteVolume': '30000000'},
                ]
            # For futures, fallback to spot tickers for ranking simplicity
            tickers = self.client.get_ticker()
            self.logger.debug(f"Ticker sayisi {len(tickers)}")
            return tickers
        except Exception as e:
            self.logger.error(f"get_ticker_24hr hata: {e}")
            return []

    def get_ticker(self, symbol: str):
        """Get ticker information for a single symbol including bid/ask prices"""
        try:
            if Settings.OFFLINE_MODE:
                # Use realistic simulator with symbol parameter
                return self.client.get_ticker(symbol=symbol)
            return self.client.get_ticker(symbol=symbol)
        except Exception as e:
            self.logger.error(f"get_ticker({symbol}) hata: {e}")
            return None

    def get_top_pairs(self, limit=150):
        try:
            self.logger.info(f"Top {limit} pariteler aliniyor")
            tickers = self.get_ticker_24hr()
            if not tickers:
                self.logger.warning("Ticker listesi boş döndü")
                return []

            usdt_pairs = [t for t in tickers if t.get('symbol','').endswith('USDT')]
            self.logger.debug(f"USDT parite sayisi {len(usdt_pairs)}")

            # filter known stablecoins as base
            stable = {'USDT','USDC','BUSD','DAI','TUSD','USDP','USDK','USDN','USDX','HUSD','GUSD'}
            filtered = []
            for t in usdt_pairs:
                base = t['symbol'][:-4]
                if base not in stable:
                    filtered.append(t)

            sorted_pairs = sorted(filtered, key=lambda x: float(x.get('quoteVolume', 0.0) or 0.0), reverse=True)
            result = [p['symbol'] for p in sorted_pairs[:limit]]
            self.logger.info(f"Top pair sonucu {len(result)}")
            return result

        except Exception as e:
            self.logger.error(f"get_top_pairs hata: {e}")
            return []

    def get_historical_klines(self, symbol, interval, limit=500):
        if Settings.OFFLINE_MODE:
            # Generate synthetic OHLCV walk for deterministic offline tests
            import time
            now_ms = int(time.time() * 1000)
            # Map common intervals to milliseconds, default 1h
            interval_map = {
                '1m': 60_000,
                '3m': 180_000,
                '5m': 300_000,
                '15m': 900_000,
                '30m': 1_800_000,
                '1h': 3_600_000,
                '2h': 7_200_000,
                '4h': 14_400_000,
                '6h': 21_600_000,
                '8h': 28_800_000,
                '12h': 43_200_000,
                '1d': 86_400_000,
            }
            step_ms = interval_map.get(interval, 3_600_000)
            start = now_ms - step_ms * limit
            price = 100.0 + (hash(symbol) % 100)  # symbol-based base
            out = []
            for i in range(limit):
                ts = start + i * step_ms
                # random-ish but deterministic-ish using i & symbol hash
                delta = ((hash(symbol) >> (i % 16)) & 0xF) / 200.0  # up to ~0.08
                direction = 1 if ((hash(symbol) + i) % 2 == 0) else -1
                open_p = price
                close_p = max(0.1, open_p * (1 + direction * delta))
                high_p = max(open_p, close_p) * (1 + 0.001)
                low_p = min(open_p, close_p) * (1 - 0.001)
                vol = 1000 + ((hash(symbol) + i) % 5000)
                quote_vol = vol * (open_p + close_p) / 2
                price = close_p
                out.append([
                    ts, f"{open_p:.4f}", f"{high_p:.4f}", f"{low_p:.4f}", f"{close_p:.4f}", f"{vol:.4f}",
                    ts + step_ms - 1, f"{quote_vol:.4f}", 0, f"{vol/2:.4f}", f"{quote_vol/2:.4f}", "0"
                ])
            return out
        # Live / normal mode
        if self.mode == "futures":
            # Use spot klines for simplicity; could switch to futures klines if needed
            return self.client.get_klines(symbol=symbol, interval=interval, limit=limit)
        return self.client.get_klines(symbol=symbol, interval=interval, limit=limit)

    def get_klines(self, symbol, interval="1h", limit=500):
        """Get klines data - wrapper around get_historical_klines for compatibility"""
        return self.get_historical_klines(symbol, interval, limit)

    def get_order_book(self, symbol: str, limit: int = 10):
        """Get order book depth"""
        try:
            if self.mode == "futures":
                return self.client.futures_order_book(symbol=symbol, limit=limit)
            return self.client.get_order_book(symbol=symbol, limit=limit)
        except Exception as e:
            self.logger.error(f"Order book fetch failed for {symbol}: {e}")
            return {'bids': [], 'asks': []}

    def get_historical_data(self, symbol, interval="1h", days=30):
        klines = self.get_historical_klines(symbol, interval, limit=days*24)
        df = pd.DataFrame(klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'count', 'taker_buy_volume',
            'taker_buy_quote_volume', 'ignore'
        ])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        for col in ['open','high','low','close','volume','quote_volume']:
            df[col] = pd.to_numeric(df[col])
        return df

    # ---------- Trading ----------
    def place_order(self, symbol, side, order_type, quantity, price=None, **kwargs):
        attempt = 0
        last_err = None
        while attempt < Settings.RETRY_MAX_ATTEMPTS:
            try:
                if Settings.OFFLINE_MODE:
                    # Return synthetic executed order immediately
                    return {
                        'symbol': symbol,
                        'side': side,
                        'type': order_type,
                        'orderId': int(time.time()*1000),
                        'price': price if price is not None else None,
                        'executedQty': str(quantity),
                        'origQty': str(quantity),
                        'partialFill': False
                    }
                qty, px = self.quantize(symbol, quantity, price)
                if qty is None or qty <= 0:
                    self.logger.warning(f"{symbol} order iptal: hesaplanan miktar minQty altinda (risk_qty={quantity})")
                    return None
                if self.mode == "futures":
                    if order_type == "MARKET":
                        resp = self.client.futures_create_order(
                            symbol=symbol, side=side, type="MARKET", quantity=qty
                        )
                    elif order_type in {"STOP_MARKET","TAKE_PROFIT_MARKET"}:
                        resp = self.client.futures_create_order(
                            symbol=symbol, side=side, type=order_type,
                            stopPrice=kwargs.get('stopPrice') or px,
                            closePosition=kwargs.get('closePosition', True),
                            timeInForce=kwargs.get('timeInForce', 'GTC')
                        )
                    else:
                        resp = self.client.futures_create_order(
                            symbol=symbol, side=side, type=order_type, quantity=qty, price=px,
                            timeInForce=kwargs.get('timeInForce', 'GTC')
                        )
                elif order_type == "MARKET":
                    resp = self.client.create_order(symbol=symbol, side=side, type="MARKET", quantity=qty)
                else:
                    resp = self.client.create_order(symbol=symbol, side=side, type=order_type, quantity=qty, price=px)
                # Simulate partial fill probability for robustness testing (only in testnet or if enabled)
                if Settings.USE_TESTNET and order_type == "MARKET":
                    if not isinstance(resp, dict):
                        self.logger.warning("Order response is not a dict; partial fill simulation skipped")
                    elif random.random() < 0.15:  # 15% partial fill
                        filled_qty = qty * random.uniform(0.3, 0.8)
                        resp['executedQty'] = str(filled_qty)
                        resp['origQty'] = str(qty)
                        resp['partialFill'] = True
                    else:
                        resp['executedQty'] = str(qty)
                        resp['origQty'] = str(qty)
                        resp['partialFill'] = False
                return resp
            except BinanceAPIException as e:
                last_err = e
                # Rate limit metrics (429/418)
                try:
                    if getattr(e, 'status_code', None) in (418, 429):
                        if self.metrics:
                            self.metrics.record_rate_limit_hit(getattr(e, 'status_code', 'err'))
                except Exception:
                    pass
                # Backoff and observe
                sleep_sec = Settings.RETRY_BACKOFF_BASE_SEC * (Settings.RETRY_BACKOFF_MULT ** attempt)
                try:
                    if self.metrics:
                        self.metrics.observe_backoff_seconds(sleep_sec)
                except Exception:
                    pass
                time.sleep(sleep_sec)
                attempt += 1
            except Exception as e:
                last_err = e
                # Generic short backoff for unknown errors
                try:
                    if self.metrics:
                        self.metrics.observe_backoff_seconds(0.2)
                except Exception:
                    pass
                time.sleep(0.2)
                attempt += 1
        self.logger.error(f"Order error after retries: {last_err}")
        return None

    # ---------- Spot OCO (TakeProfit + StopLoss) ----------
    def place_oco_order(self, symbol: str, side: str, quantity: float, take_profit: float, stop_loss: float):
        """Place a spot OCO order (only available in spot mode). Returns API response or None.
        For a long (BUY entry) we exit with SELL OCO: limit (take profit) + stop-limit (stop loss).
        We derive a stopLimitPrice slightly below stopPrice for SELL to increase fill probability.
        """
        if self.mode != 'spot':
            return None
        try:
            qty, _ = self.quantize(symbol, quantity, None)
            if qty is None or qty <= 0:
                self.logger.warning(f"OCO iptal: {symbol} miktar minQty altinda")
                return None
            # Quantize prices
            _, tp_px = self.quantize(symbol, qty, take_profit)
            _, sl_px = self.quantize(symbol, qty, stop_loss)
            offset = 0.001
            if sl_px is None:
                self.logger.error("sl_px is None")
                return None
            exit_side = 'SELL' if side.upper() == 'BUY' else 'BUY'
            if exit_side == 'SELL':
                stop_limit_price = sl_px * (1 - offset)
            else:
                stop_limit_price = sl_px * (1 + offset)
            _, stop_limit_price = self.quantize(symbol, qty, stop_limit_price)
            try:
                if stop_limit_price is not None and sl_px is not None:
                    if exit_side == 'SELL' and float(stop_limit_price) >= float(sl_px):
                        stop_limit_price = float(sl_px) * (1 - offset)
                    elif exit_side == 'BUY' and float(stop_limit_price) <= float(sl_px):
                        stop_limit_price = float(sl_px) * (1 + offset)
            except Exception:
                pass
            try:
                resp = self.client.create_oco_order(
                    symbol=symbol,
                    side=exit_side,
                    quantity=f"{qty}" if isinstance(qty, float) else qty,
                    price=f"{tp_px}" if isinstance(tp_px, float) else tp_px,
                    stopPrice=f"{sl_px}" if isinstance(sl_px, float) else sl_px,
                    stopLimitPrice=f"{stop_limit_price}" if isinstance(stop_limit_price, float) else stop_limit_price,
                    stopLimitTimeInForce='GTC'
                )
                return resp
            except Exception as oe:
                # Fallback: OCO yoksa iki ayri emir dene (LIMIT TP + STOP_LOSS_LIMIT SL)
                self.logger.warning(f"OCO failed, applying fallback for {symbol}: {oe}")
                fallback_reports = []
                try:
                    tp_order = self.client.create_order(
                        symbol=symbol,
                        side=exit_side,
                        type='LIMIT',
                        quantity=f"{qty}" if isinstance(qty, float) else qty,
                        price=f"{tp_px}" if isinstance(tp_px, float) else tp_px,
                        timeInForce='GTC'
                    )
                    if isinstance(tp_order, dict) and tp_order.get('orderId') is not None:
                        fallback_reports.append({'orderId': tp_order.get('orderId')})
                except Exception as te:
                    self.logger.error(f"Fallback TP LIMIT failed {symbol}: {te}")
                try:
                    sl_order = self.client.create_order(
                        symbol=symbol,
                        side=exit_side,
                        type='STOP_LOSS_LIMIT',
                        quantity=f"{qty}" if isinstance(qty, float) else qty,
                        price=f"{stop_limit_price}" if isinstance(stop_limit_price, float) else stop_limit_price,
                        stopPrice=f"{sl_px}" if isinstance(sl_px, float) else sl_px,
                        timeInForce='GTC'
                    )
                    if isinstance(sl_order, dict) and sl_order.get('orderId') is not None:
                        fallback_reports.append({'orderId': sl_order.get('orderId')})
                except Exception as se:
                    self.logger.error(f"Fallback SL STOP_LOSS_LIMIT failed {symbol}: {se}")
                if fallback_reports:
                    return {'orderReports': fallback_reports, 'fallback': True}
                return None
        except Exception as e:
            self.logger.error(f"OCO order error {symbol}: {e}")
            return None

    def place_futures_protection(self, symbol: str, side: str, quantity: float, take_profit: float, stop_loss: float):
        """Place futures protection orders (STOP_MARKET + TAKE_PROFIT_MARKET).
        Returns dict with sl_id and tp_id or None if failed.
        For BUY entry: exit with SELL orders
        For SELL entry: exit with BUY orders
        """
        if self.mode != 'futures':
            self.logger.error(f"place_futures_protection called in {self.mode} mode")
            return None

        if Settings.OFFLINE_MODE:
            # Simulate successful futures protection
            return {
                'sl_id': f'sim_sl_{int(time.time()*1000)}',
                'tp_id': f'sim_tp_{int(time.time()*1000)}',
                'symbol': symbol
            }

        try:
            qty, _ = self.quantize(symbol, quantity, None)
            if qty is None or qty <= 0:
                self.logger.warning(f"Futures protection iptal: {symbol} miktar minQty altinda")
                return None

            # Determine exit side
            exit_side = 'SELL' if side.upper() == 'BUY' else 'BUY'

            # Quantize protection prices
            _, tp_px = self.quantize(symbol, qty, take_profit)
            _, sl_px = self.quantize(symbol, qty, stop_loss)

            if tp_px is None or sl_px is None:
                self.logger.error(f"Price quantization failed: tp={tp_px}, sl={sl_px}")
                return None

            # Place STOP_MARKET order (stop loss)
            sl_resp = self.client.futures_create_order(
                symbol=symbol,
                side=exit_side,
                type='STOP_MARKET',
                stopPrice=f"{sl_px}",
                closePosition=True,
                timeInForce='GTC'
            )

            # Place TAKE_PROFIT_MARKET order (take profit)
            tp_resp = self.client.futures_create_order(
                symbol=symbol,
                side=exit_side,
                type='TAKE_PROFIT_MARKET',
                stopPrice=f"{tp_px}",
                closePosition=True,
                timeInForce='GTC'
            )

            if sl_resp and tp_resp:
                result = {
                    'sl_id': sl_resp.get('orderId'),
                    'tp_id': tp_resp.get('orderId'),
                    'symbol': symbol,
                    'sl_resp': sl_resp,
                    'tp_resp': tp_resp
                }
                self.logger.info(f"Futures protection placed: {symbol} SL:{result['sl_id']} TP:{result['tp_id']}")
                return result
            self.logger.error(f"Futures protection failed: SL={bool(sl_resp)}, TP={bool(tp_resp)}")
            return None

        except Exception as e:
            self.logger.error(f"Futures protection error {symbol}: {e}")
            return None

    def get_open_orders(self, symbol=None):
        if Settings.OFFLINE_MODE:
            return []
        if self.mode == "futures":
            if symbol:
                return list(self.client.futures_get_open_orders(symbol=symbol))
            return self.client.futures_get_open_orders()
        return self.client.get_open_orders(symbol=symbol)

    def get_account_info(self):
        if self.mode == "futures":
            # Use V2 account endpoint for futures
            try:
                return self._signed_request_v2("GET", "/fapi/v2/account")
            except Exception as e:
                self.logger.error(f"futures account V2 endpoint error: {e}")
                return {}
        else:
            # Use spot account endpoint
            return self.client.get_account()

    def get_account(self):
        """Alias for get_account_info for trader compatibility"""
        return self.get_account_info()

    def get_asset_balance(self, asset):
        if Settings.OFFLINE_MODE:
            return 1000.0
        if self.mode == "futures":
            try:
                # Use V2 account endpoint
                account = self._signed_request_v2("GET", "/fapi/v2/account")
                assets = account.get('assets', [])
                for a in assets:
                    if a.get('asset') == asset:
                        return float(a.get('availableBalance', 0))
                return 0.0
            except Exception as e:
                self.logger.error(f"get_asset_balance error: {e}")
                return 0.0
        else:
            bal = self.client.get_asset_balance(asset=asset)
            if isinstance(bal, dict):
                return float(bal['free']) if bal else 0.0
            self.logger.error("bal is not a dictionary")
            return 0.0

    def get_positions(self):
        """Return current position info list (simplified) for reconciliation."""
        if Settings.OFFLINE_MODE:
            return []
        try:
            if self.mode == 'futures':
                # Use V2 endpoint for futures positions
                raw = self._signed_request_v2("GET", "/fapi/v2/positionRisk")
                positions = []
                for p in raw:
                    amt = float(p.get('positionAmt') or 0.0)
                    if abs(amt) < 1e-12:
                        continue
                    entry_price = float(p.get('entryPrice') or 0.0)
                    symbol = p.get('symbol')
                    side = 'BUY' if amt > 0 else 'SELL'
                    positions.append({
                        'symbol': symbol,
                        'side': side,
                        'size': abs(amt),
                        'entry_price': entry_price
                    })
                return positions
            return []
        except Exception as e:
            self.logger.error(f"get_positions error: {e}")
            return []

    def fetch_market_data(self, endpoint):
        """Fetch market data from Binance API with enhanced error handling."""
        if Settings.OFFLINE_MODE:
            # Return minimal deterministic payload simulating a ticker snapshot
            return {"offline": True, "endpoint": endpoint, "ts": int(time.time()*1000)}
        response = None
        try:
            response = requests.get(endpoint, timeout=10)
            # Observe X-MBX-USED-WEIGHT header if present
            try:
                if response is not None and hasattr(response, 'headers') and self.metrics:
                    used_weight = response.headers.get('X-MBX-USED-WEIGHT-1m') or response.headers.get('X-MBX-USED-WEIGHT')
                    if used_weight is not None:
                        self.metrics.set_used_weight(float(used_weight))
            except Exception:
                pass
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            self.logger.error("Request timed out")
        except requests.exceptions.HTTPError as e:
            if response is not None and hasattr(response, 'status_code'):
                if response.status_code == 429:
                    self.logger.warning("Rate limit exceeded")
                    try:
                        if self.metrics:
                            self.metrics.record_rate_limit_hit(429)
                    except Exception:
                        pass
                else:
                    self.logger.error(f"HTTP Error: {e}")
            else:
                self.logger.error(f"HTTP Error: {e} (response object not available)")
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
