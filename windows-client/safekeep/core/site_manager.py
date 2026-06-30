"""
SafeKeep — Site Manager
Farshad Abolfathi — https://www.linkedin.com/in/farshad-abolfathi/
"""
import hashlib
import logging
import os
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import requests


logger = logging.getLogger(__name__)


class DownloadProgress:
    """Tracks download progress for a chunk."""
    def __init__(self, filename: str, total_size: int):
        self.filename = filename
        self.total_size = total_size
        self.downloaded = 0
        self.complete = False
        self.error: Optional[str] = None

    @property
    def percent(self) -> float:
        if self.total_size <= 0:
            return 0.0
        return min(100.0, self.downloaded / self.total_size * 100)


class SiteManager:
    """Manages backup downloading for all configured sites."""

    CHUNK_SIZE = 8192  # bytes per read

    def __init__(self, config):
        self._config = config
        self._lock = threading.Lock()
        self._active_downloads: Dict[str, DownloadProgress] = {}

    # ------------------------------------------------------------------
    # API helpers
    # ------------------------------------------------------------------

    def _api_get(self, site: Dict[str, Any], path: str,
                 stream: bool = False, range_header: Optional[str] = None):
        url = site['url'].rstrip('/') + '/wp-json/wp-vault-bridge/v1/' + path.lstrip('/')
        headers = {'X-API-Key': site['api_key']}
        if range_header:
            headers['Range'] = range_header
        resp = requests.get(url, headers=headers, stream=stream, timeout=30)
        resp.raise_for_status()
        return resp

    # ------------------------------------------------------------------
    # Backup listing
    # ------------------------------------------------------------------

    def list_backups(self, site: Dict[str, Any]) -> List[Dict[str, Any]]:
        try:
            resp = self._api_get(site, '/backups')
            return resp.json()
        except Exception as e:
            logger.error(f"list_backups error for {site.get('name')}: {e}")
            return []

    def get_manifest(self, site: Dict[str, Any], backup_id: str) -> Optional[Dict[str, Any]]:
        try:
            resp = self._api_get(site, f'/backups/{backup_id}/manifest')
            return resp.json()
        except Exception as e:
            logger.error(f"get_manifest error: {e}")
            return None

    # ------------------------------------------------------------------
    # Download
    # ------------------------------------------------------------------

    def download_backup(self, site: Dict[str, Any], backup_id: str,
                        progress_callback: Optional[Callable] = None) -> bool:
        manifest = self.get_manifest(site, backup_id)
        if not manifest:
            return False

        save_path = Path(site.get('save_path', '.')) / backup_id
        save_path.mkdir(parents=True, exist_ok=True)

        global_cfg = self._config.get_global()
        max_concurrent = int(global_cfg.get('max_concurrent_downloads', 2))

        chunks = manifest.get('chunks', [])
        semaphore = threading.Semaphore(max_concurrent)
        results = {}

        def download_chunk(chunk_info: Dict[str, Any]):
            filename = chunk_info['filename']
            expected_md5 = chunk_info.get('md5', '')
            expected_size = chunk_info.get('size', 0)
            dest = save_path / filename

            with semaphore:
                progress = DownloadProgress(filename, expected_size)
                with self._lock:
                    self._active_downloads[filename] = progress

                try:
                    # Resume support
                    resume_pos = dest.stat().st_size if dest.exists() else 0
                    range_hdr = f'bytes={resume_pos}-' if resume_pos > 0 else None

                    resp = self._api_get(site,
                                         f'/backups/{backup_id}/chunks/{filename}',
                                         stream=True, range_header=range_hdr)
                    mode = 'ab' if resume_pos > 0 else 'wb'
                    progress.downloaded = resume_pos

                    with open(dest, mode) as f:
                        for data in resp.iter_content(chunk_size=self.CHUNK_SIZE):
                            f.write(data)
                            progress.downloaded += len(data)
                            if progress_callback:
                                progress_callback(filename, progress.percent)

                    # Verify checksum
                    md5 = self._md5_file(dest)
                    if expected_md5 and md5 != expected_md5:
                        raise ValueError(f'MD5 mismatch for {filename}')

                    progress.complete = True
                    results[filename] = True
                    logger.info(f'Downloaded {filename} ({progress.downloaded} bytes)')

                except Exception as e:
                    progress.error = str(e)
                    results[filename] = False
                    logger.error(f'Failed to download {filename}: {e}')
                finally:
                    with self._lock:
                        self._active_downloads.pop(filename, None)

        threads = [threading.Thread(target=download_chunk, args=(c,), daemon=True)
                   for c in chunks]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        return all(results.values())

    @staticmethod
    def _md5_file(path: Path) -> str:
        h = hashlib.md5()
        with open(path, 'rb') as f:
            for block in iter(lambda: f.read(65536), b''):
                h.update(block)
        return h.hexdigest()

    # ------------------------------------------------------------------
    # Retention
    # ------------------------------------------------------------------

    def apply_retention(self, site: Dict[str, Any]) -> None:
        retention = int(site.get('retention_count', 5))
        save_path = Path(site.get('save_path', '.'))
        if not save_path.exists():
            return
        dirs = sorted(
            [d for d in save_path.iterdir() if d.is_dir()],
            key=lambda d: d.name
        )
        to_remove = dirs[:max(0, len(dirs) - retention)]
        for d in to_remove:
            import shutil
            shutil.rmtree(d, ignore_errors=True)
            logger.info(f'Retention: removed {d}')
