"""
ENV Isolation Permutations Tests (ASCII-only docstring)
-------------------------------------------------------
Goal: Verify deterministic path precedence and env-scoped (testnet/prod/offline)
behavior in config.settings across all permutations.

Matrix covered (ENV_ISOLATION=on):
- Only DATA_PATH (USE_TESTNET=true/false and OFFLINE_MODE=true variants)
- Only TRADES_DB_PATH (custom path is respected)
- DATA_PATH + TRADES_DB_PATH together:
    * custom filename -> keep explicit override
    * default filename (trades.db) with leak -> derive under DATA_PATH/<env>/trades.db
- Neither DATA_PATH nor TRADES_DB_PATH set (defaults):
    * testnet -> ./data/testnet/trades.db
    * prod    -> ./data/prod/trades.db
    * offline -> ./data/offline/trades.db

Technical notes:
- _reload_settings_with_env applies a fresh import (instead of reload) by evicting
    config/settings modules from sys.modules and resetting os.environ deterministically.
- norm() uses normpath+normcase for cross-platform stable path comparisons.
"""

import os
import sys
import importlib
from os.path import normpath, normcase


def norm(p: str) -> str:
    return normcase(normpath(p))


def _reload_settings_with_env(env: dict):
    # Reset relevant env keys then apply overrides
    for k in (
        "DATA_PATH",
        "TRADES_DB_PATH",
        "ENV_ISOLATION",
        "USE_TESTNET",
        "ALLOW_PROD",
        "OFFLINE_MODE",
    ):
        os.environ.pop(k, None)
    os.environ.update(env)
    # Evict modules to force a fresh import instead of reload
    for mod in ("config.settings", "config"):
        if mod in sys.modules:
            del sys.modules[mod]
    return importlib.import_module("config.settings")

def test_only_data_path_derives_env_scoped_db(tmp_path):
    settings = _reload_settings_with_env({
        "ENV_ISOLATION": "on",
        "USE_TESTNET": "true",
        "OFFLINE_MODE": "false",
        "DATA_PATH": str(tmp_path / "data"),
    })
    # TRADES_DB_PATH => DATA_PATH/<env>/trades.db
    expected = norm(os.path.join(str(tmp_path / "data"), "testnet", "trades.db"))
    assert norm(settings.Settings.TRADES_DB_PATH) == expected
    # Log/metrics/halt should be placed under env-scoped paths as well
    assert settings.Settings.DAILY_HALT_FLAG_PATH.endswith(norm(os.path.join("data", "testnet", "daily_halt.flag")))
    assert settings.Settings.METRICS_FILE_DIR.endswith(norm(os.path.join("data", "processed", "metrics", "testnet")))


def test_only_trades_db_path_respected(tmp_path):
    custom_db = str(tmp_path / "custom.db")
    settings = _reload_settings_with_env({
        "ENV_ISOLATION": "on",
        "TRADES_DB_PATH": custom_db,
        "USE_TESTNET": "true",
        "OFFLINE_MODE": "false",
    })
    assert norm(settings.Settings.TRADES_DB_PATH) == norm(custom_db)


def test_both_explicit_custom_filename_respected(tmp_path):
    data_root = str(tmp_path / "rootdata")
    custom_db = str(tmp_path / "my.db")
    settings = _reload_settings_with_env({
        "ENV_ISOLATION": "on",
        "DATA_PATH": data_root,
        "TRADES_DB_PATH": custom_db,
        "USE_TESTNET": "true",
        "OFFLINE_MODE": "false",
    })
    # Since a custom filename (my.db) is used, keep the explicit override
    assert norm(settings.Settings.TRADES_DB_PATH) == norm(custom_db)


def test_both_explicit_leak_with_default_filename_derives_under_data(tmp_path):
    data_root = str(tmp_path / "data")
    # TRADES_DB_PATH points outside DATA_PATH with default filename (leak scenario)
    leaked_db = str(tmp_path / "outside" / "trades.db")
    settings = _reload_settings_with_env({
        "ENV_ISOLATION": "on",
        "DATA_PATH": data_root,
        "TRADES_DB_PATH": leaked_db,
        "USE_TESTNET": "true",
        "OFFLINE_MODE": "false",
    })
    expected = norm(os.path.join(data_root, "testnet", "trades.db"))
    assert norm(settings.Settings.TRADES_DB_PATH) == expected


def test_neither_explicit_derives_from_default_data_testnet():
    # Default DATA_PATH ./data; testnet olduğu için ./data/testnet/trades.db beklenir
    settings = _reload_settings_with_env({
        "ENV_ISOLATION": "on",
        "USE_TESTNET": "true",
        "OFFLINE_MODE": "false",
    })
    expected_suffix = norm(os.path.join("data", "testnet", "trades.db"))
    assert norm(settings.Settings.TRADES_DB_PATH).endswith(expected_suffix)


def test_data_path_derives_env_scoped_db_prod(tmp_path):
    settings = _reload_settings_with_env({
        "ENV_ISOLATION": "on",
        "USE_TESTNET": "false",
        "OFFLINE_MODE": "false",
        "DATA_PATH": str(tmp_path / "data"),
    })
    expected = norm(os.path.join(str(tmp_path / "data"), "prod", "trades.db"))
    assert norm(settings.Settings.TRADES_DB_PATH) == expected
    assert settings.Settings.DAILY_HALT_FLAG_PATH.endswith(norm(os.path.join("data", "prod", "daily_halt.flag")))
    assert settings.Settings.METRICS_FILE_DIR.endswith(norm(os.path.join("data", "processed", "metrics", "prod")))


def test_data_path_derives_env_scoped_db_offline(tmp_path):
    settings = _reload_settings_with_env({
        "ENV_ISOLATION": "on",
        "OFFLINE_MODE": "true",
        "DATA_PATH": str(tmp_path / "data"),
    })
    expected = norm(os.path.join(str(tmp_path / "data"), "offline", "trades.db"))
    assert norm(settings.Settings.TRADES_DB_PATH) == expected
    assert settings.Settings.DAILY_HALT_FLAG_PATH.endswith(norm(os.path.join("data", "offline", "daily_halt.flag")))
    assert settings.Settings.METRICS_FILE_DIR.endswith(norm(os.path.join("data", "processed", "metrics", "offline")))


def test_both_explicit_leak_default_filename_derives_under_data_prod(tmp_path):
    data_root = str(tmp_path / "data")
    leaked_db = str(tmp_path / "outside" / "trades.db")
    settings = _reload_settings_with_env({
        "ENV_ISOLATION": "on",
        "USE_TESTNET": "false",
        "OFFLINE_MODE": "false",
        "DATA_PATH": data_root,
        "TRADES_DB_PATH": leaked_db,
    })
    expected = norm(os.path.join(data_root, "prod", "trades.db"))
    assert norm(settings.Settings.TRADES_DB_PATH) == expected


def test_neither_explicit_derives_from_default_data_offline():
    settings = _reload_settings_with_env({
        "ENV_ISOLATION": "on",
        "OFFLINE_MODE": "true",
    })
    expected_suffix = norm(os.path.join("data", "offline", "trades.db"))
    assert norm(settings.Settings.TRADES_DB_PATH).endswith(expected_suffix)
