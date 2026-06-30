"""
SafeKeep background scheduler — periodically checks for new backups.
Farshad Abolfathi — https://www.linkedin.com/in/farshad-abolfathi/
"""
import threading
import logging
import time
import datetime

from safekeep.utils.logger import setup_logger


class BackupScheduler:
    """
    Background thread that wakes periodically to download pending backups.

    The scheduler is designed as a daemon thread so it does not prevent
    the application from exiting. Use start()/stop() to control its lifecycle.
    """

    def __init__(self, site_manager, check_interval_minutes: int = 60) -> None:
        self.site_manager = site_manager
        self.check_interval = check_interval_minutes * 60  # convert to seconds
        self.logger = setup_logger('safekeep.scheduler')
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._running = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the background scheduler thread."""
        if self._running:
            self.logger.debug('Scheduler already running; ignoring start().')
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
            daemon=True,
            name='SafeKeep-Scheduler',
        )
        self._thread.start()
        self._running = True
        self.logger.info(
            f'Scheduler started; checking every {self.check_interval // 60} minute(s).'
        )

    def stop(self) -> None:
        """Signal the scheduler to stop and wait up to 5 seconds for it to exit."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._running = False
        self.logger.info('Scheduler stopped.')

    def is_running(self) -> bool:
        """Return True if the scheduler thread is active."""
        return self._running

    # ------------------------------------------------------------------
    # Background loop
    # ------------------------------------------------------------------

    def _run_loop(self) -> None:
        """Main loop executed in the scheduler thread."""
        while not self._stop_event.is_set():
            try:
                self._check_all_sites()
            except Exception as exc:
                self.logger.error(f'Scheduler error during site check: {exc}')
            # Wait for the configured interval or until stop() is called
            self._stop_event.wait(timeout=self.check_interval)

    def _check_all_sites(self) -> None:
        """Iterate over all configured sites and fetch pending backups."""
        sites = self.site_manager.get_all_sites()
        self.logger.debug(
            f'Scheduled check at {datetime.datetime.now().isoformat()} '
            f'for {len(sites)} site(s).'
        )
        for site in sites:
            try:
                fetched = self.site_manager.fetch_pending(site['id'])
                if fetched:
                    self.logger.info(
                        f'Fetched {fetched} new backup(s) for site "{site["name"]}".'
                    )
            except Exception as exc:
                self.logger.error(
                    f'Failed to check site "{site.get("name", site.get("id"))}": {exc}'
                )

    # ------------------------------------------------------------------
    # On-demand trigger
    # ------------------------------------------------------------------

    def trigger_now(self) -> None:
        """
        Run _check_all_sites immediately in a new daemon thread.

        This does not block the calling thread (GUI-safe).
        """
        trigger_thread = threading.Thread(
            target=self._check_all_sites,
            daemon=True,
            name='SafeKeep-ManualTrigger',
        )
        trigger_thread.start()
        self.logger.info('Manual backup check triggered.')
