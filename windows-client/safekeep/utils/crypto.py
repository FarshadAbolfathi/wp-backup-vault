"""
SafeKeep — Encrypted config storage using Fernet + machine-derived key.
API keys are never stored in plain text.

Author: Farshad Abolfathi — https://www.linkedin.com/in/farshad-abolfathi/
"""

import base64
import hashlib
import os
import platform
import socket

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes


def _machine_secret() -> bytes:
    """Derive a stable secret from machine-specific attributes."""
    node = platform.node() or socket.gethostname() or "safekeep-host"
    user = os.environ.get("USERNAME") or os.environ.get("USER") or "safekeep-user"
    raw = f"safekeep:{node}:{user}".encode("utf-8")
    # Use a fixed application salt so the same machine always produces the same key.
    salt = b"SafeKeepSalt_v1_"
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=200_000,
    )
    return base64.urlsafe_b64encode(kdf.derive(raw))


def _get_fernet() -> Fernet:
    return Fernet(_machine_secret())


def encrypt_data(plaintext: bytes) -> bytes:
    """Encrypt arbitrary bytes."""
    return _get_fernet().encrypt(plaintext)


def decrypt_data(ciphertext: bytes) -> bytes:
    """Decrypt bytes. Raises InvalidToken on tampered/wrong-machine data."""
    return _get_fernet().decrypt(ciphertext)


def encrypt_text(text: str) -> bytes:
    return encrypt_data(text.encode("utf-8"))


def decrypt_text(ciphertext: bytes) -> str:
    return decrypt_data(ciphertext).decode("utf-8")
