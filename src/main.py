import sys
import os

# Python path'e proje dizinini ekle
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt5.QtWidgets import QApplication
from src.ui.main_window import MainWindow
from src.utils.logger import get_logger
from config.settings import Settings
from src.data_fetcher import DataFetcher
from src.utils.logger import get_logger as _get_global_logger
import traceback
from config.runtime_thresholds import load_runtime_thresholds

def ensure_data():
    """Veri klasörlerinin ve temel tarihsel verilerin hazır olmasını sağlar."""
    fetcher = DataFetcher()
    # Top 150 listeyi garanti altına al
    fetcher.ensure_top_pairs(force=False)
    raw_path = os.path.join(Settings.DATA_PATH, 'raw')
    os.makedirs(raw_path, exist_ok=True)

    # Eğer hiç CSV yoksa toplu indirme yap
    if not any(name.endswith('.csv') for name in os.listdir(raw_path)):
        logger = get_logger("Main")
        logger.info('No historical data found. Fetching all pairs data (first run)...')
        fetcher.fetch_all_pairs_data(days=Settings.BACKTEST_DAYS, interval=Settings.TIMEFRAME)
        logger.info('Initial data fetch complete.')

    # Veri bütünlüğü hızlı kontrol
    fetcher.validate_dataset(interval=Settings.TIMEFRAME, repair=True)

def validate_environment(logger):
    """Ortam değişkenleri ve temel yapı doğrulamaları."""
    problems = []
    if not Settings.BINANCE_API_KEY or not Settings.BINANCE_API_SECRET:
        problems.append('BINANCE API anahtarları eksik (.env kontrol edin)')
    for path_attr in ['DATA_PATH', 'LOG_PATH', 'BACKUP_PATH']:
        p = getattr(Settings, path_attr)
        try:
            os.makedirs(p, exist_ok=True)
        except Exception as e:
            problems.append(f'{path_attr} oluşturulamadı: {e}')
    if problems:
        for pr in problems:
            logger.error(pr)
    else:
        logger.info('Environment validation OK')

def main():
    """Ana giriş noktası"""
    # Log dizini oluştur
    os.makedirs(Settings.LOG_PATH, exist_ok=True)

    # Logger'ı başlat
    logger = get_logger("Main")
    logger.info("Trade Bot başlatılıyor...")
    # Persist edilen eşikleri yükle (varsa)
    load_runtime_thresholds()
    validate_environment(logger)

    # Uygulamayı başlat
    app = QApplication(sys.argv)
    # Global exception hook -> uygulama tamamen kopmasın
    def _excepthook(exc_type, exc, tb):
        g_logger = _get_global_logger("Global")
        trace = ''.join(traceback.format_exception(exc_type, exc, tb))
        g_logger.error(f"UNCAUGHT EXCEPTION: {exc_type.__name__}: {exc}\n{trace}")
    sys.excepthook = _excepthook

    window = MainWindow()
    window.show()

    logger.info("Arayüz hazır")

    # Uygulamayı çalıştır
    sys.exit(app.exec_())

if __name__ == "__main__":
    ensure_data()
    main()
