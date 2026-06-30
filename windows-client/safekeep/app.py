"""
SafeKeep Application class
Farshad Abolfathi — https://www.linkedin.com/in/farshad-abolfathi/
"""
import os
import logging
from pathlib import Path
from safekeep.utils.logger import setup_logger


class SafeKeepApp:
    """Main application class managing lifecycle."""

    def __init__(self, config):
        self.config = config
        self.logger = None
        self._scheduler = None

    def initialize(self):
        """Initialize app components."""
        log_level = self.config.get_global_settings().get('log_level', 'INFO')
        self.logger = setup_logger('safekeep', log_level)
        self.logger.info('SafeKeep initialized')
        appdata = os.environ.get('APPDATA', str(Path.home()))
        for subdir in ['', 'logs', 'backups']:
            Path(appdata, 'SafeKeep', subdir).mkdir(parents=True, exist_ok=True)

    def shutdown(self):
        """Clean shutdown."""
        if self._scheduler:
            try:
                self._scheduler.stop()
            except Exception as e:
                if self.logger:
                    self.logger.error(f'Error stopping scheduler: {e}')
        if self.logger:
            self.logger.info('SafeKeep shutdown complete')
