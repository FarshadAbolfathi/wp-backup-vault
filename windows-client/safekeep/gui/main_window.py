"""
SafeKeep main application window — Persian RTL interface.
Farshad Abolfathi — https://www.linkedin.com/in/farshad-abolfathi/
"""
import sys
import os
import logging
import datetime

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QListWidget, QListWidgetItem, QTableWidget, QTableWidgetItem,
    QProgressBar, QTextEdit, QSplitter, QMessageBox, QSystemTrayIcon,
    QMenu, QApplication, QHeaderView, QFrame, QStackedWidget,
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QIcon, QColor, QFont, QAction

from safekeep.gui.site_dialog import SiteDialog
from safekeep.gui.settings_dialog import SettingsDialog
from safekeep.gui.about_dialog import AboutDialog
from safekeep.utils.logger import setup_logger


# ---------------------------------------------------------------------------
# Background worker
# ---------------------------------------------------------------------------

class BackupWorker(QThread):
    """QThread that performs backup downloads without blocking the GUI."""

    progress = Signal(int, str)
    finished = Signal(bool, str)
    log_message = Signal(str)

    def __init__(self, site_manager, site_id: str, backup_id: str = None) -> None:
        super().__init__()
        self.site_manager = site_manager
        self.site_id = site_id
        self.backup_id = backup_id
        self._total_bytes = 0
        self._downloaded_bytes = 0

    def _progress_callback(self, bytes_downloaded: int, total_bytes: int) -> None:
        """Forward download progress to the GUI thread via signals."""
        self._downloaded_bytes = bytes_downloaded
        self._total_bytes = total_bytes
        if total_bytes > 0:
            percent = int(min(bytes_downloaded / total_bytes * 100, 100))
        else:
            percent = 0
        from safekeep.utils.helpers import human_readable_size
        msg = (
            f'دریافت: {human_readable_size(bytes_downloaded)}'
            + (f' / {human_readable_size(total_bytes)}' if total_bytes > 0 else '')
        )
        self.progress.emit(percent, msg)
        self.log_message.emit(msg)

    def run(self) -> None:
        """Execute the download in the background thread."""
        try:
            if self.backup_id:
                success = self.site_manager.fetch_backup_by_id(
                    self.site_id, self.backup_id, self._progress_callback
                )
                if success:
                    self.finished.emit(True, f'بک‌آپ {self.backup_id} با موفقیت دریافت شد.')
                else:
                    self.finished.emit(False, f'دریافت بک‌آپ {self.backup_id} ناموفق بود.')
            else:
                count = self.site_manager.fetch_pending(self.site_id, self._progress_callback)
                if count > 0:
                    self.finished.emit(True, f'{count} بک‌آپ جدید با موفقیت دریافت شد.')
                else:
                    self.finished.emit(True, 'بک‌آپ جدیدی برای دریافت وجود نداشت.')
        except Exception as exc:
            self.finished.emit(False, f'خطا: {exc}')


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

_STYLESHEET = """
QMainWindow, QWidget {
    background-color: #1e1e2e;
    color: #cdd6f4;
    font-family: Tahoma, Arial, sans-serif;
    font-size: 13px;
}
QListWidget {
    background-color: #181825;
    border: 1px solid #313244;
    border-radius: 4px;
    padding: 4px;
}
QListWidget::item:selected {
    background-color: #89b4fa;
    color: #1e1e2e;
    border-radius: 3px;
}
QTableWidget {
    background-color: #181825;
    border: 1px solid #313244;
    gridline-color: #313244;
}
QTableWidget::item:selected {
    background-color: #313244;
}
QHeaderView::section {
    background-color: #313244;
    color: #cdd6f4;
    padding: 4px 8px;
    border: none;
}
QPushButton {
    background-color: #89b4fa;
    color: #1e1e2e;
    border: none;
    border-radius: 4px;
    padding: 6px 14px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #b4befe;
}
QPushButton:disabled {
    background-color: #45475a;
    color: #6c7086;
}
QProgressBar {
    border: 1px solid #313244;
    border-radius: 4px;
    background-color: #181825;
    text-align: center;
}
QProgressBar::chunk {
    background-color: #89b4fa;
    border-radius: 3px;
}
QTextEdit {
    background-color: #11111b;
    border: 1px solid #313244;
    border-radius: 4px;
    font-family: Consolas, Courier New, monospace;
    font-size: 11px;
    color: #a6e3a1;
}
QLabel#title {
    font-size: 16px;
    font-weight: bold;
    color: #89b4fa;
    padding: 8px 0;
}
"""


