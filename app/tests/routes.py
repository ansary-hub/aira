from fastapi import APIRouter, HTTPException, status

from app.schemas.requests import (
    FinDataRequest,
    NewsSearchRequest,
    SentimentAnalyzeRequest,
    TickerExtractRequest,
)
from app.schemas.responses import (
    ApiResponse,
    ArticleSentimentData,
    CompanyInfoData,
    FinDataResponse,
    NewsArticleData,
    NewsSearchData,
    PriceHistoryData,
    QuarterlyFinancialsData,
    SentimentAnalysisData,
    StockQuoteData,
    TickerExtractData,
)

router = APIRouter()


@router.post("/ticker-extract", response_model=ApiResponse[TickerExtractData])
async def test_ticker_extract(request: TickerExtractRequest) -> ApiResponse[TickerExtractData]:
    """Test endpoint to extract ticker from a query.

    Uses hybrid approach: regex patterns first, then Gemini LLM fallback.
    """
    from app.services.ticker_extractor import extract_ticker

    result = await extract_ticker(request.query)

    data = TickerExtractData(
        ticker=result.ticker,
        company_name=result.company_name,
        confidence=result.confidence,
        method=result.method,
    )

    if result.ticker:
        message = f"Extracted ticker '{result.ticker}' using {result.method} method"
    else:
        message = "Could not extract a ticker from the query"

    return ApiResponse.success(data=data, message=message)


@router.post("/news-search", response_model=ApiResponse[NewsSearchData])
async def test_news_search(request: NewsSearchRequest) -> ApiResponse[NewsSearchData]:
    """Test endpoint to search news for a ticker.

    Fetches news articles from News API and saves them to the database.
    """
    from app.tools.news_retriever import news_retriever_tool

    ticker = request.ticker.upper()

    result = await news_retriever_tool.execute(
        query=ticker,
        ticker=ticker,
        days_back=request.days_back,
        max_articles=request.max_articles,
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.error or "Failed to fetch news",
        )

    # Transform to response schema
    articles = [
        NewsArticleData(
            title=a["title"],
            description=a.get("description"),
            content=a.get("content"),
            url=a["url"],
            source=a["source"],
            author=a.get("author"),
            published_at=a["published_at"],
        )
        for a in result.data.get("articles", [])
    ]

    data = NewsSearchData(
        ticker=ticker,
        total_results=result.data.get("total_results", 0),
        articles_returned=len(articles),
        articles_saved=result.data.get("articles_saved", 0),
        articles=articles,
    )

    return ApiResponse.success(
        data=data,
        message=f"Found {len(articles)} articles for {ticker}",
    )


@router.post("/sentiment-analyze", response_model=ApiResponse[SentimentAnalysisData])
async def test_sentiment_analyze(
    request: SentimentAnalyzeRequest,
) -> ApiResponse[SentimentAnalysisData]:
    """Test endpoint to analyze sentiment for a ticker.

    Fetches news articles and analyzes their sentiment using Gemini.
    """
    from app.tools.news_retriever import news_retriever_tool
    from app.tools.sentiment_analyzer import sentiment_analyzer_tool

    ticker = request.ticker.upper()

    # Step 1: Fetch news articles
    news_result = await news_retriever_tool.execute(
        query=ticker,
        ticker=ticker,
        days_back=request.days_back,
        max_articles=request.max_articles,
    )

    if not news_result.success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=news_result.error or "Failed to fetch news",
        )

    articles = news_result.data.get("articles", [])
    if not articles:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No news articles found for {ticker}",
        )

    # Step 2: Analyze sentiment
    sentiment_result = await sentiment_analyzer_tool.execute(
        ticker=ticker,
        articles=articles,
    )

    if not sentiment_result.success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=sentiment_result.error or "Failed to analyze sentiment",
        )

    # Transform to response schema
    article_sentiments = [
        ArticleSentimentData(
            title=s["title"],
            sentiment=s["sentiment"],
            score=s["score"],
            reasoning=s["reasoning"],
        )
        for s in sentiment_result.data.get("article_sentiments", [])
    ]

    data = SentimentAnalysisData(
        ticker=ticker,
        articles_analyzed=sentiment_result.data.get("articles_analyzed", 0),
        overall_sentiment=sentiment_result.data.get("overall_sentiment", "neutral"),
        overall_score=sentiment_result.data.get("overall_score", 0.0),
        summary=sentiment_result.data.get("summary", ""),
        article_sentiments=article_sentiments,
    )

    return ApiResponse.success(
        data=data,
        message=f"Analyzed sentiment for {len(article_sentiments)} articles about {ticker}",
    )


@router.post("/findata", response_model=ApiResponse[FinDataResponse])
async def test_findata(request: FinDataRequest) -> ApiResponse[FinDataResponse]:
    """Test endpoint to fetch financial data for a ticker.

    Fetches stock quote, company info, historical price data, and quarterly financials using Yahoo Finance.
    """
    from app.tools.finData_fetcher import findata_fetcher_tool

    ticker = request.ticker.upper()

    result = await findata_fetcher_tool.execute(
        ticker=ticker,
        period=request.period,
        include_history=request.include_history,
        include_financials=request.include_financials,
    )

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.error or "Failed to fetch financial data",
        )

    # Transform to response schema
    quote_data = result.data.get("quote")
    quote = None
    if quote_data:
        quote = StockQuoteData(
            symbol=quote_data["symbol"],
            current_price=quote_data.get("current_price"),
            previous_close=quote_data.get("previous_close"),
            open_price=quote_data.get("open_price"),
            day_high=quote_data.get("day_high"),
            day_low=quote_data.get("day_low"),
            volume=quote_data.get("volume"),
            market_cap=quote_data.get("market_cap"),
            pe_ratio=quote_data.get("pe_ratio"),
            fifty_two_week_high=quote_data.get("fifty_two_week_high"),
            fifty_two_week_low=quote_data.get("fifty_two_week_low"),
        )

    company_data = result.data.get("company_info")
    company_info = None
    if company_data:
        company_info = CompanyInfoData(
            symbol=company_data["symbol"],
            name=company_data.get("name"),
            sector=company_data.get("sector"),
            industry=company_data.get("industry"),
            description=company_data.get("description"),
            website=company_data.get("website"),
            employees=company_data.get("employees"),
            country=company_data.get("country"),
        )

    price_history = [
        PriceHistoryData(
            date=p["date"],
            open=p["open"],
            high=p["high"],
            low=p["low"],
            close=p["close"],
            volume=p["volume"],
        )
        for p in result.data.get("price_history", [])
    ]

    quarterly_financials = [
        QuarterlyFinancialsData(
            date=q["date"],
            revenue=q.get("revenue"),
            earnings=q.get("earnings"),
            eps=q.get("eps"),
        )
        for q in result.data.get("quarterly_financials", [])
    ]

    data = FinDataResponse(
        symbol=ticker,
        quote=quote,
        company_info=company_info,
        price_history=price_history,
        quarterly_financials=quarterly_financials,
        price_change_percent=result.data.get("price_change_percent"),
    )

    return ApiResponse.success(
        data=data,
        message=f"Fetched financial data for {ticker}",
    )
