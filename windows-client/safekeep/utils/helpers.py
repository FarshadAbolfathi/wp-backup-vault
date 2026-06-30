"""
SafeKeep — File and checksum utilities
Author: Farshad Abolfathi — https://www.linkedin.com/in/farshad-abolfathi/
"""

import hashlib
import os
import shutil
from pathlib import Path
from typing import Optional


def compute_md5(filepath: str | Path) -> str:
    h = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def compute_sha256(filepath: str | Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_chunk(filepath: str | Path, expected_md5: str, expected_sha256: str) -> tuple[bool, str]:
    """Return (ok, error_message). ok=True means both checksums match."""
    if not os.path.exists(filepath):
        return False, f"File not found: {filepath}"

    actual_md5 = compute_md5(filepath)
    if actual_md5 != expected_md5:
        return False, f"MD5 mismatch: expected {expected_md5}, got {actual_md5}"

    actual_sha256 = compute_sha256(filepath)
    if actual_sha256 != expected_sha256:
        return False, f"SHA256 mismatch: expected {expected_sha256}, got {actual_sha256}"

    return True, ""


def human_size(size_bytes: int) -> str:
    if size_bytes >= 1_073_741_824:
        return f"{size_bytes / 1_073_741_824:.2f} GB"
    if size_bytes >= 1_048_576:
        return f"{size_bytes / 1_048_576:.2f} MB"
    if size_bytes >= 1024:
        return f"{size_bytes / 1024:.2f} KB"
    return f"{size_bytes} B"


def get_dir_size(path: str | Path) -> int:
    """Total size of all files under path, in bytes."""
    total = 0
    for dirpath, _dirnames, filenames in os.walk(path):
        for fname in filenames:
            fp = os.path.join(dirpath, fname)
            try:
                total += os.path.getsize(fp)
            except OSError:
                pass
    return total


def safe_remove_dir(path: str | Path):
    """Remove a directory tree, ignoring errors."""
    try:
        shutil.rmtree(path, ignore_errors=True)
    except Exception:
        pass


def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p
