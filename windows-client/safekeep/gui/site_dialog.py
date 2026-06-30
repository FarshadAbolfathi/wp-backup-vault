"""
SafeKeep — Add/Edit Site dialog (Persian / RTL)

Author: Farshad Abolfathi — https://www.linkedin.com/in/farshad-abolfathi/
"""

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPushButton, QSpinBox, QVBoxLayout,
    QWidget,
)

from safekeep.core.backup_manager import test_connection


class _TestWorker(QThread):
    result = Signal(bool, str)

    def __init__(self, url: str, key: str):
        super().__init__()
        self._url = url
        self._key = key

    def run(self):
        ok, msg = test_connection(self._url, self._key)
        self.result.emit(ok, msg)


class SiteDialog(QDialog):
    """Dialog for adding or editing a site."""

    def __init__(self, parent=None, site: dict | None = None):
        super().__init__(parent)
        self._site = site or {}
        self._worker = None
        self._build_ui()
        if site:
            self._populate(site)

    def _build_ui(self):
        self.setWindowTitle("افزودن / ویرایش سایت")
        self.setMinimumWidth(480)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

        layout = QVBoxLayout(self)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setFormAlignment(Qt.AlignmentFlag.AlignRight)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("مثال: سایت اصلی")
        form.addRow("نام سایت:", self.name_edit)

        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://example.com")
        form.addRow("آدرس URL:", self.url_edit)

        self.key_edit = QLineEdit()
        self.key_edit.setPlaceholderText("کلید ۳۲ کاراکتری از پنل ادمین وردپرس")
        self.key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("کلید API:", self.key_edit)

        # Save path with Browse button
        path_widget = QWidget()
        path_layout = QHBoxLayout(path_widget)
        path_layout.setContentsMargins(0, 0, 0, 0)
        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("C:\\Backups\\MySite")
        browse_btn = QPushButton("انتخاب...")
        browse_btn.setMaximumWidth(80)
        browse_btn.clicked.connect(self._browse_path)
        path_layout.addWidget(self.path_edit)
        path_layout.addWidget(browse_btn)
        form.addRow("مسیر ذخیره:", path_widget)

        self.retention_spin = QSpinBox()
        self.retention_spin.setRange(1, 50)
        self.retention_spin.setValue(5)
        self.retention_spin.setSuffix(" بک‌آپ")
        form.addRow("تعداد نگهداری:", self.retention_spin)

        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(5, 1440)
        self.interval_spin.setValue(60)
        self.interval_spin.setSuffix(" دقیقه")
        form.addRow("فاصله بررسی:", self.interval_spin)

        layout.addLayout(form)

        # Test connection button
        test_widget = QWidget()
        test_layout = QHBoxLayout(test_widget)
        test_layout.setContentsMargins(0, 0, 0, 0)
        self.test_btn = QPushButton("تست اتصال")
        self.test_btn.clicked.connect(self._test_connection)
        self.test_label = QLabel("")
        test_layout.addWidget(self.test_btn)
        test_layout.addWidget(self.test_label, 1)
        layout.addWidget(test_widget)

        # OK / Cancel
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("تأیید")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("انصراف")
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _populate(self, site: dict):
        self.name_edit.setText(site.get("name", ""))
        self.url_edit.setText(site.get("url", ""))
        self.key_edit.setText(site.get("api_key", ""))
        self.path_edit.setText(site.get("save_path", ""))
        self.retention_spin.setValue(int(site.get("retention_count", 5)))
        self.interval_spin.setValue(int(site.get("check_interval_minutes", 60)))

    def _browse_path(self):
        folder = QFileDialog.getExistingDirectory(self, "انتخاب مسیر ذخیره")
        if folder:
            self.path_edit.setText(folder)

    def _test_connection(self):
        url = self.url_edit.text().strip()
        key = self.key_edit.text().strip()
        if not url or not key:
            self.test_label.setText("آدرس URL و کلید API را وارد کنید.")
            return

        self.test_btn.setEnabled(False)
        self.test_label.setText("در حال بررسی...")
        self._worker = _TestWorker(url, key)
        self._worker.result.connect(self._on_test_result)
        self._worker.start()

    def _on_test_result(self, ok: bool, msg: str):
        self.test_btn.setEnabled(True)
        if ok:
            self.test_label.setStyleSheet("color: green;")
            self.test_label.setText(f"✓ {msg}")
        else:
            self.test_label.setStyleSheet("color: red;")
            self.test_label.setText(f"✗ {msg}")

    def _accept(self):
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "خطا", "نام سایت اجباری است.")
            return
        if not self.url_edit.text().strip():
            QMessageBox.warning(self, "خطا", "آدرس URL اجباری است.")
            return
        if not self.key_edit.text().strip():
            QMessageBox.warning(self, "خطا", "کلید API اجباری است.")
            return
        if not self.path_edit.text().strip():
            QMessageBox.warning(self, "خطا", "مسیر ذخیره اجباری است.")
            return
        self.accept()

    def get_site_data(self) -> dict:
        data = {
            "name": self.name_edit.text().strip(),
            "url": self.url_edit.text().strip().rstrip("/"),
            "api_key": self.key_edit.text().strip(),
            "save_path": self.path_edit.text().strip(),
            "retention_count": self.retention_spin.value(),
            "check_interval_minutes": self.interval_spin.value(),
        }
        if self._site.get("id"):
            data["id"] = self._site["id"]
        return data
