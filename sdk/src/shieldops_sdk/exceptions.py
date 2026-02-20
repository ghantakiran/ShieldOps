"""ShieldOps SDK exceptions."""

from __future__ import annotations


class ShieldOpsError(Exception):
    """Base exception for all SDK errors."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class AuthenticationError(ShieldOpsError):
    """Invalid or expired API credentials (401/403)."""

    def __init__(self, message: str = "Authentication failed") -> None:
        super().__init__(message, status_code=401)


class NotFoundError(ShieldOpsError):
    """Resource not found (404)."""

    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__(message, status_code=404)


class RateLimitError(ShieldOpsError):
    """Rate limit exceeded (429)."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: int | None = None,
    ) -> None:
        super().__init__(message, status_code=429)
        self.retry_after = retry_after


class ValidationError(ShieldOpsError):
    """Request validation failed (422)."""

    def __init__(self, message: str = "Validation error") -> None:
        super().__init__(message, status_code=422)


class ServerError(ShieldOpsError):
    """Server-side error (5xx)."""

    def __init__(
        self,
        message: str = "Internal server error",
        status_code: int = 500,
    ) -> None:
        super().__init__(message, status_code=status_code)
