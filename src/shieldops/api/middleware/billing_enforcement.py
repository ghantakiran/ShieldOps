"""Billing enforcement middleware -- blocks requests that exceed plan limits.

Intercepts every request and checks the org's plan against current
usage.  Agent-creation endpoints (``POST /api/v1/agents``) are checked
against the agent limit; all other tracked endpoints are checked
against the monthly API call quota.

Exempt paths (health, metrics, billing endpoints) skip enforcement
entirely so infrastructure and upgrade flows are never blocked.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from starlette.middleware.base import (
    BaseHTTPMiddleware,
    RequestResponseEndpoint,
)
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

if TYPE_CHECKING:
    from shieldops.billing.enforcement import PlanEnforcementService

logger = structlog.get_logger()

# Paths that bypass billing enforcement entirely.
_EXEMPT_PREFIXES: tuple[str, ...] = (
    "/health",
    "/ready",
    "/metrics",
    "/docs",
    "/openapi.json",
    "/api/v1/docs",
    "/api/v1/openapi.json",
    "/api/v1/billing",
    "/api/v1/webhooks",
    "/api/v1/auth",
)

# The exact route that creates a new agent.
_AGENT_CREATE_PATH = "/api/v1/agents"
_AGENT_CREATE_METHOD = "POST"


def _is_exempt(path: str) -> bool:
    """Return ``True`` if *path* should skip billing enforcement."""
    return any(path == prefix or path.startswith(prefix + "/") for prefix in _EXEMPT_PREFIXES)


def _build_402_response(
    message: str,
    plan: str,
    usage: int,
    limit: int,
    upgrade_url: str = "/api/v1/billing/plans",
) -> JSONResponse:
    """Build a 402 Payment Required response with plan headers."""
    return JSONResponse(
        status_code=402,
        content={
            "detail": message,
            "plan": plan,
            "usage": usage,
            "limit": limit,
            "upgrade_url": upgrade_url,
        },
        headers={
            "X-Plan-Name": plan,
            "X-Plan-Usage": str(usage),
            "X-Plan-Limit": str(limit),
        },
    )


class BillingEnforcementMiddleware(BaseHTTPMiddleware):
    """Reject requests that exceed the org's plan limits.

    The middleware is wired into the Starlette stack via ``app.add_middleware``
    and receives its :class:`PlanEnforcementService` at application startup.
    If no enforcement service has been set (e.g. in dev/test), all requests
    are passed through unconditionally.
    """

    _enforcement: PlanEnforcementService | None = None

    @classmethod
    def set_enforcement_service(
        cls,
        service: PlanEnforcementService,
    ) -> None:
        """Inject the enforcement service at startup.

        Called from ``app.py`` lifespan once the DB session factory
        and enforcement service are ready.
        """
        cls._enforcement = service

    @classmethod
    def get_enforcement_service(cls) -> PlanEnforcementService | None:
        """Return the current enforcement service (or ``None``)."""
        return cls._enforcement

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        path = request.url.path
        method = request.method

        # 1. Skip exempt paths (health, billing, docs, etc.)
        if _is_exempt(path):
            return await call_next(request)

        # 2. Skip if enforcement is not wired up
        enforcement = self.__class__._enforcement
        if enforcement is None:
            return await call_next(request)

        # 3. Resolve org_id from tenant middleware
        org_id: str | None = getattr(request.state, "organization_id", None)
        if org_id is None:
            # No org context -- cannot enforce, let the request through
            return await call_next(request)

        plan = await enforcement.get_org_plan(org_id)

        # 4. Agent creation check
        if method == _AGENT_CREATE_METHOD and path == _AGENT_CREATE_PATH:
            allowed, current, limit = await enforcement.check_agent_limit(org_id, plan=plan)
            if not allowed:
                logger.warning(
                    "billing_agent_limit_exceeded",
                    org_id=org_id,
                    plan=plan,
                    current=current,
                    limit=limit,
                )
                return _build_402_response(
                    message=(
                        f"Agent limit reached ({current}/{limit}). "
                        f"Upgrade your plan to add more agents."
                    ),
                    plan=plan,
                    usage=current,
                    limit=limit,
                )

        # 5. API quota check (applies to every non-exempt request)
        allowed, used, limit = await enforcement.check_api_quota(org_id, plan=plan)
        if not allowed:
            logger.warning(
                "billing_api_quota_exceeded",
                org_id=org_id,
                plan=plan,
                used=used,
                limit=limit,
            )
            return _build_402_response(
                message=(
                    f"API call quota exceeded ({used}/{limit}). "
                    f"Upgrade your plan for higher limits."
                ),
                plan=plan,
                usage=used,
                limit=limit,
            )

        # 6. Proceed and attach plan info as response headers
        response = await call_next(request)
        response.headers["X-Plan-Name"] = plan
        response.headers["X-Plan-Usage"] = str(used)
        response.headers["X-Plan-Limit"] = str(limit)
        return response
