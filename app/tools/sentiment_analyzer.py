import logging

from pydantic import BaseModel

from app.config import get_settings
from app.services.llm import generate_content
from app.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)
settings = get_settings()


class ArticleSentiment(BaseModel):
    """Sentiment analysis for a single article."""

    title: str
    sentiment: str  # "positive", "negative", "neutral"
    score: float  # -1.0 to 1.0
    reasoning: str  # Brief explanation


class SentimentAnalysisResult(BaseModel):
    """Result from sentiment analysis."""

    ticker: str
    articles_analyzed: int
    overall_sentiment: str  # "positive", "negative", "neutral", "mixed"
    overall_score: float  # -1.0 to 1.0 (average)
    article_sentiments: list[ArticleSentiment]
    summary: str  # Overall sentiment summary


class SentimentAnalyzerTool(BaseTool):
    """Tool to analyze sentiment of news articles using Google Gemini."""

    name: str = "sentiment_analyzer"
    description: str = (
        "Analyzes the sentiment of news articles related to a stock. "
        "Returns individual article sentiments and an overall sentiment score. "
        "Use this tool after fetching news to understand market sentiment."
    )

    async def execute(
        self,
        ticker: str,
        articles: list[dict],
    ) -> ToolResult:
        """
        Analyze sentiment of news articles.

        Args:
            ticker: Stock ticker symbol
            articles: List of article dicts with 'title', 'description', 'content' keys

        Returns:
            ToolResult with SentimentAnalysisResult data or error
        """
        if not articles:
            return ToolResult(
                success=False,
                error="No articles provided for sentiment analysis",
            )

        if not settings.google_api_key:
            return ToolResult(
                success=False,
                error="Google API key not configured. Set GOOGLE_API_KEY in environment.",
            )

        try:
            # Analyze each article
            article_sentiments: list[ArticleSentiment] = []

            for article in articles:
                sentiment = await self._analyze_article(article)
                if sentiment:
                    article_sentiments.append(sentiment)

            if not article_sentiments:
                return ToolResult(
                    success=False,
                    error="Failed to analyze any articles",
                )

            # Calculate overall sentiment
            scores = [s.score for s in article_sentiments]
            overall_score = sum(scores) / len(scores)

            # Determine overall sentiment label
            if overall_score >= 0.3:
                overall_sentiment = "positive"
            elif overall_score <= -0.3:
                overall_sentiment = "negative"
            elif max(scores) - min(scores) > 0.5:
                overall_sentiment = "mixed"
            else:
                overall_sentiment = "neutral"

            # Generate summary
            summary = await self._generate_summary(
                ticker, article_sentiments, overall_sentiment, overall_score
            )

            result = SentimentAnalysisResult(
                ticker=ticker,
                articles_analyzed=len(article_sentiments),
                overall_sentiment=overall_sentiment,
                overall_score=round(overall_score, 2),
                article_sentiments=article_sentiments,
                summary=summary,
            )

            return ToolResult(success=True, data=result.model_dump())

        except Exception as e:
            logger.error(f"Sentiment analysis failed: {e}")
            return ToolResult(
                success=False,
                error=f"Sentiment analysis failed: {str(e)}",
            )

    async def _analyze_article(self, article: dict) -> ArticleSentiment | None:
        """Analyze sentiment of a single article."""
        title = article.get("title", "")
        description = article.get("description", "")
        content = article.get("content", "")

        # Combine available text
        text = f"Title: {title}\n"
        if description:
            text += f"Description: {description}\n"
        if content:
            text += f"Content: {content[:500]}"  # Limit content length

        prompt = f"""Analyze the sentiment of this news article about a stock.

{text}

Respond in EXACTLY this format (no other text):
SENTIMENT: <positive/negative/neutral>
SCORE: <number from -1.0 to 1.0>
REASONING: <one sentence explanation>

Example:
SENTIMENT: positive
SCORE: 0.7
REASONING: The article highlights strong quarterly earnings and optimistic guidance.
"""

        try:
            response = await generate_content(
                prompt,
                model=settings.gemini_sentiment_model,
                temperature=0.1,
            )

            # Parse response
            sentiment = "neutral"
            score = 0.0
            reasoning = ""

            for line in response.strip().split("\n"):
                line = line.strip()
                if line.startswith("SENTIMENT:"):
                    sent = line.replace("SENTIMENT:", "").strip().lower()
                    if sent in ("positive", "negative", "neutral"):
                        sentiment = sent
                elif line.startswith("SCORE:"):
                    try:
                        score = float(line.replace("SCORE:", "").strip())
                        score = max(-1.0, min(1.0, score))  # Clamp to range
                    except ValueError:
                        pass
                elif line.startswith("REASONING:"):
                    reasoning = line.replace("REASONING:", "").strip()

            return ArticleSentiment(
                title=title[:100] if title else "Untitled",
                sentiment=sentiment,
                score=round(score, 2),
                reasoning=reasoning or "No reasoning provided",
            )

        except Exception as e:
            logger.warning(f"Failed to analyze article '{title[:50]}': {e}")
            return None

    async def _generate_summary(
        self,
        ticker: str,
        sentiments: list[ArticleSentiment],
        overall_sentiment: str,
        overall_score: float,
    ) -> str:
        """Generate an overall sentiment summary."""
        # Build context from article sentiments
        sentiment_context = "\n".join(
            f"- {s.title[:50]}... ({s.sentiment}, {s.score}): {s.reasoning}"
            for s in sentiments[:5]  # Limit to 5 articles
        )

        prompt = f"""Based on the following news sentiment analysis for {ticker}, write a brief 2-3 sentence summary of the overall market sentiment.

Overall sentiment: {overall_sentiment} (score: {overall_score})

Article sentiments:
{sentiment_context}

Write a concise summary for investors (2-3 sentences only):
"""

        try:
            summary = await generate_content(
                prompt,
                model=settings.gemini_sentiment_model,
                temperature=0.3,
            )
            return summary.strip()
        except Exception as e:
            logger.warning(f"Failed to generate summary: {e}")
            return f"Overall sentiment for {ticker} is {overall_sentiment} with a score of {overall_score}."

    def _get_parameters_schema(self) -> dict:
        """Get the JSON schema for the tool's parameters."""
        return {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Stock ticker symbol (e.g., 'TSLA', 'AAPL')",
                },
                "articles": {
                    "type": "array",
                    "description": "List of articles to analyze",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "description": {"type": "string"},
                            "content": {"type": "string"},
                        },
                        "required": ["title"],
                    },
                },
            },
            "required": ["ticker", "articles"],
        }


# Singleton instance
sentiment_analyzer_tool = SentimentAnalyzerTool()
