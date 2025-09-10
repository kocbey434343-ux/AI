import os
import sys
import traceback

# Python path'e proje dizinini ekle
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.runtime_thresholds import load_runtime_thresholds
from config.settings import Settings
from PyQt5.QtWidgets import QApplication

from src.data_fetcher import DataFetcher
from src.trader.core import Trader
from src.ui.main_window import MainWindow
from src.utils.feature_flags import flag_enabled
from src.utils.logger import get_logger, get_logger as _get_global_logger
from src.utils.structured_log import slog
from src.utils.threshold_cache import get_threshold_cache


def ensure_data():
    """Veri klasorlerinin ve temel tarihsel verilerin hazir olmasini saglar."""
    fetcher = DataFetcher()
    # Top 150 listeyi garanti altina al
    fetcher.ensure_top_pairs(force=False)
    raw_path = os.path.join(Settings.DATA_PATH, 'raw')
    os.makedirs(raw_path, exist_ok=True)

    # Eger hic CSV yoksa toplu indirme yap
    if not any(name.endswith('.csv') for name in os.listdir(raw_path)):
        logger = get_logger("Main")
        logger.info('No historical data found. Fetching all pairs data (first run)...')
        fetcher.fetch_all_pairs_data(days=Settings.BACKTEST_DAYS, interval=Settings.TIMEFRAME)
        logger.info('Initial data fetch complete.')

    # Veri butunlugu hizli kontrol
    fetcher.validate_dataset(interval=Settings.TIMEFRAME, repair=True)

def validate_environment(logger):
    """Ortam degiskenleri ve temel yapi dogrulamalari."""
    problems = []
    if not Settings.BINANCE_API_KEY or not Settings.BINANCE_API_SECRET:
        problems.append('BINANCE API anahtarlari eksik (.env kontrol edin)')
    for path_attr in ['DATA_PATH', 'LOG_PATH', 'BACKUP_PATH']:
        p = getattr(Settings, path_attr)
        try:
            os.makedirs(p, exist_ok=True)
        except Exception as e:
            problems.append(f'{path_attr} olusturulamadi: {e}')
    if problems:
        for pr in problems:
            logger.error(pr)
    else:
        logger.info('Environment validation OK')

def main():
    """Ana giris noktasi"""
    # Log dizini olustur
    os.makedirs(Settings.LOG_PATH, exist_ok=True)

    # Logger baslat
    logger = get_logger("Main")
    logger.info("Trade Bot baslatiliyor...")
    slog('app_start', version='v1', offline=Settings.OFFLINE_MODE)

    # CR-0070: Initialize threshold cache for performance
    threshold_cache = get_threshold_cache()
    logger.info(f"Threshold cache initialized with {len(threshold_cache.get_cache_status())} entries")

    # Persist edilen esikleri yukle (varsa) - legacy support
    load_runtime_thresholds()
    validate_environment(logger)

    # Uygulamayi baslat
    app = QApplication(sys.argv)
    # Global exception hook -> uygulama tamamen kopmasin
    def _excepthook(exc_type, exc, tb):
        g_logger = _get_global_logger("Global")
        trace = ''.join(traceback.format_exception(exc_type, exc, tb))
        g_logger.error(f"UNCAUGHT EXCEPTION: {exc_type.__name__}: {exc}\n{trace}")
    sys.excepthook = _excepthook

    # Gerçek trader instance oluştur
    logger.info("Trader instance oluşturuluyor...")
    trader = Trader()

    # UI'yi gercek trader ile baslat
    window = MainWindow(trader=trader)

    # Sinyal callback baglantisini kur
    if hasattr(trader, 'signal_callback'):
        trader.signal_callback = window.append_signal
        logger.info("Signal callback UI'ye baglandi")

    if flag_enabled('STARTUP_INFO'):  # Ornek flag
        slog('feature_flag', name='STARTUP_INFO', status='enabled')
        logger.info('Feature STARTUP_INFO aktif')
    window.show()

    logger.info("Arayuz hazir - Gerçek trader entegrasyonu ile")

    # Uygulamayi calistir
    sys.exit(app.exec_())

if __name__ == "__main__":
    ensure_data()
    main()
