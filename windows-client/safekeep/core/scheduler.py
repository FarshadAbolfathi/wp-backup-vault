"""
SafeKeep background scheduler — per-site configurable check intervals.
Farshad Abolfathi — https://www.linkedin.com/in/farshad-abolfathi/
"""
import threading
import logging
import time
import datetime

from safekeep.utils.logger import setup_logger

DEFAULT_CHECK_INTERVAL_MINUTES = 300  # 5 hours if site has no interval configured


class BackupScheduler:
    """
    Background thread that checks each site on its own schedule.

    Each site's ``check_interval_minutes`` field is respected.
    Sites with a missing or zero interval fall back to 5 hours.
    The scheduler wakes every minute so it can honour per-site times precisely.
    """

    def __init__(self, site_manager, check_interval_minutes: int = DEFAULT_CHECK_INTERVAL_MINUTES) -> None:
        self.site_manager = site_manager
        # Legacy global interval kept for backward-compat; per-site overrides it
        self._global_interval_minutes = check_interval_minutes
        self.logger = setup_logger('safekeep.scheduler')
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._running = False
        # {site_id: datetime of last successful check}
        self._last_checked: dict[str, datetime.datetime] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
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
        self.logger.info('Scheduler started (per-site intervals, wake tick = 60 s).')

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._running = False
        self.logger.info('Scheduler stopped.')

    def is_running(self) -> bool:
        return self._running

    # ------------------------------------------------------------------
    # Background loop
    # ------------------------------------------------------------------

    def _run_loop(self) -> None:
        """Wake every 60 seconds and check any site whose interval has elapsed."""
        while not self._stop_event.is_set():
            try:
                self._check_due_sites()
            except Exception as exc:
                self.logger.error(f'Scheduler error: {exc}')
            # Fine-grained tick so we don't overshoot a site's interval
            self._stop_event.wait(timeout=60)

    def _site_interval_minutes(self, site: dict) -> int:
        """Return the effective check interval for *site* in minutes."""
        raw = site.get('check_interval_minutes', 0)
        try:
            minutes = int(raw)
        except (TypeError, ValueError):
            minutes = 0
        return minutes if minutes > 0 else DEFAULT_CHECK_INTERVAL_MINUTES

    def _check_due_sites(self) -> None:
        """Check each site that is due for a backup poll."""
        sites = self.site_manager.get_all_sites()
        now   = datetime.datetime.now()

        for site in sites:
            site_id  = site.get('id', '')
            interval = self._site_interval_minutes(site)
            last     = self._last_checked.get(site_id)

            if last is not None:
                elapsed_minutes = (now - last).total_seconds() / 60
                if elapsed_minutes < interval:
                    continue  # not due yet

            self.logger.debug(
                f'Checking site "{site.get("name", site_id)}" '
                f'(interval={interval} min, last={last.isoformat() if last else "never"}).'
            )
            try:
                fetched = self.site_manager.fetch_pending(site_id)
                self._last_checked[site_id] = now
                if fetched:
                    self.logger.info(
                        f'Fetched {fetched} new backup(s) for site "{site.get("name", site_id)}".'
                    )
            except Exception as exc:
                self.logger.error(
                    f'Failed to check site "{site.get("name", site_id)}": {exc}'
                )
                # Still record the attempt so we don't hammer a broken site
                self._last_checked[site_id] = now

    # ------------------------------------------------------------------
    # On-demand trigger
    # ------------------------------------------------------------------

    def trigger_now(self, site_id: str | None = None) -> None:
        """
        Run a check immediately in a daemon thread.

        If *site_id* is given, only that site is checked.
        Otherwise all sites are checked (and last-check timestamps reset).
        """
        if site_id:
            self._last_checked.pop(site_id, None)

        def _run():
            if site_id:
                sites = self.site_manager.get_all_sites()
                target = next((s for s in sites if s.get('id') == site_id), None)
                if target:
                    try:
                        fetched = self.site_manager.fetch_pending(site_id)
                        self._last_checked[site_id] = datetime.datetime.now()
                        if fetched:
                            self.logger.info(
                                f'Manual check: fetched {fetched} backup(s) for site "{target.get("name")}".'
                            )
                    except Exception as exc:
                        self.logger.error(f'Manual check failed for site {site_id}: {exc}')
            else:
                self._check_due_sites()

        threading.Thread(target=_run, daemon=True, name='SafeKeep-ManualTrigger').start()
        self.logger.info(f'Manual backup check triggered (site_id={site_id or "all"}).')

    def next_check_for(self, site_id: str, site: dict) -> datetime.datetime | None:
        """Return the datetime when *site* will next be checked (for UI display)."""
        last = self._last_checked.get(site_id)
        if last is None:
            return datetime.datetime.now()  # will be checked on the next tick
        interval = self._site_interval_minutes(site)
        return last + datetime.timedelta(minutes=interval)
