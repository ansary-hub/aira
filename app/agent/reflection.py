import json
import logging
import re
from dataclasses import dataclass

from app.agent.prompts import REFLECTION_PROMPT
from app.services.llm import generate_content

logger = logging.getLogger(__name__)


@dataclass
class ReflectionResult:
    """Result from the reflection assessment."""

    quality_score: float
    is_acceptable: bool
    improvements: list[str]
    refined_summary: str | None = None


def _extract_json(text: str) -> dict | None:
    """Extract JSON from LLM response."""
    # Try to find JSON in code blocks first
    json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # Try to parse the entire text as JSON
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # Try to find any JSON object in the text
    json_match = re.search(r"\{.*\}", text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass

    return None


async def reflect_on_analysis(
    ticker: str,
    analysis_summary: str,
    sentiment_score: float,
    key_findings: list[str],
    tools_used: list[str],
    sources_count: int,
    min_quality_score: float = 0.7,
) -> ReflectionResult:
    """Reflect on the analysis quality and suggest improvements.

    Args:
        ticker: Stock ticker symbol
        analysis_summary: The generated analysis summary
        sentiment_score: The sentiment score from analysis
        key_findings: List of key findings
        tools_used: List of tools used in analysis
        sources_count: Number of data sources consulted
        min_quality_score: Minimum acceptable quality score

    Returns:
        ReflectionResult with quality assessment
    """
    logger.info(f"Reflecting on analysis for {ticker}")

    # Format key findings for the prompt
    findings_str = "\n".join(f"- {f}" for f in key_findings)
    tools_str = ", ".join(tools_used) if tools_used else "None"

    prompt = REFLECTION_PROMPT.format(
        ticker=ticker,
        analysis_summary=analysis_summary,
        sentiment_score=sentiment_score,
        key_findings=findings_str,
        tools_used=tools_str,
        sources_count=sources_count,
    )

    try:
        response = await generate_content(prompt, temperature=0.2)
        parsed = _extract_json(response)

        if parsed:
            quality_score = float(parsed.get("quality_score", 0.5))
            is_acceptable = parsed.get("is_acceptable", quality_score >= min_quality_score)
            improvements = parsed.get("improvements", [])
            refined_summary = parsed.get("refined_summary")

            return ReflectionResult(
                quality_score=quality_score,
                is_acceptable=is_acceptable,
                improvements=improvements if isinstance(improvements, list) else [],
                refined_summary=refined_summary,
            )

    except Exception as e:
        logger.error(f"Reflection failed: {e}")

    # Default result if reflection fails
    return ReflectionResult(
        quality_score=0.5,
        is_acceptable=True,  # Don't block on reflection failures
        improvements=["Reflection assessment could not be completed"],
    )
