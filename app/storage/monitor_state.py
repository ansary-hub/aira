from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import async_session_maker
from app.database.models import Monitor


class MonitorState(BaseModel):
    """State for a monitored ticker."""

    ticker: str
    interval_hours: float
    last_run: datetime | None = None
    next_run: datetime | None = None
    seen_article_hashes: set[str] = set()
    is_active: bool = True

    class Config:
        arbitrary_types_allowed = True


class MonitorStateStore:
    """SQLite-based storage for monitor states."""

    async def create_monitor(
        self, ticker: str, interval_hours: float, next_run: datetime
    ) -> MonitorState:
        """Create or update a monitor for a ticker."""
        async with async_session_maker() as session:
            # Check if monitor exists
            result = await session.execute(
                select(Monitor).where(Monitor.ticker == ticker.upper())
            )
            monitor = result.scalar_one_or_none()

            if monitor:
                # Update existing
                monitor.interval_hours = interval_hours
                monitor.next_run = next_run
                monitor.is_active = True
            else:
                # Create new
                monitor = Monitor(
                    ticker=ticker.upper(),
                    interval_hours=interval_hours,
                    next_run=next_run,
                    is_active=True,
                    seen_article_hashes=[],
                )
                session.add(monitor)

            await session.commit()
            return self._to_monitor_state(monitor)

    async def get_monitor(self, ticker: str) -> MonitorState | None:
        """Get monitor state by ticker."""
        async with async_session_maker() as session:
            result = await session.execute(
                select(Monitor).where(Monitor.ticker == ticker.upper())
            )
            monitor = result.scalar_one_or_none()
            if monitor:
                return self._to_monitor_state(monitor)
            return None

    async def update_last_run(
        self, ticker: str, last_run: datetime, next_run: datetime
    ) -> MonitorState | None:
        """Update last run time and set next run."""
        async with async_session_maker() as session:
            result = await session.execute(
                select(Monitor).where(Monitor.ticker == ticker.upper())
            )
            monitor = result.scalar_one_or_none()
            if monitor:
                monitor.last_run = last_run
                monitor.next_run = next_run
                await session.commit()
                return self._to_monitor_state(monitor)
            return None

    async def add_seen_articles(self, ticker: str, article_hashes: set[str]) -> None:
        """Add article hashes to seen set."""
        async with async_session_maker() as session:
            result = await session.execute(
                select(Monitor).where(Monitor.ticker == ticker.upper())
            )
            monitor = result.scalar_one_or_none()
            if monitor:
                existing = set(monitor.seen_article_hashes or [])
                existing.update(article_hashes)
                monitor.seen_article_hashes = list(existing)
                await session.commit()

    async def stop_monitor(self, ticker: str) -> MonitorState | None:
        """Stop monitoring a ticker."""
        async with async_session_maker() as session:
            result = await session.execute(
                select(Monitor).where(Monitor.ticker == ticker.upper())
            )
            monitor = result.scalar_one_or_none()
            if monitor:
                monitor.is_active = False
                monitor.next_run = None
                await session.commit()
                return self._to_monitor_state(monitor)
            return None

    async def delete_monitor(self, ticker: str) -> bool:
        """Delete a monitor."""
        async with async_session_maker() as session:
            result = await session.execute(
                select(Monitor).where(Monitor.ticker == ticker.upper())
            )
            monitor = result.scalar_one_or_none()
            if monitor:
                await session.delete(monitor)
                await session.commit()
                return True
            return False

    async def list_active_monitors(self) -> list[MonitorState]:
        """List all active monitors."""
        async with async_session_maker() as session:
            result = await session.execute(
                select(Monitor).where(Monitor.is_active == True)
            )
            monitors = result.scalars().all()
            return [self._to_monitor_state(m) for m in monitors]

    async def list_all_monitors(self) -> list[MonitorState]:
        """List all monitors."""
        async with async_session_maker() as session:
            result = await session.execute(select(Monitor))
            monitors = result.scalars().all()
            return [self._to_monitor_state(m) for m in monitors]

    def _to_monitor_state(self, monitor: Monitor) -> MonitorState:
        """Convert Monitor model to MonitorState schema."""
        return MonitorState(
            ticker=monitor.ticker,
            interval_hours=monitor.interval_hours,
            last_run=monitor.last_run,
            next_run=monitor.next_run,
            seen_article_hashes=set(monitor.seen_article_hashes or []),
            is_active=monitor.is_active,
        )


# Global monitor state store instance
monitor_state_store = MonitorStateStore()
