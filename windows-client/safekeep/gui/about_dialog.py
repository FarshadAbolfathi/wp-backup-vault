"""
SafeKeep about dialog — application information and credits.
Farshad Abolfathi — https://www.linkedin.com/in/farshad-abolfathi/
"""
import logging

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QDialogButtonBox,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from safekeep.utils.logger import setup_logger


class AboutDialog(QDialog):
    """Displays application version, author, and links."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.logger = setup_logger('safekeep.gui.about_dialog')
        self.setWindowTitle('درباره SafeKeep')
        self.setFixedSize(400, 300)
        self.setLayoutDirection(Qt.RightToLeft)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Build the about dialog layout."""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 20, 24, 20)

        # Application title
        lbl_title = QLabel('SafeKeep')
        title_font = QFont()
        title_font.setPointSize(22)
        title_font.setBold(True)
        lbl_title.setFont(title_font)
        lbl_title.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl_title)

        # Version
        lbl_version = QLabel('نسخه ۱.۰.۰')
        lbl_version.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl_version)

        # Description
        lbl_desc = QLabel('سیستم مدیریت بک‌آپ وردپرس با رابط فارسی')
        lbl_desc.setAlignment(Qt.AlignCenter)
        lbl_desc.setWordWrap(True)
        layout.addWidget(lbl_desc)

        # Author link
        lbl_author = QLabel(
            'توسعه‌دهنده: <a href="https://www.linkedin.com/in/farshad-abolfathi/">'
            'Farshad Abolfathi</a>'
        )
        lbl_author.setOpenExternalLinks(True)
        lbl_author.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl_author)

        # GitHub link
        lbl_github = QLabel(
            'مخزن کد: <a href="https://github.com/farshadabolfathi/wp-backup-vault">'
            'GitHub — wp-backup-vault</a>'
        )
        lbl_github.setOpenExternalLinks(True)
        lbl_github.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl_github)

        # License
        lbl_license = QLabel('MIT License')
        lbl_license.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl_license)

        layout.addStretch()

        # Close button
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.button(QDialogButtonBox.Close).setText('بستن')
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
