"""Sliding-window rate limiter with per-tenant and per-endpoint support."""

from __future__ import annotations

import time

import structlog
from redis.asyncio import Redis
from starlette.middleware.base import (
    BaseHTTPMiddleware,
    RequestResponseEndpoint,
)
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

logger = structlog.get_logger()

# Tier definitions: (requests_per_minute, window_seconds)
TIER_LIMITS: dict[str, tuple[int, int]] = {
    "read": (300, 60),
    "write": (60, 60),
    "admin": (30, 60),
    "auth": (10, 60),
}

# HTTP method to tier mapping
METHOD_TIERS: dict[str, str] = {
    "GET": "read",
    "HEAD": "read",
    "OPTIONS": "read",
    "POST": "write",
    "PUT": "write",
    "PATCH": "write",
    "DELETE": "admin",
}

_EXEMPT_PATHS: set[str] = {"/health", "/ready", "/metrics"}


class SlidingWindowRateLimiter(BaseHTTPMiddleware):
    """Redis sliding window rate limiter with per-tenant limits."""

    def __init__(self, app: ASGIApp, redis: Redis | None = None) -> None:
        super().__init__(app)
        self._redis = redis

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if self._redis is None or request.url.path in _EXEMPT_PATHS:
            return await call_next(request)

        # Determine identity key (tenant > user > IP)
        org_id = getattr(request.state, "organization_id", None)
        user_id = getattr(request.state, "user_id", None)
        client_ip = request.client.host if request.client else "unknown"
        identity = org_id or user_id or client_ip

        # Determine tier
        tier = METHOD_TIERS.get(request.method, "read")
        if "/auth/" in request.url.path:
            tier = "auth"

        # Get limit (check tenant override from request.state)
        tenant_limit = getattr(request.state, "rate_limit_override", None)
        default_limit, window = TIER_LIMITS[tier]
        limit = tenant_limit if tenant_limit else default_limit

        # Sliding window check
        key = f"ratelimit:{tier}:{identity}"
        now = time.time()
        allowed, remaining, reset_at = await self._check_rate(key, limit, window, now)

        if not allowed:
            logger.warning(
                "rate_limit_exceeded",
                identity=identity,
                tier=tier,
                limit=limit,
            )
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded",
                    "retry_after": int(reset_at - now),
                },
                headers={
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(reset_at)),
                    "Retry-After": str(int(reset_at - now)),
                },
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int(reset_at))
        return response

    async def _check_rate(
        self, key: str, limit: int, window: int, now: float
    ) -> tuple[bool, int, float]:
        """Sliding window counter using Redis sorted sets."""
        window_start = now - window
        reset_at = now + window

        assert self._redis is not None
        pipe = self._redis.pipeline()
        pipe.zremrangebyscore(key, "-inf", window_start)
        pipe.zadd(key, {f"{now}": now})
        pipe.zcard(key)
        pipe.expire(key, window + 1)
        results = await pipe.execute()

        current_count = results[2]
        remaining = max(0, limit - current_count)
        allowed = current_count <= limit

        return allowed, remaining, reset_at
