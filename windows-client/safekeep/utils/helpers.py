"""
SafeKeep general helper utilities.
Farshad Abolfathi — https://www.linkedin.com/in/farshad-abolfathi/
"""
import os
import hashlib
import shutil
import logging

logger = logging.getLogger('safekeep.helpers')


def verify_md5(filepath: str, expected_md5: str) -> bool:
    """
    Verify a file's MD5 checksum.

    Args:
        filepath: Absolute path to the file.
        expected_md5: Expected MD5 hex digest.

    Returns:
        True if the checksum matches, False otherwise.
    """
    try:
        md5 = hashlib.md5()
        with open(filepath, 'rb') as fh:
            while chunk := fh.read(8192):
                md5.update(chunk)
        return md5.hexdigest().lower() == expected_md5.lower()
    except FileNotFoundError:
        logger.error(f'verify_md5: file not found: {filepath}')
        return False
    except Exception as exc:
        logger.error(f'verify_md5 error for {filepath}: {exc}')
        return False


def verify_sha256(filepath: str, expected_sha256: str) -> bool:
    """
    Verify a file's SHA-256 checksum.

    Args:
        filepath: Absolute path to the file.
        expected_sha256: Expected SHA-256 hex digest.

    Returns:
        True if the checksum matches, False otherwise.
    """
    try:
        sha256 = hashlib.sha256()
        with open(filepath, 'rb') as fh:
            while chunk := fh.read(8192):
                sha256.update(chunk)
        return sha256.hexdigest().lower() == expected_sha256.lower()
    except FileNotFoundError:
        logger.error(f'verify_sha256: file not found: {filepath}')
        return False
    except Exception as exc:
        logger.error(f'verify_sha256 error for {filepath}: {exc}')
        return False


def get_file_size_mb(filepath: str) -> float:
    """
    Return the size of a file in megabytes.

    Args:
        filepath: Absolute path to the file.

    Returns:
        Size in MB, or 0.0 on error.
    """
    try:
        return os.path.getsize(filepath) / (1024 * 1024)
    except Exception as exc:
        logger.error(f'get_file_size_mb error for {filepath}: {exc}')
        return 0.0


def human_readable_size(size_bytes: int) -> str:
    """
    Convert a byte count to a human-readable string.

    Args:
        size_bytes: Size in bytes.

    Returns:
        String such as '3.14 MB'.
    """
    if size_bytes < 0:
        return '0 B'
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if size_bytes < 1024:
            return f'{size_bytes:.2f} {unit}' if unit != 'B' else f'{size_bytes} {unit}'
        if unit != 'TB':
            size_bytes /= 1024
    return f'{size_bytes:.2f} TB'


def ensure_dir(path: str) -> bool:
    """
    Create a directory (and parents) if it does not exist.

    Args:
        path: Directory path to create.

    Returns:
        True on success, False on OSError.
    """
    try:
        os.makedirs(path, exist_ok=True)
        return True
    except OSError as exc:
        logger.error(f'ensure_dir failed for {path}: {exc}')
        return False


def safe_delete(path: str) -> bool:
    """
    Delete a file or directory tree without raising exceptions.

    Args:
        path: Path to the file or directory.

    Returns:
        True if deleted successfully (or path did not exist), False on error.
    """
    try:
        if not os.path.exists(path):
            return True
        if os.path.isfile(path):
            os.remove(path)
        else:
            shutil.rmtree(path)
        logger.debug(f'safe_delete: removed {path}')
        return True
    except Exception as exc:
        logger.error(f'safe_delete failed for {path}: {exc}')
        return False
