"""
SafeKeep site manager — orchestrates multi-site backup operations.
Farshad Abolfathi — https://www.linkedin.com/in/farshad-abolfathi/
"""
import logging
import requests

from safekeep.core.backup_manager import BackupManager
from safekeep.core.downloader import ChunkDownloader
from safekeep.utils.logger import setup_logger


class SiteManager:
    """
    High-level interface for managing backup operations across all configured sites.

    Delegates per-site work to BackupManager and exposes simple methods
    suitable for consumption by the GUI and scheduler.
    """

    def __init__(self, config) -> None:
        self.config = config
        self.logger = setup_logger('safekeep.site_manager')

    # ------------------------------------------------------------------
    # Site CRUD
    # ------------------------------------------------------------------

    def get_all_sites(self) -> list:
        """Return all configured sites."""
        return self.config.get_sites()

    def add_site(self, site: dict) -> None:
        """Add a new site to the configuration."""
        self.config.add_site(site)
        self.logger.info(f'Site added: {site.get("name")}')

    def update_site(self, site_id: str, updates: dict) -> None:
        """Update an existing site's configuration."""
        self.config.update_site(site_id, updates)
        self.logger.info(f'Site updated: {site_id}')

    def remove_site(self, site_id: str) -> None:
        """Remove a site from the configuration."""
        self.config.remove_site(site_id)
        self.logger.info(f'Site removed: {site_id}')

    # ------------------------------------------------------------------
    # Connection test
    # ------------------------------------------------------------------

    def test_connection(self, site_id: str) -> 'tuple[bool, str]':
        """
        Verify that the API endpoint is reachable with the stored credentials.

        Args:
            site_id: ID of the site to test.

        Returns:
            (True, success_message) or (False, error_message).
        """
        try:
            site = self.config.get_site(site_id)
            if site is None:
                return (False, f'سایت با شناسه "{site_id}" یافت نشد.')
            downloader = ChunkDownloader(site['url'], site['api_key'])
            downloader.list_backups()
            return (True, 'اتصال موفق بود')
        except requests.exceptions.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 401:
                return (False, 'کلید API نادرست است')
            return (False, f'خطای HTTP: {exc}')
        except requests.exceptions.ConnectionError:
            return (False, 'اتصال برقرار نشد')
        except Exception as exc:
            self.logger.error(f'test_connection failed for {site_id}: {exc}')
            return (False, str(exc))

    # ------------------------------------------------------------------
    # Backup operations
    # ------------------------------------------------------------------

    def fetch_pending(self, site_id: str, progress_callback=None) -> int:
        """
        Download all pending backups for a site and apply retention.

        Args:
            site_id: ID of the site.
            progress_callback: Optional callable forwarded to BackupManager.

        Returns:
            Number of backups successfully fetched.
        """
        try:
            site = self.config.get_site(site_id)
            if site is None:
                self.logger.error(f'fetch_pending: site "{site_id}" not found.')
                return 0
            manager = BackupManager(site)
            pending = manager.get_pending_backups()
            fetched = 0
            for backup in pending:
                backup_id = backup.get('backup_id') or backup.get('id')
                if not backup_id:
                    continue
                if manager.fetch_backup(backup_id, progress_callback):
                    fetched += 1
                else:
                    self.logger.warning(
                        f'fetch_pending: failed to fetch backup {backup_id} '
                        f'for site "{site.get("name")}".'
                    )
            manager.apply_local_retention()
            return fetched
        except Exception as exc:
            self.logger.error(f'fetch_pending failed for site {site_id}: {exc}')
            return 0

    def get_site_status(self, site_id: str) -> dict:
        """
        Return a status summary dict for a site.

        Args:
            site_id: ID of the site.

        Returns:
            Status summary dict from BackupManager.get_status_summary().
        """
        try:
            site = self.config.get_site(site_id)
            if site is None:
                return {}
            manager = BackupManager(site)
            return manager.get_status_summary()
        except Exception as exc:
            self.logger.error(f'get_site_status failed for {site_id}: {exc}')
            return {}

    def fetch_backup_by_id(
        self,
        site_id: str,
        backup_id: str,
        progress_callback=None,
    ) -> bool:
        """
        Download a specific backup by ID for a given site.

        Args:
            site_id: ID of the site.
            backup_id: Remote backup identifier to download.
            progress_callback: Optional callable forwarded to BackupManager.

        Returns:
            True on success, False on failure.
        """
        try:
            site = self.config.get_site(site_id)
            if site is None:
                self.logger.error(f'fetch_backup_by_id: site "{site_id}" not found.')
                return False
            manager = BackupManager(site)
            return manager.fetch_backup(backup_id, progress_callback)
        except Exception as exc:
            self.logger.error(
                f'fetch_backup_by_id failed for site {site_id}, backup {backup_id}: {exc}'
            )
            return False
