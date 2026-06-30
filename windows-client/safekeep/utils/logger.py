"""
SafeKeep — Logging setup
Author: Farshad Abolfathi — https://www.linkedin.com/in/farshad-abolfathi/
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def get_log_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home())) / "SafeKeep" / "logs"
    else:
        base = Path.home() / ".safekeep" / "logs"
    base.mkdir(parents=True, exist_ok=True)
    return base


def setup_logging(level: str = "INFO") -> logging.Logger:
    log_dir = get_log_dir()
    log_file = log_dir / "safekeep.log"

    numeric_level = getattr(logging, level.upper(), logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root_logger = logging.getLogger("safekeep")
    root_logger.setLevel(numeric_level)

    if not root_logger.handlers:
        # Rotating file handler: 5 MB per file, keep 5 backups
        file_handler = RotatingFileHandler(
            log_file, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    return root_logger


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"safekeep.{name}")


def setup_logger(name: str, level: str = 'INFO') -> logging.Logger:
    """Configure and return a named logger with file + console handlers.

    Alias compatible with main.py entry point.
    """
    return setup_logging(level)
