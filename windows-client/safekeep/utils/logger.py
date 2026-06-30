"""
SafeKeep logging utilities.
Farshad Abolfathi — https://www.linkedin.com/in/farshad-abolfathi/
"""
import os
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logger(name: str, log_level: str = 'INFO') -> logging.Logger:
    """
    Create and configure a logger with rotating file and console handlers.

    Args:
        name: Logger name.
        log_level: One of DEBUG, INFO, WARNING, ERROR.

    Returns:
        Configured logging.Logger instance.
    """
    logger = logging.getLogger(name)

    # Avoid adding duplicate handlers if already configured
    if logger.handlers:
        return logger

    level = getattr(logging, log_level.upper(), logging.INFO)
    logger.setLevel(level)

    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')

    # File handler — write to APPDATA/SafeKeep/logs/safekeep.log
    try:
        appdata = os.environ.get('APPDATA', str(Path.home()))
        log_dir = Path(appdata) / 'SafeKeep' / 'logs'
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / 'safekeep.log'
        file_handler = RotatingFileHandler(
            str(log_file),
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=3,
            encoding='utf-8',
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(level)
        logger.addHandler(file_handler)
    except Exception as exc:
        # Fall back gracefully — console only
        logging.getLogger('safekeep.logger_setup').warning(
            f'Could not create file log handler: {exc}'
        )

    # Console handler
    try:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(level)
        logger.addHandler(console_handler)
    except Exception as exc:
        pass  # Nothing we can do without a console

    return logger
