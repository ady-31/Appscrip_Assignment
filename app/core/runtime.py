from functools import lru_cache

from app.core.cache import RedisTTLCache, ResilientCache, TTLCache
from app.core.config import Settings, get_settings
from app.core.rate_limiter import (
    RedisSlidingWindowRateLimiter,
    ResilientRateLimiter,
    SlidingWindowRateLimiter,
)


class RuntimeBackends:
    """Centralized runtime dependency container for cache and rate limiting."""

    def __init__(self, settings: Settings) -> None:
        memory_cache = TTLCache(ttl_seconds=settings.cache_ttl_seconds)
        memory_limiter = SlidingWindowRateLimiter(max_requests=settings.rate_limit_per_minute)

        if settings.use_redis:
            redis_cache = RedisTTLCache(redis_url=settings.redis_url, ttl_seconds=settings.cache_ttl_seconds)
            redis_limiter = RedisSlidingWindowRateLimiter(
                redis_url=settings.redis_url,
                max_requests=settings.rate_limit_per_minute,
            )
            self.cache = ResilientCache(primary=redis_cache, fallback=memory_cache)
            self.rate_limiter = ResilientRateLimiter(primary=redis_limiter, fallback=memory_limiter)
        else:
            self.cache = memory_cache
            self.rate_limiter = memory_limiter


@lru_cache
def get_runtime() -> RuntimeBackends:
    settings = get_settings()
    return RuntimeBackends(settings)
