"""HTTP rate limiting middleware using Redis fixed-window counters."""

from __future__ import annotations

import time

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from shieldops.config import settings

logger = structlog.get_logger()

# Paths exempt from rate limiting
_EXEMPT_PATHS: set[str] = {
    "/health",
    "/ready",
    f"{settings.api_prefix}/docs",
    f"{settings.api_prefix}/openapi.json",
    f"{settings.api_prefix}/redoc",
}

# Auth endpoint paths (matched after api_prefix) → stricter IP-based limits
_AUTH_LIMITS: dict[str, int] = {
    f"{settings.api_prefix}/auth/login": settings.rate_limit_auth_login,
    f"{settings.api_prefix}/auth/register": settings.rate_limit_auth_register,
}

# Role → request limit mapping
_ROLE_LIMITS: dict[str, int] = {
    "admin": settings.rate_limit_admin,
    "operator": settings.rate_limit_operator,
    "viewer": settings.rate_limit_viewer,
}


def _get_client_ip(request: Request) -> str:
    """Extract client IP, respecting X-Forwarded-For for proxied deployments."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _extract_user(request: Request) -> tuple[str | None, str | None]:
    """Lightweight JWT extraction — no DB lookup.

    Returns (user_id, role) or (None, None) if unauthenticated.
    """
    from shieldops.api.auth.service import decode_token

    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        return None, None

    payload = decode_token(auth_header[7:])
    if payload is None:
        return None, None

    return payload.get("sub"), payload.get("role")


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Fixed-window rate limiter backed by Redis INCR + EXPIRE."""

    def __init__(self, app: object) -> None:
        super().__init__(app)
        self._client: object | None = None

    async def _ensure_client(self) -> object:
        if self._client is None:
            import redis.asyncio as aioredis

            self._client = aioredis.from_url(settings.redis_url, decode_responses=True)
        return self._client

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not settings.rate_limit_enabled:
            return await call_next(request)

        path = request.url.path

        # Skip exempt paths
        if path in _EXEMPT_PATHS:
            return await call_next(request)

        # Determine identity and limit
        limit, key_identity = self._resolve_limit_and_key(request, path)

        # Build Redis key with window bucket
        window = settings.rate_limit_window_seconds
        bucket = int(time.time()) // window
        redis_key = f"shieldops:http_rate:{bucket}:{key_identity}"

        # Try Redis counter
        try:
            client = await self._ensure_client()
            count = await client.incr(redis_key)  # type: ignore[union-attr]
            if count == 1:
                await client.expire(redis_key, window)  # type: ignore[union-attr]
        except Exception as exc:
            # Fail-open: let request through, log warning
            logger.warning("rate_limit_redis_error", error=str(exc), path=path)
            return await call_next(request)

        reset_at = (bucket + 1) * window
        remaining = max(0, limit - count)

        # Over limit → 429
        if count > limit:
            retry_after = reset_at - int(time.time())
            request_id = getattr(request.state, "request_id", "unknown")
            logger.warning(
                "rate_limit_exceeded",
                identity=key_identity,
                limit=limit,
                path=path,
            )
            resp = JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded",
                    "retry_after": retry_after,
                    "request_id": request_id,
                },
            )
            resp.headers["X-RateLimit-Limit"] = str(limit)
            resp.headers["X-RateLimit-Remaining"] = "0"
            resp.headers["X-RateLimit-Reset"] = str(reset_at)
            resp.headers["Retry-After"] = str(retry_after)
            return resp

        # Normal response with rate limit headers
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_at)
        return response

    def _resolve_limit_and_key(self, request: Request, path: str) -> tuple[int, str]:
        """Return (limit, identity_key) based on path and auth status."""
        ip = _get_client_ip(request)

        # Auth endpoints use stricter IP-based limits
        if path in _AUTH_LIMITS:
            return _AUTH_LIMITS[path], f"ip:{ip}:{path}"

        # Authenticated users → role-based limit keyed by user ID
        user_id, role = _extract_user(request)
        if user_id and role:
            limit = _ROLE_LIMITS.get(role, settings.rate_limit_default)
            return limit, f"user:{user_id}"

        # Unauthenticated → IP-based default limit
        return settings.rate_limit_default, f"ip:{ip}"
