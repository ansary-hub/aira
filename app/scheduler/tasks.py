import hashlib
import logging
import uuid
from datetime import datetime, timedelta

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _hash_article(title: str, url: str) -> str:
    """Create a hash for an article to detect duplicates."""
    content = f"{title}:{url}"
    return hashlib.md5(content.encode()).hexdigest()


async def monitoring_task(ticker: str) -> None:
    """Background task that monitors a ticker for significant news.

    This task:
    1. Checks for new articles since last run
    2. If significant news (>= min_articles), triggers analysis
    3. Stores result as PROACTIVE_ALERT
    """
    from app.agent.orchestrator import run_quick_analysis
    from app.schemas.responses import AlertType
    from app.storage.alert_store import alert_store
    from app.storage.monitor_state import monitor_state_store
    from app.tools.news_retriever import news_retriever_tool

    logger.info(f"[Monitor] Starting monitoring task for {ticker}")

    # Get monitor state
    monitor = await monitor_state_store.get_monitor(ticker)
    if not monitor or not monitor.is_active:
        logger.info(f"[Monitor] Monitor for {ticker} is not active, skipping")
        return

    # Update last run time
    now = datetime.utcnow()
    next_run = now + timedelta(hours=monitor.interval_hours)
    await monitor_state_store.update_last_run(ticker, now, next_run)

    try:
        # Step 1: Fetch recent news
        logger.info(f"[Monitor] Fetching news for {ticker}")
        news_result = await news_retriever_tool.execute(
            query=ticker,
            ticker=ticker,
            days_back=1,  # Look back 1 day for monitoring
            max_articles=10,
        )

        if not news_result.success:
            logger.warning(f"[Monitor] Failed to fetch news for {ticker}: {news_result.error}")
            return

        articles = news_result.data.get("articles", [])
        if not articles:
            logger.info(f"[Monitor] No new articles found for {ticker}")
            return

        # Step 2: Filter out already seen articles
        new_articles = []
        new_hashes = set()

        for article in articles:
            article_hash = _hash_article(article.get("title", ""), article.get("url", ""))
            if article_hash not in monitor.seen_article_hashes:
                new_articles.append(article)
                new_hashes.add(article_hash)

        logger.info(f"[Monitor] Found {len(new_articles)} new articles for {ticker}")

        # Update seen articles
        if new_hashes:
            await monitor_state_store.add_seen_articles(ticker, new_hashes)

        # Step 3: Check if we have significant news
        if len(new_articles) < settings.monitor_min_articles:
            logger.info(
                f"[Monitor] Not enough new articles for {ticker} "
                f"({len(new_articles)} < {settings.monitor_min_articles}), skipping analysis"
            )
            return

        # Step 4: Run quick analysis
        logger.info(f"[Monitor] Significant news detected for {ticker}, triggering analysis")

        try:
            report = await run_quick_analysis(ticker=ticker)

            # Step 5: Create proactive alert
            alert_id = str(uuid.uuid4())
            await alert_store.create_alert(
                alert_id=alert_id,
                ticker=ticker,
                report=report,
                alert_type=AlertType.PROACTIVE_ALERT,
            )

            logger.info(f"[Monitor] Created proactive alert {alert_id} for {ticker}")

        except Exception as e:
            logger.error(f"[Monitor] Analysis failed for {ticker}: {e}")

    except Exception as e:
        logger.error(f"[Monitor] Monitoring task failed for {ticker}: {e}")


async def check_and_restore_monitors() -> None:
    """Check for active monitors and restore their scheduled jobs.

    Called on application startup to restore monitors that were active
    before the application was restarted.
    """
    from app.scheduler.scheduler import scheduler
    from app.storage.monitor_state import monitor_state_store

    logger.info("[Monitor] Checking for active monitors to restore...")

    try:
        active_monitors = await monitor_state_store.list_active_monitors()

        for monitor in active_monitors:
            logger.info(f"[Monitor] Restoring monitor for {monitor.ticker}")
            scheduler.add_monitor_job(monitor.ticker, monitor.interval_hours)

        logger.info(f"[Monitor] Restored {len(active_monitors)} monitors")

    except Exception as e:
        logger.error(f"[Monitor] Failed to restore monitors: {e}")
