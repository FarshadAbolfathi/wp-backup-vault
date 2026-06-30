"""
SafeKeep settings dialog — global application preferences.
Farshad Abolfathi — https://www.linkedin.com/in/farshad-abolfathi/
"""
import logging

from PySide6.QtWidgets import (
    QDialog, QFormLayout, QComboBox, QSpinBox,
    QDialogButtonBox, QVBoxLayout,
)
from PySide6.QtCore import Qt

from safekeep.utils.logger import setup_logger


class SettingsDialog(QDialog):
    """Dialog for editing global application settings."""

    def __init__(self, parent=None, config=None) -> None:
        super().__init__(parent)
        self.config = config
        self.logger = setup_logger('safekeep.gui.settings_dialog')
        self.setWindowTitle('تنظیمات برنامه')
        self.setMinimumWidth(350)
        self.setLayoutDirection(Qt.RightToLeft)
        self._setup_ui()
        if config:
            self._load_settings()

    def _setup_ui(self) -> None:
        """Build the settings form."""
        main_layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight)

        # Log level
        self.combo_log_level = QComboBox()
        self.combo_log_level.addItems(['DEBUG', 'INFO', 'WARNING', 'ERROR'])
        self.combo_log_level.setCurrentText('INFO')
        form.addRow('سطح لاگ:', self.combo_log_level)

        # Concurrent downloads
        self.spin_concurrent = QSpinBox()
        self.spin_concurrent.setMinimum(1)
        self.spin_concurrent.setMaximum(10)
        self.spin_concurrent.setValue(2)
        form.addRow('حداکثر دانلود همزمان:', self.spin_concurrent)

        main_layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText('تأیید')
        buttons.button(QDialogButtonBox.Cancel).setText('انصراف')
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        main_layout.addWidget(buttons)

    def _load_settings(self) -> None:
        """Populate dialog fields from the current configuration."""
        try:
            settings = self.config.get_global_settings()
            log_level = settings.get('log_level', 'INFO').upper()
            idx = self.combo_log_level.findText(log_level)
            if idx >= 0:
                self.combo_log_level.setCurrentIndex(idx)
            self.spin_concurrent.setValue(
                int(settings.get('max_concurrent_downloads', 2))
            )
        except Exception as exc:
            self.logger.error(f'_load_settings failed: {exc}')

    def get_settings(self) -> dict:
        """
        Return the current settings as a dict.

        Returns:
            Dict with log_level and max_concurrent_downloads.
        """
        return {
            'log_level': self.combo_log_level.currentText(),
            'max_concurrent_downloads': self.spin_concurrent.value(),
        }
