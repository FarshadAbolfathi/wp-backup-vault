"""
SafeKeep backup lifecycle manager — fetch, verify, and retain backups.
Farshad Abolfathi — https://www.linkedin.com/in/farshad-abolfathi/
"""
import os
import logging
import json
import datetime
from pathlib import Path

from safekeep.core.downloader import ChunkDownloader
from safekeep.utils.helpers import ensure_dir, safe_delete, human_readable_size
from safekeep.utils.logger import setup_logger


class BackupManager:
    """
    Manages the full backup lifecycle for a single WordPress site.

    Responsibilities:
    - Query remote backups
    - Identify which backups have not yet been downloaded
    - Fetch missing backups chunk by chunk
    - Enforce local retention policy
    """

    def __init__(self, site: dict) -> None:
        self.site = site
        self.logger = setup_logger('safekeep.backup_manager')
        self.downloader = ChunkDownloader(site['url'], site['api_key'])
        self.save_dir = Path(site['save_path'])

    # ------------------------------------------------------------------
    # Remote
    # ------------------------------------------------------------------

    def get_remote_backups(self) -> list:
        """
        Return remote backups with status 'complete', sorted newest first.

        Returns:
            List of backup dicts.
        """
        try:
            all_backups = self.downloader.list_backups()
            complete = [b for b in all_backups if b.get('status') == 'complete']
            complete.sort(key=lambda b: b.get('date', ''), reverse=True)
            return complete
        except Exception as exc:
            self.logger.error(f'get_remote_backups failed: {exc}')
            return []

    # ------------------------------------------------------------------
    # Local
    # ------------------------------------------------------------------

    def get_local_backups(self) -> list:
        """
        Scan the local save directory for downloaded backups.

        A valid local backup is a subdirectory containing a manifest.json file.

        Returns:
            List of manifest dicts, sorted newest first.
        """
        backups = []
        try:
            if not self.save_dir.exists():
                return backups
            for entry in self.save_dir.iterdir():
                if not entry.is_dir():
                    continue
                manifest_path = entry / 'manifest.json'
                if not manifest_path.exists():
                    continue
                try:
                    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
                    backups.append(manifest)
                except Exception as exc:
                    self.logger.warning(f'Could not read manifest {manifest_path}: {exc}')
            backups.sort(key=lambda b: b.get('date', ''), reverse=True)
        except Exception as exc:
            self.logger.error(f'get_local_backups failed: {exc}')
        return backups

    # ------------------------------------------------------------------
    # Pending
    # ------------------------------------------------------------------

    def get_pending_backups(self) -> list:
        """
        Return remote backups that have not yet been downloaded locally.

        Returns:
            List of remote backup dicts whose IDs are absent locally.
        """
        try:
            remote = self.get_remote_backups()
            local_ids = {
                b.get('backup_id') or b.get('id')
                for b in self.get_local_backups()
            }
            return [b for b in remote if (b.get('backup_id') or b.get('id')) not in local_ids]
        except Exception as exc:
            self.logger.error(f'get_pending_backups failed: {exc}')
            return []

    # ------------------------------------------------------------------
    # Fetch
    # ------------------------------------------------------------------

    def fetch_backup(self, backup_id: str, progress_callback=None) -> bool:
        """
        Download a specific backup and write its manifest to the local directory.

        Args:
            backup_id: Remote backup identifier.
            progress_callback: Optional callable(bytes_downloaded, total_bytes).

        Returns:
            True on success, False on any failure.
        """
        dest = self.save_dir / backup_id
        try:
            ensure_dir(str(dest))
            manifest = self.downloader.get_manifest(backup_id)
            chunks = manifest.get('chunks', [])

            for chunk in chunks:
                chunk_filename = chunk.get('filename')
                chunk_path = dest / chunk_filename

                ok = self.downloader.download_chunk(
                    backup_id, chunk_filename, str(chunk_path), progress_callback
                )
                if not ok:
                    self.logger.error(
                        f'Chunk download failed: {chunk_filename} for backup {backup_id}.'
                    )
                    return False

                # Verify checksum
                if 'sha256' in chunk:
                    from safekeep.utils.helpers import verify_sha256
                    if not verify_sha256(str(chunk_path), chunk['sha256']):
                        self.logger.error(
                            f'Checksum mismatch for {chunk_filename}; aborting backup {backup_id}.'
                        )
                        return False
                elif 'md5' in chunk:
                    from safekeep.utils.helpers import verify_md5
                    if not verify_md5(str(chunk_path), chunk['md5']):
                        self.logger.error(
                            f'MD5 mismatch for {chunk_filename}; aborting backup {backup_id}.'
                        )
                        return False

            # Persist manifest for local tracking
            manifest_path = dest / 'manifest.json'
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8'
            )

            self.logger.info(
                f'Backup {backup_id} fetched successfully to {dest}.'
            )
            return True

        except Exception as exc:
            self.logger.error(f'fetch_backup failed for {backup_id}: {exc}')
            return False

    # ------------------------------------------------------------------
    # Retention
    # ------------------------------------------------------------------

    def apply_local_retention(self) -> None:
        """
        Delete oldest local backups that exceed the configured retention count.
        """
        try:
            retention_count = int(self.site.get('retention_count', 5))
            local = self.get_local_backups()  # sorted newest first
            to_delete = local[retention_count:]
            for backup in to_delete:
                backup_id = backup.get('backup_id') or backup.get('id')
                if backup_id:
                    target = self.save_dir / backup_id
                    safe_delete(str(target))
                    self.logger.info(f'Retention: deleted old backup {backup_id}.')
            if to_delete:
                self.logger.info(
                    f'Retention policy applied: deleted {len(to_delete)} backup(s).'
                )
        except Exception as exc:
            self.logger.error(f'apply_local_retention failed: {exc}')

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status_summary(self) -> dict:
        """
        Return a summary of backup status for the site.

        Returns:
            Dict with site_id, site_name, remote_count, local_count,
            pending_count, latest_local_date, save_dir.
        """
        try:
            remote = self.get_remote_backups()
            local = self.get_local_backups()
            pending = self.get_pending_backups()
            latest_date = local[0].get('date', '') if local else ''
            return {
                'site_id': self.site.get('id', ''),
                'site_name': self.site.get('name', ''),
                'remote_count': len(remote),
                'local_count': len(local),
                'pending_count': len(pending),
                'latest_local_date': latest_date,
                'save_dir': str(self.save_dir),
            }
        except Exception as exc:
            self.logger.error(f'get_status_summary failed: {exc}')
            return {
                'site_id': self.site.get('id', ''),
                'site_name': self.site.get('name', ''),
                'remote_count': 0,
                'local_count': 0,
                'pending_count': 0,
                'latest_local_date': '',
                'save_dir': str(self.save_dir),
            }
