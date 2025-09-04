import importlib
import os
import sys


def _reload_settings_with_env(env: dict[str, str]):
    # Temiz ortam ve modul yeniden yukleme
    orig = os.environ.copy()
    try:
        os.environ.clear()
        os.environ.update(orig)  # mevcutlari koru
        os.environ.update(env)
        # Modul cache'ten cikart ve yeniden yukle
        if "config.settings" in sys.modules:
            del sys.modules["config.settings"]
        import config.settings as settings  # noqa
        importlib.reload(settings)
        return settings
    finally:
        os.environ.clear()
        os.environ.update(orig)


def test_env_isolation_testnet_paths_tmp(tmp_path):
    settings = _reload_settings_with_env({
        "ENV_ISOLATION": "on",
        "USE_TESTNET": "true",
        "OFFLINE_MODE": "false",
        # override yok => izolasyon devreye girmeli
        # Ayrica data klasorunu gecici dizine yonlendir
        "DATA_PATH": str(tmp_path / "data"),
    })
    # Yol beklentileri
    assert "testnet" in settings.Settings.TRADES_DB_PATH
    assert settings.Settings.TRADES_DB_PATH.endswith(os.path.normpath("data/testnet/trades.db")) or \
           settings.Settings.TRADES_DB_PATH.endswith(os.path.normpath("data\\testnet\\trades.db"))
    assert settings.Settings.DAILY_HALT_FLAG_PATH.endswith(os.path.normpath("data/testnet/daily_halt.flag"))
    assert settings.Settings.METRICS_FILE_DIR.endswith(os.path.normpath("data/processed/metrics/testnet"))


def test_env_isolation_respects_override(tmp_path):
    custom_db = str(tmp_path / "my.db")
    settings = _reload_settings_with_env({
        "ENV_ISOLATION": "on",
        "TRADES_DB_PATH": custom_db,
        "USE_TESTNET": "true",
        "OFFLINE_MODE": "false",
    })
    assert settings.Settings.TRADES_DB_PATH == custom_db
