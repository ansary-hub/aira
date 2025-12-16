import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, HTTPException, status

from app.config import get_settings
from app.schemas.requests import (
    AnalyzeRequest,
    MonitorStartRequest,
    MonitorStopRequest,
)
from app.schemas.responses import (
    AlertData,
    AnalyzeJobData,
    ApiResponse,
    HealthData,
    JobStatus,
    JobStatusData,
    MonitorData,
)
from app.storage.alert_store import alert_store
from app.storage.job_store import job_store
from app.storage.monitor_state import monitor_state_store

router = APIRouter()
settings = get_settings()


async def run_analysis_task(job_id: str, query: str) -> None:
    """Background task to run the analysis agent.

    Steps:
    1. Extract ticker from query using hybrid approach (regex + Gemini LLM)
    2. Run the analysis agent with the extracted ticker
    3. Store the report or error
    """
    from app.agent.orchestrator import run_agent
    from app.services.ticker_extractor import extract_ticker

    await job_store.update_status(job_id, JobStatus.RUNNING)

    try:
        # Step 1: Extract ticker from query
        ticker_result = await extract_ticker(query)

        if not ticker_result.ticker:
            await job_store.set_error(
                job_id,
                "Could not identify a stock ticker from your query. "
                "Please include a ticker symbol (e.g., TSLA, AAPL) or company name.",
            )
            return

        # Step 2: Run the analysis agent with extracted ticker
        report = await run_agent(
            query=query,
            ticker=ticker_result.ticker,
            company_name=ticker_result.company_name,
        )
        await job_store.set_report(job_id, report)
    except Exception as e:
        await job_store.set_error(job_id, str(e))


@router.get("/health", response_model=ApiResponse[HealthData])
async def health_check() -> ApiResponse[HealthData]:
    """Health check endpoint."""
    data = HealthData(
        app_name=settings.app_name,
        version=settings.app_version,
        status="healthy",
    )
    return ApiResponse.success(data=data, message="Service is healthy")


@router.post("/analyze", response_model=ApiResponse[AnalyzeJobData], status_code=status.HTTP_202_ACCEPTED)
async def analyze(
    request: AnalyzeRequest,
    background_tasks: BackgroundTasks,
) -> ApiResponse[AnalyzeJobData]:
    """Submit an analysis request.

    Accepts a query like "Analyze the near-term prospects of Tesla, Inc. (TSLA)"
    and returns a job ID for tracking the analysis progress.
    """
    job_id = str(uuid.uuid4())

    await job_store.create_job(job_id, query=request.query)

    background_tasks.add_task(run_analysis_task, job_id, request.query)

    data = AnalyzeJobData(
        job_id=job_id,
        status=JobStatus.PENDING,
        status_url=f"{settings.api_prefix}/status/{job_id}",
    )

    return ApiResponse.success(
        data=data,
        message="Analysis job submitted successfully",
    )


@router.get("/status/{job_id}", response_model=ApiResponse[JobStatusData])
async def get_job_status(job_id: str) -> ApiResponse[JobStatusData]:
    """Get the status of an analysis job.

    Returns the current status and, if completed, the analysis report.
    """
    job = await job_store.get_job(job_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )

    message = f"Job status: {job.status.value}"
    if job.status == JobStatus.COMPLETED:
        message = "Analysis completed successfully"
    elif job.status == JobStatus.FAILED:
        message = f"Analysis failed: {job.error}"

    return ApiResponse.success(data=job, message=message)


@router.post("/monitor_start", response_model=ApiResponse[MonitorData])
async def start_monitor(request: MonitorStartRequest) -> ApiResponse[MonitorData]:
    """Start monitoring a stock ticker.

    Creates a scheduled task to monitor the ticker at the specified interval.
    The monitor will trigger analysis only if significant news is detected.
    """
    from app.scheduler.scheduler import scheduler

    ticker = request.ticker.upper()

    existing = await monitor_state_store.get_monitor(ticker)
    if existing and existing.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Monitor for {ticker} is already active",
        )

    # Use config default if interval_hours not provided
    interval_hours = request.interval_hours if request.interval_hours is not None else settings.monitor_interval_hours

    next_run = datetime.utcnow() + timedelta(hours=interval_hours)

    monitor = await monitor_state_store.create_monitor(
        ticker=ticker,
        interval_hours=interval_hours,
        next_run=next_run,
    )

    scheduler.add_monitor_job(ticker, interval_hours)

    data = MonitorData(
        ticker=ticker,
        interval_hours=interval_hours,
        next_run=next_run,
        is_active=True,
        seen_article_hashes=[],
    )

    return ApiResponse.success(
        data=data,
        message=f"Started monitoring {ticker} every {interval_hours} hours",
    )


@router.post("/monitor_stop", response_model=ApiResponse[MonitorData])
async def stop_monitor(request: MonitorStopRequest) -> ApiResponse[MonitorData]:
    """Stop monitoring a stock ticker."""
    from app.scheduler.scheduler import scheduler

    ticker = request.ticker.upper()

    monitor = await monitor_state_store.get_monitor(ticker)

    if not monitor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No monitor found for {ticker}",
        )

    if not monitor.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Monitor for {ticker} is already stopped",
        )

    await monitor_state_store.stop_monitor(ticker)

    scheduler.remove_monitor_job(ticker)

    data = MonitorData(
        ticker=ticker,
        interval_hours=monitor.interval_hours,
        next_run=None,
        is_active=False,
        seen_article_hashes=list(monitor.seen_article_hashes),
    )

    return ApiResponse.success(
        data=data,
        message=f"Stopped monitoring {ticker}",
    )


@router.get("/monitors", response_model=ApiResponse[list[MonitorData]])
async def list_monitors() -> ApiResponse[list[MonitorData]]:
    """List all active monitors."""
    monitors = await monitor_state_store.list_all_monitors()

    data = [
        MonitorData(
            ticker=m.ticker,
            interval_hours=m.interval_hours,
            next_run=m.next_run,
            is_active=m.is_active,
            seen_article_hashes=list(m.seen_article_hashes),
        )
        for m in monitors
    ]

    return ApiResponse.success(
        data=data,
        message=f"Found {len(data)} monitors",
    )


@router.get("/alerts", response_model=ApiResponse[list[AlertData]])
async def list_alerts(ticker: str | None = None) -> ApiResponse[list[AlertData]]:
    """List all alerts, optionally filtered by ticker."""
    if ticker:
        alerts = await alert_store.list_alerts_by_ticker(ticker.upper())
    else:
        alerts = await alert_store.list_all_alerts()

    return ApiResponse.success(
        data=alerts,
        message=f"Found {len(alerts)} alerts",
    )


@router.get("/alerts/{alert_id}", response_model=ApiResponse[AlertData])
async def get_alert(alert_id: str) -> ApiResponse[AlertData]:
    """Get a specific alert by ID."""
    alert = await alert_store.get_alert(alert_id)

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert {alert_id} not found",
        )

    return ApiResponse.success(data=alert, message="Alert retrieved successfully")


