import logging
import re

from pydantic import BaseModel

from app.config import get_settings
from app.services.llm import generate_content

logger = logging.getLogger(__name__)
settings = get_settings()


class TickerExtractionResult(BaseModel):
    """Result of ticker extraction."""

    ticker: str | None
    company_name: str | None
    confidence: str  # "high", "medium", "low"
    method: str  # "regex" or "llm"


# Common patterns for ticker symbols
TICKER_PATTERNS = [
    r'\(([A-Z]{1,5})\)',  # (TSLA), (AAPL)
    r'\$([A-Z]{1,5})\b',  # $TSLA, $AAPL
    r'\b([A-Z]{2,5})\b(?=\s+stock|\s+shares|\s+price)',  # TSLA stock, AAPL shares
]

# Common company name to ticker mapping
COMPANY_TICKER_MAP = {
    "tesla": "TSLA",
    "apple": "AAPL",
    "google": "GOOGL",
    "alphabet": "GOOGL",
    "microsoft": "MSFT",
    "amazon": "AMZN",
    "meta": "META",
    "facebook": "META",
    "nvidia": "NVDA",
    "netflix": "NFLX",
    "amd": "AMD",
    "intel": "INTC",
    "ibm": "IBM",
    "oracle": "ORCL",
    "salesforce": "CRM",
    "adobe": "ADBE",
    "paypal": "PYPL",
    "shopify": "SHOP",
    "spotify": "SPOT",
    "uber": "UBER",
    "lyft": "LYFT",
    "airbnb": "ABNB",
    "coinbase": "COIN",
    "robinhood": "HOOD",
    "palantir": "PLTR",
    "snowflake": "SNOW",
    "zoom": "ZM",
    "twitter": "X",
    "disney": "DIS",
    "boeing": "BA",
    "walmart": "WMT",
    "target": "TGT",
    "costco": "COST",
    "starbucks": "SBUX",
    "mcdonald": "MCD",
    "coca-cola": "KO",
    "coca cola": "KO",
    "pepsi": "PEP",
    "pepsico": "PEP",
    "johnson & johnson": "JNJ",
    "j&j": "JNJ",
    "pfizer": "PFE",
    "moderna": "MRNA",
    "berkshire": "BRK.B",
    "jpmorgan": "JPM",
    "jp morgan": "JPM",
    "goldman sachs": "GS",
    "morgan stanley": "MS",
    "bank of america": "BAC",
    "wells fargo": "WFC",
    "citigroup": "C",
    "visa": "V",
    "mastercard": "MA",
    "american express": "AXP",
    "amex": "AXP",
}


def extract_ticker_regex(query: str) -> TickerExtractionResult | None:
    """
    Try to extract ticker using regex patterns.

    Args:
        query: User's analysis query

    Returns:
        TickerExtractionResult if found, None otherwise
    """
    # Try regex patterns first
    for pattern in TICKER_PATTERNS:
        match = re.search(pattern, query)
        if match:
            ticker = match.group(1).upper()
            return TickerExtractionResult(
                ticker=ticker,
                company_name=None,
                confidence="high",
                method="regex",
            )

    # Try company name mapping
    query_lower = query.lower()
    for company, ticker in COMPANY_TICKER_MAP.items():
        if company in query_lower:
            return TickerExtractionResult(
                ticker=ticker,
                company_name=company.title(),
                confidence="high",
                method="regex",
            )

    return None


async def extract_ticker_llm(query: str) -> TickerExtractionResult:
    """
    Extract ticker using Google Gemini LLM.

    Args:
        query: User's analysis query

    Returns:
        TickerExtractionResult with extracted ticker
    """
    prompt = f"""Extract the stock ticker symbol from the following query.

Query: "{query}"

Instructions:
1. Identify the company or stock being mentioned
2. Return ONLY the stock ticker symbol (e.g., TSLA, AAPL, GOOGL)
3. If multiple companies are mentioned, return the PRIMARY one being analyzed
4. If no specific company/stock can be identified, return "UNKNOWN"

Response format (respond with ONLY this, no other text):
TICKER: <ticker_symbol>
COMPANY: <company_name>
CONFIDENCE: <high/medium/low>

Example response:
TICKER: TSLA
COMPANY: Tesla, Inc.
CONFIDENCE: high
"""

    try:
        response = await generate_content(prompt, temperature=0.1)

        # Parse response
        ticker = None
        company_name = None
        confidence = "medium"

        for line in response.strip().split("\n"):
            line = line.strip()
            if line.startswith("TICKER:"):
                ticker = line.replace("TICKER:", "").strip().upper()
                if ticker == "UNKNOWN":
                    ticker = None
            elif line.startswith("COMPANY:"):
                company_name = line.replace("COMPANY:", "").strip()
            elif line.startswith("CONFIDENCE:"):
                conf = line.replace("CONFIDENCE:", "").strip().lower()
                if conf in ("high", "medium", "low"):
                    confidence = conf

        return TickerExtractionResult(
            ticker=ticker,
            company_name=company_name,
            confidence=confidence,
            method="llm",
        )

    except Exception as e:
        # Log the error and return unknown
        logger.error(f"LLM ticker extraction failed: {e}")
        return TickerExtractionResult(
            ticker=None,
            company_name=None,
            confidence="low",
            method="llm",
        )


async def extract_ticker(query: str) -> TickerExtractionResult:
    """
    Extract ticker from query using hybrid approach.

    1. First tries fast regex patterns
    2. Falls back to LLM for complex queries

    Args:
        query: User's analysis query

    Returns:
        TickerExtractionResult with extracted ticker info
    """
    # Try regex first (fast path)
    result = extract_ticker_regex(query)
    if result and result.ticker:
        return result

    # Fall back to LLM
    return await extract_ticker_llm(query)
