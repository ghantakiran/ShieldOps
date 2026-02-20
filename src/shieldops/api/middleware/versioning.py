"""API versioning middleware -- adds version headers to all responses."""

from __future__ import annotations

from starlette.middleware.base import (
    BaseHTTPMiddleware,
    RequestResponseEndpoint,
)
from starlette.requests import Request
from starlette.responses import Response

API_VERSION = "1.0.0"


class APIVersionMiddleware(BaseHTTPMiddleware):
    """Adds X-API-Version and X-Powered-By headers to responses."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers["X-API-Version"] = API_VERSION
        response.headers["X-Powered-By"] = "ShieldOps"
        return response
