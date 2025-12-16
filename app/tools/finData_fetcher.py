import asyncio
import logging
from datetime import datetime, timedelta

import yfinance as yf
from pydantic import BaseModel

from app.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class StockQuote(BaseModel):
    """Current stock quote data."""

    symbol: str
    current_price: float | None
    previous_close: float | None
    open_price: float | None
    day_high: float | None
    day_low: float | None
    volume: int | None
    market_cap: int | None
    pe_ratio: float | None
    dividend_yield: float | None
    fifty_two_week_high: float | None
    fifty_two_week_low: float | None


class PriceHistory(BaseModel):
    """Historical price data point."""

    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int


class CompanyInfo(BaseModel):
    """Company information."""

    symbol: str
    name: str | None
    sector: str | None
    industry: str | None
    description: str | None
    website: str | None
    employees: int | None
    country: str | None
    currency: str | None


class QuarterlyFinancials(BaseModel):
    """Quarterly financial data."""

    date: str
    revenue: float | None
    earnings: float | None
    eps: float | None  # Earnings per share


class FinancialDataResult(BaseModel):
    """Result from financial data fetcher."""

    symbol: str
    quote: StockQuote | None
    company_info: CompanyInfo | None
    price_history: list[PriceHistory]
    quarterly_financials: list[QuarterlyFinancials]
    price_change_percent: float | None
    fetched_at: str


