"""
SafeKeep — Backup manager: list, download, assemble, and manage backups.

Author: Farshad Abolfathi — https://www.linkedin.com/in/farshad-abolfathi/
"""

import os
import shutil
from pathlib import Path
from typing import Callable, Optional

import requests

from safekeep.core.downloader import download_chunk
from safekeep.utils.helpers import verify_chunk, get_dir_size, safe_remove_dir, human_size
from safekeep.utils.logger import get_logger

logger = get_logger("backup_manager")

HTTP_TIMEOUT = (15, 60)


def _api_get(site_url: str, api_key: str, path: str) -> dict | list:
    url = site_url.rstrip("/") + "/wp-json/wp-vault-bridge/v1" + path
    resp = requests.get(url, headers={"X-API-Key": api_key}, timeout=HTTP_TIMEOUT, verify=True)
    resp.raise_for_status()
    return resp.json()


def list_remote_backups(site_url: str, api_key: str) -> list:
    """Return list of backup objects from the remote WordPress site."""
    try:
        return _api_get(site_url, api_key, "/backups")
    except Exception as e:
        logger.error(f"list_remote_backups failed: {e}")
        raise


def get_manifest(site_url: str, api_key: str, backup_id: str) -> dict:
    try:
        return _api_get(site_url, api_key, f"/backups/{backup_id}/manifest")
    except Exception as e:
        logger.error(f"get_manifest failed for {backup_id}: {e}")
        raise


def test_connection(site_url: str, api_key: str) -> tuple[bool, str]:
    """Test connectivity and API key validity. Returns (ok, message)."""
    try:
        result = _api_get(site_url, api_key, "/backups")
        return True, f"اتصال موفق — {len(result)} بک‌آپ موجود"
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 401:
            return False, "کلید API نادرست است (۴۰۱ Unauthorized)"
        return False, f"خطای HTTP: {e}"
    except requests.exceptions.ConnectionError:
        return False, "اتصال برقرار نشد — آدرس سایت را بررسی کنید"
    except Exception as e:
        return False, f"خطا: {e}"


def download_backup(
    site_url: str,
    api_key: str,
    backup_id: str,
    save_path: str | Path,
    progress_callback: Optional[Callable[[str, int, int], None]] = None,
) -> bool:
    """
    Download all chunks for a backup, verify checksums, and assemble into final archive.

    Args:
        progress_callback: Called with (chunk_filename, bytes_done, total_bytes)

    Returns:
        True if backup downloaded and assembled successfully.
    """
    save_path = Path(save_path)
    backup_dir = save_path / backup_id
    backup_dir.mkdir(parents=True, exist_ok=True)

    # Check if already downloaded
    done_marker = backup_dir / ".complete"
    if done_marker.exists():
        logger.info(f"Backup {backup_id} already complete, skipping.")
        return True

    try:
        manifest = get_manifest(site_url, api_key, backup_id)
    except Exception as e:
        logger.error(f"Cannot get manifest for {backup_id}: {e}")
        return False

    chunks = manifest.get("chunks", [])
    if not chunks:
        logger.error(f"Manifest has no chunks for {backup_id}")
        return False

    logger.info(f"Downloading backup {backup_id}: {len(chunks)} chunk(s)")

    for chunk_info in chunks:
        filename = chunk_info["filename"]
        chunk_path = backup_dir / filename
        chunk_url = (
            site_url.rstrip("/")
            + f"/wp-json/wp-vault-bridge/v1/backups/{backup_id}/chunks/{filename}"
        )

        if chunk_path.exists():
            ok, err = verify_chunk(
                chunk_path,
                chunk_info.get("md5", ""),
                chunk_info.get("sha256", ""),
            )
            if ok:
                logger.info(f"Chunk already verified: {filename}")
                continue
            else:
                logger.warning(f"Chunk verification failed, re-downloading: {filename} — {err}")
                chunk_path.unlink(missing_ok=True)

        def _progress(done: int, total: int, _fname=filename):
            if progress_callback:
                progress_callback(_fname, done, total)

        ok = download_chunk(
            url=chunk_url,
            api_key=api_key,
            save_path=chunk_path,
            expected_md5=chunk_info.get("md5"),
            expected_sha256=chunk_info.get("sha256"),
            progress_callback=_progress,
        )

        if not ok:
            logger.error(f"Failed to download chunk {filename}")
            return False

    # Write manifest locally
    import json
    with open(backup_dir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    # Mark as complete
    done_marker.touch()
    logger.info(f"Backup {backup_id} downloaded successfully.")
    return True


def list_local_backups(save_path: str | Path) -> list:
    """List complete local backups in save_path, newest first."""
    save_path = Path(save_path)
    if not save_path.exists():
        return []

    result = []
    for entry in save_path.iterdir():
        if not entry.is_dir():
            continue
        done_marker = entry / ".complete"
        manifest_file = entry / "manifest.json"
        if not done_marker.exists():
            continue

        info = {
            "id": entry.name,
            "path": str(entry),
            "size": get_dir_size(entry),
        }
        if manifest_file.exists():
            import json
            try:
                info["manifest"] = json.loads(manifest_file.read_text("utf-8"))
                info["created_at"] = info["manifest"].get("created_at", "")
            except Exception:
                info["created_at"] = ""
        result.append(info)

    result.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return result


def cleanup_old_backups(save_path: str | Path, retention_count: int):
    """Delete local backups older than the retention limit."""
    backups = list_local_backups(save_path)
    if len(backups) <= retention_count:
        return

    to_delete = backups[retention_count:]
    for b in to_delete:
        safe_remove_dir(b["path"])
        logger.info(f"Deleted old local backup: {b['id']} ({human_size(b['size'])})")