class MainWindow(QMainWindow):
    """Primary application window with Persian RTL layout."""

    def __init__(self, site_manager, config) -> None:
        super().__init__()
        self.site_manager = site_manager
        self.config = config
        self.logger = setup_logger('safekeep.gui')
        self.active_workers: list[BackupWorker] = []
        self._current_site_id: str | None = None
        self._tray: QSystemTrayIcon | None = None

        self.setWindowTitle('SafeKeep — مدیریت بک‌آپ وردپرس')
        self.resize(1100, 700)
        self.setLayoutDirection(Qt.RightToLeft)
        self.setStyleSheet(_STYLESHEET)

        self._setup_ui()
        self._setup_tray()
        self._load_sites()

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        """Build the main window layout."""
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)
        root_layout.addWidget(splitter)

        # ------ Left panel (site list) ----------------------------------
        left_panel = QWidget()
        left_panel.setFixedWidth(250)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(8, 8, 8, 8)
        left_layout.setSpacing(6)

        title_label = QLabel('SafeKeep')
        title_label.setObjectName('title')
        title_label.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(title_label)

        sites_label = QLabel('سایت‌های پیکربندی‌شده')
        sites_label.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(sites_label)

        self.site_list = QListWidget()
        self.site_list.currentItemChanged.connect(self._on_site_list_selection_changed)
        left_layout.addWidget(self.site_list)

        btn_row = QHBoxLayout()
        self.btn_add_site = QPushButton('+ افزودن')
        self.btn_remove_site = QPushButton('حذف')
        self.btn_add_site.clicked.connect(self._on_add_site)
        self.btn_remove_site.clicked.connect(self._on_remove_site)
        btn_row.addWidget(self.btn_add_site)
        btn_row.addWidget(self.btn_remove_site)
        left_layout.addLayout(btn_row)

        splitter.addWidget(left_panel)

        # ------ Right panel (details) -----------------------------------
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(12, 8, 12, 8)
        right_layout.setSpacing(8)

        # Toolbar row
        toolbar = QHBoxLayout()
        self.lbl_site_name = QLabel('هیچ سایتی انتخاب نشده')
        self.lbl_site_name.setStyleSheet('font-size:15px; font-weight:bold;')
        toolbar.addWidget(self.lbl_site_name)
        toolbar.addStretch()

        self.btn_fetch = QPushButton('دریافت بک‌آپ')
        self.btn_fetch.clicked.connect(self._on_fetch_clicked)
        self.btn_fetch.setEnabled(False)
        toolbar.addWidget(self.btn_fetch)

        self.btn_test = QPushButton('بررسی اتصال')
        self.btn_test.clicked.connect(self._on_test_connection)
        self.btn_test.setEnabled(False)
        toolbar.addWidget(self.btn_test)

        btn_settings = QPushButton('تنظیمات')
        btn_settings.clicked.connect(self._on_settings)
        toolbar.addWidget(btn_settings)

        btn_about = QPushButton('درباره')
        btn_about.clicked.connect(self._on_about)
        toolbar.addWidget(btn_about)

        right_layout.addLayout(toolbar)

        # Backup table
        self.backup_table = QTableWidget()
        self.backup_table.setColumnCount(5)
        self.backup_table.setHorizontalHeaderLabels(
            ['شناسه', 'تاریخ', 'حجم', 'وضعیت', 'عملیات']
        )
        self.backup_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.backup_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.backup_table.setEditTriggers(QTableWidget.NoEditTriggers)
        right_layout.addWidget(self.backup_table, stretch=3)

        # Progress area
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        right_layout.addWidget(self.progress_bar)

        self.lbl_progress = QLabel('')
        self.lbl_progress.setAlignment(Qt.AlignCenter)
        right_layout.addWidget(self.lbl_progress)

        # Log viewer
        log_label = QLabel('گزارش عملیات')
        right_layout.addWidget(log_label)
        self.log_viewer = QTextEdit()
        self.log_viewer.setReadOnly(True)
        self.log_viewer.setMaximumHeight(150)
        right_layout.addWidget(self.log_viewer, stretch=1)

        splitter.addWidget(right_panel)
        splitter.setSizes([250, 850])

    def _setup_tray(self) -> None:
        """Configure the system tray icon and context menu."""
        try:
            self._tray = QSystemTrayIcon(self)

            # Use a generic application icon or fall back gracefully
            icon = QApplication.style().standardIcon(
                QApplication.style().StandardPixmap.SP_ComputerIcon
            )
            self._tray.setIcon(icon)
            self._tray.setToolTip('SafeKeep — مدیریت بک‌آپ وردپرس')

            tray_menu = QMenu()
            tray_menu.setLayoutDirection(Qt.RightToLeft)

            action_show = QAction('نمایش پنجره', self)
            action_show.triggered.connect(self._show_window)
            tray_menu.addAction(action_show)

            action_fetch_all = QAction('دریافت همه بک‌آپ‌ها', self)
            action_fetch_all.triggered.connect(self._fetch_all_sites)
            tray_menu.addAction(action_fetch_all)

            tray_menu.addSeparator()

            action_quit = QAction('خروج', self)
            action_quit.triggered.connect(QApplication.quit)
            tray_menu.addAction(action_quit)

            self._tray.setContextMenu(tray_menu)
            self._tray.activated.connect(self._on_tray_activated)
            self._tray.show()
        except Exception as exc:
            self.logger.warning(f'System tray setup failed: {exc}')
            self._tray = None

    # ------------------------------------------------------------------
    # Site list management
    # ------------------------------------------------------------------

    def _load_sites(self) -> None:
        """Populate the site list widget from the configuration."""
        try:
            self.site_list.blockSignals(True)
            self.site_list.clear()
            sites = self.site_manager.get_all_sites()
            for site in sites:
                item = QListWidgetItem(site.get('name', site.get('id', '?')))
                item.setData(Qt.UserRole, site.get('id'))
                self.site_list.addItem(item)
            self.site_list.blockSignals(False)
            if self.site_list.count() > 0:
                self.site_list.setCurrentRow(0)
        except Exception as exc:
            self.logger.error(f'_load_sites error: {exc}')

    def _on_site_list_selection_changed(self, current, previous) -> None:
        """Handle site selection changes."""
        if current is None:
            self._current_site_id = None
            self.lbl_site_name.setText('هیچ سایتی انتخاب نشده')
            self.btn_fetch.setEnabled(False)
            self.btn_test.setEnabled(False)
            self.backup_table.setRowCount(0)
            return
        site_id = current.data(Qt.UserRole)
        self._current_site_id = site_id
        self.lbl_site_name.setText(current.text())
        self.btn_fetch.setEnabled(True)
        self.btn_test.setEnabled(True)
        self._refresh_backup_table(site_id)

    # ------------------------------------------------------------------
    # Backup table
    # ------------------------------------------------------------------

    def _refresh_backup_table(self, site_id: str) -> None:
        """Reload the backup table for the given site."""
        self.backup_table.setRowCount(0)
        try:
            status = self.site_manager.get_site_status(site_id)
            site = self.config.get_site(site_id)
            if site is None:
                return

            from safekeep.core.backup_manager import BackupManager
            manager = BackupManager(site)
            local_backups = manager.get_local_backups()
            remote_backups = manager.get_remote_backups()
            local_ids = {b.get('backup_id') or b.get('id') for b in local_backups}

            # Merge remote and local for display
            shown_ids: set = set()
            rows = []
            for b in remote_backups:
                bid = b.get('backup_id') or b.get('id', '')
                shown_ids.add(bid)
                state = 'محلی موجود' if bid in local_ids else 'در انتظار دریافت'
                rows.append({
                    'id': bid,
                    'date': b.get('date', ''),
                    'size': b.get('size', 0),
                    'status': state,
                })
            for b in local_backups:
                bid = b.get('backup_id') or b.get('id', '')
                if bid not in shown_ids:
                    rows.append({
                        'id': bid,
                        'date': b.get('date', ''),
                        'size': b.get('size', 0),
                        'status': 'محلی (بدون کپی ریموت)',
                    })

            self.backup_table.setRowCount(len(rows))
            from safekeep.utils.helpers import human_readable_size
            for row_idx, row in enumerate(rows):
                self.backup_table.setItem(row_idx, 0, QTableWidgetItem(str(row['id'])))
                self.backup_table.setItem(row_idx, 1, QTableWidgetItem(str(row['date'])))
                size_str = human_readable_size(int(row['size'])) if row['size'] else '—'
                self.backup_table.setItem(row_idx, 2, QTableWidgetItem(size_str))
                self.backup_table.setItem(row_idx, 3, QTableWidgetItem(row['status']))

                # Download button in last column
                if row['status'] == 'در انتظار دریافت':
                    btn = QPushButton('دریافت')
                    btn_backup_id = row['id']
                    btn.clicked.connect(
                        lambda checked=False, bid=btn_backup_id: self._on_single_backup_fetch(bid)
                    )
                    self.backup_table.setCellWidget(row_idx, 4, btn)
                else:
                    self.backup_table.setItem(row_idx, 4, QTableWidgetItem('✓'))

            summary = (
                f'ریموت: {status.get("remote_count", 0)}  |  '
                f'محلی: {status.get("local_count", 0)}  |  '
                f'در انتظار: {status.get("pending_count", 0)}'
            )
            self.lbl_progress.setText(summary)
        except Exception as exc:
            self.logger.error(f'_refresh_backup_table error: {exc}')
            self._append_log(f'خطا در بارگذاری جدول: {exc}')

    # ------------------------------------------------------------------
    # Fetch operations
    # ------------------------------------------------------------------

    def _on_fetch_clicked(self) -> None:
        """Start downloading all pending backups for the selected site."""
        if not self._current_site_id:
            return
        self._start_worker(self._current_site_id)

    def _on_single_backup_fetch(self, backup_id: str) -> None:
        """Download a specific backup by ID."""
        if not self._current_site_id:
            return
        self._start_worker(self._current_site_id, backup_id=backup_id)

    def _fetch_all_sites(self) -> None:
        """Trigger fetch for every configured site (called from tray menu)."""
        for site in self.site_manager.get_all_sites():
            self._start_worker(site['id'])

    def _start_worker(self, site_id: str, backup_id: str = None) -> None:
        """Create and start a BackupWorker thread."""
        try:
            worker = BackupWorker(self.site_manager, site_id, backup_id)
            worker.progress.connect(self._on_worker_progress)
            worker.finished.connect(lambda ok, msg, sid=site_id: self._on_worker_finished(ok, msg, sid))
            worker.log_message.connect(self._append_log)
            worker.finished.connect(lambda ok, msg, w=worker: self._cleanup_worker(w))
            self.active_workers.append(worker)
            self.btn_fetch.setEnabled(False)
            self.progress_bar.setValue(0)
            self.progress_bar.setVisible(True)
            worker.start()
            self._append_log(f'شروع دریافت برای سایت {site_id}...')
        except Exception as exc:
            self.logger.error(f'_start_worker error: {exc}')
            self._append_log(f'خطا در شروع دریافت: {exc}')

    def _cleanup_worker(self, worker: BackupWorker) -> None:
        """Remove completed worker from active list."""
        try:
            self.active_workers.remove(worker)
        except ValueError:
            pass

    # ------------------------------------------------------------------
    # Worker signal handlers
    # ------------------------------------------------------------------

    def _on_worker_progress(self, percent: int, message: str) -> None:
        """Update progress bar and label."""
        self.progress_bar.setValue(percent)
        self.lbl_progress.setText(message)

    def _on_worker_finished(self, success: bool, message: str, site_id: str) -> None:
        """Handle worker completion."""
        self.progress_bar.setVisible(False)
        self.btn_fetch.setEnabled(True)
        self._append_log(message)

        if success:
            if self._current_site_id == site_id:
                self._refresh_backup_table(site_id)
            if self._tray:
                try:
                    self._tray.showMessage(
                        'SafeKeep',
                        message,
                        QSystemTrayIcon.Information,
                        4000,
                    )
                except Exception:
                    pass
        else:
            QMessageBox.warning(self, 'خطا در دریافت', message)

    # ------------------------------------------------------------------
    # Connection test
    # ------------------------------------------------------------------

    def _on_test_connection(self) -> None:
        """Test the API connection for the selected site (runs in background thread)."""
        if not self._current_site_id:
            return
        site_id = self._current_site_id
        self.btn_test.setEnabled(False)
        self.lbl_progress.setText('در حال بررسی اتصال...')

        class _TestWorker(QThread):
            done = Signal(bool, str)
            def __init__(self, sm, sid):
                super().__init__()
                self._sm = sm
                self._sid = sid
            def run(self):
                try:
                    ok, msg = self._sm.test_connection(self._sid)
                    self.done.emit(ok, msg)
                except Exception as exc:
                    self.done.emit(False, str(exc))

        worker = _TestWorker(self.site_manager, site_id)

        def on_done(ok, msg):
            self.btn_test.setEnabled(True)
            self.lbl_progress.setText('')
            if ok:
                QMessageBox.information(self, 'بررسی اتصال', msg)
            else:
                QMessageBox.warning(self, 'بررسی اتصال', msg)

        worker.done.connect(on_done)
        worker.done.connect(lambda ok, msg, w=worker: None)  # keep ref alive
        self._test_worker = worker  # prevent GC
        worker.start()

    # ------------------------------------------------------------------
    # Site add / remove
    # ------------------------------------------------------------------

    def _on_add_site(self) -> None:
        """Open the add-site dialog."""
        try:
            dlg = SiteDialog(parent=self)
            if dlg.exec():
                site_data = dlg.get_site_data()
                self.site_manager.add_site(site_data)
                self._load_sites()
                self._append_log(f'سایت "{site_data["name"]}" اضافه شد.')
        except Exception as exc:
            self.logger.error(f'_on_add_site error: {exc}')
            QMessageBox.critical(self, 'خطا', str(exc))

    def _on_remove_site(self) -> None:
        """Confirm and remove the selected site."""
        if not self._current_site_id:
            QMessageBox.warning(self, 'هشدار', 'لطفاً ابتدا یک سایت را انتخاب کنید.')
            return
        site = self.config.get_site(self._current_site_id)
        site_name = site.get('name', self._current_site_id) if site else self._current_site_id
        reply = QMessageBox.question(
            self,
            'تأیید حذف',
            f'آیا مطمئن هستید که می‌خواهید سایت "{site_name}" را حذف کنید؟',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            try:
                self.site_manager.remove_site(self._current_site_id)
                self._current_site_id = None
                self._load_sites()
                self._append_log(f'سایت "{site_name}" حذف شد.')
            except Exception as exc:
                self.logger.error(f'_on_remove_site error: {exc}')
                QMessageBox.critical(self, 'خطا', str(exc))

    # ------------------------------------------------------------------
    # Dialogs
    # ------------------------------------------------------------------

    def _on_settings(self) -> None:
        """Open the settings dialog."""
        try:
            dlg = SettingsDialog(parent=self, config=self.config)
            if dlg.exec():
                self.config.update_global_settings(dlg.get_settings())
                self._append_log('تنظیمات ذخیره شد.')
        except Exception as exc:
            self.logger.error(f'_on_settings error: {exc}')
            QMessageBox.critical(self, 'خطا', str(exc))

    def _on_about(self) -> None:
        """Open the about dialog."""
        try:
            dlg = AboutDialog(parent=self)
            dlg.exec()
        except Exception as exc:
            self.logger.error(f'_on_about error: {exc}')

    # ------------------------------------------------------------------
    # Tray helpers
    # ------------------------------------------------------------------

    def _on_tray_activated(self, reason) -> None:
        """Show window on tray icon double-click."""
        if reason == QSystemTrayIcon.DoubleClick:
            self._show_window()

    def _show_window(self) -> None:
        """Restore and activate the main window."""
        self.showNormal()
        self.raise_()
        self.activateWindow()

    # ------------------------------------------------------------------
    # Close event
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:
        """Minimize to tray on close if tray is available."""
        if self._tray and self._tray.isVisible():
            self.hide()
            self._tray.showMessage(
                'SafeKeep',
                'برنامه در پس‌زمینه اجرا می‌شود.',
                QSystemTrayIcon.Information,
                2000,
            )
            event.ignore()
        else:
            event.accept()

    # ------------------------------------------------------------------
    # Log viewer
    # ------------------------------------------------------------------

    def _append_log(self, message: str) -> None:
        """Append a timestamped message to the log viewer."""
        ts = datetime.datetime.now().strftime('%H:%M:%S')
        self.log_viewer.append(f'[{ts}] {message}')
