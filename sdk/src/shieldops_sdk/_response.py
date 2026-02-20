"""Shared HTTP response handling for sync and async clients."""

from __future__ import annotations

import httpx

from shieldops_sdk.exceptions import (
    AuthenticationError,
    NotFoundError,
    RateLimitError,
    ServerError,
    ShieldOpsError,
    ValidationError,
)


def handle_response(response: httpx.Response) -> None:
    """Raise the appropriate SDK exception for non-2xx responses.

    This is intentionally a plain function so both sync and async
    resource classes can reuse it without duplication.
    """
    if response.is_success:
        return

    status = response.status_code

    # Try to extract a detail message from the JSON body
    detail = ""
    try:
        body = response.json()
        detail = body.get("detail", "") if isinstance(body, dict) else ""
    except Exception:  # noqa: BLE001
        detail = response.text[:200] if response.text else ""

    if status in (401, 403):
        raise AuthenticationError(detail or "Authentication failed")

    if status == 404:
        raise NotFoundError(detail or "Resource not found")

    if status == 422:
        raise ValidationError(detail or "Validation error")

    if status == 429:
        retry_after: int | None = None
        raw = response.headers.get("Retry-After")
        if raw is not None:
            try:
                retry_after = int(raw)
            except ValueError:
                pass
        # Also try the JSON body which ShieldOps returns
        if retry_after is None:
            try:
                body = response.json()
                retry_after = body.get("retry_after")
            except Exception:  # noqa: BLE001
                pass
        raise RateLimitError(
            detail or "Rate limit exceeded",
            retry_after=retry_after,
        )

    if status >= 500:
        raise ServerError(
            detail or "Internal server error",
            status_code=status,
        )

    # Catch-all for other 4xx
    raise ShieldOpsError(detail or f"Request failed with status {status}", status_code=status)
