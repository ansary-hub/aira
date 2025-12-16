from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    """Request body for /analyze endpoint."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Analysis query, e.g., 'Analyze the near-term prospects of Tesla, Inc. (TSLA)'",
        examples=["Analyze the near-term prospects of Tesla, Inc. (TSLA)"],
    )


class MonitorStartRequest(BaseModel):
    """Request body for /monitor_start endpoint."""

    ticker: str = Field(
        ...,
        min_length=1,
        max_length=10,
        description="Stock ticker symbol to monitor, e.g., 'GOOGL'",
        examples=["GOOGL", "TSLA", "AAPL"],
    )
    interval_hours: float | None = Field(
        default=None,
        ge=0.01,
        le=168.0,
        description="Monitoring interval in hours (0.01-168, e.g., 0.1 = 6 minutes). If not set, uses MONITOR_INTERVAL_HOURS from config.",
    )


class MonitorStopRequest(BaseModel):
    """Request body for /monitor_stop endpoint."""

    ticker: str = Field(
        ...,
        min_length=1,
        max_length=10,
        description="Stock ticker symbol to stop monitoring",
    )


class TickerExtractRequest(BaseModel):
    """Request body for /test/ticker-extract endpoint."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Query to extract ticker from",
        examples=["Analyze Tesla stock", "What's happening with AAPL?", "Microsoft earnings report"],
    )


class NewsSearchRequest(BaseModel):
    """Request body for /test/news-search endpoint."""

    ticker: str = Field(
        ...,
        min_length=1,
        max_length=10,
        description="Stock ticker to search news for",
        examples=["TSLA", "AAPL", "GOOGL"],
    )
    days_back: int = Field(
        default=7,
        ge=1,
        le=30,
        description="Number of days to look back for news (1-30)",
    )
    max_articles: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Maximum number of articles to return (1-10)",
    )


class SentimentAnalyzeRequest(BaseModel):
    """Request body for /test/sentiment-analyze endpoint."""

    ticker: str = Field(
        ...,
        min_length=1,
        max_length=10,
        description="Stock ticker to analyze sentiment for",
        examples=["TSLA", "AAPL", "GOOGL"],
    )
    days_back: int = Field(
        default=7,
        ge=1,
        le=30,
        description="Number of days to look back for news (1-30)",
    )
    max_articles: int = Field(
        default=5,
        ge=1,
        le=10,
        description="Maximum number of articles to analyze (1-10)",
    )


class FinDataRequest(BaseModel):
    """Request body for /test/findata endpoint."""

    ticker: str = Field(
        ...,
        min_length=1,
        max_length=10,
        description="Stock ticker to fetch financial data for",
        examples=["TSLA", "AAPL", "GOOGL"],
    )
    period: str = Field(
        default="1mo",
        description="Historical data period",
        examples=["1d", "5d", "1mo", "3mo", "6mo", "1y"],
    )
    include_history: bool = Field(
        default=True,
        description="Whether to include price history",
    )
    include_financials: bool = Field(
        default=True,
        description="Whether to include quarterly financial data",
    )
