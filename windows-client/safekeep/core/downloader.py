"""
SafeKeep chunk-based backup downloader with resume support.
Farshad Abolfathi — https://www.linkedin.com/in/farshad-abolfathi/
"""
import os
import logging
import requests
import hashlib
from pathlib import Path

from safekeep.utils.helpers import verify_sha256, verify_md5, ensure_dir
from safekeep.utils.logger import setup_logger


class ChunkDownloader:
    """
    Downloads WordPress backup chunks from a SafeKeep-Bridge REST endpoint.

    Supports HTTP range requests for resumable downloads and verifies
    SHA-256 or MD5 checksums after each chunk is received.
    """

    def __init__(self, site_url: str, api_key: str) -> None:
        self.site_url = site_url.rstrip('/')
        self.api_key = api_key
        self.logger = setup_logger('safekeep.downloader')
        self.session = requests.Session()
        self.session.headers.update({
            'X-API-Key': api_key,
            'User-Agent': 'SafeKeep/1.0',
        })
        self.timeout = 60

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _api_url(self, path: str) -> str:
        """Build the full API URL for a given endpoint path."""
        return f'{self.site_url}/wp-json/wp-vault/v1/{path.lstrip("/")}'

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_backups(self) -> list:
        """
        Retrieve the list of available backups from the remote site.

        Returns:
            List of backup dicts.

        Raises:
            requests.RequestException: On network or HTTP errors.
        """
        try:
            response = self.session.get(self._api_url('backups'), timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            self.logger.error(f'list_backups failed: {exc}')
            raise

    def get_manifest(self, backup_id: str) -> dict:
        """
        Retrieve the manifest for a specific backup.

        Args:
            backup_id: Remote backup identifier.

        Returns:
            Manifest dict describing chunks and metadata.

        Raises:
            requests.RequestException: On network or HTTP errors (including 404).
        """
        try:
            url = self._api_url(f'backups/{backup_id}/manifest')
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            self.logger.error(f'get_manifest failed for {backup_id}: {exc}')
            raise

    def download_chunk(
        self,
        backup_id: str,
        filename: str,
        dest_path: str,
        progress_callback=None,
    ) -> bool:
        """
        Download a single backup chunk with resume support.

        If the destination file already exists and is partially downloaded,
        a Range header is sent to continue where the download left off.

        Args:
            backup_id: Remote backup identifier.
            filename: Chunk filename (e.g. 'chunk_001.bin').
            dest_path: Local file path where the chunk should be saved.
            progress_callback: Optional callable(bytes_downloaded, total_bytes).

        Returns:
            True on success, False on failure.
        """
        url = self._api_url(f'backups/{backup_id}/chunks/{filename}')
        headers = {}
        resuming = False
        existing_size = 0

        try:
            if os.path.exists(dest_path):
                existing_size = os.path.getsize(dest_path)
                if existing_size > 0:
                    headers['Range'] = f'bytes={existing_size}-'
                    resuming = True
                    self.logger.debug(
                        f'Resuming {filename} from byte {existing_size}'
                    )

            response = self.session.get(
                url,
                headers=headers,
                stream=True,
                timeout=self.timeout,
            )

            # If we tried to resume but server returned 200 (no range support),
            # restart from the beginning.
            if resuming and response.status_code == 200:
                self.logger.debug(
                    f'Server does not support range requests for {filename}; restarting.'
                )
                resuming = False
                existing_size = 0
            else:
                response.raise_for_status()

            # Determine total size for progress reporting
            total_bytes: int = 0
            content_length = response.headers.get('Content-Length')
            content_range = response.headers.get('Content-Range')
            if content_range:
                # Content-Range: bytes start-end/total
                try:
                    total_bytes = int(content_range.split('/')[-1])
                except (ValueError, IndexError):
                    total_bytes = 0
            elif content_length:
                try:
                    total_bytes = int(content_length) + existing_size
                except ValueError:
                    total_bytes = 0

            write_mode = 'ab' if resuming else 'wb'
            bytes_downloaded = existing_size

            with open(dest_path, write_mode) as fh:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        fh.write(chunk)
                        bytes_downloaded += len(chunk)
                        if progress_callback:
                            try:
                                progress_callback(bytes_downloaded, total_bytes)
                            except Exception:
                                pass  # Never let a callback crash the download

            self.logger.debug(f'Chunk downloaded: {filename} ({bytes_downloaded} bytes)')
            return True

        except Exception as exc:
            self.logger.error(f'download_chunk failed for {filename}: {exc}')
            return False

    def download_backup(
        self,
        backup_id: str,
        save_dir: str,
        progress_callback=None,
    ) -> bool:
        """
        Download all chunks for a backup and verify their checksums.

        Args:
            backup_id: Remote backup identifier.
            save_dir: Local directory to store downloaded chunks.
            progress_callback: Optional callable forwarded to download_chunk.

        Returns:
            True if all chunks downloaded and verified, False otherwise.
        """
        try:
            manifest = self.get_manifest(backup_id)
        except Exception as exc:
            self.logger.error(f'Cannot download backup {backup_id}: manifest error: {exc}')
            return False

        chunks = manifest.get('chunks', [])
        if not chunks:
            self.logger.warning(f'Manifest for {backup_id} contains no chunks.')
            return False

        ensure_dir(save_dir)

        for chunk in chunks:
            chunk_filename = chunk.get('filename')
            dest_path = os.path.join(save_dir, chunk_filename)

            success = self.download_chunk(
                backup_id, chunk_filename, dest_path, progress_callback
            )
            if not success:
                self.logger.error(
                    f'Failed to download chunk {chunk_filename} for backup {backup_id}.'
                )
                return False

            # Verify checksum — prefer SHA-256, fall back to MD5
            if 'sha256' in chunk:
                if not verify_sha256(dest_path, chunk['sha256']):
                    self.logger.error(
                        f'SHA-256 mismatch for chunk {chunk_filename}; deleting.'
                    )
                    try:
                        os.remove(dest_path)
                    except OSError:
                        pass
                    return False
            elif 'md5' in chunk:
                if not verify_md5(dest_path, chunk['md5']):
                    self.logger.error(
                        f'MD5 mismatch for chunk {chunk_filename}; deleting.'
                    )
                    try:
                        os.remove(dest_path)
                    except OSError:
                        pass
                    return False

        self.logger.info(f'Backup {backup_id} downloaded successfully ({len(chunks)} chunks).')
        return True
