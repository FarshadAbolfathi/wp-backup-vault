"""
SafeKeep configuration manager with encrypted persistence.
Farshad Abolfathi — https://www.linkedin.com/in/farshad-abolfathi/
"""
import os
import json
import logging
import copy
from pathlib import Path

from safekeep.utils.crypto import encrypt_data, decrypt_data
from safekeep.utils.logger import setup_logger


class Config:
    """
    Manages application configuration stored in an encrypted file.

    Configuration is encrypted with a machine-bound key so that the
    config file cannot be read on a different machine.
    """

    def __init__(self):
        self.logger = setup_logger('safekeep.config')
        self._config_path = (
            Path(os.environ.get('APPDATA', str(Path.home()))) / 'SafeKeep' / 'config.enc'
        )
        self._data: dict = {
            'sites': [],
            'global': {
                'log_level': 'INFO',
                'max_concurrent_downloads': 2,
            },
        }

    def load_config(self) -> None:
        """Load and decrypt configuration from disk, falling back to defaults."""
        if not self._config_path.exists():
            self.logger.info('No config file found; using defaults.')
            return

        try:
            encrypted = self._config_path.read_text(encoding='utf-8')
            plaintext = decrypt_data(encrypted)
            loaded: dict = json.loads(plaintext)
            # Merge loaded data into defaults so new keys survive upgrades
            if 'sites' in loaded:
                self._data['sites'] = loaded['sites']
            if 'global' in loaded:
                self._data['global'].update(loaded['global'])
            self.logger.info('Configuration loaded successfully.')
        except ValueError as exc:
            self.logger.warning(f'Config decryption failed: {exc}. Using defaults.')
        except json.JSONDecodeError as exc:
            self.logger.warning(f'Config JSON parse error: {exc}. Using defaults.')
        except Exception as exc:
            self.logger.error(f'Unexpected error loading config: {exc}. Using defaults.')

    def save_config(self) -> None:
        """Encrypt and persist the current configuration to disk."""
        try:
            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            plaintext = json.dumps(self._data, ensure_ascii=False, indent=2)
            encrypted = encrypt_data(plaintext)
            self._config_path.write_text(encrypted, encoding='utf-8')
            self.logger.info('Configuration saved.')
        except Exception as exc:
            self.logger.error(f'Failed to save configuration: {exc}')

    # ------------------------------------------------------------------
    # Sites
    # ------------------------------------------------------------------

    def get_sites(self) -> list:
        """Return a deep copy of the sites list."""
        return copy.deepcopy(self._data['sites'])

    def get_site(self, site_id: str) -> 'dict | None':
        """Return a copy of a site dict by its id, or None if not found."""
        for site in self._data['sites']:
            if site.get('id') == site_id:
                return copy.deepcopy(site)
        return None

    def add_site(self, site: dict) -> None:
        """
        Add a new site to the configuration.

        Args:
            site: Site dict with required keys: id, name, url, api_key, save_path.

        Raises:
            ValueError: If required fields are missing or a site with the same id exists.
        """
        required = ('id', 'name', 'url', 'api_key', 'save_path')
        missing = [k for k in required if not site.get(k)]
        if missing:
            raise ValueError(f'Site is missing required fields: {missing}')
        if any(s['id'] == site['id'] for s in self._data['sites']):
            raise ValueError(f'A site with id "{site["id"]}" already exists.')
        self._data['sites'].append(copy.deepcopy(site))
        self.save_config()
        self.logger.info(f'Site "{site["name"]}" added.')

    def update_site(self, site_id: str, updates: dict) -> None:
        """
        Update fields of an existing site.

        Args:
            site_id: ID of the site to update.
            updates: Dict of fields to update (id cannot be changed).

        Raises:
            ValueError: If the site is not found.
        """
        updates.pop('id', None)  # Do not allow changing the id
        for idx, site in enumerate(self._data['sites']):
            if site.get('id') == site_id:
                self._data['sites'][idx].update(updates)
                self.save_config()
                self.logger.info(f'Site "{site_id}" updated.')
                return
        raise ValueError(f'Site with id "{site_id}" not found.')

    def remove_site(self, site_id: str) -> None:
        """
        Remove a site from the configuration.

        Args:
            site_id: ID of the site to remove.

        Raises:
            ValueError: If the site is not found.
        """
        original_count = len(self._data['sites'])
        self._data['sites'] = [s for s in self._data['sites'] if s.get('id') != site_id]
        if len(self._data['sites']) == original_count:
            raise ValueError(f'Site with id "{site_id}" not found.')
        self.save_config()
        self.logger.info(f'Site "{site_id}" removed.')

    # ------------------------------------------------------------------
    # Global settings
    # ------------------------------------------------------------------

    def get_global_settings(self) -> dict:
        """Return a copy of the global settings dict."""
        return copy.deepcopy(self._data['global'])

    def update_global_settings(self, updates: dict) -> None:
        """
        Merge updates into the global settings and persist.

        Args:
            updates: Dict of settings to update.
        """
        self._data['global'].update(updates)
        self.save_config()
        self.logger.info('Global settings updated.')
