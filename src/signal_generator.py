import pandas as pd
from src.indicators import IndicatorCalculator
from src.data_fetcher import DataFetcher
from src.utils.logger import get_logger
from config.settings import Settings
import json
import threading
import os

class SignalGenerator:
    def __init__(self):
        self.data_fetcher = DataFetcher()
        self.indicator_calc = IndicatorCalculator()
        self.logger = get_logger("SignalGenerator")
        # Histerezis için önceki sinyaller (thread-safe)
        self._prev_signals = {}
        self._lock = threading.Lock()

    # ---------------- Internal Helpers -----------------
    def _serialize_indicators(self, indicators: dict):
        """Pandas Series içeren indikatör sonuçlarını JSON uyumlu hale getir.

        Stratejik olarak sadece SON değeri saklıyoruz; böylece dosya boyutu
        küçülüyor ve serialization hatası oluşmuyor. Gerekirse ileride
        'last_n' parametresi eklenebilir.
        """
        import pandas as pd  # lokal import: sadece gerektiğinde
        from datetime import datetime
        out = {}
        for name, val in indicators.items():
            if isinstance(val, pd.Series):
                # Tek seri -> son değer
                try:
                    out[name] = self._to_primitive(val.iloc[-1])
                except Exception:
                    out[name] = None
            elif isinstance(val, dict):
                inner = {}
                for k, v in val.items():
                    if isinstance(v, pd.Series):
                        try:
                            inner[k] = self._to_primitive(v.iloc[-1])
                        except Exception:
                            inner[k] = None
                    else:
                        inner[k] = self._to_primitive(v)
                out[name] = inner
            else:
                out[name] = self._to_primitive(val)
        return out

    def _to_primitive(self, value):
        """Numpy / pandas / datetime türlerini JSON için primitive'e çevir."""
        import numpy as np
        import pandas as pd
        from datetime import datetime
        if isinstance(value, (pd.Timestamp, datetime)):
            return value.isoformat()
        if isinstance(value, (np.floating,)):
            return float(value)
        if isinstance(value, (np.integer,)):
            return int(value)
        if isinstance(value, (np.bool_,)):
            return bool(value)
        if hasattr(value, 'item') and callable(getattr(value, 'item')):
            try:
                return value.item()
            except Exception:
                pass
        return value

    def generate_signals(self, pairs=None):
        """Tüm pariteler için sinyal üret"""
        if pairs is None:
            pairs = self.data_fetcher.load_top_pairs()
        if not pairs:
            self.logger.warning("Sinyal üretmek için parite listesi boş")
            return {}

        signals = {}

        for pair in pairs:
            try:
                signal = self.generate_pair_signal(pair)
                if signal:
                    # Timestamp'i koru, ek olarak iso formatlı kopya ekle
                    if 'timestamp' in signal and not signal.get('timestamp_iso'):
                        ts_val = signal['timestamp']
                        try:
                            iso_val = ts_val.isoformat() if hasattr(ts_val, 'isoformat') else str(ts_val)
                        except Exception:
                            iso_val = str(ts_val)
                        signal['timestamp_iso'] = iso_val
                    # Diğer pandas serilerini JSON uyumlu hale getirmek istersen burada kısaltılabilir
                    signals[pair] = signal
            except Exception as e:
                self.logger.error(f"{pair} sinyal üretilemedi: {str(e)}")

        return signals

    def generate_pair_signal(self, symbol):
        """Tek bir parite için sinyal üret"""
        # Verileri yükle
        df = self.data_fetcher.get_pair_data(symbol, Settings.TIMEFRAME)

        if df is None or df.empty:
            self.logger.warning(f"{symbol} için veri bulunamadı")
            return None

        # İndikatörleri hesapla
        indicators_full = self.indicator_calc.calculate_all_indicators(df)

        # Puanları hesapla
        scores = self.indicator_calc.score_indicators(df, indicators_full)
        # Rejim filtresi (ADX düşükse sinyali BEKLE'ye zorlama)
        try:
            adx_val = scores['scores'].get('ADX')
            if adx_val is not None and hasattr(Settings, 'ADX_MIN_THRESHOLD') and adx_val < Settings.ADX_MIN_THRESHOLD:
                # Histerezis öncesi sinyali zayıflat
                scores['signal'] = 'BEKLE'
        except Exception:
            pass

        # Histerezis uygulama
        raw_signal = scores['signal']
        total_score = scores['total_score']
        final_signal = raw_signal
        with self._lock:
            prev = self._prev_signals.get(symbol)
        # Threshold override dosyasını (varsa) oku (hafif IO; gerekirse cache yapılabilir)
        try:
            th_path = os.path.join(Settings.DATA_PATH, 'processed', 'threshold_overrides.json')
            if os.path.isfile(th_path):
                with open(th_path, 'r', encoding='utf-8') as f:
                    thj = json.load(f)
                dyn_buy = thj.get('buy', Settings.BUY_SIGNAL_THRESHOLD)
                dyn_sell = thj.get('sell', Settings.SELL_SIGNAL_THRESHOLD)
                dyn_buy_exit = thj.get('buy_exit', dyn_buy - 5)
                dyn_sell_exit = thj.get('sell_exit', dyn_sell + 5)
            else:
                dyn_buy = Settings.BUY_SIGNAL_THRESHOLD
                dyn_sell = Settings.SELL_SIGNAL_THRESHOLD
                dyn_buy_exit = Settings.BUY_EXIT_THRESHOLD
                dyn_sell_exit = Settings.SELL_EXIT_THRESHOLD
        except Exception:
            dyn_buy = Settings.BUY_SIGNAL_THRESHOLD
            dyn_sell = Settings.SELL_SIGNAL_THRESHOLD
            dyn_buy_exit = Settings.BUY_EXIT_THRESHOLD
            dyn_sell_exit = Settings.SELL_EXIT_THRESHOLD

        try:
            buy_exit = min(dyn_buy_exit, dyn_buy - 1) if dyn_buy_exit >= dyn_buy else dyn_buy_exit
            sell_exit = max(dyn_sell_exit, dyn_sell + 1) if dyn_sell_exit <= dyn_sell else dyn_sell_exit
        except Exception:
            buy_exit = dyn_buy - 1
            sell_exit = dyn_sell + 1

        # Histerezis kararları (doğru indentation)
        if prev == 'AL' and raw_signal == 'BEKLE' and total_score >= buy_exit:
            final_signal = 'AL'
        elif prev == 'SAT' and raw_signal == 'BEKLE' and total_score <= sell_exit:
            final_signal = 'SAT'
        else:
            final_signal = raw_signal

        with self._lock:
            if final_signal in ('AL', 'SAT'):
                self._prev_signals[symbol] = final_signal
            elif prev in ('AL', 'SAT') and final_signal == 'BEKLE':
                # Pozisyondan çıktı
                self._prev_signals[symbol] = 'BEKLE'

        # Sonuçları birleştir
        # JSON'un sorunsuz kaydedilmesi için indikatörleri sadeleştir
        indicators_serialized = self._serialize_indicators(indicators_full)

        signal_data = {
            'symbol': symbol,
            'timestamp': df['timestamp'].iloc[-1],
            # hızlı erişim için iso string
            'timestamp_iso': df['timestamp'].iloc[-1].isoformat() if hasattr(df['timestamp'].iloc[-1], 'isoformat') else str(df['timestamp'].iloc[-1]),
            'close_price': df['close'].iloc[-1],
            'percent_change': float(((df['close'].iloc[-1] - df['close'].iloc[-2]) / df['close'].iloc[-2] * 100) if len(df) > 1 else 0.0),
            'volume_24h': self.get_24h_volume(symbol),
            'indicators': indicators_serialized,
            'scores': scores['scores'],
            'total_score': scores['total_score'],
            'contributions': scores.get('contributions', {}),
            'signal_raw': raw_signal,
            'signal': final_signal
        }

        return signal_data

    def get_24h_volume(self, symbol):
        """24 saatlik hacmi al"""
        try:
            from config.settings import Settings as _S
            if getattr(_S, 'OFFLINE_MODE', False):
                # Deterministic sentetik hacim (symbol hash'ına göre) -> 50k - 5M arası
                base = (abs(hash(symbol)) % 4_950_000) + 50_000
                return float(base)
            ticker = self.data_fetcher.api.client.get_ticker(symbol=symbol)
            if isinstance(ticker, dict):
                return float(ticker.get('quoteVolume') or ticker.get('volume') or 0.0)
            return 0.0
        except Exception:
            return 0.0

    def save_signals(self, signals):
        """Sinyalleri kaydet"""
        from datetime import datetime

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = f"{Settings.DATA_PATH}/processed/signals_{timestamp}.json"
        # Derin kopya / dönüştürme: timestamp'leri ve numpy tiplerini primitive'e çevir
        def convert_obj(obj):
            from datetime import datetime
            import pandas as pd
            import numpy as np
            if isinstance(obj, dict):
                return {k: convert_obj(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [convert_obj(v) for v in obj]
            if isinstance(obj, (pd.Timestamp, datetime)):
                return obj.isoformat()
            if isinstance(obj, (np.floating,)):
                return float(obj)
            if isinstance(obj, (np.integer,)):
                return int(obj)
            if isinstance(obj, (np.bool_,)):
                return bool(obj)
            if hasattr(obj, 'item') and callable(getattr(obj, 'item')):
                try:
                    return obj.item()
                except Exception:
                    return str(obj)
            return obj

        serializable = convert_obj(signals)
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(serializable, f, indent=2, ensure_ascii=False)
            self.logger.info(f"Sinyaller kaydedildi: {file_path}")
        except Exception as e:
            self.logger.error(f"Sinyaller kaydedilemedi: {e}")
        return file_path
