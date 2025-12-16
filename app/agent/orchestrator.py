import logging
from datetime import datetime

from app.agent.react import run_react_loop, ReActResult
from app.agent.reflection import reflect_on_analysis
from app.schemas.responses import AnalysisReport

logger = logging.getLogger(__name__)


async def run_agent(
    query: str,
    ticker: str,
    company_name: str | None = None,
    max_steps: int = 10,
    enable_reflection: bool = True,
    max_retries: int = 1,
) -> AnalysisReport:
    """Run the analysis agent on the given query.

    This orchestrator:
    1. Runs the ReAct loop to gather data and generate analysis
    2. Optionally runs reflection to assess quality
    3. Retries if quality is below threshold
    4. Returns a structured AnalysisReport

    Args:
        query: The user's original analysis query
        ticker: Extracted stock ticker symbol (e.g., "TSLA")
        company_name: Optional company name if identified
        max_steps: Maximum ReAct loop steps
        enable_reflection: Whether to run quality reflection
        max_retries: Maximum retries if quality is low

    Returns:
        AnalysisReport with the analysis results

    Raises:
        ValueError: If analysis fails after all retries
    """
    logger.info(f"Starting agent for {ticker} ({company_name or 'unknown'})")
    logger.info(f"Query: {query}")

    last_error: str | None = None
    react_result: ReActResult | None = None

    for attempt in range(max_retries + 1):
        if attempt > 0:
            logger.info(f"Retry attempt {attempt}/{max_retries}")

        # Run the ReAct loop
        react_result = await run_react_loop(
            ticker=ticker,
            query=query,
            company_name=company_name,
            max_steps=max_steps,
        )

        if not react_result.success:
            last_error = react_result.error or "ReAct loop failed"
            logger.warning(f"ReAct loop failed: {last_error}")
            continue

        if not react_result.final_answer:
            last_error = "No final answer generated"
            logger.warning(last_error)
            continue

        # Extract final answer components
        final = react_result.final_answer
        analysis_summary = final.get("analysis_summary", "")
        sentiment_score = float(final.get("sentiment_score", 0.0))
        key_findings = final.get("key_findings", [])

        # Validate sentiment score range
        sentiment_score = max(-1.0, min(1.0, sentiment_score))

        # Ensure key_findings is a list of strings
        if not isinstance(key_findings, list):
            key_findings = [str(key_findings)]
        key_findings = [str(f) for f in key_findings[:5]]  # Max 5 findings

        # Run reflection if enabled
        if enable_reflection:
            reflection = await reflect_on_analysis(
                ticker=ticker,
                analysis_summary=analysis_summary,
                sentiment_score=sentiment_score,
                key_findings=key_findings,
                tools_used=react_result.tools_used,
                sources_count=len(react_result.sources),
            )

            logger.info(f"Reflection quality score: {reflection.quality_score}")

            # Use refined summary if provided and quality is acceptable
            if reflection.refined_summary and reflection.is_acceptable:
                analysis_summary = reflection.refined_summary

            # If not acceptable and we have retries left, try again
            if not reflection.is_acceptable and attempt < max_retries:
                last_error = f"Quality score too low: {reflection.quality_score}"
                logger.warning(f"{last_error}. Improvements: {reflection.improvements}")
                continue

        # Build the final report
        report = AnalysisReport(
            company_ticker=ticker,
            analysis_summary=analysis_summary,
            sentiment_score=sentiment_score,
            key_findings=key_findings if key_findings else ["Analysis completed but no specific findings extracted"],
            tools_used=react_result.tools_used,
            citation_sources=react_result.sources,
            generated_at=datetime.utcnow(),
        )

        logger.info(f"Agent completed successfully for {ticker}")
        return report

    # All retries exhausted
    error_msg = f"Analysis failed after {max_retries + 1} attempts: {last_error}"
    logger.error(error_msg)
    raise ValueError(error_msg)


async def run_quick_analysis(
    ticker: str,
    company_name: str | None = None,
) -> AnalysisReport:
    """Run a quick analysis with fewer steps and no reflection.

    Useful for scheduled monitoring tasks where speed is important.

    Args:
        ticker: Stock ticker symbol
        company_name: Optional company name

    Returns:
        AnalysisReport with basic analysis
    """
    return await run_agent(
        query=f"Provide a brief market update for {ticker}",
        ticker=ticker,
        company_name=company_name,
        max_steps=6,
        enable_reflection=False,
        max_retries=0,
    )
