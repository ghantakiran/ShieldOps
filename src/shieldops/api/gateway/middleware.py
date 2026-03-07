"""API Gateway middleware — key auth, rate limiting, usage recording."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

import structlog
from starlette.middleware.base import (
    BaseHTTPMiddleware,
    RequestResponseEndpoint,
)
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from shieldops.api.gateway.key_manager import APIKeyManager
from shieldops.api.gateway.models import APIUsageRecord
from shieldops.api.gateway.rate_limiter import TenantRateLimiter

logger = structlog.get_logger()

# Paths that skip API-key authentication entirely
_SKIP_AUTH_PATHS: frozenset[str] = frozenset(
    {
        "/health",
        "/api/v1/health",
        "/ready",
        "/metrics",
        "/api/v1/docs",
        "/api/v1/openapi.json",
        "/api/v1/redoc",
    }
)

_API_KEY_HEADER = "x-api-key"
_BEARER_PREFIX = "so_live_"


def _extract_api_key(request: Request) -> str | None:
    """Extract raw API key from ``X-API-Key`` or ``Authorization`` header."""
    # Prefer dedicated header
    api_key = request.headers.get(_API_KEY_HEADER)
    if api_key:
        return api_key

    # Fall back to Bearer token if it looks like an API key
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer ") and auth[7:].startswith(_BEARER_PREFIX):
        return auth[7:]

    return None


class APIGatewayMiddleware(BaseHTTPMiddleware):
    """Tenant-aware gateway: authenticate key, enforce rate limits,
    record usage.
    """

    def __init__(
        self,
        app: ASGIApp,
        key_manager: APIKeyManager | None = None,
        rate_limiter: TenantRateLimiter | None = None,
        usage_records: list[APIUsageRecord] | None = None,
    ) -> None:
        super().__init__(app)
        self.key_manager = key_manager or APIKeyManager()
        self.rate_limiter = rate_limiter or TenantRateLimiter()
        # In-memory usage log; swap for a queue/DB in production
        self._usage_records: list[APIUsageRecord] = (
            usage_records if usage_records is not None else []
        )

    # ── Dispatch ─────────────────────────────────────────────

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        path = request.url.path

        # Skip auth for health / docs endpoints
        if path in _SKIP_AUTH_PATHS:
            return await call_next(request)

        # --- Authenticate API key ---
        raw_key = _extract_api_key(request)
        if raw_key is None:
            return _error_response(
                status_code=401,
                detail="Missing API key. Provide via X-API-Key header "
                "or Authorization: Bearer so_live_...",
            )

        api_key = self.key_manager.validate_key(raw_key)
        if api_key is None:
            logger.warning(
                "gateway_invalid_key",
                path=path,
            )
            return _error_response(
                status_code=401,
                detail="Invalid, expired, or revoked API key",
            )

        # --- Rate limiting ---
        allowed, remaining = await self.rate_limiter.check_rate_limit(
            org_id=api_key.org_id,
            limit_override=api_key.rate_limit_per_minute,
        )
        if not allowed:
            logger.warning(
                "gateway_rate_limited",
                org_id=api_key.org_id,
                key_id=api_key.key_id,
                path=path,
            )
            resp = _error_response(
                status_code=429,
                detail="Rate limit exceeded",
            )
            resp.headers["Retry-After"] = "60"
            resp.headers["X-RateLimit-Limit"] = str(
                api_key.rate_limit_per_minute,
            )
            resp.headers["X-RateLimit-Remaining"] = "0"
            return resp

        # --- Inject tenant context ---
        request.state.org_id = api_key.org_id
        request.state.scopes = [s.value for s in api_key.scopes]
        request.state.api_key_id = api_key.key_id

        # --- Forward request and measure latency ---
        start = time.perf_counter()
        response = await call_next(request)
        latency_ms = (time.perf_counter() - start) * 1000.0

        # --- Record usage ---
        record = APIUsageRecord(
            org_id=api_key.org_id,
            endpoint=path,
            method=request.method,
            status_code=response.status_code,
            latency_ms=round(latency_ms, 2),
            timestamp=datetime.now(UTC),
            api_key_id=api_key.key_id,
        )
        self._usage_records.append(record)

        # Attach rate-limit headers to successful responses
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Limit"] = str(
            api_key.rate_limit_per_minute,
        )

        return response

    # ── Usage access ─────────────────────────────────────────

    def get_usage_records(
        self,
        org_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return recorded usage, optionally filtered by *org_id*."""
        records = self._usage_records
        if org_id is not None:
            records = [r for r in records if r.org_id == org_id]
        return [r.model_dump() for r in records]


# ── Helpers ──────────────────────────────────────────────────


def _error_response(
    status_code: int,
    detail: str,
) -> JSONResponse:
    """Build a JSON error response."""
    return JSONResponse(
        status_code=status_code,
        content={"detail": detail},
    )
