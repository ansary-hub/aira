from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.tests.routes import router as tests_router
from app.config import get_settings
from app.schemas.responses import ApiResponse

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manage application lifespan - startup and shutdown events."""
    # Startup
    from app.database.connection import init_db, close_db
    from app.scheduler.scheduler import scheduler
    from app.scheduler.tasks import check_and_restore_monitors
    from app.tools.registry import register_all_tools

    # Initialize database
    await init_db()
    print("Database initialized")

    # Register all tools
    register_all_tools()
    print("Tools registered")

    # Start scheduler
    scheduler.start()
    print("Scheduler started")

    # Restore active monitors from database
    await check_and_restore_monitors()

    print(f"{settings.app_name} v{settings.app_version} started")

    yield

    # Shutdown
    scheduler.shutdown()
    await close_db()
    print(f"{settings.app_name} shutdown complete")


app = FastAPI(
    title=settings.app_name,
    description="Autonomous Investment Research Agent - An AI-powered financial analysis service",
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler to maintain consistent response format."""
    return JSONResponse(
        status_code=500,
        content=ApiResponse.error(
            message=f"Internal server error: {str(exc)}"
        ).model_dump(mode="json"),
    )


# Include API routes
app.include_router(router, prefix=settings.api_prefix)

# Include test routes
app.include_router(tests_router, prefix="/tests", tags=["tests"])


@app.get("/")
async def root() -> dict:
    """Root endpoint with API information."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "health": f"{settings.api_prefix}/health",
    }
