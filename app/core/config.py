from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    app_name: str = "Trade Opportunity Intelligence API"
    log_level: str = "INFO"
    cache_ttl_seconds: int = 600
    rate_limit_per_minute: int = 5
    use_redis: bool = False
    redis_url: str = "redis://localhost:6379/0"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-flash"
    news_api_key: str = ""
    request_timeout_seconds: int = 15
    enable_tracing: bool = False
    otel_service_name: str = "trade-intel-api"
    otel_exporter_otlp_endpoint: str = "http://localhost:4318"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    """Return a memoized settings instance for cheap repeated access."""
    return Settings()
