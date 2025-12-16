from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import async_session_maker
from app.database.models import Job
from app.schemas.responses import AnalysisReport, JobStatus, JobStatusData


class JobStore:
    """SQLite-based storage for analysis jobs."""

    async def create_job(self, job_id: str, query: str = "") -> JobStatusData:
        """Create a new pending job."""
        async with async_session_maker() as session:
            job = Job(
                id=job_id,
                status=JobStatus.PENDING,
                query=query,
                created_at=datetime.utcnow(),
            )
            session.add(job)
            await session.commit()
            return self._to_job_status_data(job)

    async def get_job(self, job_id: str) -> JobStatusData | None:
        """Get job by ID."""
        async with async_session_maker() as session:
            result = await session.execute(select(Job).where(Job.id == job_id))
            job = result.scalar_one_or_none()
            if job:
                return self._to_job_status_data(job)
            return None

    async def update_status(self, job_id: str, status: JobStatus) -> JobStatusData | None:
        """Update job status."""
        async with async_session_maker() as session:
            result = await session.execute(select(Job).where(Job.id == job_id))
            job = result.scalar_one_or_none()
            if job:
                job.status = status
                if status in (JobStatus.COMPLETED, JobStatus.FAILED):
                    job.completed_at = datetime.utcnow()
                await session.commit()
                return self._to_job_status_data(job)
            return None

    async def set_report(self, job_id: str, report: AnalysisReport) -> JobStatusData | None:
        """Set the analysis report for a completed job."""
        async with async_session_maker() as session:
            result = await session.execute(select(Job).where(Job.id == job_id))
            job = result.scalar_one_or_none()
            if job:
                job.company_ticker = report.company_ticker
                job.analysis_summary = report.analysis_summary
                job.sentiment_score = report.sentiment_score
                job.key_findings = report.key_findings
                job.tools_used = report.tools_used
                job.citation_sources = report.citation_sources
                job.status = JobStatus.COMPLETED
                job.completed_at = datetime.utcnow()
                await session.commit()
                return self._to_job_status_data(job)
            return None

    async def set_error(self, job_id: str, error: str) -> JobStatusData | None:
        """Set error message for a failed job."""
        async with async_session_maker() as session:
            result = await session.execute(select(Job).where(Job.id == job_id))
            job = result.scalar_one_or_none()
            if job:
                job.error = error
                job.status = JobStatus.FAILED
                job.completed_at = datetime.utcnow()
                await session.commit()
                return self._to_job_status_data(job)
            return None

    async def list_jobs(self) -> list[JobStatusData]:
        """List all jobs."""
        async with async_session_maker() as session:
            result = await session.execute(select(Job).order_by(Job.created_at.desc()))
            jobs = result.scalars().all()
            return [self._to_job_status_data(job) for job in jobs]

    async def delete_job(self, job_id: str) -> bool:
        """Delete a job."""
        async with async_session_maker() as session:
            result = await session.execute(select(Job).where(Job.id == job_id))
            job = result.scalar_one_or_none()
            if job:
                await session.delete(job)
                await session.commit()
                return True
            return False

    def _to_job_status_data(self, job: Job) -> JobStatusData:
        """Convert Job model to JobStatusData schema."""
        report = None
        if job.status == JobStatus.COMPLETED and job.company_ticker:
            report = AnalysisReport(
                company_ticker=job.company_ticker,
                analysis_summary=job.analysis_summary or "",
                sentiment_score=job.sentiment_score or 0.0,
                key_findings=job.key_findings or [],
                tools_used=job.tools_used or [],
                citation_sources=job.citation_sources or [],
            )

        return JobStatusData(
            job_id=job.id,
            status=job.status,
            created_at=job.created_at,
            completed_at=job.completed_at,
            report=report,
            error=job.error,
        )


# Global job store instance
job_store = JobStore()
