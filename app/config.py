from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_name: str = "A.I.R.A."
    app_version: str = "1.0.0"
    debug: bool = False

    # API
    api_prefix: str = "/api/v1"

    # Google Gemini Configuration
    google_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    gemini_sentiment_model: str = "gemini-2.0-flash"  # Model for sentiment analysis
    gemini_react_model: str = "gemini-2.5-pro"  # Model for ReAct reasoning loop

    # News API Configuration
    news_api_key: str = ""
    news_api_base_url: str = "https://newsapi.org/v2"

    # Monitoring Configuration (used as defaults if not specified in request)
    monitor_interval_hours: float = 24.0
    monitor_min_articles: int = 5

    # Analysis Configuration (used as defaults for /analyze endpoint)
    analysis_days_back: int = 7
    analysis_max_articles: int = 5

    # Reflection Configuration
    reflection_enabled: bool = True  # Enable/disable reflection layer
    reflection_min_quality_score: float = 0.7  # Minimum quality score to accept analysis

    # Database Configuration
    database_url: str = "sqlite+aiosqlite:///./aira.db"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
