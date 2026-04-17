import json
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Any

from redis import asyncio as redis


class CacheBackend(ABC):
    """Abstract cache backend for analysis payloads."""

    @abstractmethod
    async def get(self, key: str) -> Any | None:
        raise NotImplementedError

    @abstractmethod
    async def set(self, key: str, value: Any) -> None:
        raise NotImplementedError


class TTLCache(CacheBackend):
    """Simple in-memory TTL cache for sector-level analysis payloads."""

    def __init__(self, ttl_seconds: int) -> None:
        self.ttl_seconds = ttl_seconds
        self._store: dict[str, tuple[datetime, Any]] = {}

    async def get(self, key: str) -> Any | None:
        item = self._store.get(key)
        if not item:
            return None
        inserted_at, value = item
        expires_at = inserted_at + timedelta(seconds=self.ttl_seconds)
        if datetime.now(timezone.utc) > expires_at:
            self._store.pop(key, None)
            return None
        return value

    async def set(self, key: str, value: Any) -> None:
        self._store[key] = (datetime.now(timezone.utc), value)


class RedisTTLCache(CacheBackend):
    """Redis-backed cache that stores JSON payloads with TTL."""

    def __init__(self, redis_url: str, ttl_seconds: int) -> None:
        self.ttl_seconds = ttl_seconds
        self._client = redis.from_url(redis_url, decode_responses=True)

    async def get(self, key: str) -> Any | None:
        raw = await self._client.get(key)
        if not raw:
            return None
        return json.loads(raw)

    async def set(self, key: str, value: Any) -> None:
        await self._client.set(key, json.dumps(value, ensure_ascii=True), ex=self.ttl_seconds)


class ResilientCache(CacheBackend):
    """Primary/secondary cache wrapper that degrades gracefully on backend failure."""

    def __init__(self, primary: CacheBackend, fallback: CacheBackend) -> None:
        self.primary = primary
        self.fallback = fallback

    async def get(self, key: str) -> Any | None:
        try:
            value = await self.primary.get(key)
            if value is not None:
                return value
        except Exception:
            pass
        return await self.fallback.get(key)

    async def set(self, key: str, value: Any) -> None:
        try:
            await self.primary.set(key, value)
        except Exception:
            await self.fallback.set(key, value)
