import logging
from logging.handlers import RotatingFileHandler
import os
import time
from config.settings import Settings  # original reference (fallback)
from datetime import datetime
from typing import Optional
from importlib import import_module

_LOGGER_CACHE = {}

# --- CR-0043 Redaction Filter ---
class _RedactionFilter(logging.Filter):
    def __init__(self, api_key: Optional[str], secret: Optional[str]):
        super().__init__()
        self.api_key = api_key or ''
        self.secret = secret or ''
        self.mask_key = self._mask(self.api_key)
        self.mask_secret = self._mask(self.secret)

    @staticmethod
    def _mask(val: str) -> str:
        if not val:
            return val
        if len(val) <= 6:
            return '*' * len(val)
        return f"{val[:4]}***{val[-2:]}"

    def _redact(self, text: str) -> str:
        if not text:
            return text
        if self.api_key and self.api_key in text:
            text = text.replace(self.api_key, self.mask_key)
        if self.secret and self.secret in text:
            text = text.replace(self.secret, self.mask_secret)
        return text

    def filter(self, record: logging.LogRecord) -> bool:  # pragma: no cover (format path tested via file read)
        try:
            # Build original message safely
            msg = record.getMessage()
            redacted = self._redact(msg)
            if redacted != msg:
                record.msg = redacted
                record.args = ()
        except Exception:
            pass
        return True


def _current_settings():  # CR-0043 dynamic settings accessor
    try:
        mod = import_module('config.settings')
        return getattr(mod, 'Settings', Settings)
    except Exception:  # pragma: no cover
        return Settings


def get_logger(name: str) -> logging.Logger:
    """İsim bazlı singleton logger.
    CR-0043: Dinamik Settings yeniden yükleme (env değişiklikleri testte yansısın)."""
    if name in _LOGGER_CACHE:
        return _LOGGER_CACHE[name]

    S = _current_settings()
    level = getattr(logging, getattr(S, 'LOG_LEVEL', 'INFO').upper(), logging.INFO)
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = False

    log_path = getattr(S, 'LOG_PATH', './data/logs')
    os.makedirs(log_path, exist_ok=True)
    log_file = os.path.join(log_path, f"{name}.log")

    formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s - %(message)s')

    file_handler = RotatingFileHandler(log_file, maxBytes=5_000_000, backupCount=3, encoding='utf-8')
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)

    redaction_filter = _RedactionFilter(getattr(S, 'BINANCE_API_KEY', None), getattr(S, 'BINANCE_API_SECRET', None))
    if getattr(S, 'BINANCE_API_KEY', None) or getattr(S, 'BINANCE_API_SECRET', None):
        file_handler.addFilter(redaction_filter)
        console_handler.addFilter(redaction_filter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    _LOGGER_CACHE[name] = logger
    return logger

class Logger:
    def __init__(self, name):
        # Ensure log directory exists
        log_dir = "logs/errors"
        try:
            os.makedirs(log_dir, exist_ok=True)
            print(f"Log directory created or already exists: {log_dir}")
        except Exception as e:
            print(f"Failed to create log directory: {e}")

        self.logger = get_logger(name)

    def info(self, message):
        """Log an info message."""
        self.logger.info(message)

    def error(self, message):
        """Log an error message and save it to a separate file."""
        self.logger.error(message)
        self.save_error_to_file(message)

    def debug(self, message):
        """Log a debug message."""
        self.logger.debug(message)

    def log_performance(self, operation_name, start_time):
        """Log the performance of an operation."""
        duration = time.time() - start_time
        self.info(f"{operation_name} took {duration:.2f} seconds.")

    def save_error_to_file(self, message):
        """Save the error message to a file with a timestamp."""
        log_dir = "logs/errors"
        os.makedirs(log_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        log_file = os.path.join(log_dir, f"error_{timestamp}.log")
        with open(log_file, "w") as f:
            f.write(f"[{timestamp}] {message}\n")

if __name__ == "__main__":
    logger = get_logger("TestLogger")
    logger.error("Test error log")
