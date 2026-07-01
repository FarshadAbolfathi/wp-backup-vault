"""
SafeKeep — WordPress Backup Manager
Entry point
Farshad Abolfathi — https://www.linkedin.com/in/farshad-abolfathi/
"""
import sys
import socket
import logging

def check_single_instance():
    """Prevent multiple instances using a socket lock."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(('127.0.0.1', 47832))
        sock.listen(1)
        return sock  # Keep socket open to maintain lock
    except OSError:
        return None

def main():
    if sys.platform != 'win32':
        print("Warning: SafeKeep is designed for Windows. Some features may not work correctly.")

    # --minimized flag is passed by the autorun registry entry so the window
    # starts hidden in the system tray instead of appearing on screen.
    start_minimized = '--minimized' in sys.argv

    lock_socket = check_single_instance()
    if lock_socket is None:
        from PySide6.QtWidgets import QApplication, QMessageBox
        app = QApplication(sys.argv)
        QMessageBox.warning(None, 'SafeKeep', 'نسخه دیگری از SafeKeep در حال اجراست.')
        sys.exit(1)

    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFontDatabase, QFont
    from safekeep.core.config import Config
    from safekeep.core.site_manager import SiteManager
    from safekeep.utils.logger import setup_logger
    from safekeep.gui.main_window import MainWindow

    logger = setup_logger('safekeep', 'INFO')
    logger.info('SafeKeep starting...')

    app = QApplication(sys.argv)
    app.setLayoutDirection(Qt.RightToLeft)
    app.setApplicationName('SafeKeep')

    # Load YekanBakh font (bundled inside the exe via PyInstaller)
    import os, sys as _sys
    _base = getattr(_sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    _fonts_dir = os.path.join(_base, 'safekeep', 'assets', 'fonts')
    _loaded_family = None
    for _fname in ('YekanBakh-Regular.ttf', 'YekanBakh-Bold.ttf'):
        _fpath = os.path.join(_fonts_dir, _fname)
        if os.path.exists(_fpath):
            _fid = QFontDatabase.addApplicationFont(_fpath)
            if _fid >= 0 and _loaded_family is None:
                families = QFontDatabase.applicationFontFamilies(_fid)
                if families:
                    _loaded_family = families[0]
    if _loaded_family:
        _default_font = QFont(_loaded_family, 11)
        app.setFont(_default_font)
        logger.info(f'YekanBakh font loaded: {_loaded_family}')
    else:
        logger.warning('YekanBakh font not found; falling back to system font.')
    app.setApplicationVersion('1.0.0')
    app.setOrganizationName('Farshad Abolfathi')

    try:
        config = Config()
        config.load_config()
    except Exception as e:
        logger.error(f'Failed to load config: {e}')
        config = Config()

    site_manager = SiteManager(config)

    window = MainWindow(site_manager, config)

    if start_minimized:
        # Start hidden in the system tray (autorun scenario)
        logger.info('Starting minimized to tray (autorun mode).')
        window.hide()
    else:
        window.show()

    exit_code = app.exec()
    if lock_socket:
        lock_socket.close()
    sys.exit(exit_code)

if __name__ == '__main__':
    main()
