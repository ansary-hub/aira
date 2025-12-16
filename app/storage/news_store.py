import hashlib
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert

from app.database.connection import async_session_maker
from app.database.models import NewsArticle


class NewsStore:
    """SQLite-based storage for news articles."""

    @staticmethod
    def generate_article_id(url: str) -> str:
        """Generate a unique ID for an article based on its URL."""
        return hashlib.sha256(url.encode()).hexdigest()[:64]

    async def save_article(
        self,
        ticker: str,
        title: str,
        url: str,
        source: str,
        description: str | None = None,
        author: str | None = None,
        published_at: datetime | None = None,
        content: str | None = None,
        image_url: str | None = None,
    ) -> NewsArticle:
        """Save a single news article (upsert - insert or update)."""
        article_id = self.generate_article_id(url)

        async with async_session_maker() as session:
            # Use SQLite upsert
            stmt = insert(NewsArticle).values(
                id=article_id,
                ticker=ticker.upper(),
                title=title,
                description=description,
                url=url,
                source=source,
                author=author,
                published_at=published_at,
                content=content,
                image_url=image_url,
                fetched_at=datetime.now(timezone.utc),
            )

            # On conflict, update the fetched_at timestamp
            stmt = stmt.on_conflict_do_update(
                index_elements=["id"],
                set_={
                    "fetched_at": datetime.now(timezone.utc),
                    "content": content,  # Update content if it changed
                },
            )

            await session.execute(stmt)
            await session.commit()

            # Fetch and return the article
            result = await session.execute(
                select(NewsArticle).where(NewsArticle.id == article_id)
            )
            return result.scalar_one()

    async def save_articles(
        self,
        ticker: str,
        articles: list[dict],
    ) -> list[str]:
        """
        Save multiple news articles.

        Args:
            ticker: Stock ticker the articles are related to
            articles: List of article dicts with keys:
                title, url, source, description, author, published_at, content, image_url

        Returns:
            List of article IDs that were saved
        """
        saved_ids = []

        async with async_session_maker() as session:
            for article in articles:
                article_id = self.generate_article_id(article.get("url", ""))

                # Parse published_at if it's a string
                published_at = article.get("published_at")
                if isinstance(published_at, str):
                    try:
                        published_at = datetime.fromisoformat(
                            published_at.replace("Z", "+00:00")
                        )
                    except ValueError:
                        published_at = None

                stmt = insert(NewsArticle).values(
                    id=article_id,
                    ticker=ticker.upper(),
                    title=article.get("title", ""),
                    description=article.get("description"),
                    url=article.get("url", ""),
                    source=article.get("source", "Unknown"),
                    author=article.get("author"),
                    published_at=published_at,
                    content=article.get("content"),
                    image_url=article.get("image_url"),
                    fetched_at=datetime.now(timezone.utc),
                )

                stmt = stmt.on_conflict_do_update(
                    index_elements=["id"],
                    set_={"fetched_at": datetime.now(timezone.utc)},
                )

                await session.execute(stmt)
                saved_ids.append(article_id)

            await session.commit()

        return saved_ids

    async def get_article(self, article_id: str) -> NewsArticle | None:
        """Get an article by ID."""
        async with async_session_maker() as session:
            result = await session.execute(
                select(NewsArticle).where(NewsArticle.id == article_id)
            )
            return result.scalar_one_or_none()

    async def get_articles_by_ticker(
        self,
        ticker: str,
        limit: int = 10,
        days_back: int | None = None,
    ) -> list[NewsArticle]:
        """Get articles for a ticker, optionally filtered by date."""
        async with async_session_maker() as session:
            query = select(NewsArticle).where(
                NewsArticle.ticker == ticker.upper()
            )

            if days_back:
                from datetime import timedelta
                cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
                query = query.where(NewsArticle.published_at >= cutoff)

            query = query.order_by(NewsArticle.published_at.desc()).limit(limit)

            result = await session.execute(query)
            return list(result.scalars().all())

    async def get_article_ids_by_ticker(self, ticker: str) -> set[str]:
        """Get all article IDs for a ticker (for deduplication)."""
        async with async_session_maker() as session:
            result = await session.execute(
                select(NewsArticle.id).where(NewsArticle.ticker == ticker.upper())
            )
            return {row[0] for row in result.fetchall()}

    async def delete_old_articles(self, days: int = 30) -> int:
        """Delete articles older than specified days. Returns count deleted."""
        from datetime import timedelta
        from sqlalchemy import delete

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        async with async_session_maker() as session:
            result = await session.execute(
                delete(NewsArticle).where(NewsArticle.fetched_at < cutoff)
            )
            await session.commit()
            return result.rowcount


# Global news store instance
news_store = NewsStore()
