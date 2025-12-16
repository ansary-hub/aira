from datetime import datetime, timedelta, timezone

import httpx
from pydantic import BaseModel

from app.config import get_settings
from app.tools.base import BaseTool, ToolResult


class NewsArticleSchema(BaseModel):
    """Represents a single news article."""

    title: str
    description: str | None
    url: str
    source: str
    author: str | None
    published_at: str
    content: str | None
    image_url: str | None = None


class NewsRetrieverResult(BaseModel):
    """Result from the news retriever tool."""

    query: str
    ticker: str
    total_results: int
    articles: list[NewsArticleSchema]
    articles_saved: int
    from_date: str
    to_date: str


class NewsRetrieverTool(BaseTool):
    """Tool to fetch recent news articles about a company or topic."""

    name: str = "news_retriever"
    description: str = (
        "Fetches the most recent and relevant news articles about a company or topic. "
        "Use this tool to gather current news for sentiment analysis and market research. "
        "Returns up to 5 recent articles with title, description, source, and URL. "
        "Articles are automatically saved to the database for future reference."
    )

    def __init__(self):
        self.settings = get_settings()
        self.base_url = self.settings.news_api_base_url

    async def execute(
        self,
        query: str,
        ticker: str | None = None,
        days_back: int | None = None,
        max_articles: int | None = None,
    ) -> ToolResult:
        """
        Fetch news articles for a given query and save to database.

        Args:
            query: Search query (e.g., "TSLA" or "Tesla")
            ticker: Stock ticker to associate with articles (defaults to query)
            days_back: Number of days to look back (uses config default if not specified)
            max_articles: Maximum number of articles to return (uses config default if not specified)

        Returns:
            ToolResult with NewsRetrieverResult data or error
        """
        # Use config defaults if not specified
        days_back = days_back if days_back is not None else self.settings.analysis_days_back
        max_articles = max_articles if max_articles is not None else self.settings.analysis_max_articles
        if not self.settings.news_api_key:
            return ToolResult(
                success=False,
                error="News API key not configured. Set NEWS_API_KEY in environment.",
            )

        # Use query as ticker if not specified
        ticker = ticker or query.upper()

        # Calculate date range
        to_date = datetime.now(timezone.utc)
        from_date = to_date - timedelta(days=days_back)

        # Build request URL
        params = {
            "q": query,
            "from": from_date.strftime("%Y-%m-%d"),
            "to": to_date.strftime("%Y-%m-%d"),
            "sortBy": "publishedAt",
            "pageSize": max_articles,
            "apiKey": self.settings.news_api_key,
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.base_url}/everything",
                    params=params,
                )
                response.raise_for_status()
                data = response.json()

            if data.get("status") != "ok":
                return ToolResult(
                    success=False,
                    error=f"News API error: {data.get('message', 'Unknown error')}",
                )

            # Parse articles
            articles = []
            articles_for_db = []

            for article in data.get("articles", [])[:max_articles]:
                article_schema = NewsArticleSchema(
                    title=article.get("title", ""),
                    description=article.get("description"),
                    url=article.get("url", ""),
                    source=article.get("source", {}).get("name", "Unknown"),
                    author=article.get("author"),
                    published_at=article.get("publishedAt", ""),
                    content=article.get("content"),
                    image_url=article.get("urlToImage"),
                )
                articles.append(article_schema)

                # Prepare for database storage
                articles_for_db.append({
                    "title": article_schema.title,
                    "description": article_schema.description,
                    "url": article_schema.url,
                    "source": article_schema.source,
                    "author": article_schema.author,
                    "published_at": article_schema.published_at,
                    "content": article_schema.content,
                    "image_url": article_schema.image_url,
                })

            # Save articles to database
            articles_saved = 0
            if articles_for_db:
                from app.storage.news_store import news_store
                saved_ids = await news_store.save_articles(ticker, articles_for_db)
                articles_saved = len(saved_ids)

            result = NewsRetrieverResult(
                query=query,
                ticker=ticker,
                total_results=data.get("totalResults", 0),
                articles=articles,
                articles_saved=articles_saved,
                from_date=from_date.strftime("%Y-%m-%d"),
                to_date=to_date.strftime("%Y-%m-%d"),
            )

            return ToolResult(success=True, data=result.model_dump())

        except httpx.HTTPStatusError as e:
            return ToolResult(
                success=False,
                error=f"HTTP error fetching news: {e.response.status_code} - {e.response.text}",
            )
        except httpx.RequestError as e:
            return ToolResult(
                success=False,
                error=f"Request error fetching news: {str(e)}",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Unexpected error fetching news: {str(e)}",
            )

    def _get_parameters_schema(self) -> dict:
        """Get the JSON schema for the tool's parameters."""
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query for news articles (e.g., 'TSLA', 'Tesla', 'Apple Inc')",
                },
                "ticker": {
                    "type": "string",
                    "description": "Stock ticker to associate with articles (defaults to query if not provided)",
                },
                "days_back": {
                    "type": "integer",
                    "description": "Number of days to look back for articles (uses ANALYSIS_DAYS_BACK from config if not specified)",
                },
                "max_articles": {
                    "type": "integer",
                    "description": "Maximum number of articles to return (uses ANALYSIS_MAX_ARTICLES from config if not specified)",
                },
            },
            "required": ["query"],
        }


# Singleton instance
news_retriever_tool = NewsRetrieverTool()
