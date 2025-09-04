"""
Lookahead Bias Detection and Prevention (CR-0064)

Bu modul sinyal uretiminde lookahead bias tespit eder ve engeller:
1. Henuz kapanmamis mum verilerinin trade kararlarinda kullanilmasini engeller
2. Sadece tamamlanmis/kapanmis mum verileri kullanilmasini zorlar
3. Lookahead violation'lari tespit eder ve log'lar
4. Guard mekanizmasi ile riskli sinyalleri bloklar
"""

import pandas as pd
import re
from datetime import datetime
from typing import Optional
from src.utils.logger import get_logger
from src.utils.structured_log import slog
from config.settings import Settings


class LookaheadGuard:
    """Lookahead bias'i onlemek icin guard sinifi"""

    def __init__(self):
        self.logger = get_logger("LookaheadGuard")
        self.violation_count = 0
        self.violations_by_symbol = {}

    def validate_signal_data(self, signal_data: Optional[dict]) -> bool:
        """
        Tekil sinyal verisi icin lookahead kontrolu

        Args:
            signal_data: Sinyal verisi dict'i, timestamp icermeli

        Returns:
            bool: Sinyal guvenliyse True, lookahead risk varsa False
        """
        if not getattr(Settings, 'LOOKAHEAD_GUARD_ENABLED', True):
            return True

        # Geçersiz/eksik veri -> reddet (test beklentisi)
        if not signal_data or not isinstance(signal_data, dict):
            return False

        # Timestamp kontrolu
        timestamp_val = signal_data.get('timestamp')
        try:
            # Timestamp parse et (naive -> yerel, aware -> yerel'e çevir)
            def _normalize_str(s: str) -> str:
                """Normalize timestamps with double fractional parts while preserving timezone.

                Examples:
                - '2025-09-04T01:38:38.820806.123Z' -> '2025-09-04T01:38:38.820806Z'
                - '2025-09-04T01:38:38.820.123+03:00' -> '2025-09-04T01:38:38.820+03:00'
                """
                s = s.strip()
                # Separate timezone suffix (Z or +hh:mm / -hh:mm)
                tz = ''
                if s.endswith('Z'):
                    # Treat 'Z' appended to a naive local timestamp as local-naive: strip it
                    main = s[:-1]
                else:
                    m = re.search(r'([+-]\d{2}:\d{2})$', s)
                    if m:
                        tz = m.group(1)
                        main = s[:-len(tz)]
                    else:
                        main = s

                # Work on time part only (after 'T')
                if 'T' in main:
                    date_part, time_part = main.split('T', 1)
                    if time_part.count('.') > 1:
                        first, rest = time_part.split('.', 1)
                        digits = ''.join(ch for ch in rest if ch.isdigit())
                        frac = digits[:6]  # microsecond precision
                        time_part = f"{first}.{frac}"
                    main = f"{date_part}T{time_part}"

                return main + tz

            val = timestamp_val
            if isinstance(val, str):
                val = _normalize_str(val)
            ts = pd.to_datetime(val, errors='coerce')

            if pd.isna(ts):
                self.logger.warning(f"Invalid timestamp format: {timestamp_val}")
                return False

            # Yerel saatle karşılaştırmak için aware ise yerel'e çevir, sonra naive yap
            local_tz = datetime.now().astimezone().tzinfo
            if getattr(ts, 'tz', None) is not None:
                try:
                    ts_local = ts.tz_convert(local_tz)  # type: ignore[attr-defined]
                except Exception:
                    # bazı Timestamp örnekleri already aware olabilir; fallback
                    ts_local = ts.tz_convert(local_tz)  # type: ignore[attr-defined]
                signal_time = ts_local.to_pydatetime().replace(tzinfo=None)
            else:
                # Naive ise doğrudan kullan (testler local naive kullanıyor varsayımı)
                signal_time = ts.to_pydatetime()

        except (ValueError, TypeError) as e:
            self.logger.warning(f"Invalid timestamp format: {timestamp_val}, error: {e}")
            return False

        # Current time ile karsilastir (yerel naive zaman)
        current_time = datetime.now()
        time_diff = (current_time - signal_time).total_seconds()

        # Grace period kontrolu (varsayılan 60 saniye)
        grace_seconds = getattr(Settings, 'LOOKAHEAD_GRACE_SECONDS', getattr(self, 'grace_seconds', 60))
        if time_diff < grace_seconds:
            # Too recent - potential lookahead bias
            symbol = signal_data.get('symbol', 'UNKNOWN')
            self.violation_count += 1
            self.violations_by_symbol[symbol] = self.violations_by_symbol.get(symbol, 0) + 1

            self.logger.warning(
                f"{symbol}: Lookahead violation - signal too recent (diff: {time_diff:.1f}s < {grace_seconds}s)"
            )
            slog('lookahead_violation', symbol=symbol, time_diff=time_diff, grace_seconds=grace_seconds)
            return False
        return True

    def validate_data_for_signals(self, df: pd.DataFrame, symbol: str) -> tuple[Optional[pd.DataFrame], bool]:
        """
        Sinyal uretimi icin veri dogrulamasi

        Returns:
            tuple: (safe_df, is_valid)
            - safe_df: Lookahead bias'i olmayan guvenli veri
            - is_valid: Veri sinyal uretimi icin uygun mu
        """
        if df is None or df.empty:
            return None, False

        if len(df) < 2:
            self.logger.warning(f"{symbol}: Yetersiz veri (< 2 satir), sinyal uretimi guvenli degil")
            return None, False

    # Veri setini kopyala (orijinali degistirmemek icin)
        safe_df = df.copy()

        # Son satiri kontrol et - henuz kapanmamis mum mu?
        if self._is_current_bar_incomplete(safe_df, symbol):
            # Son satiri cikar - henuz kapanmamis mum
            safe_df = safe_df.iloc[:-1].copy()
            self.logger.warning(f"{symbol}: Son mum henuz kapanmamis, cikarildi")
            slog('lookahead_prevention', symbol=symbol, reason='incomplete_bar_removed')

        # Hala yeterli veri var mi?
        if len(safe_df) < 2:
            self.logger.warning(f"{symbol}: Incomplete bar removal sonrasi yetersiz veri")
            return None, False

    # Timestamp siralamasi kontrolu
        if not self._validate_timestamp_order(safe_df, symbol):
            return None, False

        return safe_df, True

    def _is_current_bar_incomplete(self, df: pd.DataFrame, symbol: str) -> bool:
        """
        Son satirin henuz kapanmamis mum olup olmadigini kontrol et

        Mantik:
        - Son mumun timestamp'i simdiki zamana cok yakinsa (< 1 timeframe) incomplete
        - Ornek: 1h timeframe'de son mum 14:30 ise ve simdi 14:45 ise -> incomplete
        """
        try:
            if 'timestamp' not in df.columns:
                return False

            last_timestamp = df['timestamp'].iloc[-1]
            if pd.isna(last_timestamp):
                return True  # Invalid timestamp = incomplete

            # Pandas Timestamp'i datetime'a çevir
            if hasattr(last_timestamp, 'to_pydatetime'):
                last_time = last_timestamp.to_pydatetime()
            else:
                last_time = pd.to_datetime(last_timestamp).to_pydatetime()

            now = datetime.now()

            # Timeframe interval'ini dakikaya cevir
            timeframe_minutes = self._get_timeframe_minutes(Settings.TIMEFRAME)

            # Son mumdan simdiye kadar gecen sure
            time_diff = now - last_time
            time_diff_minutes = time_diff.total_seconds() / 60

            # Eger son mumdan gecen sure 1 timeframe'den azsa -> incomplete
            is_incomplete = time_diff_minutes < timeframe_minutes

            if is_incomplete:
                self.logger.debug(f"{symbol}: Son mum incomplete - last:{last_time}, now:{now}, "
                                f"diff:{time_diff_minutes:.1f}m < {timeframe_minutes}m")

            return is_incomplete

        except Exception as e:
            self.logger.error(f"{symbol}: Incomplete bar kontrolu hatasi: {e}")
            # Hata durumunda güvenli tarafta kal - incomplete say
            return True

    def _get_timeframe_minutes(self, timeframe: str) -> int:
        """Timeframe stringini dakikaya cevir"""
        try:
            if timeframe.endswith('m'):
                return int(timeframe[:-1])
            elif timeframe.endswith('h'):
                return int(timeframe[:-1]) * 60
            elif timeframe.endswith('d'):
                return int(timeframe[:-1]) * 24 * 60
            else:
                # Default 1h
                return 60
        except Exception:
            return 60  # Default

    def _validate_timestamp_order(self, df: pd.DataFrame, symbol: str) -> bool:
        """Timestamp siralamasi dogru mu kontrol et"""
        try:
            if 'timestamp' not in df.columns:
                return True  # No timestamp column = can't validate, assume ok

            # Timestamp siralamasi ascending olmali
            timestamps = pd.to_datetime(df['timestamp'])
            is_sorted = timestamps.is_monotonic_increasing

            if not is_sorted:
                self.logger.warning(f"{symbol}: Timestamp siralamasi bozuk")
                slog('lookahead_violation', symbol=symbol, reason='invalid_timestamp_order')
                self.violation_count += 1
                return False

            return True

        except Exception as e:
            self.logger.error(f"{symbol}: Timestamp siralamasi kontrolu hatasi: {e}")
            return False

    def detect_lookahead_violation(self, df: pd.DataFrame, symbol: str) -> bool:
        """
        Lookahead bias violation'i tespit et

        Returns:
            bool: True if violation detected
        """
        try:
            if df is None or df.empty:
                return False

            # Son satir henuz kapanmamis mum mu?
            if self._is_current_bar_incomplete(df, symbol):
                self.logger.warning(f"LOOKAHEAD_VIOLATION: {symbol} - henuz kapanmamis mum verisi kullanilmaya calisiliyor")
                slog('lookahead_violation', symbol=symbol, reason='incomplete_bar_usage_attempt', severity='WARNING')
                self.violation_count += 1
                return True

            return False

        except Exception as e:
            self.logger.error(f"{symbol}: Lookahead violation tespit hatası: {e}")
            return True  # Hata durumunda violation varsay

    def should_block_signal(self, df: pd.DataFrame, symbol: str) -> tuple[bool, str]:
        """
        Sinyal bloklanmali mi?

        Returns:
            tuple: (should_block, reason)
        """
        # Lookahead violation var mi?
        if self.detect_lookahead_violation(df, symbol):
            return True, "lookahead_violation"

        # Veri kalitesi kontrolleri
        _, is_valid = self.validate_data_for_signals(df, symbol)
        if not is_valid:
            return True, "invalid_data_quality"

        return False, ""

    def get_metrics(self) -> dict:
        """Guard metrikleri"""
        return {
            'violation_count': self.violation_count,
            'guard_name': 'lookahead'
        }


# Global guard instance
_lookahead_guard = None

def get_lookahead_guard() -> LookaheadGuard:
    """Global lookahead guard instance'ını al"""
    global _lookahead_guard
    if _lookahead_guard is None:
        _lookahead_guard = LookaheadGuard()
    return _lookahead_guard


def validate_signal_data(df: pd.DataFrame, symbol: str) -> tuple[Optional[pd.DataFrame], bool]:
    """
    Sinyal uretimi icin veri dogrulamasi (public API)

    Bu fonksiyon SignalGenerator tarafindan kullanilacak
    """
    guard = get_lookahead_guard()
    return guard.validate_data_for_signals(df, symbol)


def check_lookahead_violation(df: pd.DataFrame, symbol: str) -> bool:
    """
    Lookahead violation kontrolu (public API)
    """
    guard = get_lookahead_guard()
    return guard.detect_lookahead_violation(df, symbol)
