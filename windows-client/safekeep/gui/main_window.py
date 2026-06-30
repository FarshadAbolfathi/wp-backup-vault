"""
SafeKeep — Main Window
Farshad Abolfathi — https://www.linkedin.com/in/farshad-abolfathi/
"""
import logging
import threading
import uuid

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QPushButton, QTableWidget, QTableWidgetItem,
    QComboBox, QProgressBar, QSpinBox, QLineEdit, QDialog,
    QDialogButtonBox, QFormLayout, QFileDialog, QMessageBox,
    QHeaderView,
)
from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl


class _Signals(QObject):
    backups_loaded = Signal(list)
    download_progress = Signal(float)
    download_done = Signal(bool)


class MainWindow(QMainWindow):

    def __init__(self, site_manager, config):
        super().__init__()
        self.site_manager = site_manager
        self.config = config
        self.logger = logging.getLogger(__name__)
        self._signals = _Signals()

        self.setWindowTitle('SafeKeep — مدیریت بک‌آپ وردپرس')
        self.setMinimumSize(900, 600)
        self.setLayoutDirection(Qt.RightToLeft)

        self._build_ui()
        self._refresh_sites()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        tabs = QTabWidget()
        tabs.setLayoutDirection(Qt.RightToLeft)
        layout.addWidget(tabs)

        tabs.addTab(self._build_sites_tab(), 'سایت‌ها')
        tabs.addTab(self._build_backups_tab(), 'بک‌آپ‌ها')
        tabs.addTab(self._build_settings_tab(), 'تنظیمات')

    def _build_sites_tab(self) -> QWidget:
        widget = QWidget()
        vbox = QVBoxLayout(widget)

        top = QHBoxLayout()
        top.addWidget(QLabel('سایت‌های مدیریت‌شده'))
        top.addStretch()
        add_btn = QPushButton('افزودن سایت')
        add_btn.clicked.connect(self._add_site)
        top.addWidget(add_btn)
        vbox.addLayout(top)

        self.sites_table = QTableWidget(0, 4)
        self.sites_table.setHorizontalHeaderLabels(['نام', 'آدرس', 'وضعیت', 'عملیات'])
        self.sites_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.sites_table.setEditTriggers(QTableWidget.NoEditTriggers)
        vbox.addWidget(self.sites_table)

        return widget

    def _build_backups_tab(self) -> QWidget:
        widget = QWidget()
        vbox = QVBoxLayout(widget)

        top = QHBoxLayout()
        top.addWidget(QLabel('سایت:'))
        self.site_selector = QComboBox()
        top.addWidget(self.site_selector)
        load_btn = QPushButton('بارگذاری بک‌آپ‌ها')
        load_btn.clicked.connect(self._load_backups)
        top.addWidget(load_btn)
        top.addStretch()
        vbox.addLayout(top)

        self.backups_table = QTableWidget(0, 5)
        self.backups_table.setHorizontalHeaderLabels(['شناسه', 'تاریخ', 'حجم (MB)', 'وضعیت', 'عملیات'])
        self.backups_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.backups_table.setEditTriggers(QTableWidget.NoEditTriggers)
        vbox.addWidget(self.backups_table)

        self.dl_progress = QProgressBar()
        self.dl_progress.setRange(0, 100)
        self.dl_progress.setVisible(False)
        vbox.addWidget(self.dl_progress)

        self.dl_status = QLabel('')
        vbox.addWidget(self.dl_status)

        self._signals.backups_loaded.connect(self._display_backups)
        self._signals.download_progress.connect(self._on_download_progress)
        self._signals.download_done.connect(self._on_download_done)

        return widget

    def _build_settings_tab(self) -> QWidget:
        widget = QWidget()
        vbox = QVBoxLayout(widget)

        form = QFormLayout()

        self.max_dl_spin = QSpinBox()
        self.max_dl_spin.setRange(1, 10)
        global_cfg = self.config.get_global()
        self.max_dl_spin.setValue(int(global_cfg.get('max_concurrent_downloads', 2)))
        form.addRow('حداکثر دانلود همزمان:', self.max_dl_spin)

        self.log_level_combo = QComboBox()
        for lvl in ['DEBUG', 'INFO', 'WARNING', 'ERROR']:
            self.log_level_combo.addItem(lvl)
        current_level = global_cfg.get('log_level', 'INFO')
        idx = self.log_level_combo.findText(current_level)
        if idx >= 0:
            self.log_level_combo.setCurrentIndex(idx)
        form.addRow('سطح لاگ:', self.log_level_combo)

        vbox.addLayout(form)

        save_btn = QPushButton('ذخیره تنظیمات')
        save_btn.clicked.connect(self._save_settings)
        vbox.addWidget(save_btn)

        vbox.addStretch()

        author_label = QLabel(
            '<a href="https://www.linkedin.com/in/farshad-abolfathi/">'
            'Farshad Abolfathi — linkedin.com/in/farshad-abolfathi/</a>'
        )
        author_label.setOpenExternalLinks(True)
        author_label.setAlignment(Qt.AlignCenter)
        vbox.addWidget(author_label)

        return widget

    # ------------------------------------------------------------------
    # Sites
    # ------------------------------------------------------------------

    def _refresh_sites(self):
        self.sites_table.setRowCount(0)
        self.site_selector.clear()

        for site in self.config.get_sites():
            row = self.sites_table.rowCount()
            self.sites_table.insertRow(row)
            self.sites_table.setItem(row, 0, QTableWidgetItem(site.get('name', '')))
            self.sites_table.setItem(row, 1, QTableWidgetItem(site.get('url', '')))
            self.sites_table.setItem(row, 2, QTableWidgetItem('آماده'))

            del_btn = QPushButton('حذف')
            site_id = site.get('id', '')
            del_btn.clicked.connect(lambda checked, sid=site_id: self._delete_site(sid))
            self.sites_table.setCellWidget(row, 3, del_btn)

            self.site_selector.addItem(site.get('name', site_id), userData=site)

    def _add_site(self):
        dialog = QDialog(self)
        dialog.setWindowTitle('افزودن سایت جدید')
        dialog.setLayoutDirection(Qt.RightToLeft)
        dialog.setMinimumWidth(450)

        form = QFormLayout()

        name_edit = QLineEdit()
        form.addRow('نام سایت:', name_edit)

        url_edit = QLineEdit()
        url_edit.setPlaceholderText('https://example.com')
        form.addRow('آدرس سایت:', url_edit)

        api_key_edit = QLineEdit()
        api_key_edit.setEchoMode(QLineEdit.Password)
        form.addRow('کلید API:', api_key_edit)

        path_row = QHBoxLayout()
        save_path_edit = QLineEdit()
        save_path_edit.setPlaceholderText('C:\\Backups\\my-site')
        path_row.addWidget(save_path_edit)
        browse_btn = QPushButton('انتخاب...')

        def browse():
            folder = QFileDialog.getExistingDirectory(dialog, 'انتخاب پوشه ذخیره')
            if folder:
                save_path_edit.setText(folder)

        browse_btn.clicked.connect(browse)
        path_row.addWidget(browse_btn)
        path_widget = QWidget()
        path_widget.setLayout(path_row)
        form.addRow('مسیر ذخیره:', path_widget)

        retention_spin = QSpinBox()
        retention_spin.setRange(1, 20)
        retention_spin.setValue(5)
        form.addRow('تعداد نگهداری:', retention_spin)

        interval_spin = QSpinBox()
        interval_spin.setRange(10, 1440)
        interval_spin.setValue(60)
        form.addRow('بازه بررسی (دقیقه):', interval_spin)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)

        main_layout = QVBoxLayout(dialog)
        main_layout.addLayout(form)
        main_layout.addWidget(buttons)

        if dialog.exec() == QDialog.Accepted:
            site = {
                'id': str(uuid.uuid4()),
                'name': name_edit.text().strip(),
                'url': url_edit.text().strip(),
                'api_key': api_key_edit.text().strip(),
                'save_path': save_path_edit.text().strip(),
                'retention_count': retention_spin.value(),
                'check_interval_minutes': interval_spin.value(),
            }
            self.config.add_site(site)
            self._refresh_sites()

    def _delete_site(self, site_id: str):
        reply = QMessageBox.question(
            self, 'حذف سایت', 'آیا از حذف این سایت مطمئن هستید؟',
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.config.remove_site(site_id)
            self._refresh_sites()

    # ------------------------------------------------------------------
    # Backups
    # ------------------------------------------------------------------

    def _load_backups(self):
        idx = self.site_selector.currentIndex()
        if idx < 0:
            return
        site = self.site_selector.itemData(idx)
        if not site:
            return

        self.dl_status.setText('در حال بارگذاری...')

        def worker():
            backups = self.site_manager.list_backups(site)
            self._signals.backups_loaded.emit(backups)

        threading.Thread(target=worker, daemon=True).start()

    def _display_backups(self, backups: list):
        self.backups_table.setRowCount(0)
        self.dl_status.setText(f'{len(backups)} بک‌آپ یافت شد')

        idx = self.site_selector.currentIndex()
        site = self.site_selector.itemData(idx) if idx >= 0 else None

        for backup in backups:
            row = self.backups_table.rowCount()
            self.backups_table.insertRow(row)

            backup_id = backup.get('id', '')
            date_str = backup.get('date', backup.get('created_at', ''))
            total_bytes = backup.get('total_size', 0)
            size_mb = f'{total_bytes / (1024 * 1024):.1f}' if total_bytes else '—'
            status = backup.get('status', 'موجود')

            self.backups_table.setItem(row, 0, QTableWidgetItem(backup_id))
            self.backups_table.setItem(row, 1, QTableWidgetItem(str(date_str)))
            self.backups_table.setItem(row, 2, QTableWidgetItem(size_mb))
            self.backups_table.setItem(row, 3, QTableWidgetItem(status))

            dl_btn = QPushButton('دانلود')
            if site:
                dl_btn.clicked.connect(
                    lambda checked, s=site, bid=backup_id: self._download_backup(s, bid)
                )
            self.backups_table.setCellWidget(row, 4, dl_btn)

    def _download_backup(self, site: dict, backup_id: str):
        self.dl_progress.setVisible(True)
        self.dl_progress.setValue(0)
        self.dl_status.setText(f'در حال دانلود {backup_id}...')

        def progress_cb(filename: str, percent: float):
            self._signals.download_progress.emit(percent)

        def worker():
            success = self.site_manager.download_backup(site, backup_id, progress_cb)
            self._signals.download_done.emit(success)

        threading.Thread(target=worker, daemon=True).start()

    def _on_download_progress(self, percent: float):
        self.dl_progress.setValue(int(percent))

    def _on_download_done(self, success: bool):
        self.dl_progress.setVisible(False)
        if success:
            self.dl_status.setText('دانلود با موفقیت انجام شد.')
            QMessageBox.information(self, 'SafeKeep', 'بک‌آپ با موفقیت دانلود شد.')
        else:
            self.dl_status.setText('خطا در دانلود بک‌آپ.')
            QMessageBox.warning(self, 'SafeKeep', 'دانلود بک‌آپ با خطا مواجه شد.')

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def _save_settings(self):
        self.config.update_global({
            'max_concurrent_downloads': self.max_dl_spin.value(),
            'log_level': self.log_level_combo.currentText(),
        })
        QMessageBox.information(self, 'SafeKeep', 'تنظیمات ذخیره شد.')
