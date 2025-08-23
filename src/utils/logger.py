import logging
from logging.handlers import RotatingFileHandler
import os
import time
from config.settings import Settings
from datetime import datetime

_LOGGER_CACHE = {}

def get_logger(name: str) -> logging.Logger:
    """İsim bazlı singleton logger. Dönen logger'da dönen handler tekrar eklenmez.
    RotatingFileHandler ile log boyutu sınırlandırılır.
    """
    if name in _LOGGER_CACHE:
        return _LOGGER_CACHE[name]

    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, Settings.LOG_LEVEL.upper(), logging.INFO))
    logger.propagate = False

    os.makedirs(Settings.LOG_PATH, exist_ok=True)
    log_file = os.path.join(Settings.LOG_PATH, f"{name}.log")

    formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s - %(message)s')

    # Rotating file handler (5 MB * 3 backups)
    file_handler = RotatingFileHandler(log_file, maxBytes=5_000_000, backupCount=3, encoding='utf-8')
    file_handler.setLevel(getattr(logging, Settings.LOG_LEVEL.upper(), logging.INFO))
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, Settings.LOG_LEVEL.upper(), logging.INFO))
    console_handler.setFormatter(formatter)

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
