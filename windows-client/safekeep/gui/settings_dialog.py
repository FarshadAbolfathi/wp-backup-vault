"""
SafeKeep settings dialog — global application preferences.
Farshad Abolfathi — https://www.linkedin.com/in/farshad-abolfathi/
"""
import sys
import logging

from PySide6.QtWidgets import (
    QDialog, QFormLayout, QComboBox, QSpinBox, QCheckBox,
    QDialogButtonBox, QVBoxLayout, QLabel,
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
        self.setMinimumWidth(380)
        self.setLayoutDirection(Qt.RightToLeft)
        self._setup_ui()
        if config:
            self._load_settings()

    def _setup_ui(self) -> None:
        """Build the settings form."""
        main_layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(12)
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

        # Autorun toggle (Windows only)
        self.chk_autorun = QCheckBox('اجرای خودکار هنگام روشن شدن ویندوز')
        if sys.platform != 'win32':
            self.chk_autorun.setEnabled(False)
            self.chk_autorun.setToolTip('فقط در ویندوز پشتیبانی می‌شود')
        else:
            self.chk_autorun.setToolTip(
                'SafeKeep را به استارتاپ ویندوز اضافه می‌کند تا پس از هر بار روشن شدن سیستم به طور خودکار اجرا شود'
            )
        form.addRow('استارتاپ:', self.chk_autorun)

        # Minimized-to-tray on autorun hint
        self.lbl_hint = QLabel('(برنامه در پس‌زمینه شروع می‌شود و در سینی سیستم نمایش داده می‌شود)')
        self.lbl_hint.setStyleSheet('color: #888; font-size: 11px;')
        self.lbl_hint.setWordWrap(True)
        form.addRow('', self.lbl_hint)

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
            # Read live registry state (source of truth)
            if sys.platform == 'win32':
                from safekeep.utils.autorun import is_autorun_enabled
                self.chk_autorun.setChecked(is_autorun_enabled())
            else:
                self.chk_autorun.setChecked(
                    bool(settings.get('autorun', False))
                )
        except Exception as exc:
            self.logger.error(f'_load_settings failed: {exc}')

    def get_settings(self) -> dict:
        """Return the current settings as a dict."""
        return {
            'log_level': self.combo_log_level.currentText(),
            'max_concurrent_downloads': self.spin_concurrent.value(),
            'autorun': self.chk_autorun.isChecked(),
        }

    def accept(self) -> None:
        """Save settings and apply autorun change before closing."""
        if sys.platform == 'win32':
            from safekeep.utils.autorun import enable_autorun, disable_autorun
            if self.chk_autorun.isChecked():
                enable_autorun()
            else:
                disable_autorun()
        super().accept()
