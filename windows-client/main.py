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

    lock_socket = check_single_instance()
    if lock_socket is None:
        from PySide6.QtWidgets import QApplication, QMessageBox
        app = QApplication(sys.argv)
        QMessageBox.warning(None, 'SafeKeep', 'نسخه دیگری از SafeKeep در حال اجراست.')
        sys.exit(1)

    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    from safekeep.core.config import Config
    from safekeep.core.site_manager import SiteManager
    from safekeep.utils.logger import setup_logger
    from safekeep.gui.main_window import MainWindow

    logger = setup_logger('safekeep', 'INFO')
    logger.info('SafeKeep starting...')

    app = QApplication(sys.argv)
    app.setLayoutDirection(Qt.RightToLeft)
    app.setApplicationName('SafeKeep')
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
    window.show()

    exit_code = app.exec()
    if lock_socket:
        lock_socket.close()
    sys.exit(exit_code)

if __name__ == '__main__':
    main()
