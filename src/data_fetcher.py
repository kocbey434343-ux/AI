import os
import json
import pandas as pd
from datetime import datetime, timedelta
from src.api.binance_api import BinanceAPI
from src.utils.logger import get_logger
from config.settings import Settings
from concurrent.futures import ThreadPoolExecutor

class DataFetcher:
    def __init__(self):
        self.api = BinanceAPI()
        self.logger = get_logger("DataFetcher")
        self.data_path = Settings.DATA_PATH
        self.ensure_directories()

    def ensure_directories(self):
        """Gerekli dizinleri oluştur"""
        os.makedirs(f"{self.data_path}/raw", exist_ok=True)
        os.makedirs(f"{self.data_path}/processed", exist_ok=True)
        os.makedirs(f"{self.data_path}/logs", exist_ok=True)

    def update_top_pairs(self, limit: int | None = None):
        """Top N (varsayılan 150) parite listesini güncelle.

        Spot USDT çifti olup base'i stable olmayanları 24h quoteVolume'a göre sıralar.
        """
        limit = limit or Settings.TOP_PAIRS_COUNT
        try:
            self.logger.info(f"Top {limit} parite listesi güncelleniyor...")
            top_pairs = self.api.get_top_pairs(limit)
            if not top_pairs:
                self.logger.warning("API boş liste döndürdü; önceki liste korunuyor")
                return False

            # JSON dosyasına kaydet (pretty + sorted uniq)
            unique = []
            for p in top_pairs:
                if p not in unique:
                    unique.append(p)

            file_path = f"{self.data_path}/top_150_pairs.json"
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(unique, f, indent=2)

            self.logger.info(f"{len(unique)} parite güncellendi ve kaydedildi: {file_path}")
            return True
        except Exception as e:
            self.logger.error(f"Parite güncelleme hatası: {str(e)}")
            return False

    def load_top_pairs(self, ensure: bool = True):
        """Top parite listesini yükle; eksik / yetersiz ise opsiyonel güncelle.

        ensure=True iken:
          - Dosya yoksa
          - Boşsa
          - Sayı istenen limitten azsa
          - Dosya çok eskiyse (varsayılan 60 dk)
        otomatik update tetiklenir.
        """
        limit = Settings.TOP_PAIRS_COUNT
        file_path = f"{self.data_path}/top_150_pairs.json"
        needs_update = False
        pairs: list[str] = []

        if os.path.exists(file_path):
            try:
                age_min = (datetime.now() - datetime.fromtimestamp(os.path.getmtime(file_path))).total_seconds() / 60.0
                with open(file_path, "r", encoding="utf-8") as f:
                    pairs = json.load(f) or []
                if not isinstance(pairs, list):
                    self.logger.warning("Parite listesi formatı bozuk, yeniden güncellenecek")
                    needs_update = True
                elif len(pairs) < limit:
                    self.logger.info(f"Parite listesi eksik ({len(pairs)}/{limit}), güncellenecek")
                    needs_update = True
                elif age_min > 60:  # 1 saatten eskiyse tazele
                    self.logger.info(f"Parite listesi {age_min:.1f} dk eski, tazeleniyor")
                    needs_update = True
            except Exception as e:
                self.logger.warning(f"Parite listesi okunamadı ({e}), yeniden alınacak")
                needs_update = True
        else:
            self.logger.info("Parite listesi dosyası yok, oluşturulacak")
            needs_update = True

        if ensure and needs_update:
            if self.update_top_pairs(limit):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        pairs = json.load(f) or []
                except Exception:
                    pairs = []

        # Geçici analiz limiti uygula (dosyayı bozmadan sadece dönen listede kısıtla)
        try:
            limit_override = getattr(Settings, 'ANALYSIS_PAIRS_LIMIT', 0) or 0
            if limit_override and isinstance(limit_override, int) and limit_override > 0:
                return pairs[:limit_override]
        except Exception:
            pass
        return pairs

    def ensure_top_pairs(self, force: bool = False):
        """Dışarıdan çağrı için: force veya yetersizlik durumunda güncelle."""
        pairs = self.load_top_pairs(ensure=not force)
        if force or len(pairs) < Settings.TOP_PAIRS_COUNT:
            self.update_top_pairs(Settings.TOP_PAIRS_COUNT)
            pairs = self.load_top_pairs(ensure=False)
        return pairs

    def fetch_pair_data(self, symbol, days=30, interval="1h"):
        """Belirli bir paritenin verilerini çek"""
        try:
            self.logger.info(f"{symbol} verileri çekiliyor...")
            df = self.api.get_historical_data(symbol, interval, days)

            # CSV dosyasına kaydet
            file_path = f"{self.data_path}/raw/{symbol}_{interval}.csv"
            df.to_csv(file_path, index=False)

            self.logger.info(f"{symbol} verileri kaydedildi: {file_path}")
            return True
        except Exception as e:
            self.logger.error(f"{symbol} veri çekme hatası: {str(e)}")
            return False

    def fetch_all_pairs_data(self, days=30, interval="1h"):
        """Tüm paritelerin verilerini çek"""
        pairs = self.load_top_pairs()
        success_count = 0

        for pair in pairs:
            if self.fetch_pair_data(pair, days, interval):
                success_count += 1

        self.logger.info(f"{success_count}/{len(pairs)} parite başarıyla çekildi")
        return success_count == len(pairs)

    # ---------------- Validation & Maintenance -----------------
    def _read_pair(self, symbol, interval):
        path = f"{self.data_path}/raw/{symbol}_{interval}.csv"
        if not os.path.exists(path):
            return None
        try:
            df = pd.read_csv(path, parse_dates=['timestamp'])
            return df
        except Exception:
            return None

    def validate_dataset(self, interval="1h", repair=False, min_rows=50):
        """Kayıtlı veri setini bütünlük açısından kontrol eder.

        Args:
            interval (str): Zaman aralığı
            repair (bool): Eksik veya bozuksa yeniden çekmeyi dener
            min_rows (int): Geçerli sayılması için minimum satır
        """
        raw_dir = f"{self.data_path}/raw"
        if not os.path.isdir(raw_dir):
            self.logger.warning("Ham veri klasörü yok, atlanıyor")
            return False

        csv_files = [f for f in os.listdir(raw_dir) if f.endswith(f"_{interval}.csv")] 
        if not csv_files:
            self.logger.warning("Doğrulanacak CSV bulunamadı")
            return False

        ok = 0
        for file in csv_files:
            symbol = file.replace(f"_{interval}.csv", "")
            df = self._read_pair(symbol, interval)
            if df is None:
                self.logger.warning(f"{symbol}: okunamadı")
                if repair:
                    self.fetch_pair_data(symbol, days=Settings.BACKTEST_DAYS, interval=interval)
                continue
            problems = []
            if 'timestamp' not in df.columns:
                problems.append('timestamp missing')
            if len(df) < min_rows:
                problems.append(f'yetersiz satır ({len(df)})')
            if df.isna().sum().sum() > 0:
                problems.append('NA değerler var')
            if problems:
                self.logger.warning(f"{symbol}: sorun -> {', '.join(problems)}")
                if repair:
                    self.logger.info(f"{symbol} yeniden çekiliyor (onarım)")
                    self.fetch_pair_data(symbol, days=Settings.BACKTEST_DAYS, interval=interval)
            else:
                ok += 1
        self.logger.info(f"Veri doğrulama tamamlandı: {ok}/{len(csv_files)} temiz")
        return ok == len(csv_files)

    def get_pair_data(self, symbol, interval="1h", auto_fetch=True):
        """Diskten parite verilerini yükle; yoksa çek ve normalize et"""
        file_path = f"{self.data_path}/raw/{symbol}_{interval}.csv"

        # Eğer veri yoksa çek
        if not os.path.exists(file_path) and auto_fetch:
            self.logger.warning(f"{symbol} verisi bulunamadı, çekiliyor...")
            if not self.fetch_pair_data(symbol, 30, interval):
                return None
        
        # Veriyi yükle
        if os.path.exists(file_path):
            try:
                return pd.read_csv(file_path, parse_dates=['timestamp'])
            except ValueError as e:
                # Common pandas error when parse_dates column missing
                self.logger.error(f"CSV parse_dates error for {symbol}: {e}")
                # Try to read without parse_dates and normalize
                try:
                    df = pd.read_csv(file_path)
                except Exception as read_e:
                    self.logger.error(f"{symbol} CSV okunamadı: {read_e}")
                    return None

                # Look for candidate time columns
                candidates = [c for c in df.columns if any(k in c.lower() for k in ['time', 'date', 'timestamp', 't'])]
                self.logger.info(f"{symbol} için zaman sütunu adayları: {candidates}")

                timestamp_col = None
                for c in candidates:
                    # prefer exact 'timestamp' or common names
                    if c.lower() in ('timestamp', 'open_time', 'time', 'date', 'datetime'):
                        timestamp_col = c
                        break
                if timestamp_col is None and candidates:
                    timestamp_col = candidates[0]

                if timestamp_col:
                    # Try to convert the column to datetime
                    try:
                        # If values look like integers (ms), try unit='ms'
                        sample = df[timestamp_col].dropna().iloc[0]
                        if isinstance(sample, (int, float)) or (isinstance(sample, str) and sample.isdigit()):
                            df['timestamp'] = pd.to_datetime(df[timestamp_col].astype('int64'), unit='ms', errors='coerce')
                        else:
                            df['timestamp'] = pd.to_datetime(df[timestamp_col], errors='coerce')

                        # If timestamp conversion failed for all, attempt fallback using index
                        if df['timestamp'].isna().all():
                            self.logger.warning(f"{symbol}: timestamp dönüşümü başarısız, index'ten denenecek")
                            try:
                                df['timestamp'] = pd.to_datetime(df.index, errors='coerce')
                            except Exception:
                                pass

                        # Save normalized CSV back so next read works
                        df.to_csv(file_path, index=False)
                        self.logger.info(f"{symbol} CSV normalize edildi ve kaydedildi: {file_path}")
                        return df
                    except Exception as conv_e:
                        self.logger.error(f"{symbol} timestamp normalize edilemedi: {conv_e}")
                        return None
                else:
                    self.logger.error(f"{symbol} için zaman sütunu bulunamadı: {file_path}")
                    return None
        
        # Dosya hiç yok
        return None

    def backup_data(self):
        """Verileri yedekle"""
        import shutil
        from datetime import datetime

        backup_dir = f"{Settings.BACKUP_PATH}/backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        os.makedirs(backup_dir, exist_ok=True)

        try:
            shutil.copytree(self.data_path, backup_dir)
            self.logger.info(f"Veriler yedeklendi: {backup_dir}")
            return True
        except Exception as e:
            self.logger.error(f"Yedekleme hatası: {str(e)}")
            return False

    def fetch_data_parallel(self, data_sources):
        """Fetch data from multiple sources in parallel."""
        with ThreadPoolExecutor() as executor:
            results = list(executor.map(self.fetch_data, data_sources))
        return results

    def fetch_data(self, source):
        """Fetch data from a single source."""
        raise NotImplementedError(f"fetch_data() henüz implemente edilmedi: source={source}")
