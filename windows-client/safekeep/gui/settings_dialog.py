"""
SafeKeep — Global settings dialog (Persian / RTL)

Author: Farshad Abolfathi — https://www.linkedin.com/in/farshad-abolfathi/
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QSpinBox, QVBoxLayout,
)

from safekeep.core import config as cfg


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("تنظیمات کلی")
        self.setMinimumWidth(360)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self._build_ui()
        self._load()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        form.addRow("سطح لاگ:", self.log_level_combo)

        self.max_downloads_spin = QSpinBox()
        self.max_downloads_spin.setRange(1, 10)
        self.max_downloads_spin.setValue(2)
        self.max_downloads_spin.setSuffix(" دانلود همزمان")
        form.addRow("حداکثر دانلود:", self.max_downloads_spin)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("ذخیره")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("انصراف")
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _load(self):
        settings = cfg.get_global_settings()
        log_level = settings.get("log_level", "INFO")
        idx = self.log_level_combo.findText(log_level)
        if idx >= 0:
            self.log_level_combo.setCurrentIndex(idx)
        self.max_downloads_spin.setValue(int(settings.get("max_concurrent_downloads", 2)))

    def _save(self):
        cfg.save_global_settings({
            "log_level": self.log_level_combo.currentText(),
            "max_concurrent_downloads": self.max_downloads_spin.value(),
        })
        self.accept()
