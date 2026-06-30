"""
SafeKeep — Background scheduler: periodically checks each site for new backups.

Author: Farshad Abolfathi — https://www.linkedin.com/in/farshad-abolfathi/
"""

import threading
import time
from typing import Callable, Optional

from safekeep.utils.logger import get_logger

logger = get_logger("scheduler")


class SitePoller(threading.Thread):
    """Background thread that polls one site on a configurable interval."""

    def __init__(
        self,
        site: dict,
        fetch_callback: Callable[[str], None],
        interval_minutes: int = 60,
    ):
        super().__init__(daemon=True)
        self.site = site
        self.fetch_callback = fetch_callback
        self.interval = interval_minutes * 60
        self._stop_event = threading.Event()
        self.name = f"poller-{site['id']}"

    def run(self):
        logger.info(f"Poller started for site '{self.site.get('name')}' (interval={self.interval}s)")
        # Wait a few seconds before first check so the GUI can finish loading
        self._stop_event.wait(5)
        while not self._stop_event.is_set():
            try:
                logger.info(f"Checking site: {self.site.get('name')}")
                self.fetch_callback(self.site["id"])
            except Exception as e:
                logger.error(f"Poller error for site {self.site.get('name')}: {e}")
            self._stop_event.wait(self.interval)

    def stop(self):
        self._stop_event.set()


class BackupScheduler:
    """Manages one SitePoller thread per site."""

    def __init__(self, fetch_callback: Callable[[str], None]):
        self._fetch_callback = fetch_callback
        self._pollers: dict[str, SitePoller] = {}
        self._lock = threading.Lock()

    def start_site(self, site: dict):
        site_id = site["id"]
        interval = int(site.get("check_interval_minutes", 60))
        with self._lock:
            if site_id in self._pollers:
                self._pollers[site_id].stop()
            poller = SitePoller(site, self._fetch_callback, interval)
            poller.start()
            self._pollers[site_id] = poller

    def stop_site(self, site_id: str):
        with self._lock:
            poller = self._pollers.pop(site_id, None)
            if poller:
                poller.stop()

    def restart_site(self, site: dict):
        self.stop_site(site["id"])
        self.start_site(site)

    def start_all(self, sites: list):
        for site in sites:
            self.start_site(site)

    def stop_all(self):
        with self._lock:
            for poller in self._pollers.values():
                poller.stop()
            self._pollers.clear()
