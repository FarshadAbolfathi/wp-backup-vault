"""
SafeKeep — Chunk downloader with resume support and checksum verification.
Uses HTTP Range headers to resume interrupted downloads.

Author: Farshad Abolfathi — https://www.linkedin.com/in/farshad-abolfathi/
"""

import os
import time
from pathlib import Path
from typing import Callable, Optional

import requests

from safekeep.utils.helpers import compute_md5, compute_sha256
from safekeep.utils.logger import get_logger

logger = get_logger("downloader")

# Timeout for HTTP requests (connect, read)
HTTP_TIMEOUT = (15, 60)
MAX_RETRIES = 3


def download_chunk(
    url: str,
    api_key: str,
    save_path: str | Path,
    expected_md5: Optional[str] = None,
    expected_sha256: Optional[str] = None,
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> bool:
    """
    Download a single chunk file to save_path.
    Resumes from existing partial file using Range header.

    Args:
        url: Full URL to the chunk endpoint
        api_key: WP Vault Bridge API key
        save_path: Local destination path (partial .tmp file used during download)
        expected_md5: MD5 from manifest (verified after download)
        expected_sha256: SHA256 from manifest (verified after download)
        progress_callback: Called with (bytes_downloaded, total_bytes)

    Returns:
        True on success, False on failure.
    """
    save_path = Path(save_path)
    tmp_path = Path(str(save_path) + ".tmp")

    headers = {"X-API-Key": api_key}
    existing_size = tmp_path.stat().st_size if tmp_path.exists() else 0

    if existing_size > 0:
        headers["Range"] = f"bytes={existing_size}-"
        logger.info(f"Resuming download from byte {existing_size}: {url}")

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(
                url,
                headers=headers,
                stream=True,
                timeout=HTTP_TIMEOUT,
                verify=True,
            )

            if response.status_code == 416:
                # Range not satisfiable — file already fully downloaded as tmp
                logger.info(f"Range 416 — file already complete: {save_path.name}")
                break

            if response.status_code not in (200, 206):
                logger.error(f"HTTP {response.status_code} downloading {url}")
                if attempt < MAX_RETRIES:
                    time.sleep(2 ** attempt)
                    continue
                return False

            mode = "ab" if response.status_code == 206 else "wb"
            if mode == "wb":
                existing_size = 0

            total = int(response.headers.get("Content-Length", 0)) + existing_size
            downloaded = existing_size

            save_path.parent.mkdir(parents=True, exist_ok=True)
            with open(tmp_path, mode) as f:
                for chunk in response.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback and total > 0:
                            progress_callback(downloaded, total)

            logger.info(f"Downloaded: {save_path.name} ({downloaded} bytes)")
            break  # Success

        except requests.RequestException as e:
            logger.warning(f"Download attempt {attempt}/{MAX_RETRIES} failed: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(2 ** attempt)
            else:
                logger.error(f"All retries exhausted for {url}")
                return False

    # Verify checksums if provided
    if expected_md5 or expected_sha256:
        if not _verify_checksums(tmp_path, expected_md5, expected_sha256):
            logger.error(f"Checksum mismatch for {save_path.name}. Deleting partial file.")
            tmp_path.unlink(missing_ok=True)
            return False

    # Rename tmp to final
    tmp_path.rename(save_path)
    return True


def _verify_checksums(
    filepath: Path,
    expected_md5: Optional[str],
    expected_sha256: Optional[str],
) -> bool:
    if expected_md5:
        actual = compute_md5(filepath)
        if actual != expected_md5:
            logger.error(f"MD5 mismatch: expected {expected_md5}, got {actual}")
            return False

    if expected_sha256:
        actual = compute_sha256(filepath)
        if actual != expected_sha256:
            logger.error(f"SHA256 mismatch: expected {expected_sha256}, got {actual}")
            return False

    return True
