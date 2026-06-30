"""
SafeKeep encryption/decryption utilities using machine-bound keys.
Farshad Abolfathi — https://www.linkedin.com/in/farshad-abolfathi/
"""
import os
import hashlib
import base64
import platform
import logging

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

logger = logging.getLogger('safekeep.crypto')


def get_machine_id() -> str:
    """
    Return a stable machine-specific identifier.

    On Windows, reads MachineGuid from the registry.
    Falls back to platform.node() on any failure.
    """
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r'SOFTWARE\Microsoft\Cryptography',
        )
        value, _ = winreg.QueryValueEx(key, 'MachineGuid')
        winreg.CloseKey(key)
        return str(value)
    except Exception as exc:
        logger.debug(f'Registry read failed, using fallback machine ID: {exc}')
        return platform.node()


def derive_key(machine_id: str) -> bytes:
    """
    Derive a Fernet-compatible key from the machine ID using PBKDF2-HMAC-SHA256.

    Args:
        machine_id: Stable machine identifier string.

    Returns:
        URL-safe base64-encoded 32-byte derived key.
    """
    salt = hashlib.sha256(b'SafeKeep-WP-Backup-Vault-v1').digest()
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100_000,
    )
    raw = kdf.derive(machine_id.encode('utf-8'))
    return base64.urlsafe_b64encode(raw)


def encrypt_data(data: str) -> str:
    """
    Encrypt a plaintext string using a machine-bound Fernet key.

    Args:
        data: Plaintext string to encrypt.

    Returns:
        Encrypted token as a string.

    Raises:
        Exception: On encryption failure.
    """
    try:
        machine_id = get_machine_id()
        key = derive_key(machine_id)
        fernet = Fernet(key)
        return fernet.encrypt(data.encode('utf-8')).decode('utf-8')
    except Exception as exc:
        logger.error(f'encrypt_data failed: {exc}')
        raise


def decrypt_data(token: str) -> str:
    """
    Decrypt a Fernet token using the machine-bound key.

    Args:
        token: Encrypted token string.

    Returns:
        Decrypted plaintext string.

    Raises:
        ValueError: If the token is invalid or from a different machine.
        Exception: On other decryption failures.
    """
    try:
        machine_id = get_machine_id()
        key = derive_key(machine_id)
        fernet = Fernet(key)
        return fernet.decrypt(token.encode('utf-8')).decode('utf-8')
    except InvalidToken:
        raise ValueError('Decryption failed — config may be from different machine')
    except Exception as exc:
        logger.error(f'decrypt_data failed: {exc}')
        raise
