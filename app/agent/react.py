import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from app.agent.prompts import SYSTEM_PROMPT, REACT_PROMPT_TEMPLATE
from app.config import get_settings
from app.services.llm import generate_content
from app.tools.registry import get_tool_registry, register_all_tools

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class ReActStep:
    """A single step in the ReAct loop."""

    step_number: int
    thought: str
    action: str
    action_input: dict[str, Any]
    observation: str | None = None
    error: str | None = None


@dataclass
class ReActResult:
    """Result from the ReAct loop execution."""

    success: bool
    steps: list[ReActStep] = field(default_factory=list)
    final_answer: dict[str, Any] | None = None
    tools_used: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    error: str | None = None


def _extract_json(text: str) -> dict | None:
    """Extract JSON from LLM response, handling markdown code blocks."""
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


def _format_history(steps: list[ReActStep]) -> str:
    """Format step history for the prompt."""
    if not steps:
        return "No previous steps yet."

    history_parts = []
    for step in steps:
        parts = [
            f"Step {step.step_number}:",
            f"  Thought: {step.thought}",
            f"  Action: {step.action}",
            f"  Action Input: {json.dumps(step.action_input, indent=2)}",
        ]
        if step.observation:
            # Truncate long observations
            obs = step.observation
            if len(obs) > 2000:
                obs = obs[:2000] + "... [truncated]"
            parts.append(f"  Observation: {obs}")
        if step.error:
            parts.append(f"  Error: {step.error}")
        history_parts.append("\n".join(parts))

    return "\n\n".join(history_parts)


def _format_observation(result_data: Any) -> str:
    """Format tool result data as observation string."""
    if isinstance(result_data, dict):
        # Create a readable summary
        return json.dumps(result_data, indent=2, default=str)
    return str(result_data)


async def run_react_loop(
    ticker: str,
    query: str,
    company_name: str | None = None,
    max_steps: int = 10,
) -> ReActResult:
    """Run the ReAct reasoning loop for stock analysis.

    Args:
        ticker: Stock ticker symbol (e.g., 'TSLA')
        query: User's original analysis query
        company_name: Optional company name
        max_steps: Maximum number of reasoning steps

    Returns:
        ReActResult with all steps, final answer, and metadata
    """
    # Ensure tools are registered
    register_all_tools()
    registry = get_tool_registry()

    company = company_name or ticker
    steps: list[ReActStep] = []
    tools_used: list[str] = []
    sources: list[str] = []

    logger.info(f"Starting ReAct loop for {ticker} ({company})")

    for step_num in range(1, max_steps + 1):
        logger.info(f"ReAct step {step_num}/{max_steps}")

        # Build the prompt
        react_section = REACT_PROMPT_TEMPLATE.format(
            ticker=ticker,
            company_name=company,
            query=query,
            tools_description=registry.get_tools_description(),
            history=_format_history(steps),
        )
        prompt = f"{SYSTEM_PROMPT}\n\n{react_section}"

        # Get LLM response using the ReAct model
        try:
            response = await generate_content(
                prompt,
                model=settings.gemini_react_model,
                temperature=0.3,
            )
            logger.debug(f"LLM response: {response[:500]}...")
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return ReActResult(
                success=False,
                steps=steps,
                tools_used=tools_used,
                sources=sources,
                error=f"LLM call failed: {str(e)}",
            )

        # Parse the response
        parsed = _extract_json(response)
        if not parsed:
            logger.warning(f"Failed to parse JSON from LLM response: {response[:200]}")
            # Try one more time with a reminder
            continue

        thought = parsed.get("thought", "")
        action = parsed.get("action", "")
        action_input = parsed.get("action_input", {})

        step = ReActStep(
            step_number=step_num,
            thought=thought,
            action=action,
            action_input=action_input,
        )

        # Check if this is the final answer
        if action == "final_answer":
            logger.info("ReAct loop completed with final_answer")
            steps.append(step)
            return ReActResult(
                success=True,
                steps=steps,
                final_answer=action_input,
                tools_used=list(set(tools_used)),
                sources=sources,
            )

        # Execute the tool
        if action not in registry:
            step.error = f"Unknown tool: {action}. Available tools: {registry.list_tools()}"
            step.observation = step.error
            steps.append(step)
            continue

        try:
            logger.info(f"Executing tool: {action} with {action_input}")
            result = await registry.execute(action, **action_input)

            if result.success:
                step.observation = _format_observation(result.data)

                # Track tool usage with method for ticker_extractor
                if action == "ticker_extractor" and result.data:
                    method = result.data.get("method", "unknown")
                    tools_used.append(f"ticker_extractor:{method}")
                else:
                    tools_used.append(action)

                # Extract sources from results
                if action == "news_retriever" and result.data:
                    articles = result.data.get("articles", [])
                    for article in articles:
                        if url := article.get("url"):
                            sources.append(url)
            else:
                step.error = result.error
                step.observation = f"Tool error: {result.error}"

        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            step.error = str(e)
            step.observation = f"Tool execution failed: {str(e)}"

        steps.append(step)

    # Max steps reached without final answer
    logger.warning(f"ReAct loop reached max steps ({max_steps}) without final answer")
    return ReActResult(
        success=False,
        steps=steps,
        tools_used=list(set(tools_used)),
        sources=sources,
        error=f"Analysis incomplete after {max_steps} steps",
    )
