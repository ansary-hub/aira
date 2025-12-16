import logging

from app.services.ticker_extractor import extract_ticker
from app.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class TickerExtractorTool(BaseTool):
    """Tool to extract stock ticker symbols from text."""

    name: str = "ticker_extractor"
    description: str = (
        "Extracts stock ticker symbols from text. Use this tool when you encounter "
        "company names or need to identify ticker symbols from news articles or user queries. "
        "Returns the ticker symbol, company name, and confidence level."
    )

    async def execute(self, text: str) -> ToolResult:
        """Extract ticker from the given text.

        Args:
            text: Text containing company name or ticker reference

        Returns:
            ToolResult with extracted ticker information
        """
        try:
            logger.info(f"Extracting ticker from: {text[:100]}...")

            result = await extract_ticker(text)

            return ToolResult(
                success=True,
                data={
                    "ticker": result.ticker,
                    "company_name": result.company_name,
                    "confidence": result.confidence,
                    "method": result.method,
                },
            )

        except Exception as e:
            logger.error(f"Ticker extraction failed: {e}")
            return ToolResult(
                success=False,
                error=f"Failed to extract ticker: {str(e)}",
            )

    def _get_parameters_schema(self) -> dict:
        """Get the JSON schema for the tool's parameters."""
        return {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Text containing a company name or ticker reference to extract",
                },
            },
            "required": ["text"],
        }


# Singleton instance
ticker_extractor_tool = TickerExtractorTool()
