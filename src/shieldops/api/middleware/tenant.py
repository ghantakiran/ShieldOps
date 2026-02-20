"""Tenant isolation middleware -- extracts org_id from JWT / header."""

from __future__ import annotations

import structlog
from starlette.middleware.base import (
    BaseHTTPMiddleware,
    RequestResponseEndpoint,
)
from starlette.requests import Request
from starlette.responses import Response

logger = structlog.get_logger()

_PUBLIC_PATHS: set[str] = {
    "/health",
    "/ready",
    "/metrics",
    "/api/v1/docs",
    "/api/v1/openapi.json",
    "/api/v1/auth/login",
    "/api/v1/auth/register",
    "/api/v1/auth/oidc/login",
    "/api/v1/auth/oidc/callback",
}


class TenantMiddleware(BaseHTTPMiddleware):
    """Extract organization_id and place it on ``request.state``."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        # Skip tenant resolution for unauthenticated paths
        if request.url.path in _PUBLIC_PATHS:
            request.state.organization_id = None
            return await call_next(request)

        # Prefer org_id already set by auth (e.g. JWT claim)
        org_id: str | None = getattr(request.state, "organization_id", None)
        if org_id is None:
            # Fallback: API-key-style header
            org_id = request.headers.get("X-Organization-ID")
            request.state.organization_id = org_id

        if org_id:
            logger.debug(
                "tenant_resolved",
                organization_id=org_id,
                path=request.url.path,
            )

        return await call_next(request)
