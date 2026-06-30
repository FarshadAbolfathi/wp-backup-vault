"""
SafeKeep — About dialog

Author: Farshad Abolfathi — https://www.linkedin.com/in/farshad-abolfathi/
"""

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QLabel, QPushButton, QVBoxLayout,
)

from safekeep import __version__, __author__, __author_url__


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("درباره SafeKeep")
        self.setMinimumWidth(360)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # App name
        title = QLabel("SafeKeep")
        title_font = QFont()
        title_font.setPointSize(20)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Version
        version_label = QLabel(f"نسخه {__version__}")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_label.setStyleSheet("color: #666;")
        layout.addWidget(version_label)

        # Description
        desc = QLabel("مدیریت بک‌آپ وردپرس برای ویندوز سرور\nدانلود خودکار و ایمن از سایت‌های وردپرس")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setWordWrap(True)
        layout.addWidget(desc)

        layout.addSpacing(8)

        # Author
        author_label = QLabel(f"سازنده: {__author__}")
        author_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(author_label)

        # LinkedIn link
        linkedin_btn = QPushButton("LinkedIn: Farshad Abolfathi")
        linkedin_btn.setFlat(True)
        linkedin_btn.setStyleSheet(
            "color: #0073aa; text-decoration: underline; border: none; font-size: 13px;"
        )
        linkedin_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        linkedin_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(__author_url__))
        )
        linkedin_btn.setAlignment = None  # QPushButton doesn't have this, skip
        layout.addWidget(linkedin_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        # GitHub
        github_btn = QPushButton("GitHub: farshadabolfathi/wp-backup-vault")
        github_btn.setFlat(True)
        github_btn.setStyleSheet(
            "color: #0073aa; text-decoration: underline; border: none; font-size: 12px;"
        )
        github_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        github_btn.clicked.connect(
            lambda: QDesktopServices.openUrl(
                QUrl("https://github.com/farshadabolfathi/wp-backup-vault")
            )
        )
        layout.addWidget(github_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        layout.addSpacing(8)

        # License
        license_label = QLabel("لایسنس: MIT")
        license_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        license_label.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(license_label)

        # Close button
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText("بستن")
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
