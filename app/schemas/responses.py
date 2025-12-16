from datetime import datetime
from enum import Enum
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field


T = TypeVar("T")


class ResponseStatus(str, Enum):
    """API response status."""

    SUCCESS = "success"
    ERROR = "error"


class ApiResponse(BaseModel, Generic[T]):
    """Unified API response wrapper."""

    status: ResponseStatus = Field(description="Response status")
    message: str = Field(description="Human-readable message")
    data: T | None = Field(default=None, description="Response payload")
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    @classmethod
    def success(cls, data: T, message: str = "Request successful") -> "ApiResponse[T]":
        """Create a success response."""
        return cls(status=ResponseStatus.SUCCESS, message=message, data=data)

    @classmethod
    def error(cls, message: str, data: T | None = None) -> "ApiResponse[T]":
        """Create an error response."""
        return cls(status=ResponseStatus.ERROR, message=message, data=data)


class JobStatus(str, Enum):
    """Analysis job status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AnalyzeJobData(BaseModel):
    """Data returned when an analysis job is created."""

    job_id: str = Field(description="Unique job identifier")
    status: JobStatus = Field(description="Current job status")
    status_url: str = Field(description="URL to check job status")


class AnalysisReport(BaseModel):
    """The structured investment analysis report."""

    company_ticker: str = Field(description="Stock ticker symbol")
    analysis_summary: str = Field(description="Concise paragraph synthesis of all findings")
    sentiment_score: float = Field(
        ge=-1.0,
        le=1.0,
        description="Derived sentiment score between -1.0 (negative) and 1.0 (positive)",
    )
    key_findings: list[str] = Field(
        description="Top 3 actionable insights",
        min_length=1,
        max_length=5,
    )
    tools_used: list[str] = Field(description="List of tools used during analysis")
    citation_sources: list[str] = Field(description="List of source URLs")
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class JobStatusData(BaseModel):
    """Data returned when checking job status."""

    job_id: str = Field(description="Unique job identifier")
    status: JobStatus = Field(description="Current job status")
    created_at: datetime = Field(description="Job creation timestamp")
    completed_at: datetime | None = Field(default=None, description="Job completion timestamp")
    report: AnalysisReport | None = Field(default=None, description="Analysis report if completed")
    error: str | None = Field(default=None, description="Error message if failed")


class MonitorData(BaseModel):
    """Data returned for monitor operations."""

    ticker: str = Field(description="Stock ticker being monitored")
    interval_hours: float = Field(description="Monitoring interval in hours")
    next_run: datetime | None = Field(default=None, description="Next scheduled run time")
    is_active: bool = Field(description="Whether monitoring is active")
    seen_article_hashes: list[str] = Field(default=[], description="Hashes of articles already processed")


class AlertType(str, Enum):
    """Type of alert."""

    PROACTIVE_ALERT = "PROACTIVE_ALERT"
    USER_REQUESTED = "USER_REQUESTED"


class AlertData(BaseModel):
    """Data for proactive alerts."""

    alert_id: str = Field(description="Unique alert identifier")
    alert_type: AlertType = Field(description="Type of alert")
    ticker: str = Field(description="Stock ticker")
    report: AnalysisReport = Field(description="Analysis report")
    triggered_at: datetime = Field(description="When the alert was triggered")


class HealthData(BaseModel):
    """Health check response data."""

    app_name: str
    version: str
    status: str = "healthy"


class TickerExtractData(BaseModel):
    """Data returned from ticker extraction test."""

    ticker: str | None = Field(description="Extracted ticker symbol")
    company_name: str | None = Field(description="Identified company name")
    confidence: str = Field(description="Confidence level: high, medium, or low")
    method: str = Field(description="Extraction method: regex or llm")


class NewsArticleData(BaseModel):
    """News article data."""

    title: str = Field(description="Article title")
    description: str | None = Field(description="Article description")
    content: str | None = Field(description="Article content")
    url: str = Field(description="Article URL")
    source: str = Field(description="News source name")
    author: str | None = Field(description="Article author")
    published_at: str = Field(description="Publication date")


class NewsSearchData(BaseModel):
    """Data returned from news search."""

    ticker: str = Field(description="Stock ticker searched")
    total_results: int = Field(description="Total results available")
    articles_returned: int = Field(description="Number of articles returned")
    articles_saved: int = Field(description="Number of articles saved to database")
    articles: list[NewsArticleData] = Field(description="List of news articles")


class ArticleSentimentData(BaseModel):
    """Sentiment data for a single article."""

    title: str = Field(description="Article title")
    sentiment: str = Field(description="Sentiment: positive, negative, or neutral")
    score: float = Field(description="Sentiment score from -1.0 to 1.0")
    reasoning: str = Field(description="Brief explanation of the sentiment")


class SentimentAnalysisData(BaseModel):
    """Data returned from sentiment analysis."""

    ticker: str = Field(description="Stock ticker analyzed")
    articles_analyzed: int = Field(description="Number of articles analyzed")
    overall_sentiment: str = Field(description="Overall sentiment: positive, negative, neutral, or mixed")
    overall_score: float = Field(description="Overall sentiment score from -1.0 to 1.0")
    summary: str = Field(description="Summary of the sentiment analysis")
    article_sentiments: list[ArticleSentimentData] = Field(description="Individual article sentiments")


class StockQuoteData(BaseModel):
    """Stock quote data."""

    symbol: str = Field(description="Stock ticker symbol")
    current_price: float | None = Field(description="Current stock price")
    previous_close: float | None = Field(description="Previous closing price")
    open_price: float | None = Field(description="Opening price")
    day_high: float | None = Field(description="Day's high price")
    day_low: float | None = Field(description="Day's low price")
    volume: int | None = Field(description="Trading volume")
    market_cap: int | None = Field(description="Market capitalization")
    pe_ratio: float | None = Field(description="Price-to-earnings ratio")
    fifty_two_week_high: float | None = Field(description="52-week high")
    fifty_two_week_low: float | None = Field(description="52-week low")


class CompanyInfoData(BaseModel):
    """Company information data."""

    symbol: str = Field(description="Stock ticker symbol")
    name: str | None = Field(description="Company name")
    sector: str | None = Field(description="Business sector")
    industry: str | None = Field(description="Industry")
    description: str | None = Field(description="Company description")
    website: str | None = Field(description="Company website")
    employees: int | None = Field(description="Number of employees")
    country: str | None = Field(description="Country")


class PriceHistoryData(BaseModel):
    """Historical price data point."""

    date: str = Field(description="Date")
    open: float = Field(description="Opening price")
    high: float = Field(description="High price")
    low: float = Field(description="Low price")
    close: float = Field(description="Closing price")
    volume: int = Field(description="Trading volume")


class QuarterlyFinancialsData(BaseModel):
    """Quarterly financial data."""

    date: str = Field(description="Quarter end date")
    revenue: float | None = Field(description="Quarterly revenue")
    earnings: float | None = Field(description="Quarterly earnings")
    eps: float | None = Field(description="Earnings per share")


class FinDataResponse(BaseModel):
    """Data returned from financial data fetch."""

    symbol: str = Field(description="Stock ticker symbol")
    quote: StockQuoteData | None = Field(description="Current stock quote")
    company_info: CompanyInfoData | None = Field(description="Company information")
    price_history: list[PriceHistoryData] = Field(description="Historical price data")
    quarterly_financials: list[QuarterlyFinancialsData] = Field(description="Quarterly financial data")
    price_change_percent: float | None = Field(description="Price change percentage from previous close")
