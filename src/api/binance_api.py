import math
import pandas as pd
import requests
from binance import Client
from binance.exceptions import BinanceAPIException
from config.settings import Settings, RuntimeConfig
import time
import random
from src.utils.logger import get_logger
class BinanceAPI:
    def __init__(self, mode: str | None = None):
        self.mode = (mode or RuntimeConfig.get_market_mode()).lower()
        self.logger = get_logger("BinanceAPI")
        # Offline / test fallback: if OFFLINE_MODE skip real client heavy init (still create dummy for attribute safety)
        if Settings.OFFLINE_MODE:
            class _Dummy:
                def __getattr__(self, item):
                    def _f(*a, **k):
                        return [] if 'ticker' in item.lower() else {}
                    return _f
                # Explicit helpers used elsewhere
                def get_server_time(self):
                    import time; return {"serverTime": int(time.time()*1000)}
                def get_klines(self, symbol, interval, limit=500):
                    # delegate to BinanceAPI offline generator through outer class later if needed
                    return []
            self.client = _Dummy()
            self.logger.info("OFFLINE_MODE aktif: dummy Binance client kullanılıyor")
        else:
            self.client = Client(
                api_key=Settings.BINANCE_API_KEY,
                api_secret=Settings.BINANCE_API_SECRET,
                testnet=Settings.USE_TESTNET
            )

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

    def _round_step(self, value: float, step: float):
        if step in (0, None):
            return value
        return math.floor(value / step) * step

    def quantize(self, symbol: str, quantity: float, price: float | None = None):
        filters = self._get_filters(symbol)
        # Quantity
        step = float(filters.get('LOT_SIZE', {}).get('stepSize', 0) or 0)
        min_qty = float(filters.get('LOT_SIZE', {}).get('minQty', 0) or 0)
        # Yeni mantık: minQty altında kalan miktarı minQty'ye zorlamak yerine 0 döndür (işlem atlanır)
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
            self.logger.debug(f"Ticker sayısı {len(tickers)}")
            return tickers
        except Exception as e:
            self.logger.error(f"get_ticker_24hr hata: {e}")
            return []

    def get_top_pairs(self, limit=150):
        try:
            self.logger.info(f"Top {limit} pariteler alınıyor")
            tickers = self.get_ticker_24hr()
            if not tickers:
                self.logger.warning("Ticker listesi boş döndü")
                return []
                
            usdt_pairs = [t for t in tickers if t.get('symbol','').endswith('USDT')]
            self.logger.debug(f"USDT parite sayısı {len(usdt_pairs)}")
            
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
            import time, random
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
        else:
            return self.client.get_klines(symbol=symbol, interval=interval, limit=limit)

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
                    self.logger.warning(f"{symbol} order iptal: hesaplanan miktar minQty altında (risk_qty={quantity})")
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
                else:
                    if order_type == "MARKET":
                        resp = self.client.create_order(symbol=symbol, side=side, type="MARKET", quantity=qty)
                    else:
                        resp = self.client.create_order(symbol=symbol, side=side, type=order_type, quantity=qty, price=px)
                # Simulate partial fill probability for robustness testing (only in testnet or if enabled)
                if Settings.USE_TESTNET and order_type == "MARKET":
                    if not isinstance(resp, dict):
                        self.logger.warning("Order response is not a dict; partial fill simulation skipped")
                    else:
                        if random.random() < 0.15:  # 15% partial fill
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
                # Backoff
                sleep_sec = Settings.RETRY_BACKOFF_BASE_SEC * (Settings.RETRY_BACKOFF_MULT ** attempt)
                time.sleep(sleep_sec)
                attempt += 1
            except Exception as e:
                last_err = e
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
                self.logger.warning(f"OCO iptal: {symbol} miktar minQty altında")
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
        except Exception as e:
            self.logger.error(f"OCO order error {symbol}: {e}")
            return None

    def get_open_orders(self, symbol=None):
        if Settings.OFFLINE_MODE:
            return []
        if self.mode == "futures":
            if symbol:
                return [o for o in self.client.futures_get_open_orders(symbol=symbol)]
            return self.client.futures_get_open_orders()
        else:
            return self.client.get_open_orders(symbol=symbol)

    def get_account_info(self):
        return self.client.get_account()

    def get_asset_balance(self, asset):
        if Settings.OFFLINE_MODE:
            return 1000.0
        if self.mode == "futures":
            # Approximate via futures account balance
            balances = self.client.futures_account_balance()
            for b in balances:
                if b.get('asset') == asset:
                    return float(b.get('balance', 0))
            return 0.0
        else:
            bal = self.client.get_asset_balance(asset=asset)
            if isinstance(bal, dict):
                return float(bal['free']) if bal else 0.0
            else:
                self.logger.error("bal is not a dictionary")
                return 0.0

    def get_positions(self):
        """Return current position info list (simplified) for reconciliation."""
        if Settings.OFFLINE_MODE:
            return []
        try:
            if self.mode == 'futures':
                raw = self.client.futures_position_information()
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
            else:
                # Spot'ta tam envanter scan gerekli; basit placeholder (daha sonra genişletilebilir)
                return []
        except Exception:
            return []

    def fetch_market_data(self, endpoint):
        """Fetch market data from Binance API with enhanced error handling."""
        if Settings.OFFLINE_MODE:
            # Return minimal deterministic payload simulating a ticker snapshot
            return {"offline": True, "endpoint": endpoint, "ts": int(time.time()*1000)}
        response = None
        try:
            response = requests.get(endpoint, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            self.logger.error("Request timed out")
        except requests.exceptions.HTTPError as e:
            if response is not None and hasattr(response, 'status_code'):
                if response.status_code == 429:
                    self.logger.warning("Rate limit exceeded")
                else:
                    self.logger.error(f"HTTP Error: {e}")
            else:
                self.logger.error(f"HTTP Error: {e} (response object not available)")
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
