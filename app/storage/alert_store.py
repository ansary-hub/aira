from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import async_session_maker
from app.database.models import Alert
from app.schemas.responses import AlertData, AlertType, AnalysisReport


class AlertStore:
    """SQLite-based storage for alerts."""

    async def create_alert(
        self,
        alert_id: str,
        ticker: str,
        report: AnalysisReport,
        alert_type: AlertType = AlertType.PROACTIVE_ALERT,
    ) -> AlertData:
        """Create a new alert."""
        async with async_session_maker() as session:
            alert = Alert(
                id=alert_id,
                alert_type=alert_type,
                ticker=ticker.upper(),
                triggered_at=datetime.utcnow(),
                company_ticker=report.company_ticker,
                analysis_summary=report.analysis_summary,
                sentiment_score=report.sentiment_score,
                key_findings=report.key_findings,
                tools_used=report.tools_used,
                citation_sources=report.citation_sources,
            )
            session.add(alert)
            await session.commit()
            return self._to_alert_data(alert)

    async def get_alert(self, alert_id: str) -> AlertData | None:
        """Get alert by ID."""
        async with async_session_maker() as session:
            result = await session.execute(select(Alert).where(Alert.id == alert_id))
            alert = result.scalar_one_or_none()
            if alert:
                return self._to_alert_data(alert)
            return None

    async def list_alerts_by_ticker(self, ticker: str) -> list[AlertData]:
        """List all alerts for a specific ticker."""
        async with async_session_maker() as session:
            result = await session.execute(
                select(Alert)
                .where(Alert.ticker == ticker.upper())
                .order_by(Alert.triggered_at.desc())
            )
            alerts = result.scalars().all()
            return [self._to_alert_data(a) for a in alerts]

    async def list_alerts_by_type(self, alert_type: AlertType) -> list[AlertData]:
        """List all alerts of a specific type."""
        async with async_session_maker() as session:
            result = await session.execute(
                select(Alert)
                .where(Alert.alert_type == alert_type)
                .order_by(Alert.triggered_at.desc())
            )
            alerts = result.scalars().all()
            return [self._to_alert_data(a) for a in alerts]

    async def list_all_alerts(self) -> list[AlertData]:
        """List all alerts."""
        async with async_session_maker() as session:
            result = await session.execute(
                select(Alert).order_by(Alert.triggered_at.desc())
            )
            alerts = result.scalars().all()
            return [self._to_alert_data(a) for a in alerts]

    async def delete_alert(self, alert_id: str) -> bool:
        """Delete an alert."""
        async with async_session_maker() as session:
            result = await session.execute(select(Alert).where(Alert.id == alert_id))
            alert = result.scalar_one_or_none()
            if alert:
                await session.delete(alert)
                await session.commit()
                return True
            return False

    def _to_alert_data(self, alert: Alert) -> AlertData:
        """Convert Alert model to AlertData schema."""
        report = AnalysisReport(
            company_ticker=alert.company_ticker,
            analysis_summary=alert.analysis_summary,
            sentiment_score=alert.sentiment_score,
            key_findings=alert.key_findings,
            tools_used=alert.tools_used,
            citation_sources=alert.citation_sources,
        )

        return AlertData(
            alert_id=alert.id,
            alert_type=alert.alert_type,
            ticker=alert.ticker,
            report=report,
            triggered_at=alert.triggered_at,
        )


# Global alert store instance
alert_store = AlertStore()
