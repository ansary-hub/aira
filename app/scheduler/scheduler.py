from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger


class MonitorScheduler:
    """Wrapper for APScheduler to manage monitoring jobs."""

    def __init__(self) -> None:
        self._scheduler = AsyncIOScheduler()
        self._running = False

    def start(self) -> None:
        """Start the scheduler."""
        if not self._running:
            self._scheduler.start()
            self._running = True

    def shutdown(self) -> None:
        """Shutdown the scheduler."""
        if self._running:
            self._scheduler.shutdown(wait=False)
            self._running = False

    def add_monitor_job(self, ticker: str, interval_hours: float) -> None:
        """Add a monitoring job for a ticker."""
        from app.scheduler.tasks import monitoring_task

        job_id = f"monitor_{ticker}"

        # Remove existing job if any
        self.remove_monitor_job(ticker)

        # Add new job
        self._scheduler.add_job(
            monitoring_task,
            trigger=IntervalTrigger(hours=interval_hours),
            id=job_id,
            args=[ticker],
            replace_existing=True,
        )

    def remove_monitor_job(self, ticker: str) -> None:
        """Remove a monitoring job for a ticker."""
        job_id = f"monitor_{ticker}"
        try:
            self._scheduler.remove_job(job_id)
        except Exception:
            pass  # Job might not exist

    def get_job(self, ticker: str):
        """Get a monitoring job by ticker."""
        job_id = f"monitor_{ticker}"
        return self._scheduler.get_job(job_id)

    @property
    def is_running(self) -> bool:
        """Check if scheduler is running."""
        return self._running


# Global scheduler instance
scheduler = MonitorScheduler()
