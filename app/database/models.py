from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, DateTime, Enum, Float, String, Text, Boolean, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.database.connection import Base
from app.schemas.responses import AlertType, JobStatus


class Job(Base):
    """Analysis job model."""

    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    status: Mapped[str] = mapped_column(
        Enum(JobStatus), default=JobStatus.PENDING
    )
    query: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Report fields (stored as JSON for flexibility)
    company_ticker: Mapped[Optional[str]] = mapped_column(
        String(10), nullable=True
    )
    analysis_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sentiment_score: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )
    key_findings: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    tools_used: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    citation_sources: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)


class Monitor(Base):
    """Stock monitoring model."""

    __tablename__ = "monitors"

    ticker: Mapped[str] = mapped_column(String(10), primary_key=True)
    interval_hours: Mapped[float] = mapped_column(Float, default=24.0)
    last_run: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    next_run: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )
    seen_article_hashes: Mapped[Optional[list]] = mapped_column(
        JSON, default=list
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )


class Alert(Base):
    """Proactive alert model."""

    __tablename__ = "alerts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    alert_type: Mapped[str] = mapped_column(
        Enum(AlertType), default=AlertType.PROACTIVE_ALERT
    )
    ticker: Mapped[str] = mapped_column(String(10), nullable=False)
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )

    # Report fields
    company_ticker: Mapped[str] = mapped_column(String(10), nullable=False)
    analysis_summary: Mapped[str] = mapped_column(Text, nullable=False)
    sentiment_score: Mapped[float] = mapped_column(Float, nullable=False)
    key_findings: Mapped[list] = mapped_column(JSON, nullable=False)
    tools_used: Mapped[list] = mapped_column(JSON, nullable=False)
    citation_sources: Mapped[list] = mapped_column(JSON, nullable=False)


class NewsArticle(Base):
    """News article model for storing fetched articles."""

    __tablename__ = "news_articles"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # Hash of URL
    ticker: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    author: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )

    __table_args__ = (
        Index("ix_news_articles_ticker_published", "ticker", "published_at"),
    )
