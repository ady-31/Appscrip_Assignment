import time
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from dataclasses import dataclass

from redis import asyncio as redis


@dataclass
class RateLimitResult:
    allowed: bool
    remaining: int
    retry_after_seconds: int


class RateLimiterBackend(ABC):
    @abstractmethod
    async def check(self, key: str) -> RateLimitResult:
        raise NotImplementedError


class SlidingWindowRateLimiter(RateLimiterBackend):
    """In-memory rate limiter keyed by API key or session identifier."""

    def __init__(self, max_requests: int, window_seconds: int = 60) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, deque[float]] = defaultdict(deque)

    async def check(self, key: str) -> RateLimitResult:
        now = time.time()
        request_times = self._requests[key]

        while request_times and now - request_times[0] > self.window_seconds:
            request_times.popleft()

        if len(request_times) >= self.max_requests:
            retry_after = int(self.window_seconds - (now - request_times[0]))
            return RateLimitResult(allowed=False, remaining=0, retry_after_seconds=max(1, retry_after))

        request_times.append(now)
        remaining = self.max_requests - len(request_times)
        return RateLimitResult(allowed=True, remaining=remaining, retry_after_seconds=0)


class RedisSlidingWindowRateLimiter(RateLimiterBackend):
    """Redis sorted-set based sliding-window rate limiter."""

    def __init__(self, redis_url: str, max_requests: int, window_seconds: int = 60) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._client = redis.from_url(redis_url, decode_responses=True)

    async def check(self, key: str) -> RateLimitResult:
        now = time.time()
        bucket = f"rate:{key}"
        window_start = now - self.window_seconds

        async with self._client.pipeline(transaction=True) as pipe:
            pipe.zremrangebyscore(bucket, 0, window_start)
            pipe.zcard(bucket)
            _, count = await pipe.execute()

        current = int(count)
        if current >= self.max_requests:
            oldest = await self._client.zrange(bucket, 0, 0, withscores=True)
            retry_after = 1
            if oldest:
                oldest_ts = oldest[0][1]
                retry_after = max(1, int(self.window_seconds - (now - oldest_ts)))
            return RateLimitResult(allowed=False, remaining=0, retry_after_seconds=retry_after)

        member = f"{now}:{current}"
        async with self._client.pipeline(transaction=True) as pipe:
            pipe.zadd(bucket, {member: now})
            pipe.expire(bucket, self.window_seconds + 1)
            await pipe.execute()

        remaining = self.max_requests - (current + 1)
        return RateLimitResult(allowed=True, remaining=remaining, retry_after_seconds=0)


class ResilientRateLimiter(RateLimiterBackend):
    """Primary/secondary limiter wrapper for graceful degradation."""

    def __init__(self, primary: RateLimiterBackend, fallback: RateLimiterBackend) -> None:
        self.primary = primary
        self.fallback = fallback

    async def check(self, key: str) -> RateLimitResult:
        try:
            return await self.primary.check(key)
        except Exception:
            return await self.fallback.check(key)
