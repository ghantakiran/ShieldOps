"""Security headers middleware for the ShieldOps API.

Adds OWASP-recommended HTTP response headers to every response,
hardening the application against common web vulnerabilities.
"""

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

# Paths exempt from security headers (operational endpoints)
EXEMPT_PATHS = frozenset({"/metrics", "/health", "/ready"})

# Security headers applied to all non-exempt responses
SECURITY_HEADERS: dict[str, str] = {
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "0",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self'"
    ),
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware that adds security headers to every HTTP response."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)

        if request.url.path not in EXEMPT_PATHS:
            for header, value in SECURITY_HEADERS.items():
                response.headers[header] = value

        return response
