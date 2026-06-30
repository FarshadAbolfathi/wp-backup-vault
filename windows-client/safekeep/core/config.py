"""
SafeKeep — Configuration Manager
Farshad Abolfathi — https://www.linkedin.com/in/farshad-abolfathi/
"""
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import platform


def _get_machine_key() -> bytes:
    """Derive a machine-specific encryption key."""
    if platform.system() == 'Windows':
        import winreg
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                 r'SOFTWARE\Microsoft\Cryptography')
            machine_guid, _ = winreg.QueryValueEx(key, 'MachineGuid')
            winreg.CloseKey(key)
            seed = machine_guid.encode()
        except Exception:
            seed = b'safekeep-default-seed'
    else:
        seed = b'safekeep-default-seed'

    salt = b'safekeep-salt-v1'
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100_000,
    )
    raw = kdf.derive(seed)
    return base64.urlsafe_b64encode(raw)


class Config:
    """Manages encrypted application configuration."""

    DEFAULT_CONFIG: Dict[str, Any] = {
        'sites': [],
        'global': {
            'log_level': 'INFO',
            'max_concurrent_downloads': 2,
        },
    }

    def __init__(self):
        self._config: Dict[str, Any] = dict(self.DEFAULT_CONFIG)
        self._fernet: Optional[Fernet] = None
        self._config_path: Path = self._get_config_path()

    @staticmethod
    def _get_config_path() -> Path:
        if platform.system() == 'Windows':
            base = Path(os.environ.get('APPDATA', Path.home()))
        else:
            base = Path.home() / '.config'
        config_dir = base / 'SafeKeep'
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / 'config.enc'

    def _get_fernet(self) -> Fernet:
        if self._fernet is None:
            self._fernet = Fernet(_get_machine_key())
        return self._fernet

    def load_config(self) -> None:
        """Load and decrypt config from disk."""
        if not self._config_path.exists():
            self._config = dict(self.DEFAULT_CONFIG)
            return
        try:
            encrypted = self._config_path.read_bytes()
            decrypted = self._get_fernet().decrypt(encrypted)
            self._config = json.loads(decrypted.decode('utf-8'))
        except Exception:
            self._config = dict(self.DEFAULT_CONFIG)

    def save_config(self) -> None:
        """Encrypt and save config to disk."""
        raw = json.dumps(self._config, ensure_ascii=False, indent=2).encode('utf-8')
        encrypted = self._get_fernet().encrypt(raw)
        self._config_path.write_bytes(encrypted)

    def get_sites(self) -> List[Dict[str, Any]]:
        return self._config.get('sites', [])

    def get_global(self) -> Dict[str, Any]:
        return self._config.get('global', self.DEFAULT_CONFIG['global'])

    def add_site(self, site: Dict[str, Any]) -> None:
        sites = self.get_sites()
        sites.append(site)
        self._config['sites'] = sites
        self.save_config()

    def update_site(self, site_id: str, updates: Dict[str, Any]) -> bool:
        sites = self.get_sites()
        for i, s in enumerate(sites):
            if s.get('id') == site_id:
                sites[i] = {**s, **updates}
                self._config['sites'] = sites
                self.save_config()
                return True
        return False

    def remove_site(self, site_id: str) -> bool:
        sites = self.get_sites()
        original_len = len(sites)
        self._config['sites'] = [s for s in sites if s.get('id') != site_id]
        if len(self._config['sites']) < original_len:
            self.save_config()
            return True
        return False

    def update_global(self, updates: Dict[str, Any]) -> None:
        global_cfg = self.get_global()
        global_cfg.update(updates)
        self._config['global'] = global_cfg
        self.save_config()
