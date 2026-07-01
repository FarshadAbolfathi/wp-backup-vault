"""
SafeKeep Windows autorun — registry-based startup management.
Farshad Abolfathi — https://www.linkedin.com/in/farshad-abolfathi/

Writes / removes a registry key under:
  HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Run
so the app launches automatically at Windows login without requiring admin rights.
"""
import sys
import os
import logging

logger = logging.getLogger('safekeep.autorun')

_REG_KEY_PATH = r'Software\Microsoft\Windows\CurrentVersion\Run'
_VALUE_NAME   = 'SafeKeep'


def _get_exe_path() -> str:
    """Return the path to the running executable (works both frozen and in dev)."""
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller .exe
        return sys.executable
    # Running from source — point to the main.py launcher
    return f'"{sys.executable}" "{os.path.abspath(sys.argv[0])}"'


def enable_autorun() -> bool:
    """
    Register SafeKeep to start on Windows login.

    Returns True on success, False if an error occurred (e.g. non-Windows platform).
    """
    if sys.platform != 'win32':
        logger.warning('enable_autorun() called on non-Windows platform; skipped.')
        return False

    import winreg
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            _REG_KEY_PATH,
            0,
            winreg.KEY_SET_VALUE,
        )
        exe = _get_exe_path()
        # Pass --minimized so the window starts in the tray, not on screen
        winreg.SetValueEx(key, _VALUE_NAME, 0, winreg.REG_SZ, f'{exe} --minimized')
        winreg.CloseKey(key)
        logger.info(f'Autorun enabled: {exe}')
        return True
    except Exception as exc:
        logger.error(f'Failed to enable autorun: {exc}')
        return False


def disable_autorun() -> bool:
    """
    Remove SafeKeep from the Windows startup registry key.

    Returns True on success, False if an error occurred.
    """
    if sys.platform != 'win32':
        return False

    import winreg
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            _REG_KEY_PATH,
            0,
            winreg.KEY_SET_VALUE,
        )
        winreg.DeleteValue(key, _VALUE_NAME)
        winreg.CloseKey(key)
        logger.info('Autorun disabled.')
        return True
    except FileNotFoundError:
        # Key did not exist — that's fine
        return True
    except Exception as exc:
        logger.error(f'Failed to disable autorun: {exc}')
        return False


def is_autorun_enabled() -> bool:
    """Return True if the autorun registry value currently exists."""
    if sys.platform != 'win32':
        return False

    import winreg
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            _REG_KEY_PATH,
            0,
            winreg.KEY_READ,
        )
        winreg.QueryValueEx(key, _VALUE_NAME)
        winreg.CloseKey(key)
        return True
    except FileNotFoundError:
        return False
    except Exception as exc:
        logger.error(f'Failed to read autorun state: {exc}')
        return False
