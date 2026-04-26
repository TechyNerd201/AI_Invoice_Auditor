import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler

# Logs directory: project_root/logs/
LOGS_DIR = Path(__file__).resolve().parent.parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

LOG_FILE = LOGS_DIR / "app.log"

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def get_logger(name: str) -> logging.Logger:
    """
    Returns a named logger that writes to logs/app.log only (no console output).
    Uses a RotatingFileHandler — max 5 MB per file, keeps last 3 backups.

    Usage:
        from logging.logger import get_logger
        logger = get_logger(__name__)
        logger.info("Starting agent")
        logger.error("Something failed: %s", str(e))
    """
    logger = logging.getLogger(name)

    # Avoid adding duplicate handlers if get_logger is called multiple times
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    logger.propagate = False  # don't bubble up to root logger (prevents console leaks)

    handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=3,
        encoding="utf-8",
    )
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT))

    logger.addHandler(handler)
    return logger
