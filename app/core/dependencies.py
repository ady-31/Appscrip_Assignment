from fastapi import Header, HTTPException, Request, status

from app.core.rate_limiter import RateLimiterBackend


def resolve_identity(
    request: Request,
    x_api_key: str | None = Header(default=None),
    x_session_id: str | None = Header(default=None),
) -> str:
    """Resolve caller identity for rate limiting and tracking."""

    if x_api_key:
        return f"api_key:{x_api_key}"
    if x_session_id:
        return f"session:{x_session_id}"
    client = request.client.host if request.client else "unknown"
    return f"ip:{client}"


async def enforce_rate_limit(identity: str, limiter: RateLimiterBackend) -> None:
    result = await limiter.check(identity)
    if not result.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "message": "Rate limit exceeded. Max 5 requests per minute.",
                "retry_after_seconds": result.retry_after_seconds,
            },
            headers={"Retry-After": str(result.retry_after_seconds)},
        )