class FinDataFetcherTool(BaseTool):
    """Tool to fetch financial data using Yahoo Finance."""

    name: str = "findata_fetcher"
    description: str = (
        "Fetches financial data for a stock including current price, company info, "
        "and historical price data. Use this tool to get quantitative data about a stock "
        "for investment analysis."
    )

    async def execute(
        self,
        ticker: str,
        period: str = "1mo",
        include_history: bool = True,
        include_financials: bool = True,
    ) -> ToolResult:
        """
        Fetch financial data for a stock.

        Args:
            ticker: Stock ticker symbol (e.g., 'TSLA', 'AAPL')
            period: Historical data period ('1d', '5d', '1mo', '3mo', '6mo', '1y', '2y', '5y', 'max')
            include_history: Whether to include price history
            include_financials: Whether to include quarterly financial data

        Returns:
            ToolResult with FinancialDataResult data or error
        """
        try:
            # Run yfinance calls in thread pool (it's synchronous)
            result = await asyncio.to_thread(
                self._fetch_data, ticker.upper(), period, include_history, include_financials
            )
            return result
        except Exception as e:
            logger.error(f"Financial data fetch failed for {ticker}: {e}")
            return ToolResult(
                success=False,
                error=f"Failed to fetch financial data: {str(e)}",
            )

    def _fetch_data(
        self, ticker: str, period: str, include_history: bool, include_financials: bool
    ) -> ToolResult:
        """Synchronous data fetch (runs in thread pool)."""
        try:
            stock = yf.Ticker(ticker)

            # Get stock info
            info = stock.info

            if not info or info.get("regularMarketPrice") is None:
                # Try to check if ticker exists
                if not info.get("symbol"):
                    return ToolResult(
                        success=False,
                        error=f"Ticker '{ticker}' not found or invalid",
                    )

            # Build quote data
            quote = StockQuote(
                symbol=ticker,
                current_price=info.get("regularMarketPrice") or info.get("currentPrice"),
                previous_close=info.get("regularMarketPreviousClose") or info.get("previousClose"),
                open_price=info.get("regularMarketOpen") or info.get("open"),
                day_high=info.get("regularMarketDayHigh") or info.get("dayHigh"),
                day_low=info.get("regularMarketDayLow") or info.get("dayLow"),
                volume=info.get("regularMarketVolume") or info.get("volume"),
                market_cap=info.get("marketCap"),
                pe_ratio=info.get("trailingPE"),
                dividend_yield=info.get("dividendYield"),
                fifty_two_week_high=info.get("fiftyTwoWeekHigh"),
                fifty_two_week_low=info.get("fiftyTwoWeekLow"),
            )

            # Build company info
            company_info = CompanyInfo(
                symbol=ticker,
                name=info.get("longName") or info.get("shortName"),
                sector=info.get("sector"),
                industry=info.get("industry"),
                description=info.get("longBusinessSummary"),
                website=info.get("website"),
                employees=info.get("fullTimeEmployees"),
                country=info.get("country"),
                currency=info.get("currency"),
            )

            # Get price history if requested
            price_history: list[PriceHistory] = []
            if include_history:
                hist = stock.history(period=period)
                for date, row in hist.iterrows():
                    price_history.append(
                        PriceHistory(
                            date=date.strftime("%Y-%m-%d"),
                            open=round(row["Open"], 2),
                            high=round(row["High"], 2),
                            low=round(row["Low"], 2),
                            close=round(row["Close"], 2),
                            volume=int(row["Volume"]),
                        )
                    )

            # Get quarterly financials if requested
            quarterly_financials: list[QuarterlyFinancials] = []
            if include_financials:
                try:
                    # yfinance DataFrames have metrics as rows (index) and dates as columns
                    quarterly_income = stock.quarterly_income_stmt

                    if quarterly_income is not None and not quarterly_income.empty:
                        # Columns are dates, iterate over them
                        for date_col in quarterly_income.columns:
                            date_str = date_col.strftime("%Y-%m-%d") if hasattr(date_col, "strftime") else str(date_col)

                            # Get values from rows (index contains metric names)
                            revenue = None
                            earnings = None
                            eps = None

                            # Revenue - try different row names
                            for rev_key in ["Total Revenue", "Revenue", "Operating Revenue"]:
                                if rev_key in quarterly_income.index:
                                    val = quarterly_income.loc[rev_key, date_col]
                                    if val is not None and str(val) != "nan":
                                        revenue = float(val)
                                        break

                            # Net Income / Earnings
                            for earn_key in ["Net Income", "Net Income Common Stockholders", "Normalized Income"]:
                                if earn_key in quarterly_income.index:
                                    val = quarterly_income.loc[earn_key, date_col]
                                    if val is not None and str(val) != "nan":
                                        earnings = float(val)
                                        break

                            # EPS
                            for eps_key in ["Basic EPS", "Diluted EPS"]:
                                if eps_key in quarterly_income.index:
                                    val = quarterly_income.loc[eps_key, date_col]
                                    if val is not None and str(val) != "nan":
                                        eps = float(val)
                                        break

                            quarterly_financials.append(
                                QuarterlyFinancials(
                                    date=date_str,
                                    revenue=revenue,
                                    earnings=earnings,
                                    eps=eps,
                                )
                            )

                except Exception as e:
                    logger.warning(f"Could not fetch quarterly financials for {ticker}: {e}")

            # Calculate price change percentage
            price_change_percent = None
            if quote.current_price and quote.previous_close:
                price_change_percent = round(
                    ((quote.current_price - quote.previous_close) / quote.previous_close) * 100,
                    2,
                )

            result = FinancialDataResult(
                symbol=ticker,
                quote=quote,
                company_info=company_info,
                price_history=price_history,
                quarterly_financials=quarterly_financials,
                price_change_percent=price_change_percent,
                fetched_at=datetime.utcnow().isoformat(),
            )

            return ToolResult(success=True, data=result.model_dump())

        except Exception as e:
            logger.error(f"Error fetching data for {ticker}: {e}")
            return ToolResult(
                success=False,
                error=f"Error fetching data for {ticker}: {str(e)}",
            )

    def _get_parameters_schema(self) -> dict:
        """Get the JSON schema for the tool's parameters."""
        return {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Stock ticker symbol (e.g., 'TSLA', 'AAPL', 'GOOGL')",
                },
                "period": {
                    "type": "string",
                    "description": "Historical data period",
                    "enum": ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "max"],
                    "default": "1mo",
                },
                "include_history": {
                    "type": "boolean",
                    "description": "Whether to include price history (default: true)",
                    "default": True,
                },
                "include_financials": {
                    "type": "boolean",
                    "description": "Whether to include quarterly financial data (default: true)",
                    "default": True,
                },
            },
            "required": ["ticker"],
        }


# Singleton instance
findata_fetcher_tool = FinDataFetcherTool()
